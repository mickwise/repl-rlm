"""
Purpose
-------
Validate step nodes and top-level programs from the RLM DSL AST before runtime
execution. This module exists to enforce the structural correctness of
executable step nodes and to catch malformed program structure before
interpretation begins.

Key behaviors
-------------
- Validates tool-call, conditional, foreach, return, LLM-call, and assignment
  step nodes.
- Recursively validates nested step tuples contained inside branching and loop
  constructs.
- Delegates all expression validation to the expression-validator module.
- Validates the top-level program structure and its metadata container.

Conventions
-----------
- Validation in this module is structural rather than semantic.
- Expression fields are validated by calling `validate_expression`.
- Nested step sequences must be tuples and are recursively validated step by
  step.
- This module does not perform runtime name resolution, tool lookup, or value
  compatibility checks.

Downstream usage
----------------
Program-level validation should call `validate_program` before interpretation.
Internal runtime components that validate individual step nodes may call
`validate_step` directly when needed.
"""
from __future__ import annotations

from collections.abc import Mapping

from rlm.repl.expressions.expression_validator import validate_expression
from rlm.repl.steps.steps import (
    ToolCallStep,
    IfStep,
    ForEachStep,
    ReturnStep,
    LlmCallStep,
    AssignmentStep,
    Step,
    Program,
)


def _validate_non_empty_string(value: object, field_name: str) -> None:
    """
    Validate that a field value is a non-empty string.

    Parameters
    ----------
    value : object
        Value to validate as a non-empty string.
    field_name : str
        Human-readable field name used in error messages.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the supplied value is not a string.
    ValueError
        When the supplied value is an empty or whitespace-only string.

    Notes
    -----
    - This helper is used for repeated string-field validation across step
      nodes.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")


def _validate_step_tuple(steps: object, field_name: str) -> None:
    """
    Validate that a field contains a tuple of valid step nodes.

    Parameters
    ----------
    steps : object
        Value expected to be a tuple of step nodes.
    field_name : str
        Human-readable field name used in error messages.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the supplied value is not a tuple or contains an unsupported step
        node.

    Notes
    -----
    - Each contained step is recursively validated through `validate_step`.
    - Empty tuples are allowed.
    """
    if not isinstance(steps, tuple):
        raise TypeError(f"{field_name} must be a tuple of steps.")

    for step in steps:
        validate_step(step)


def _validate_tool_call_step(step: ToolCallStep) -> None:
    """
    Validate the structural correctness of a tool-call step.

    Parameters
    ----------
    step : ToolCallStep
        Tool-call step node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When a field has the wrong type.
    ValueError
        When the tool name is empty or whitespace-only.

    Notes
    -----
    - Tool lookup is not performed here.
    - Arguments are validated structurally through the expression validator when
      present.
    """
    _validate_non_empty_string(step.tool_name, "ToolCallStep.tool_name")

    if step.args is not None:
        validate_expression(step.args)


def _validate_if_step(step: IfStep) -> None:
    """
    Validate the structural correctness of an if step.

    Parameters
    ----------
    step : IfStep
        If-step node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When a field has the wrong type or a branch container is not a tuple.
    ValueError
        When a nested field violates delegated validation constraints.

    Notes
    -----
    - Condition validation is delegated to the expression validator.
    - Branch step tuples are recursively validated.
    """
    validate_expression(step.condition)
    _validate_step_tuple(step.then_steps, "IfStep.then_steps")
    _validate_step_tuple(step.else_steps, "IfStep.else_steps")


def _validate_for_each_step(step: ForEachStep) -> None:
    """
    Validate the structural correctness of a foreach step.

    Parameters
    ----------
    step : ForEachStep
        Foreach-step node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When a field has the wrong type or the body container is not a tuple.
    ValueError
        When the loop variable name is empty or whitespace-only.

    Notes
    -----
    - Iterable expression validation is delegated to the expression validator.
    - Body steps are recursively validated through the step validator.
    """
    validate_expression(step.iterable_expr)
    _validate_non_empty_string(
        step.loop_var_name,
        "ForEachStep.loop_var_name",
    )
    _validate_step_tuple(step.body_steps, "ForEachStep.body_steps")


def _validate_return_step(step: ReturnStep) -> None:
    """
    Validate the structural correctness of a return step.

    Parameters
    ----------
    step : ReturnStep
        Return-step node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the return expression is malformed.

    Notes
    -----
    - Return-value validation is delegated entirely to the expression
      validator.
    """
    validate_expression(step.value_expr)


def _validate_llm_call_step(step: LlmCallStep) -> None:
    """
    Validate the structural correctness of an LLM-call step.

    Parameters
    ----------
    step : LlmCallStep
        LLM-call step node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When a field has the wrong type.
    ValueError
        When the BAML function name is empty or whitespace-only.

    Notes
    -----
    - Actual BAML function resolution is not performed here.
    - Arguments are validated structurally through the expression validator when
      present.
    """
    _validate_non_empty_string(
        step.baml_func_name,
        "LlmCallStep.baml_func_name",
    )

    if step.args is not None:
        validate_expression(step.args)


def _validate_assignment_step(step: AssignmentStep) -> None:
    """
    Validate the structural correctness of an assignment step.

    Parameters
    ----------
    step : AssignmentStep
        Assignment-step node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When a field has the wrong type.
    ValueError
        When the binding target is empty or whitespace-only.

    Notes
    -----
    - Assigned-value validation is delegated to the expression validator.
    - Binding-target name resolution is not performed here.
    """
    validate_expression(step.value_expr)
    _validate_non_empty_string(
        step.binding_target,
        "AssignmentStep.binding_target",
    )


def validate_step(step: Step) -> None:
    """
    Validate the structural correctness of a general step AST node.

    Parameters
    ----------
    step : Step
        Step AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When a node field has the wrong type or when the step node class is
        unsupported.
    ValueError
        When a node contains an invalid non-empty-string constraint violation.

    Notes
    -----
    - This is the public entry point for step validation.
    - Validation dispatch is performed on concrete AST node classes.
    """
    match step:
        case ToolCallStep():
            _validate_tool_call_step(step)
        case IfStep():
            _validate_if_step(step)
        case ForEachStep():
            _validate_for_each_step(step)
        case ReturnStep():
            _validate_return_step(step)
        case LlmCallStep():
            _validate_llm_call_step(step)
        case AssignmentStep():
            _validate_assignment_step(step)
        case _:
            raise TypeError(
                f"Unsupported step node for validation: {type(step).__name__}"
            )


def validate_program(program: Program) -> None:
    """
    Validate the structural correctness of a top-level DSL program.

    Parameters
    ----------
    program : Program
        Program AST node to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    TypeError
        When the program step container is not a tuple or metadata is not a
        mapping.
    ValueError
        When a nested step violates a delegated validation constraint.

    Notes
    -----
    - Program-step validation is delegated to the step validator.
    - Metadata is validated only as a mapping container at this layer.
    """
    _validate_step_tuple(program.steps, "Program.steps")

    if not isinstance(program.metadata, Mapping):
        raise TypeError("Program.metadata must be a mapping.")
