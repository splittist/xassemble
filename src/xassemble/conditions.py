from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any


class ConditionError(ValueError):
    """Raised when a condition uses unsupported syntax or cannot be evaluated."""


_ALLOWED_COMPARE_OPERATORS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)


def referenced_variables(expression: str) -> set[str]:
    if not expression.strip():
        return set()
    tree = _parse(expression)
    _validate(tree)
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in {"true", "false", "null"}
    }


def evaluate_condition(expression: str, answers: Mapping[str, Any]) -> bool:
    if not expression.strip():
        return True
    tree = _parse(expression)
    _validate(tree)
    try:
        return bool(_evaluate(tree.body, answers))
    except KeyError as exc:
        raise ConditionError(f"Unknown variable: {exc.args[0]}") from exc


def _parse(expression: str) -> ast.Expression:
    try:
        return ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ConditionError(f"Invalid condition syntax: {exc.msg}") from exc


def _validate(tree: ast.AST) -> None:
    allowed = (
        ast.Expression,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Name,
        ast.Constant,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Eq,
        ast.NotEq,
        ast.In,
        ast.NotIn,
        ast.Load,
        ast.List,
        ast.Tuple,
        ast.Set,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ConditionError(f"Unsupported condition syntax: {type(node).__name__}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (str, bool, type(None))):
            raise ConditionError("Only string, boolean, and null literals are allowed")
        if isinstance(node, ast.Compare) and (
            len(node.ops) != 1 or not isinstance(node.ops[0], _ALLOWED_COMPARE_OPERATORS)
        ):
            raise ConditionError("Only ==, !=, in, and not in comparisons are allowed")


def _evaluate(node: ast.AST, answers: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "true":
            return True
        if node.id == "false":
            return False
        if node.id == "null":
            return None
        if node.id not in answers:
            raise KeyError(node.id)
        return answers[node.id]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_evaluate(item, answers) for item in node.elts]
    if isinstance(node, ast.BoolOp):
        values = (_evaluate(value, answers) for value in node.values)
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _evaluate(node.operand, answers)
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, answers)
        right = _evaluate(node.comparators[0], answers)
        operator = node.ops[0]
        if isinstance(operator, ast.Eq):
            return left == right
        if isinstance(operator, ast.NotEq):
            return left != right
        if isinstance(operator, ast.In):
            return left in right
        if isinstance(operator, ast.NotIn):
            return left not in right
    raise ConditionError(f"Cannot evaluate syntax: {type(node).__name__}")
