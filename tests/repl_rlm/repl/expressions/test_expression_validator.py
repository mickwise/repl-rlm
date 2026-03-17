"""
Purpose
-------
Exercise structural validation for expression AST nodes. This module exists to
keep the expression validator aligned with the DSL contract and to catch
regressions in supported node and operator shape.

Key behaviors
-------------
- Verifies that valid nested expressions pass validation.
- Verifies that malformed names, operators, and unsupported nodes fail with the
  expected native validation codes.

Conventions
-----------
- Tests assert on native error codes instead of raw Python exception classes.
- Coverage focuses on public validation behavior rather than helper function
  internals.

Downstream usage
----------------
CI runs this module to protect the expression-validation boundary consumed by
the step validator and runtime entrypoints.
"""

from typing import cast

import pytest

from repl_rlm.repl.errors import RlmErrorCode, RlmValidationError
from repl_rlm.repl.expressions.expression_validator import validate_expression
from repl_rlm.repl.expressions.expressions import (
    AlgebraicExpr,
    AlgebraicOperator,
    ComparisonExpr,
    ComparisonOperator,
    FieldAccessExpr,
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


def test_validate_expression_accepts_nested_valid_structure() -> None:
    """
    Accept a nested expression tree with valid names and operators.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when a representative nested expression
        validates successfully.

    Raises
    ------
    AssertionError
        If valid nested expression nodes unexpectedly fail validation.

    Notes
    -----
    - This stabilizes the recursive dispatch path used by larger program
      validation.
    """
    expr = ObjectExpr(
        fields={
            "items": ListExpr(values=(Literal(value=1), Ref(name="count"))),
            "decision": LogicalExpr(
                lhs_expr=ComparisonExpr(
                    lhs_expr=Ref(name="count"),
                    rhs_expr=Literal(value=0),
                    operator=ComparisonOperator.GREATER_THAN,
                ),
                rhs_expr=UnaryExpr(
                    expr=TaskRef(name="task_1"),
                    operator=UnaryOperator.NOT,
                ),
                operator=LogicalOperator.OR,
            ),
        }
    )

    validate_expression(expr)


def test_validate_expression_rejects_blank_reference_names() -> None:
    """
    Reject reference names that are empty after trimming whitespace.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when blank reference names raise the expected
        validation error.

    Raises
    ------
    AssertionError
        If blank reference names are accepted or map to the wrong error code.

    Notes
    -----
    - Name validation is part of the stable DSL structure, not a cosmetic
      detail.
    """
    with pytest.raises(RlmValidationError) as excinfo:
        validate_expression(Ref(name="   "))

    assert excinfo.value.code is RlmErrorCode.VALIDATION_VALUE_ERROR


def test_validate_expression_accepts_algebraic_and_field_access_nodes() -> None:
    """
    Accept nested algebraic and field-access expressions with valid structure.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when algebraic and field-access nodes
        validate successfully.

    Raises
    ------
    AssertionError
        If valid algebraic or field-access nodes unexpectedly fail validation.

    Notes
    -----
    - This stabilizes the new expression-node branches added to validator
      dispatch.
    """
    expr = AlgebraicExpr(
        lhs_expr=FieldAccessExpr(
            base_expr=ObjectExpr(
                fields={
                    "total": Literal(value=5),
                    "count": Ref(name="count"),
                }
            ),
            field_name="total",
        ),
        rhs_expr=FieldAccessExpr(
            base_expr=ObjectExpr(fields={"count": Ref(name="count")}),
            field_name="count",
        ),
        operator=AlgebraicOperator.ADD,
    )

    validate_expression(expr)


def test_validate_expression_rejects_invalid_operator_types() -> None:
    """
    Reject operator payloads that are not members of the expected enum type.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when an invalid operator payload triggers the
        expected validation error.

    Raises
    ------
    AssertionError
        If a malformed operator payload is accepted or maps to the wrong code.

    Notes
    -----
    - Operator type checks are a core part of the validator's structural
      contract.
    """
    expr = ComparisonExpr(
        lhs_expr=Literal(value=1),
        rhs_expr=Literal(value=2),
        operator=cast(ComparisonOperator, "??"),
    )

    with pytest.raises(RlmValidationError) as excinfo:
        validate_expression(expr)

    assert excinfo.value.code is RlmErrorCode.VALIDATION_TYPE_ERROR


def test_validate_expression_rejects_blank_field_access_names() -> None:
    """
    Reject field-access expressions whose field name is blank after trimming.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when blank field names raise the expected
        validation error.

    Raises
    ------
    AssertionError
        If blank field names are accepted or map to the wrong error code.

    Notes
    -----
    - Field-name validation is part of the stable DSL shape for field access.
    """
    expr = FieldAccessExpr(
        base_expr=ObjectExpr(fields={"total": Literal(value=1)}),
        field_name="   ",
    )

    with pytest.raises(RlmValidationError) as excinfo:
        validate_expression(expr)

    assert excinfo.value.code is RlmErrorCode.VALIDATION_VALUE_ERROR


def test_validate_expression_rejects_invalid_algebraic_operator_types() -> None:
    """
    Reject algebraic operator payloads that are not enum members.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when malformed algebraic operators trigger
        the expected validation error.

    Raises
    ------
    AssertionError
        If a malformed algebraic operator is accepted or mapped incorrectly.

    Notes
    -----
    - This pins the new algebraic-expression validator branch to the same
      structural guarantees as existing operator nodes.
    """
    expr = AlgebraicExpr(
        lhs_expr=Literal(value=1),
        rhs_expr=Literal(value=2),
        operator=cast(AlgebraicOperator, "??"),
    )

    with pytest.raises(RlmValidationError) as excinfo:
        validate_expression(expr)

    assert excinfo.value.code is RlmErrorCode.VALIDATION_TYPE_ERROR


def test_validate_expression_rejects_unsupported_nodes() -> None:
    """
    Reject objects that are not supported expression AST node classes.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when unsupported node instances produce the
        expected validation code.

    Raises
    ------
    AssertionError
        If unsupported expression objects are accepted or mapped incorrectly.

    Notes
    -----
    - This preserves a stable failure mode for malformed planner output.
    """
    with pytest.raises(RlmValidationError) as excinfo:
        validate_expression(object())  # type: ignore[arg-type]

    assert excinfo.value.code is RlmErrorCode.UNSUPPORTED_EXPRESSION_NODE
