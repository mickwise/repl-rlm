"""
Purpose
-------
Interpret expression nodes from the RLM DSL AST into concrete runtime values.
This module exists to provide the expression-evaluation layer consumed by the
runtime loop and step interpreter.

Key behaviors
-------------
- Evaluates literal, reference, object, list, comparison, algebraic,
  field-access, logical, and unary expression nodes.
- Resolves named references against the supplied runtime bindings and task
  references against runtime task registry state.
- Recursively evaluates nested expressions into concrete runtime values.
- Uses Python truthiness for logical and unary-not evaluation.

Conventions
-----------
- `interpret_expression` is the public entry point for expression evaluation.
- Helper functions in this module are private and dispatch on concrete AST node
  classes.
- Structural validation is expected to happen in a separate validator pass.
- This module raises native execution errors for unsupported nodes, unsupported
  operators, reference lookup failures, division by zero, and invalid
  field-access operations.

Downstream usage
----------------
Step interpreters and runtime loops should call `interpret_expression` whenever
they need to evaluate an AST expression node against the current
`RuntimeState`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Dict, List

from repl_rlm.repl.errors import (
    ErrorPhase,
    RlmErrorCode,
    RlmExecutionError,
    RlmRuntimeError,
    translate_exception,
)
from repl_rlm.repl.expressions.expressions import (
    AlgebraicExpr,
    AlgebraicOperator,
    AtomicType,
    ComparisonExpr,
    ComparisonOperator,
    Expr,
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
from repl_rlm.repl.runtime.runtime_state import RuntimeState, RuntimeValue


def _interpret_literal(literal: Literal) -> AtomicType:
    """
    Interpret a literal node into its stored atomic runtime value.

    Parameters
    ----------
    literal : Literal
        Literal AST node whose value should be returned directly.

    Returns
    -------
    AtomicType
        Atomic value stored on the literal node.

    Raises
    ------
    None

    Notes
    -----
    - Literal evaluation does not consult runtime bindings.
    """
    return literal.value


def _interpret_ref(ref: Ref, runtime_state: RuntimeState) -> RuntimeValue:
    """
    Resolve a reference node against the current runtime bindings.

    Parameters
    ----------
    ref : Ref
        Reference AST node naming a previously bound runtime value.
    runtime_state : RuntimeState
        Current runtime state used for name resolution.

    Returns
    -------
    RuntimeValue
        Runtime value currently bound to the supplied reference name.

    Raises
    ------
    KeyError
        When the reference name is not present in runtime bindings.

    Notes
    -----
    - Reference lookup is a runtime concern and depends on current bindings.
    """
    try:
        return runtime_state.bindings[ref.name]
    except KeyError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.UNBOUND_REFERENCE,
            message=f"Unbound reference: {ref.name}",
            cause=error,
        ) from error


def _interpret_task_ref(
    task_ref: TaskRef,
    runtime_state: RuntimeState,
) -> RuntimeValue:
    """
    Resolve a task-reference node against the current runtime task registry.

    Parameters
    ----------
    task_ref : TaskRef
        Task-reference AST node naming a previously registered task handle.
    runtime_state : RuntimeState
        Current runtime state used for task-name resolution.

    Returns
    -------
    RuntimeValue
        Runtime task handle currently registered to the supplied task name.

    Raises
    ------
    KeyError
        When the task-reference name is not present in runtime task registry.

    Notes
    -----
    - Task-reference lookup is a runtime concern and depends on current task
      registry content.
    """
    try:
        return runtime_state.task_registry[task_ref.name]
    except KeyError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.UNBOUND_TASK_REFERENCE,
            message=f"Unbound task reference: {task_ref.name}",
            cause=error,
        ) from error


def _interpret_object_expr(
    object_expr: ObjectExpr,
    runtime_state: RuntimeState,
) -> Dict[str, RuntimeValue]:
    """
    Interpret an object expression into a runtime dictionary.

    Parameters
    ----------
    object_expr : ObjectExpr
        Object-expression AST node whose field expressions should be
        recursively evaluated.
    runtime_state : RuntimeState
        Current runtime state used when evaluating nested field expressions.

    Returns
    -------
    dict[str, RuntimeValue]
        Dictionary mapping field names to evaluated runtime values.

    Raises
    ------
    KeyError
        When a nested reference cannot be resolved.

    Notes
    -----
    - Each field expression is evaluated through the public expression entry
      point.
    """
    return {
        field_name: interpret_expression(expr, runtime_state)
        for field_name, expr in object_expr.fields.items()
    }


def _interpret_list_expr(
    list_expr: ListExpr,
    runtime_state: RuntimeState,
) -> List[RuntimeValue]:
    """
    Interpret a list expression into a runtime list.

    Parameters
    ----------
    list_expr : ListExpr
        List-expression AST node whose element expressions should be
        recursively evaluated.
    runtime_state : RuntimeState
        Current runtime state used when evaluating nested list expressions.

    Returns
    -------
    list[RuntimeValue]
        List of evaluated runtime values in AST order.

    Raises
    ------
    KeyError
        When a nested reference cannot be resolved.

    Notes
    -----
    - Each list element is evaluated through the public expression entry point.
    """
    return [interpret_expression(expr, runtime_state) for expr in list_expr.values]


def _interpret_comparison_expr(
    comparison_expr: ComparisonExpr,
    runtime_state: RuntimeState,
) -> bool:
    """
    Interpret a comparison expression into a boolean runtime result.

    Parameters
    ----------
    comparison_expr : ComparisonExpr
        Comparison-expression AST node containing two operand expressions and a
        comparison operator.
    runtime_state : RuntimeState
        Current runtime state used when evaluating operand expressions.

    Returns
    -------
    bool
        Result of applying the comparison operator to the evaluated operands.

    Raises
    ------
    ValueError
        When the comparison operator is unsupported.

    Notes
    -----
    - Operand values are obtained by recursively evaluating both sides.
    - Invalid host-language comparisons are allowed to propagate naturally.
    """
    lhs: RuntimeValue = interpret_expression(
        comparison_expr.lhs_expr,
        runtime_state,
    )
    rhs: RuntimeValue = interpret_expression(
        comparison_expr.rhs_expr,
        runtime_state,
    )
    operator: ComparisonOperator = comparison_expr.operator

    match operator:
        case ComparisonOperator.GREATER_THAN:
            return lhs > rhs
        case ComparisonOperator.GREATER_THAN_OR_EQUAL:
            return lhs >= rhs
        case ComparisonOperator.EQUAL:
            return lhs == rhs
        case ComparisonOperator.LESS_THAN_OR_EQUAL:
            return lhs <= rhs
        case ComparisonOperator.LESS_THAN:
            return lhs < rhs
        case ComparisonOperator.NOT_EQUAL:
            return lhs != rhs
        case _:
            raise RlmExecutionError(
                code=RlmErrorCode.UNSUPPORTED_OPERATOR,
                message=f"Unsupported comparison operator: {operator}",
            )


def _interpret_logical_expr(
    logical_expr: LogicalExpr,
    runtime_state: RuntimeState,
) -> bool:
    """
    Interpret a logical expression into a boolean runtime result.

    Parameters
    ----------
    logical_expr : LogicalExpr
        Logical-expression AST node containing two operand expressions and a
        logical operator.
    runtime_state : RuntimeState
        Current runtime state used when evaluating operand expressions.

    Returns
    -------
    bool
        Boolean result of applying the logical operator under Python
        truthiness semantics.

    Raises
    ------
    ValueError
        When the logical operator is unsupported.

    Notes
    -----
    - Operand values are recursively evaluated before logical combination.
    - Python truthiness is used intentionally for this DSL runtime.
    """
    lhs: RuntimeValue = interpret_expression(
        logical_expr.lhs_expr,
        runtime_state,
    )
    rhs: RuntimeValue = interpret_expression(
        logical_expr.rhs_expr,
        runtime_state,
    )
    operator: LogicalOperator = logical_expr.operator

    match operator:
        case LogicalOperator.AND:
            return bool(lhs) and bool(rhs)
        case LogicalOperator.OR:
            return bool(lhs) or bool(rhs)
        case _:
            raise RlmExecutionError(
                code=RlmErrorCode.UNSUPPORTED_OPERATOR,
                message=f"Unsupported logical operator: {operator}",
            )


def _interpret_algebraic_expr(
    algebraic_expr: AlgebraicExpr,
    runtime_state: RuntimeState,
) -> RuntimeValue:
    """
    Interpret an algebraic expression into a runtime value.

    Parameters
    ----------
    algebraic_expr : AlgebraicExpr
        Algebraic-expression AST node containing two operand expressions and an
        algebraic operator.
    runtime_state : RuntimeState
        Current runtime state used when evaluating operand expressions.

    Returns
    -------
    RuntimeValue
        Runtime value produced by applying the algebraic operator to the
        evaluated operands.

    Raises
    ------
    RlmExecutionError
        When division is attempted with a zero divisor or the operator is
        unsupported.

    Notes
    -----
    - Operand values are recursively evaluated before the algebraic operation
      is applied.
    - Invalid host-language algebraic operations are allowed to propagate to
      native translation, except for division by zero which is raised as an
      explicit native execution error.
    """
    lhs: RuntimeValue = interpret_expression(
        algebraic_expr.lhs_expr,
        runtime_state,
    )
    rhs: RuntimeValue = interpret_expression(
        algebraic_expr.rhs_expr,
        runtime_state,
    )
    operator: AlgebraicOperator = algebraic_expr.operator

    match operator:
        case AlgebraicOperator.ADD:
            return lhs + rhs
        case AlgebraicOperator.SUBTRACT:
            return lhs - rhs
        case AlgebraicOperator.MULTIPLY:
            return lhs * rhs
        case AlgebraicOperator.DIVIDE:
            try:
                return lhs / rhs
            except ZeroDivisionError as error:
                raise RlmExecutionError(
                    code=RlmErrorCode.DIVISION_BY_ZERO,
                    message="Division by zero is not allowed.",
                    cause=error,
                ) from error
        case _:
            raise RlmExecutionError(
                code=RlmErrorCode.UNSUPPORTED_OPERATOR,
                message=f"Unsupported algebraic operator: {operator}",
            )


def _interpret_field_access_expr(
    field_access_expr: FieldAccessExpr,
    runtime_state: RuntimeState,
) -> RuntimeValue:
    """
    Interpret a field-access expression into a runtime value.

    Parameters
    ----------
    field_access_expr : FieldAccessExpr
        Field-access AST node containing a base expression and field name.
    runtime_state : RuntimeState
        Current runtime state used when evaluating the base expression.

    Returns
    -------
    RuntimeValue
        Runtime value stored under the requested field name.

    Raises
    ------
    RlmExecutionError
        When the base expression is not field-accessible or the requested
        field is missing.

    Notes
    -----
    - Field access is intentionally limited to mapping-like runtime values.
    - Missing-field and invalid-base failures are raised as explicit native
      execution errors rather than relying on generic Python exception
      translation.
    """
    base_value: RuntimeValue = interpret_expression(
        field_access_expr.base_expr,
        runtime_state,
    )
    field_name: str = field_access_expr.field_name

    if not isinstance(base_value, Mapping):
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_FIELD_ACCESS,
            message=("Field access base expression must evaluate to a mapping-like value."),
        )

    try:
        return base_value[field_name]
    except KeyError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.MISSING_FIELD,
            message=f"Field not found: {field_name}",
            cause=error,
        ) from error


def _interpret_unary_expr(
    unary_expr: UnaryExpr,
    runtime_state: RuntimeState,
) -> RuntimeValue:
    """
    Interpret a unary expression into a runtime value.

    Parameters
    ----------
    unary_expr : UnaryExpr
        Unary-expression AST node containing a single operand expression and a
        unary operator.
    runtime_state : RuntimeState
        Current runtime state used when evaluating the operand expression.

    Returns
    -------
    RuntimeValue
        Runtime value produced by applying the unary operator to the evaluated
        operand.

    Raises
    ------
    ValueError
        When the unary operator is unsupported.

    Notes
    -----
    - Unary minus and logical negation rely on normal Python runtime behavior.
    """
    interpreted_expr: RuntimeValue = interpret_expression(
        unary_expr.expr,
        runtime_state,
    )
    operator: UnaryOperator = unary_expr.operator

    match operator:
        case UnaryOperator.MINUS:
            return -interpreted_expr
        case UnaryOperator.NOT:
            return not interpreted_expr
        case _:
            raise RlmExecutionError(
                code=RlmErrorCode.UNSUPPORTED_OPERATOR,
                message=f"Unsupported unary operator: {operator}",
            )


def interpret_expression(expr: Expr, runtime_state: RuntimeState) -> RuntimeValue:  # type: ignore
    """
    Interpret a general AST expression node into a concrete runtime value.

    Parameters
    ----------
    expr : Expr
        Expression AST node to evaluate.
    runtime_state : RuntimeState
        Current runtime state used for reference resolution and recursive
        nested evaluation.

    Returns
    -------
    RuntimeValue
        Concrete runtime value produced by evaluating the supplied expression
        node.

    Raises
    ------
    KeyError
        When a reference names a missing binding or task reference names a
        missing task handle.
    ValueError
        When the expression node or one of its operators is unsupported.

    Notes
    -----
    - This function is the public entry point for expression interpretation.
    - Dispatch is performed on concrete AST node classes.
    """
    try:
        match expr:
            case Literal():
                return _interpret_literal(expr)
            case Ref():
                return _interpret_ref(expr, runtime_state)
            case TaskRef():
                return _interpret_task_ref(expr, runtime_state)
            case ObjectExpr():
                return _interpret_object_expr(expr, runtime_state)
            case ListExpr():
                return _interpret_list_expr(expr, runtime_state)
            case ComparisonExpr():
                return _interpret_comparison_expr(expr, runtime_state)
            case AlgebraicExpr():
                return _interpret_algebraic_expr(expr, runtime_state)
            case FieldAccessExpr():
                return _interpret_field_access_expr(expr, runtime_state)
            case LogicalExpr():
                return _interpret_logical_expr(expr, runtime_state)
            case UnaryExpr():
                return _interpret_unary_expr(expr, runtime_state)
            case _:
                raise RlmExecutionError(
                    code=RlmErrorCode.UNSUPPORTED_EXPRESSION_NODE,
                    message=f"Unsupported expression node: {type(expr).__name__}",
                )
    except Exception as error:
        if isinstance(error, RlmRuntimeError):
            raise
        raise translate_exception(error, ErrorPhase.EXECUTION) from error
