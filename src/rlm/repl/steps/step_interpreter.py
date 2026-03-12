"""
Purpose
-------
Interpret executable step nodes from the RLM DSL AST against the current
runtime state. This module exists to provide the step-execution layer used by
the runtime loop and to propagate return control flow through nested step
structures.

Key behaviors
-------------
- Executes tool-call, conditional, foreach, return, LLM-call, and assignment
  steps.
- Resolves call arguments by evaluating their object-expression payloads.
- Propagates return control flow through nested branch and loop execution.
- Mutates runtime bindings for loop variables and assignment targets.

Conventions
-----------
- `interpret_step` is the public entry point for single-step execution.
- `interpret_step_tuple` is the public entry point for ordered step-sequence
  execution.
- Helper functions in this module are private and dispatch on concrete AST node
  classes.
- This module assumes structural validation has already happened.
- Tool and LLM call targets are resolved through registries stored on
  `RuntimeState`.

Downstream usage
----------------
The runtime loop should call `interpret_step_tuple` on a program's top-level
steps, passing the current runtime state that already contains bindings,
registered tools, and registered LLM functions.
"""
from __future__ import annotations

from typing import Tuple

from rlm.repl.expressions.expression_interpreter import interpret_expression
from rlm.repl.steps.steps import (
    ToolCallStep,
    IfStep,
    ForEachStep,
    ReturnStep,
    LlmCallStep,
    AssignmentStep,
    Step,
)
from rlm.repl.runtime.runtime_state import (
    RuntimeState,
    RuntimeValue,
    StepExecutionResult,
)


