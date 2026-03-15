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
    ComparisonExpr,
    ComparisonOperator,
    ListExpr,
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
