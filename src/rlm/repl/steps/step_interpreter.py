"""
Purpose
-------
Interpret executable step nodes from the RLM DSL AST against the current
runtime state. This module exists to provide the step-execution layer used by
the runtime loop, to support spawned sub-program execution, and to propagate
return control flow through nested step structures.

Key behaviors
-------------
- Executes tool-call, conditional, foreach, return, LLM-call, recursive-call,
  assignment, spawn, and join steps, awaiting tool and LLM results only when
  the invoked call returns an awaitable.
- Resolves call arguments by evaluating their object-expression payloads.
- Launches spawned sub-programs in child runtime states and joins their task
  handles back into normal step execution.

Conventions
-----------
- `interpret_step` is the public async entry point for single-step
  execution.
- `interpret_step_tuple` is the public async entry point for ordered
  step-sequence execution.
- Helper functions in this module are private and dispatch on concrete AST node
  classes.
- This module assumes structural validation has already happened.
- Tool and LLM call targets are resolved through registries stored on
  `RuntimeState`, and their return values may be synchronous or awaitable.
- Spawned sub-programs execute against forked child runtime states, while task
  handles are tracked on the parent runtime state.

Downstream usage
----------------
The runtime loop should await `interpret_step_tuple` on a program's
top-level steps, passing the current runtime state that already contains
bindings, registered tools, registered LLM functions, and any active spawned
sub-program task handles.
"""
from __future__ import annotations

import asyncio
from inspect import isawaitable
from typing import List, Tuple

from rlm.repl.errors import (
    ErrorPhase,
    RlmErrorCode,
    RlmExecutionError,
    RlmRuntimeError,
    translate_exception,
)
from rlm.repl.expressions.expression_interpreter import interpret_expression
from rlm.repl.runtime.runtime_state import (
    LlmFunction,
    RuntimeState,
    RuntimeValue,
    StepExecutionResult,
    TaskHandle,
    ToolFunction,
)
from rlm.repl.steps.step_validator import validate_program
from rlm.repl.steps.steps import (
    AssignmentStep,
    ForEachStep,
    IfStep,
    JoinStep,
    LlmCallStep,
    Program,
    RecursiveCallStep,
    ReturnStep,
    SpawnStep,
    Step,
    ToolCallStep,
)


async def _interpret_tool_call_step(
    step: ToolCallStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a deterministic tool-call step, awaiting only when the invoked
    callable returns an awaitable.

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
    - Arguments are evaluated synchronously through the expression interpreter
      and passed as keyword arguments to the tool callable.
    - If the tool callable returns an awaitable, it is awaited before normal
      execution resumes.
    - If `step.binding_target` is set, the final tool result is stored under
      that binding name in `runtime_state.bindings`.
    """
    try:
        tool_callable: ToolFunction = runtime_state.tool_registry[step.tool_name]
    except KeyError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.REGISTRY_LOOKUP_ERROR,
            message=f"Tool not found in registry: {step.tool_name}",
            cause=error,
        ) from error

    kwargs: RuntimeValue = (
        interpret_expression(step.args, runtime_state) if step.args is not None else {}
    )
    if not isinstance(kwargs, dict):
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_CALL_OPERATION,
            message="Tool call arguments must evaluate to an object/dict.",
        )

    try:
        tool_result: RuntimeValue = tool_callable(**kwargs)
    except TypeError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_CALL_OPERATION,
            message=f"Invalid tool call arguments for: {step.tool_name}",
            cause=error,
        ) from error

    if isawaitable(tool_result):
        tool_result = await tool_result

    if step.binding_target:
        runtime_state.bindings[step.binding_target] = tool_result

    return StepExecutionResult.normal()


async def _interpret_if_step(
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
    selected_steps: Tuple[Step, ...] = (
        step.then_steps if condition_value else step.else_steps
    )
    return await interpret_step_tuple(selected_steps, runtime_state)


async def _interpret_for_each_step(
    step: ForEachStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a foreach step by iterating over the evaluated iterable
    expression.

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
    iterable_value: RuntimeValue = interpret_expression(step.iterable_expr, runtime_state)

    try:
        iterator = iter(iterable_value)
    except TypeError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_ITERATION_OPERATION,
            message="Foreach iterable expression did not produce an iterable value.",
            cause=error,
        ) from error

    for item in iterator:
        runtime_state.bindings[step.loop_var_name] = item
        result: StepExecutionResult = await interpret_step_tuple(
            step.body_steps,
            runtime_state,
        )
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


async def _interpret_llm_call_step(
    step: LlmCallStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute an LLM-call step, awaiting only when the invoked callable returns
    an awaitable.

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
    - Arguments are evaluated synchronously through the expression interpreter
      and passed as keyword arguments to the LLM callable.
    - If the LLM callable returns an awaitable, it is awaited before normal
      execution resumes.
    - If `step.binding_target` is set, the final LLM-call result is stored
      under that binding name in `runtime_state.bindings`.
    """
    try:
        llm_callable: LlmFunction = runtime_state.llm_registry[step.baml_func_name]
    except KeyError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.REGISTRY_LOOKUP_ERROR,
            message=f"LLM function not found in registry: {step.baml_func_name}",
            cause=error,
        ) from error

    kwargs: RuntimeValue = (
        interpret_expression(step.args, runtime_state) if step.args is not None else {}
    )
    if not isinstance(kwargs, dict):
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_CALL_OPERATION,
            message="LLM call arguments must evaluate to an object/dict.",
        )

    try:
        llm_result: RuntimeValue = llm_callable(**kwargs)
    except TypeError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_CALL_OPERATION,
            message=f"Invalid LLM call arguments for: {step.baml_func_name}",
            cause=error,
        ) from error

    if isawaitable(llm_result):
        llm_result = await llm_result

    if step.binding_target:
        runtime_state.bindings[step.binding_target] = llm_result

    return StepExecutionResult.normal()


