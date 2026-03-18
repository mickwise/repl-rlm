"""
Purpose
-------
Exercise runtime interpretation for expression AST nodes. This module exists to
keep expression evaluation behavior stable across reference resolution,
operator handling, and unsupported-node failures.

Key behaviors
-------------
- Verifies recursive evaluation of structured expressions.
- Verifies native execution errors for missing references and unsupported
  operators.

Conventions
-----------
- Tests construct runtime state explicitly rather than relying on the top-level
  runtime entrypoint.
- Assertions focus on stable public values and native error codes.

Downstream usage
----------------
CI runs this module to guard the expression-evaluation layer used by step
execution and recursive child programs.
"""

import asyncio
from typing import cast

import pytest

from repl_rlm.repl.errors import RlmErrorCode, RlmExecutionError
from repl_rlm.repl.expressions.expression_interpreter import interpret_expression
from repl_rlm.repl.expressions.expressions import (
    AlgebraicExpr,
    AlgebraicOperator,
    ComparisonExpr,
    ComparisonOperator,
    FieldAccessExpr,
    ListExpr,
    ListIndexExpr,
    Literal,
    LogicalExpr,
    LogicalOperator,
    ObjectExpr,
    Ref,
    TaskRef,
    UnaryExpr,
    UnaryOperator,
)
from repl_rlm.repl.runtime.runtime_state import RuntimeState


def test_interpret_expression_evaluates_nested_structures() -> None:
    """
    Evaluate nested object, list, comparison, logical, and unary expressions.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when nested expressions evaluate to the
        expected runtime values.

    Raises
    ------
    AssertionError
        If recursive expression evaluation produces an unexpected result.

    Notes
    -----
    - This covers the main interpreter dispatch path without depending on step
      execution.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    runtime_state.bindings["count"] = 2

    expr = ObjectExpr(
        fields={
            "items": ListExpr(values=(Ref(name="count"), Literal(value="x"))),
            "comparison": ComparisonExpr(
                lhs_expr=Ref(name="count"),
                rhs_expr=Literal(value=1),
                operator=ComparisonOperator.GREATER_THAN,
            ),
            "gate": LogicalExpr(
                lhs_expr=Literal(value=0),
                rhs_expr=Literal(value="value"),
                operator=LogicalOperator.OR,
            ),
            "negated": UnaryExpr(
                expr=Literal(value=""),
                operator=UnaryOperator.NOT,
            ),
        }
    )

    result = interpret_expression(expr, runtime_state)

    assert result == {
        "items": [2, "x"],
        "comparison": True,
        "gate": True,
        "negated": True,
    }


def test_interpret_expression_rejects_missing_references() -> None:
    """
    Raise an unbound-reference error when a binding is missing at runtime.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when missing bindings raise the expected
        native execution error.

    Raises
    ------
    AssertionError
        If missing references do not map to the expected error code.

    Notes
    -----
    - Reference resolution is a core runtime behavior used by most programs.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(Ref(name="missing"), runtime_state)

    assert excinfo.value.code is RlmErrorCode.UNBOUND_REFERENCE


def test_interpret_expression_evaluates_algebraic_and_field_access_nodes() -> None:
    """
    Evaluate algebraic and field-access expressions against runtime bindings.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when algebraic and field-access expressions
        evaluate to the expected runtime value.

    Raises
    ------
    AssertionError
        If the interpreted value does not match the expected result.

    Notes
    -----
    - This covers the new expression-node dispatch paths without involving
      step execution.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    runtime_state.bindings["result"] = {"total": 9, "count": 3}

    expr = AlgebraicExpr(
        lhs_expr=FieldAccessExpr(
            base_expr=Ref(name="result"),
            field_name="total",
        ),
        rhs_expr=FieldAccessExpr(
            base_expr=Ref(name="result"),
            field_name="count",
        ),
        operator=AlgebraicOperator.DIVIDE,
    )

    result = interpret_expression(expr, runtime_state)

    assert result == 3


def test_interpret_expression_evaluates_nested_list_index_nodes() -> None:
    """
    Evaluate nested list-index expressions against runtime bindings.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when nested list-index expressions resolve
        the expected runtime value.

    Raises
    ------
    AssertionError
        If nested list indexing does not produce the expected result.

    Notes
    -----
    - This covers the list-index interpreter branch using the real rolling-like
      `instances[0].total` access pattern.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    runtime_state.bindings["roll_result"] = {
        "instances": [
            {"total": 7},
            {"total": 11},
        ]
    }

    expr = FieldAccessExpr(
        base_expr=ListIndexExpr(
            base_expr=FieldAccessExpr(
                base_expr=Ref(name="roll_result"),
                field_name="instances",
            ),
            index_expr=Literal(value=0),
        ),
        field_name="total",
    )

    result = interpret_expression(expr, runtime_state)

    assert result == 7


