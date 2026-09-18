import json
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient

from xassemble.answers import MAX_ANSWER_BYTES, parse_answer_file, validate_answers
from xassemble.app import DOCX_MEDIA_TYPE
from xassemble.models import Question, QuestionnaireSchema

from .auth_helpers import authenticated_app, log_in
from .helpers import questionnaire_docx, template_docx


@pytest.fixture
def exchange(tmp_path):
    app, _ = authenticated_app(tmp_path / "exchange.sqlite3")
    with TestClient(app) as client:
        log_in(client)
        client.post("/document-sets", json={"slug": "letters", "name": "Letters"})
        root = "/document-sets/letters"
        uploaded = client.post(
            root + "/questionnaire-versions",
            files={"file": ("q.docx", questionnaire_docx(), DOCX_MEDIA_TYPE)},
        ).json()
        client.post(root + f"/questionnaire-versions/{uploaded['id']}/publish")
        template = client.post(
            root + "/template-versions",
            data={"label": "letter"},
            files={
                "file": (
                    "t.docx",
                    template_docx("{{ client_name }} / {{ reason }}"),
                    DOCX_MEDIA_TYPE,
                )
            },
        ).json()
        client.post(root + f"/template-versions/{template['id']}/publish")
        schema = client.get(root + "/questionnaire").json()
        identity = {
            "questionnaire_version_id": schema["version_id"],
            "questionnaire_schema_sha256": schema["schema_sha256"],
        }
        response = client.get(
            root + "/questionnaire/answer-briefing",
            params={"version_id": schema["version_id"], "schema_sha256": schema["schema_sha256"]},
        )
        assert response.status_code == 200
        value = json.loads(response.text.split("```json\n")[1].split("```")[0])
        yield client, root, value, identity


def upload(client, root, value):
    return client.post(
        root + "/questionnaire/answer-import",
        files={"file": ("answers.json", json.dumps(value).encode(), "application/json")},
    )


def test_round_trip_partial_and_hidden_answers(exchange):
    client, root, value, identity = exchange
    assert upload(client, root, value).json()["answers"] == {}
    value["answers"] = {
        "client_name": "Müller & <Co>\nSecond line",
        "urgent": False,
        "reason": "DO NOT RENDER",
    }
    imported = upload(client, root, value)
    assert imported.status_code == 200
    answers = imported.json()["answers"]
    evaluated = client.post(root + "/questionnaire/evaluate", json={**identity, "answers": answers})
    assert evaluated.json()["hidden"] == ["reason"]
    generated = client.post(
        root + "/generate", json={**identity, "answers": answers, "project_code": "TEST"}
    )
    assert generated.status_code == 200, generated.text
    text = Document(BytesIO(generated.content)).paragraphs[0].text
    assert "Müller & <Co>\nSecond line" in text
    assert "DO NOT RENDER" not in text
    partial = {**identity, "answers": {"urgent": False}, "project_code": "PARTIAL"}
    assert client.post(root + "/generate", json=partial).status_code == 422
    assert (
        client.post(
            root + "/generate", json={**partial, "acknowledge_incomplete": True}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "answers",
    [
        {"urgent": "false"},
        {"urgent": 0},
        {"unknown": "x"},
        {"client_name": []},
        {"client_name": {}},
        {"reason": "\u0000"},
        {"reason": "x" * 20_001},
    ],
)
def test_invalid_values_rejected_on_all_entry_points(exchange, answers):
    client, root, value, identity = exchange
    assert upload(client, root, {**value, "answers": answers}).status_code == 422
    assert (
        client.post(
            root + "/questionnaire/evaluate", json={**identity, "answers": answers}
        ).status_code
        == 422
    )
    assert (
        client.post(
            root + "/generate",
            json={
                **identity,
                "answers": answers,
                "project_code": "TEST",
                "acknowledge_incomplete": True,
            },
        ).status_code
        == 422
    )


def test_identity_and_publication_changes(exchange):
    client, root, value, identity = exchange
    assert upload(client, root, {**value, "document_set_slug": "other"}).status_code == 409
    assert (
        upload(client, root, {**value, "questionnaire_schema_sha256": "wrong"}).status_code == 409
    )
    version = client.post(
        root + "/questionnaire-versions",
        files={"file": ("q.docx", questionnaire_docx(), DOCX_MEDIA_TYPE)},
    ).json()["id"]
    client.post(root + f"/questionnaire-versions/{version}/publish")
    assert upload(client, root, value).status_code == 409
    assert (
        client.post(root + "/questionnaire/evaluate", json={**identity, "answers": {}}).status_code
        == 409
    )
    assert (
        client.post(
            root + "/generate", json={**identity, "answers": {}, "project_code": "X"}
        ).status_code
        == 409
    )
    assert (
        client.get(
            root + "/questionnaire/answer-briefing",
            params={
                "version_id": identity["questionnaire_version_id"],
                "schema_sha256": identity["questionnaire_schema_sha256"],
            },
        ).status_code
        == 409
    )
    client.post(root + f"/questionnaire-versions/{identity['questionnaire_version_id']}/publish")
    assert upload(client, root, value).status_code == 200


def test_file_errors_and_authentication(exchange):
    client, root, value, _identity = exchange
    for content, expected in [
        (b"bad", 422),
        (b"[]", 422),
        (b"", 422),
        (b"x" * (MAX_ANSWER_BYTES + 1), 413),
    ]:
        response = client.post(
            root + "/questionnaire/answer-import",
            files={"file": ("answers.json", content, "application/json")},
        )
        assert response.status_code == expected
    assert upload(client, root, {**value, "format": "v2"}).status_code == 422
    assert upload(client, root, {**value, "extra": True}).status_code == 422
    assert (
        client.post(root + "/generate", json={"answers": {}, "project_code": "X"}).status_code
        == 422
    )
    client.post("/auth/logout")
    assert upload(client, root, value).status_code == 401
    assert client.get(root + "/questionnaire/answer-briefing").status_code == 401


@pytest.mark.parametrize(
    "content",
    [
        b'{"a": 1, "a": 2}',
        b'{"a": NaN}',
        b'{"a": Infinity}',
        b"\xff",
        b"```json\n{}\n```",
        b"[" * 2000,
    ],
)
def test_strict_json(content):
    with pytest.raises(ValueError):
        parse_answer_file(content)


def test_choice_and_unanswered_values():
    schema = QuestionnaireSchema(
        questions=(Question("choice", "Choice", "choice", ("A", "B")),), outputs=()
    )
    assert validate_answers(schema, {"choice": "A"}) == {"choice": "A"}
    for value in [None, "", "   "]:
        assert validate_answers(schema, {"choice": value}) == {}
    for value in ["a", False, 1, ["A"]]:
        with pytest.raises(ValueError, match="choice"):
            validate_answers(schema, {"choice": value})


def test_oversize_stream_is_rejected_before_parsing(exchange):
    client, root, _value, _identity = exchange
    for suffix in ["/questionnaire/answer-import", "/questionnaire/evaluate", "/generate"]:
        response = client.post(root + suffix, content=iter([b"x" * 100_000] * 12),
                               headers={"Content-Type": "application/json"})
        assert response.status_code == 413