async def _interpret_recursive_call_step(
    step: RecursiveCallStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a recursive-call step by asking an LLM callable to generate a child
    program, then executing that child program in a forked runtime state.

    Parameters
    ----------
    step : RecursiveCallStep
        Recursive-call step node to execute.
    runtime_state : RuntimeState
        Current parent runtime state used for argument evaluation, registry
        lookup, and optional result binding.

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
    ValueError
        When the resolved callable does not return a valid child `Program`.

    Notes
    -----
    - Arguments are evaluated synchronously through the expression interpreter
      and passed as keyword arguments to the LLM callable.
    - The LLM callable is expected to return a `Program` object, directly or
      via an awaitable.
    - Child execution occurs against a recursion-budget-aware forked runtime so
      child rebinding does not mutate the parent's bindings dictionary.
    - If `step.binding_target` is set, the child-program return value is stored
      under that binding name in `runtime_state.bindings`.
    """
    try:
        llm_callable: LlmFunction = runtime_state.llm_registry[step.baml_func_name]
    except KeyError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.REGISTRY_LOOKUP_ERROR,
            message=(
                "Recursive child-program generator not found in registry: "
                f"{step.baml_func_name}"
            ),
            cause=error,
        ) from error

    kwargs: RuntimeValue = (
        interpret_expression(step.args, runtime_state) if step.args is not None else {}
    )
    if not isinstance(kwargs, dict):
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_CALL_OPERATION,
            message="Recursive call arguments must evaluate to an object/dict.",
        )

    try:
        child_program_result = llm_callable(**kwargs)
    except TypeError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_CALL_OPERATION,
            message=(
                "Invalid recursive child-program call arguments for: "
                f"{step.baml_func_name}"
            ),
            cause=error,
        ) from error

    if isawaitable(child_program_result):
        child_program_result = await child_program_result

    if not isinstance(child_program_result, Program):
        raise RlmExecutionError(
            code=RlmErrorCode.INVALID_CALL_OPERATION,
            message=(
                "Recursive child-program generator must return a Program: "
                f"{step.baml_func_name}"
            ),
        )

    validate_program(child_program_result)

    child_runtime_state = runtime_state.register_recursive_call_and_fork_child()
    child_result = await interpret_step_tuple(
        steps=child_program_result.steps,
        runtime_state=child_runtime_state,
    )

    if step.binding_target:
        runtime_state.bindings[step.binding_target] = child_result.return_value

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


def _interpret_spawn_step(
    step: SpawnStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a spawn step by launching a sub-program as an asyncio task against
    a forked child runtime state.

    Parameters
    ----------
    step : SpawnStep
        Spawn-step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for task registration and child-runtime
        creation.

    Returns
    -------
    StepExecutionResult
        Non-returning result for normal execution.

    Raises
    ------
    RuntimeError
        When task creation fails inside the active asyncio event loop.

    Notes
    -----
    - The spawned sub-program is executed by `interpret_step_tuple` in a child
      runtime state created via `runtime_state.fork_child()`.
    - The created task handle is stored in `runtime_state.task_registry` under
      `step.binding_target`.
    - Spawn does not wait for task completion, synchronization is delegated to
      join steps.
    """
    try:
        runtime_state.task_registry[step.binding_target] = asyncio.create_task(
            interpret_step_tuple(
                steps=step.sub_program.steps,
                runtime_state=runtime_state.fork_child(),
            ),
            name=step.binding_target,
        )
    except RuntimeError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.TASK_SPAWN_ERROR,
            message=f"Failed to spawn task: {step.binding_target}",
            cause=error,
        ) from error

    return StepExecutionResult.normal()


