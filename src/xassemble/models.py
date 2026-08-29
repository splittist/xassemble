from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

QuestionType = Literal["yesno", "choice", "text", "textarea"]


@dataclass(frozen=True)
class Question:
    variable_name: str
    question_text: str
    type: QuestionType
    options: tuple[str, ...] = field(default_factory=tuple)
    examples: tuple[str, ...] = field(default_factory=tuple)
    commentary: str = ""
    skip_if: str = ""
    section: str = ""

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["options"] = list(self.options)
        value["examples"] = list(self.examples)
        return value


@dataclass(frozen=True)
class OutputDocument:
    label: str
    include_if: str = ""
    filename_pattern: str = "{project_code}_{label}_{date}"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class QuestionnaireSchema:
    questions: tuple[Question, ...]
    outputs: tuple[OutputDocument, ...]

    @property
    def variables(self) -> set[str]:
        return {question.variable_name for question in self.questions}

    def to_dict(self) -> dict[str, object]:
        return {
            "questions": [question.to_dict() for question in self.questions],
            "outputs": [output.to_dict() for output in self.outputs],
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> QuestionnaireSchema:
        questions = tuple(
            Question(**_question_kwargs(item)) for item in value.get("questions", [])
        )
        outputs = tuple(OutputDocument(**item) for item in value.get("outputs", []))
        return cls(questions=questions, outputs=outputs)


def _question_kwargs(item: dict[str, object]) -> dict[str, object]:
    kwargs = dict(item)
    kwargs["options"] = tuple(kwargs.get("options", []))
    # older cached schemas stored a single "example" string instead of "examples"
    legacy_example = kwargs.pop("example", None)
    examples = kwargs.get("examples")
    if examples is None:
        examples = (legacy_example,) if legacy_example else ()
    kwargs["examples"] = tuple(examples)
    return kwargs

