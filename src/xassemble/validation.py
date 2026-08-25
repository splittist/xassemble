from __future__ import annotations

from io import BytesIO

from docxtpl import DocxTemplate

from .models import QuestionnaireSchema

RESERVED_TEMPLATE_VARIABLES = {"date", "project_code"}


class TemplateError(ValueError):
    """Raised when a template is invalid or incompatible with a questionnaire."""


def template_variables(content: bytes) -> set[str]:
    try:
        template = DocxTemplate(BytesIO(content))
        return set(template.get_undeclared_template_variables())
    except Exception as exc:
        raise TemplateError("The upload is not a readable docxtpl .docx template") from exc


def validate_template(content: bytes, questionnaire: QuestionnaireSchema) -> set[str]:
    variables = template_variables(content)
    unknown = variables - questionnaire.variables - RESERVED_TEMPLATE_VARIABLES
    if unknown:
        raise TemplateError(f"Unknown template variable(s): {', '.join(sorted(unknown))}")
    return variables

