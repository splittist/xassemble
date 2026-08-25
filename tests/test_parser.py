import pytest

from xassemble.parser import QuestionnaireError, parse_questionnaire

from .helpers import questionnaire_docx


def test_parses_questionnaire_tables() -> None:
    schema = parse_questionnaire(questionnaire_docx())
    assert schema.variables == {"client_name", "urgent", "reason"}
    assert schema.questions[2].skip_if == "urgent == false"
    assert schema.outputs[0].label == "letter"


def test_choice_must_have_options() -> None:
    content = questionnaire_docx(
        questions=[["kind", "Which kind?", "choice", "", "", "", ""]]
    )
    with pytest.raises(QuestionnaireError, match="choice requires options"):
        parse_questionnaire(content)


def test_skip_condition_can_only_reference_earlier_questions() -> None:
    content = questionnaire_docx(
        questions=[
            ["first", "First", "text", "", "", "later == 'x'", ""],
            ["later", "Later", "text", "", "", "", ""],
        ]
    )
    with pytest.raises(QuestionnaireError, match="Unknown variable.*later"):
        parse_questionnaire(content)


def test_duplicate_variables_are_rejected() -> None:
    content = questionnaire_docx(
        questions=[
            ["name", "Name", "text", "", "", "", ""],
            ["name", "Name again", "text", "", "", "", ""],
        ]
    )
    with pytest.raises(QuestionnaireError, match="Duplicate question variable"):
        parse_questionnaire(content)

