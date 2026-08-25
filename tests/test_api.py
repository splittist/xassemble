from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from xassemble.app import DOCX_MEDIA_TYPE

from .auth_helpers import authenticated_app, log_in
from .helpers import questionnaire_docx, template_docx


def test_version_publish_evaluate_generate_and_rollback_workflow(tmp_path) -> None:
    app, _ = authenticated_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        log_in(client)
        created = client.post(
            "/document-sets",
            json={"slug": "nda-pack", "name": "NDA Pack", "description": "Test"},
        )
        assert created.status_code == 201

        upload = client.post(
            "/document-sets/nda-pack/questionnaire-versions",
            files={"file": ("questionnaire.docx", questionnaire_docx(), DOCX_MEDIA_TYPE)},
            data={"note": "Initial"},
        )
        assert upload.status_code == 201, upload.text
        questionnaire_v1 = upload.json()["id"]
        assert upload.json()["is_current"] is False
        assert client.post(
            f"/document-sets/nda-pack/questionnaire-versions/{questionnaire_v1}/publish"
        ).status_code == 200

        template_upload = client.post(
            "/document-sets/nda-pack/template-versions",
            files={"file": ("letter.docx", template_docx(), DOCX_MEDIA_TYPE)},
            data={"label": "letter", "note": "Initial"},
        )
        assert template_upload.status_code == 201, template_upload.text
        template_v1 = template_upload.json()["id"]
        assert client.post(
            f"/document-sets/nda-pack/template-versions/{template_v1}/publish"
        ).status_code == 200

        evaluation = client.post(
            "/document-sets/nda-pack/questionnaire/evaluate",
            json={"answers": {"urgent": False}},
        )
        assert evaluation.json()["hidden"] == ["reason"]

        generation = client.post(
            "/document-sets/nda-pack/generate",
            json={
                "answers": {"client_name": "Example Ltd", "urgent": True, "reason": "Today"},
                "project_code": "ABC-123",
            },
        )
        assert generation.status_code == 200, generation.text
        assert generation.headers["content-type"] == DOCX_MEDIA_TYPE
        rendered = Document(BytesIO(generation.content))
        assert rendered.paragraphs[0].text == "Dear Example Ltd"

        second_upload = client.post(
            "/document-sets/nda-pack/questionnaire-versions",
            files={"file": ("questionnaire.docx", questionnaire_docx(), DOCX_MEDIA_TYPE)},
            data={"note": "Second"},
        )
        questionnaire_v2 = second_upload.json()["id"]
        assert client.post(
            f"/document-sets/nda-pack/questionnaire-versions/{questionnaire_v2}/publish"
        ).status_code == 200
        assert client.post(
            f"/document-sets/nda-pack/questionnaire-versions/{questionnaire_v1}/publish"
        ).status_code == 200
        versions = client.get("/document-sets/nda-pack/versions").json()
        assert versions["questionnaires"][0]["uploaded_by"] == "editor"
        current = [row for row in versions["questionnaires"] if row["is_current"]]
        assert [row["id"] for row in current] == [questionnaire_v1]


def test_questionnaire_update_is_blocked_if_it_breaks_current_template(tmp_path) -> None:
    app, _ = authenticated_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        log_in(client)
        client.post("/document-sets", json={"slug": "letters", "name": "Letters"})
        upload = client.post(
            "/document-sets/letters/questionnaire-versions",
            files={"file": ("q.docx", questionnaire_docx(), DOCX_MEDIA_TYPE)},
            data={},
        )
        client.post(
            f"/document-sets/letters/questionnaire-versions/{upload.json()['id']}/publish"
        )
        template = client.post(
            "/document-sets/letters/template-versions",
            files={"file": ("letter.docx", template_docx(), DOCX_MEDIA_TYPE)},
            data={"label": "letter"},
        )
        client.post(f"/document-sets/letters/template-versions/{template.json()['id']}/publish")

        incompatible = questionnaire_docx(
            questions=[["other_name", "Other name", "text", "", "", "", ""]]
        )
        rejected = client.post(
            "/document-sets/letters/questionnaire-versions",
            files={"file": ("q.docx", incompatible, DOCX_MEDIA_TYPE)},
            data={},
        )
        assert rejected.status_code == 422
        assert "client_name" in rejected.json()["detail"]