@pytest.mark.asyncio
async def test_interpret_expression_resolves_task_references() -> None:
    """
    Resolve task references from the runtime task registry.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when task references resolve to their
        registered task handles.

    Raises
    ------
    AssertionError
        If a valid task reference does not resolve to the original task.

    Notes
    -----
    - Task references are used by join steps and therefore need direct
      coverage.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    task = asyncio.create_task(asyncio.sleep(0, result="done"))
    runtime_state.task_registry["task_1"] = task

    result = interpret_expression(TaskRef(name="task_1"), runtime_state)
    await task

    assert result is task


def test_interpret_expression_rejects_division_by_zero() -> None:
    """
    Raise a native division-by-zero error for zero divisors.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when zero-division attempts map to the
        expected native execution error.

    Raises
    ------
    AssertionError
        If division by zero is not surfaced with the dedicated native code.

    Notes
    -----
    - Division by zero must not leak as a raw Python exception.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    expr = AlgebraicExpr(
        lhs_expr=Literal(value=1),
        rhs_expr=Literal(value=0),
        operator=AlgebraicOperator.DIVIDE,
    )

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(expr, runtime_state)

    assert excinfo.value.code is RlmErrorCode.DIVISION_BY_ZERO


def test_interpret_expression_rejects_invalid_field_access_bases() -> None:
    """
    Raise a native field-access error for non-mapping base values.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when invalid field-access bases map to the
        expected native execution error.

    Raises
    ------
    AssertionError
        If invalid field-access bases are accepted or mapped to the wrong
        code.

    Notes
    -----
    - Field access is intentionally restricted to mapping-like runtime values.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    expr = FieldAccessExpr(
        base_expr=Literal(value=1),
        field_name="total",
    )

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(expr, runtime_state)

    assert excinfo.value.code is RlmErrorCode.INVALID_FIELD_ACCESS


def test_interpret_expression_rejects_missing_fields() -> None:
    """
    Raise a native missing-field error when a mapping lacks the field.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when missing field names map to the expected
        native execution error.

    Raises
    ------
    AssertionError
        If missing fields are accepted or mapped to the wrong error code.

    Notes
    -----
    - Missing-field failures are surfaced explicitly for downstream planner
      feedback.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    runtime_state.bindings["result"] = {"total": 9}
    expr = FieldAccessExpr(
        base_expr=Ref(name="result"),
        field_name="count",
    )

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(expr, runtime_state)

    assert excinfo.value.code is RlmErrorCode.MISSING_FIELD


def test_interpret_expression_rejects_non_integer_list_indices() -> None:
    """
    Raise a native list-index error for non-integer index values.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when non-integer list indices map to the
        expected native execution error.

    Raises
    ------
    AssertionError
        If invalid list-index values are accepted or mapped incorrectly.

    Notes
    -----
    - Bool values are rejected separately by runtime code, so this test uses a
      plain string index.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    expr = ListIndexExpr(
        base_expr=ListExpr(values=(Literal(value=1), Literal(value=2))),
        index_expr=Literal(value="0"),
    )

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(expr, runtime_state)

    assert excinfo.value.code is RlmErrorCode.INVALID_LIST_INDEX


def test_interpret_expression_rejects_negative_list_indices() -> None:
    """
    Raise a native list-index error for negative index values.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when negative list indices map to the
        expected native execution error.

    Raises
    ------
    AssertionError
        If negative list indices are accepted or mapped incorrectly.

    Notes
    -----
    - Negative Python indexing is intentionally unsupported by this DSL.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    expr = ListIndexExpr(
        base_expr=ListExpr(values=(Literal(value=1), Literal(value=2))),
        index_expr=Literal(value=-1),
    )

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(expr, runtime_state)

    assert excinfo.value.code is RlmErrorCode.INVALID_LIST_INDEX


def test_interpret_expression_rejects_out_of_range_list_indices() -> None:
    """
    Raise a native list-index error for out-of-range index values.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when out-of-range list indices map to the
        expected native execution error.

    Raises
    ------
    AssertionError
        If out-of-range list indices are accepted or mapped incorrectly.

    Notes
    -----
    - Out-of-range access must surface a dedicated native error code rather
      than a raw Python IndexError.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    expr = ListIndexExpr(
        base_expr=ListExpr(values=(Literal(value=1), Literal(value=2))),
        index_expr=Literal(value=3),
    )

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(expr, runtime_state)

    assert excinfo.value.code is RlmErrorCode.LIST_INDEX_OUT_OF_RANGE


def test_interpret_expression_rejects_unsupported_operators() -> None:
    """
    Raise an unsupported-operator error for unknown unary operators.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when unsupported operators map to the
        expected native execution error.

    Raises
    ------
    AssertionError
        If unknown operators are accepted or mapped to the wrong error code.

    Notes
    -----
    - This preserves a stable failure mode for malformed planner output.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    expr = UnaryExpr(expr=Literal(value=1), operator=cast(UnaryOperator, "??"))

    with pytest.raises(RlmExecutionError) as excinfo:
        interpret_expression(expr, runtime_state)

    assert excinfo.value.code is RlmErrorCode.UNSUPPORTED_OPERATOR
