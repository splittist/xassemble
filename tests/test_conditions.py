import pytest

from xassemble.conditions import ConditionError, evaluate_condition, referenced_variables


def test_condition_language_supports_expected_operations() -> None:
    expression = 'urgent == true and category in ("employment", "commercial")'
    assert evaluate_condition(expression, {"urgent": True, "category": "employment"}) is True
    assert referenced_variables(expression) == {"urgent", "category"}


@pytest.mark.parametrize(
    "expression",
    ["run()", "person.name == 'x'", "count + 1 == 2", "items[0] == 'x'"],
)
def test_condition_language_rejects_executable_or_extended_python(expression: str) -> None:
    with pytest.raises(ConditionError, match="Unsupported"):
        evaluate_condition(expression, {})


def test_unknown_variable_has_clear_error() -> None:
    with pytest.raises(ConditionError, match="Unknown variable: missing"):
        evaluate_condition("missing == true", {})