async def _interpret_join_step(
    step: JoinStep,
    runtime_state: RuntimeState,
) -> StepExecutionResult:
    """
    Execute a join step by awaiting previously spawned task handles and
    optionally binding their return payloads.

    Parameters
    ----------
    step : JoinStep
        Join-step node to execute.
    runtime_state : RuntimeState
        Current runtime state used for task-handle resolution and optional
        result binding.

    Returns
    -------
    StepExecutionResult
        Non-returning result for normal execution.

    Raises
    ------
    KeyError
        When any task reference cannot be resolved from runtime bindings.
    TypeError
        When a resolved task reference is not awaitable as a task handle.

    Notes
    -----
    - Task references are resolved through the expression interpreter before
      awaiting them with `asyncio.gather`.
    - Each joined task is expected to resolve to a `StepExecutionResult` from a
      spawned sub-program.
    - If `step.binding_target` is set, the join result stores a list of joined
      sub-program return values in `runtime_state.bindings`.
    """
    tasks: List[TaskHandle] = []

    for task_ref in step.tasks_ref:
        task_handle: RuntimeValue = interpret_expression(task_ref, runtime_state)
        if not isinstance(task_handle, asyncio.Task):
            raise RlmExecutionError(
                code=RlmErrorCode.INVALID_CALL_OPERATION,
                message="Join step task references must resolve to task handles.",
            )
        tasks.append(task_handle)

    try:
        results: List[StepExecutionResult] = await asyncio.gather(*tasks)
    except asyncio.CancelledError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.TASK_JOIN_ERROR,
            message="Task join was cancelled.",
            cause=error,
        ) from error
    except RuntimeError as error:
        raise RlmExecutionError(
            code=RlmErrorCode.TASK_JOIN_ERROR,
            message="Task join failed due to runtime task scheduling error.",
            cause=error,
        ) from error

    if step.binding_target:
        runtime_state.bindings[step.binding_target] = [
            result.return_value for result in results
        ]

    return StepExecutionResult.normal()


async def interpret_step(
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
    - Recursive-call steps generate and execute child programs in forked child
      runtimes.
    - Spawn steps register background sub-program tasks, and join steps await
      them and optionally bind their collected return values.
    """
    try:
        match step:
            case ToolCallStep():
                return await _interpret_tool_call_step(step, runtime_state)
            case IfStep():
                return await _interpret_if_step(step, runtime_state)
            case ForEachStep():
                return await _interpret_for_each_step(step, runtime_state)
            case ReturnStep():
                return _interpret_return_step(step, runtime_state)
            case LlmCallStep():
                return await _interpret_llm_call_step(step, runtime_state)
            case RecursiveCallStep():
                return await _interpret_recursive_call_step(step, runtime_state)
            case AssignmentStep():
                return _interpret_assignment_step(step, runtime_state)
            case SpawnStep():
                return _interpret_spawn_step(step, runtime_state)
            case JoinStep():
                return await _interpret_join_step(step, runtime_state)
            case _:
                raise RlmExecutionError(
                    code=RlmErrorCode.UNSUPPORTED_STEP_NODE,
                    message=f"Unsupported step node: {type(step).__name__}",
                )
    except Exception as error:
        if isinstance(error, RlmRuntimeError):
            raise
        raise translate_exception(error, ErrorPhase.EXECUTION) from error


async def interpret_step_tuple(
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
      loop bodies, spawned sub-program bodies, and top-level program step
      tuples.
    - Sequence execution stops immediately when a nested return is
      encountered.
    - A spawned sub-program that returns will surface that return through its
      task result rather than directly through the parent sequence.
    """
    try:
        for step in steps:
            result = await interpret_step(step, runtime_state)
            if result.did_return:
                return result

        return StepExecutionResult.normal()
    except Exception as error:
        if isinstance(error, RlmRuntimeError):
            raise
        raise translate_exception(error, ErrorPhase.EXECUTION) from error