def _interpret_tool_call_step(
    step: ToolCallStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a deterministic tool-call step.

    Parameters
    ----------
    step : ToolCallStep
        Tool-call step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for argument evaluation, registry lookup,
        and binding updates.

    Returns
    -------
    StepExecutionResult
        Non-returning result for normal execution.

    Raises
    ------
    KeyError
        When the step's tool name does not exist in the runtime tool registry.
    TypeError
        When the resolved callable is invoked with incompatible arguments.

    Notes
    -----
    - Arguments are evaluated through the expression interpreter and passed as
      keyword arguments.
    - This step does not automatically bind the tool's result into runtime
      state.
    """
    tool_callable = runtime_state.tool_registry[step.tool_name]
    kwargs: dict[str, RuntimeValue] = (
        interpret_expression(step.args, runtime_state) if step.args is not None else {}
    )
    tool_callable(**kwargs)
    return StepExecutionResult.normal()


def _interpret_if_step(
    step: IfStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute an if step by evaluating its condition and one branch.

    Parameters
    ----------
    step : IfStep
        If-step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for condition evaluation and nested step
        execution.

    Returns
    -------
    StepExecutionResult
        Normal result when branch execution completes normally, or a propagated
        return result when a nested return is encountered.

    Raises
    ------
    KeyError
        When nested execution encounters an unresolved tool, function, or
        reference.
    TypeError
        When nested execution applies invalid runtime operations.

    Notes
    -----
    - Python truthiness is used for the interpreted condition value.
    - Branch execution is delegated to the step-sequence interpreter.
    """
    condition_value: RuntimeValue = interpret_expression(step.condition, runtime_state)
    selected_steps = step.then_steps if condition_value else step.else_steps
    return interpret_step_tuple(selected_steps, runtime_state)


def _interpret_for_each_step(
    step: ForEachStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a foreach step by iterating over the evaluated iterable expression.

    Parameters
    ----------
    step : ForEachStep
        Foreach-step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for iterable evaluation, loop-variable
        binding, and nested step execution.

    Returns
    -------
    StepExecutionResult
        Normal result when loop execution completes normally, or a propagated
        return result when a nested return is encountered.

    Raises
    ------
    TypeError
        When the evaluated iterable expression is not actually iterable or
        nested execution applies invalid runtime operations.
    KeyError
        When nested execution encounters an unresolved tool, function, or
        reference.

    Notes
    -----
    - The current iteration element is bound to `step.loop_var_name` before
      each body execution.
    - Loop-body steps may refer to the current element via `Ref` using that
      binding name.
    """
    iterable_value = interpret_expression(step.iterable_expr, runtime_state)

    for item in iterable_value:
        runtime_state.bindings[step.loop_var_name] = item
        result = interpret_step_tuple(step.body_steps, runtime_state)
        if result.did_return:
            return result

    return StepExecutionResult.normal()


def _interpret_return_step(
    step: ReturnStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a return step by evaluating and propagating its return value.

    Parameters
    ----------
    step : ReturnStep
        Return-step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for value-expression evaluation.

    Returns
    -------
    StepExecutionResult
        Returning result carrying the interpreted return value.

    Raises
    ------
    KeyError
        When return-value evaluation encounters an unresolved reference.
    TypeError
        When return-value evaluation applies invalid runtime operations.

    Notes
    -----
    - The returned value is propagated upward through nested step execution by
      callers that observe `did_return=True`.
    """
    return_value: RuntimeValue = interpret_expression(step.value_expr, runtime_state)
    return StepExecutionResult.with_return(return_value)


def _interpret_llm_call_step(
    step: LlmCallStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute an LLM-call step.

    Parameters
    ----------
    step : LlmCallStep
        LLM-call step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for argument evaluation and registry lookup.

    Returns
    -------
    StepExecutionResult
        Non-returning result for normal execution.

    Raises
    ------
    KeyError
        When the step's BAML function name does not exist in the runtime LLM
        registry.
    TypeError
        When the resolved callable is invoked with incompatible arguments.

    Notes
    -----
    - Arguments are evaluated through the expression interpreter and passed as
      keyword arguments.
    - This step does not automatically bind the LLM-call result into runtime
      state.
    """
    llm_callable = runtime_state.llm_registry[step.baml_func_name]
    kwargs: dict[str, RuntimeValue] = (
        interpret_expression(step.args, runtime_state) if step.args is not None else {}
    )
    llm_callable(**kwargs)
    return StepExecutionResult.normal()


def _interpret_assignment_step(
    step: AssignmentStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute an assignment step by evaluating its value expression and storing
    the result in runtime bindings.

    Parameters
    ----------
    step : AssignmentStep
        Assignment-step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for expression evaluation and binding
        mutation.

    Returns
    -------
    StepExecutionResult
        Non-returning result for normal execution.

    Raises
    ------
    KeyError
        When assigned-value evaluation encounters an unresolved reference.
    TypeError
        When assigned-value evaluation applies invalid runtime operations.

    Notes
    -----
    - Assignment mutates `runtime_state.bindings` and does not itself return a
      value into surrounding execution.
    """
    interpreted_value: RuntimeValue = interpret_expression(step.value_expr, runtime_state)
    runtime_state.bindings[step.binding_target] = interpreted_value
    return StepExecutionResult.normal()


def interpret_step(
    step: Step,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Interpret a single step AST node against the current runtime state.

    Parameters
    ----------
    step : Step
        Step AST node to execute.
    runtime_state : RuntimeState
        Current runtime state used for evaluation, reference resolution,
        registry lookup, and binding mutation.

    Returns
    -------
    StepExecutionResult
        Result indicating either normal execution or a propagated return.

    Raises
    ------
    ValueError
        When an unsupported step node class is encountered.
    KeyError
        When execution encounters an unresolved tool, function, or reference.
    TypeError
        When execution applies invalid runtime operations.

    Notes
    -----
    - This is the public entry point for single-step execution.
    - Dispatch is performed on concrete AST node classes.
    """
    match step:
        case ToolCallStep():
            return _interpret_tool_call_step(step, runtime_state)
        case IfStep():
            return _interpret_if_step(step, runtime_state)
        case ForEachStep():
            return _interpret_for_each_step(step, runtime_state)
        case ReturnStep():
            return _interpret_return_step(step, runtime_state)
        case LlmCallStep():
            return _interpret_llm_call_step(step, runtime_state)
        case AssignmentStep():
            return _interpret_assignment_step(step, runtime_state)
        case _:
            raise ValueError(f"Unsupported step node: {type(step).__name__}")


def interpret_step_tuple(
    steps: Tuple[Step, ...],
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Interpret an ordered tuple of step nodes until completion or propagated
    return.

    Parameters
    ----------
    steps : tuple[Step, ...]
        Ordered tuple of step AST nodes to execute.
    runtime_state : RuntimeState
        Current runtime state used throughout sequence execution.

    Returns
    -------
    StepExecutionResult
        Normal result if the sequence completes, or a propagated return result
        if execution encounters a return step within the sequence.

    Raises
    ------
    ValueError
        When a contained step node is unsupported.
    KeyError
        When execution encounters an unresolved tool, function, or reference.
    TypeError
        When execution applies invalid runtime operations.

    Notes
    -----
    - This function is the natural entry point for executing branch bodies,
      loop bodies, and top-level program step tuples.
    - Sequence execution stops immediately when a nested return is encountered.
    """
    for step in steps:
        result = interpret_step(step, runtime_state)
        if result.did_return:
            return result

    return StepExecutionResult.normal()
