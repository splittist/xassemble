import pytest

from xassemble.parser import parse_questionnaire
from xassemble.validation import TemplateError, validate_template

from .helpers import questionnaire_docx, template_docx


def test_template_variables_must_exist_in_questionnaire() -> None:
    schema = parse_questionnaire(questionnaire_docx())
    assert validate_template(template_docx(), schema) == {"client_name"}
    with pytest.raises(TemplateError, match="unknown_name"):
        validate_template(template_docx("Hello {{ unknown_name }}"), schema)


def test_reserved_generation_variables_are_allowed() -> None:
    schema = parse_questionnaire(questionnaire_docx())
    variables = validate_template(template_docx("{{ project_code }} on {{ date }}"), schema)
    assert variables == {"project_code", "date"}

