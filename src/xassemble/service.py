from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePath
from string import Formatter
from zipfile import ZIP_DEFLATED, ZipFile

from docxtpl import DocxTemplate

from .conditions import evaluate_condition
from .database import Database, load_schema
from .models import QuestionnaireSchema
from .validation import validate_template


class GenerationError(ValueError):
    pass


def questionnaire_visibility(
    schema: QuestionnaireSchema, answers: dict[str, object]
) -> tuple[list[str], list[str], dict[str, object]]:
    context: dict[str, object] = {"date": _today()}
    visible: list[str] = []
    hidden: list[str] = []
    for question in schema.questions:
        should_skip = evaluate_condition(question.skip_if, context) if question.skip_if else False
        if should_skip:
            hidden.append(question.variable_name)
            context[question.variable_name] = None
        else:
            visible.append(question.variable_name)
            context[question.variable_name] = answers.get(question.variable_name)
    return visible, hidden, context


def validate_questionnaire_against_templates(
    schema: QuestionnaireSchema, templates: list[dict[str, object]]
) -> None:
    problems = []
    for template in templates:
        try:
            validate_template(template["docx_blob"], schema)  # type: ignore[arg-type]
        except ValueError as exc:
            problems.append(f"{template['label']}: {exc}")
    if problems:
        raise ValueError("; ".join(problems))


def generate_documents(
    database: Database,
    document_set_id: int,
    questionnaire_row: dict[str, object],
    answers: dict[str, object],
    project_code: str,
    generated_by: str,
) -> tuple[bytes, str, str]:
    schema = load_schema(questionnaire_row)
    _, _, context = questionnaire_visibility(schema, answers)
    context["project_code"] = project_code
    context["date"] = _today()
    rendered: list[tuple[str, bytes, int]] = []
    for output in schema.outputs:
        if output.include_if and not evaluate_condition(output.include_if, context):
            continue
        template_row = database.get_template(document_set_id, label=output.label)
        if template_row is None:
            raise GenerationError(f"No published template exists for output '{output.label}'")
        template = DocxTemplate(BytesIO(template_row["docx_blob"]))
        template.render(context, autoescape=True)
        destination = BytesIO()
        template.save(destination)
        filename = _output_filename(output.filename_pattern, project_code, output.label)
        rendered.append((filename, destination.getvalue(), template_row["id"]))

    if not rendered:
        raise GenerationError("The answers do not select any output documents")
    database.log_generation(
        document_set_id,
        questionnaire_row["id"],
        [item[2] for item in rendered],
        project_code,
        generated_by,
    )
    if len(rendered) == 1:
        return rendered[0][1], rendered[0][0], "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        for filename, content, _ in rendered:
            zip_file.writestr(filename, content)
    return archive.getvalue(), f"{_safe_component(project_code)}_{_today()}.zip", "application/zip"


def _output_filename(pattern: str, project_code: str, label: str) -> str:
    fields = {field for _, field, _, _ in Formatter().parse(pattern) if field}
    unsupported = fields - {"project_code", "label", "date"}
    if unsupported:
        raise GenerationError(f"Unsupported filename field(s): {', '.join(sorted(unsupported))}")
    name = pattern.format(project_code=project_code, label=label, date=_today())
    name = _safe_component(PurePath(name).name)
    if not name.lower().endswith(".docx"):
        name += ".docx"
    return name


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned[:160] or "document"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()
