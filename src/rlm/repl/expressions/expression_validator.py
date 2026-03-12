"""
Purpose
-------
Validate expression nodes from the RLM DSL AST before interpretation. This
module exists to enforce the structural correctness of expression nodes and to
catch malformed AST data before runtime execution begins.

Key behaviors
-------------
- Validates literal, object, list, comparison, logical, and unary
  expression nodes, including both binding references and task references.
- Recursively validates nested expressions contained inside object and list
  expressions.
- Checks that operator fields are instances of the correct enum types.
- Rejects unsupported expression node classes.

Conventions
-----------
- Validation in this module is structural rather than semantic.
- This module does not attempt to resolve references against runtime state.
- This module does not attempt to prove runtime operator compatibility for
  values that are only known during interpretation.
- `validate_expression` is the public entry point for this module.

Downstream usage
----------------
Program-level and step-level validators should call `validate_expression` for
every expression field they encounter. The interpreter should assume that
structural expression validation has already happened before runtime execution.
"""
from __future__ import annotations

from collections.abc import Mapping
from rlm.repl.expressions.expressions import (
    Literal,
    Ref,
    TaskRef,
    ObjectExpr,
    ListExpr,
    ComparisonExpr,
    ComparisonOperator,
    LogicalExpr,
    LogicalOperator,
    UnaryExpr,
    UnaryOperator,
    Expr,
)


def _validate_literal(literal: Literal) -> None:
    """
    Validate that a literal node stores a legal atomic value.

    Parameters
    ----------
    literal : Literal
        Literal AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the literal value is not one of the allowed atomic runtime types.

    Notes
    -----
    - This check is structural and defensive.
    - Allowed atomic types are int, float, str, bool, and None.
    """
    if not isinstance(literal.value, (int, float, str, bool, type(None))):
        raise TypeError("Literal value must be int, float, str, bool, or None.")


def _validate_ref(ref: Ref) -> None:
    """
    Validate that a reference node contains a usable binding name.

    Parameters
    ----------
    ref : Ref
        Reference AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the reference name is not a string.
    ValueError
        When the reference name is empty or only whitespace.

    Notes
    -----
    - This function validates only the shape of the reference name.
    - Actual name resolution against runtime bindings is not performed here.
    """
    if not isinstance(ref.name, str):
        raise TypeError("Reference name must be a string.")
    if not ref.name.strip():
        raise ValueError("Reference name must be a non-empty string.")


def _validate_task_ref(task_ref: TaskRef) -> None:
    """
    Validate that a task-reference node contains a usable task name.

    Parameters
    ----------
    task_ref : TaskRef
        Task-reference AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the task-reference name is not a string.
    ValueError
        When the task-reference name is empty or only whitespace.

    Notes
    -----
    - This function validates only the shape of the task-reference name.
    - Actual name resolution against runtime task registry is not performed
      here.
    """
    if not isinstance(task_ref.name, str):
        raise TypeError("Task reference name must be a string.")
    if not task_ref.name.strip():
        raise ValueError("Task reference name must be a non-empty string.")


def _validate_object_expr(object_expr: ObjectExpr) -> None:
    """
    Validate that an object expression contains a legal mapping of fields.

    Parameters
    ----------
    object_expr : ObjectExpr
        Object-expression AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the fields container is not a mapping or when a field name is not
        a string.
    ValueError
        When a field name is empty or only whitespace.

    Notes
    -----
    - Field values are recursively validated through the public expression
      entry point.
    - Empty objects are allowed.
    """
    if not isinstance(object_expr.fields, Mapping):
        raise TypeError("ObjectExpr.fields must be a mapping.")

    for field_name, field_expr in object_expr.fields.items():
        if not isinstance(field_name, str):
            raise TypeError("ObjectExpr field names must be strings.")
        if not field_name.strip():
            raise ValueError("ObjectExpr field names must be non-empty strings.")
        validate_expression(field_expr)


def _validate_list_expr(list_expr: ListExpr) -> None:
    """
    Validate that a list expression contains a legal tuple of expressions.

    Parameters
    ----------
    list_expr : ListExpr
        List-expression AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the values container is not a tuple.

    Notes
    -----
    - Element expressions are recursively validated through the public
      expression entry point.
    - Empty lists are allowed.
    """
    if not isinstance(list_expr.values, tuple):
        raise TypeError("ListExpr.values must be a tuple.")

    for element_expr in list_expr.values:
        validate_expression(element_expr)


def _validate_comparison_expr(comparison_expr: ComparisonExpr) -> None:
    """
    Validate that a comparison expression has legal operands and operator type.

    Parameters
    ----------
    comparison_expr : ComparisonExpr
        Comparison-expression AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the comparison operator is not a ComparisonOperator.

    Notes
    -----
    - Operand expressions are recursively validated through the public
      expression entry point.
    - This function does not attempt to prove that the evaluated operand values
      will be comparable at runtime.
    """
    validate_expression(comparison_expr.lhs_expr)
    validate_expression(comparison_expr.rhs_expr)

    if not isinstance(comparison_expr.operator, ComparisonOperator):
        raise TypeError(
            "ComparisonExpr.operator must be a ComparisonOperator."
        )


def _validate_logical_expr(logical_expr: LogicalExpr) -> None:
    """
    Validate that a logical expression has legal operands and operator type.

    Parameters
    ----------
    logical_expr : LogicalExpr
        Logical-expression AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the logical operator is not a LogicalOperator.

    Notes
    -----
    - Operand expressions are recursively validated through the public
      expression entry point.
    - This function does not enforce strict boolean-only semantics.
    """
    validate_expression(logical_expr.lhs_expr)
    validate_expression(logical_expr.rhs_expr)

    if not isinstance(logical_expr.operator, LogicalOperator):
        raise TypeError("LogicalExpr.operator must be a LogicalOperator.")


def _validate_unary_expr(unary_expr: UnaryExpr) -> None:
    """
    Validate that a unary expression has a legal operand and operator type.

    Parameters
    ----------
    unary_expr : UnaryExpr
        Unary-expression AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the unary operator is not a UnaryOperator.

    Notes
    -----
    - Operand expressions are recursively validated through the public
      expression entry point.
    - This function does not attempt to prove runtime compatibility between the
      operator and the evaluated operand value.
    """
    validate_expression(unary_expr.expr)

    if not isinstance(unary_expr.operator, UnaryOperator):
        raise TypeError("UnaryExpr.operator must be a UnaryOperator.")


def validate_expression(expr: Expr) -> None:
    """
    Validate the structural correctness of a general expression AST node.

    Parameters
    ----------
    expr : Expr
        Expression AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When a node field has the wrong type or when the expression node class
        is unsupported.
    ValueError
        When a node contains an invalid non-empty-string constraint violation.

    Notes
    -----
    - This is the public entry point for expression validation.
    - Validation dispatch is performed on concrete AST node classes.
    """
    match expr:
        case Literal():
            _validate_literal(expr)
        case Ref():
            _validate_ref(expr)
        case TaskRef():
            _validate_task_ref(expr)
        case ObjectExpr():
            _validate_object_expr(expr)
        case ListExpr():
            _validate_list_expr(expr)
        case ComparisonExpr():
            _validate_comparison_expr(expr)
        case LogicalExpr():
            _validate_logical_expr(expr)
        case UnaryExpr():
            _validate_unary_expr(expr)
        case _:
            raise TypeError(
                f"Unsupported expression node for validation: "
                f"{type(expr).__name__}"
            )
