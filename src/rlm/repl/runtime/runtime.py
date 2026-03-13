"""
Purpose
-------
Provide the top-level runtime execution boundary for validated REPL DSL
programs. This module exists to initialize runtime state, inject initial
bindings such as the prompt, validate programs, execute them through the step
interpreter, and return a structured execution result using native translated
errors.

Key behaviors
-------------
- Builds runtime state objects from tool and LLM registries plus runtime
  policy config.
- Injects initial bindings, including the original user prompt when desired.
- Validates programs before any step execution begins.
- Executes validated programs asynchronously through the step interpreter.
- Translates raw validation and execution exceptions into native RLM errors
  before they propagate.

Conventions
-----------
- Structural validation happens before interpretation.
- Validation and execution errors are translated separately so the caller can
  distinguish malformed programs from runtime failures.
- Program execution returns a stable summary object containing return status,
  return value, bindings, and active task names.

Downstream usage
----------------
Planner-facing code should call `execute_program(...)` or
`execute_program_from_prompt(...)` and catch the translated native exceptions
from the runtime error module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from rlm.repl.runtime.runtime_state import (
    RuntimeState,
    RuntimeValue,
    Bindings,
    ToolRegistry,
    LlmRegistry,
)
from rlm.repl.steps.step_interpreter import interpret_step_tuple
from rlm.repl.steps.step_validator import validate_program
from rlm.repl.steps.steps import Program
from rlm.repl.errors import (
    ErrorPhase,
    translate_exception,
)
from rlm.repl.runtime.config import RuntimeConfig


@dataclass(frozen=True)
class ProgramExecutionResult:
    """
    Purpose
    -------
    Represent the top-level result of validating and executing one DSL
    program. This class exists to provide a stable execution summary for the
    caller after one program run completes successfully.

    Key behaviors
    -------------
    - Carries whether execution terminated via an explicit return.
    - Carries the returned runtime value, if one was produced.
    - Carries a snapshot of runtime bindings after execution completes.
    - Carries the names of any task handles still present in runtime state.

    Parameters
    ----------
    did_return : bool
        Whether program execution terminated through an explicit return step.
    return_value : RuntimeValue | None
        Returned runtime value, if the program produced one.
    bindings : Mapping[str, RuntimeValue]
        Snapshot of runtime bindings after execution completes.
    active_task_names : tuple[str, ...]
        Names of task handles still registered after execution completes.

    Attributes
    ----------
    did_return : bool
        Whether program execution terminated through an explicit return step.
    return_value : RuntimeValue | None
        Returned runtime value, if the program produced one.
    bindings : Mapping[str, RuntimeValue]
        Snapshot of runtime bindings after execution completes.
    active_task_names : tuple[str, ...]
        Names of task handles still registered after execution completes.

    Notes
    -----
    - This is a summary object for successful execution, not a control-flow
      carrier used by the step interpreter.
    - Bindings are returned as a snapshot so callers can inspect them without
      mutating the live runtime state accidentally.
    """
    did_return: bool
    return_value: RuntimeValue | None
    bindings: Mapping[str, RuntimeValue]
    active_task_names: Tuple[str, ...]


def create_runtime_state(
    tool_registry: ToolRegistry,
    llm_registry: LlmRegistry,
    initial_bindings: Bindings | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> RuntimeState:
    """
    Create a runtime state with optional initial bindings.

    Parameters
    ----------
    tool_registry : ToolRegistry
        Mapping from tool names to concrete tool callables.
    llm_registry : LlmRegistry
        Mapping from LLM function names to concrete LLM callables.
    initial_bindings : Bindings | None
        Optional initial runtime bindings to preload into the new runtime
        state.
    runtime_config : RuntimeConfig | None
        Optional runtime policy config controlling recursion budgets.

    Returns
    -------
    RuntimeState
        Newly created runtime state ready for validation and execution.

    Raises
    ------
    None

    Notes
    -----
    - The returned runtime state starts with an empty task registry.
    - Initial bindings are copied into the runtime state so callers can keep
      their original mapping unchanged.
    """
    runtime_state = RuntimeState(
        tool_registry=tool_registry,
        llm_registry=llm_registry,
        runtime_config=runtime_config,
    )
    if initial_bindings is not None:
        runtime_state.bindings.update(dict(initial_bindings))
    return runtime_state


async def execute_program(
    program: Program,
    runtime_state: RuntimeState,
) -> ProgramExecutionResult:
    """
    Validate and execute a DSL program against an existing runtime state.

    Parameters
    ----------
    program : Program
        Program AST to validate and execute.
    runtime_state : RuntimeState
        Runtime state against which the program should be executed.

    Returns
    -------
    ProgramExecutionResult
        Structured summary of successful program execution, including return
        status, return value, binding snapshot, and currently registered task
        names.

    Raises
    ------
    RlmRuntimeError
        Native translated validation or execution error produced by the runtime
        error translation layer.

    Notes
    -----
    - Validation and execution are wrapped separately so native error
      translation can preserve the correct phase.
    """
    try:
        validate_program(program)
    except Exception as error:
        raise translate_exception(error, phase=ErrorPhase.VALIDATION) from error

    try:
        step_result = await interpret_step_tuple(
            steps=program.steps,
            runtime_state=runtime_state,
        )
    except Exception as error:
        raise translate_exception(error, phase=ErrorPhase.EXECUTION) from error

    return ProgramExecutionResult(
        did_return=step_result.did_return,
        return_value=step_result.return_value,
        bindings=dict(runtime_state.bindings),
        active_task_names=tuple(runtime_state.task_registry.keys()),
    )


async def execute_program_from_prompt(
    prompt: str,
    program: Program,
    tool_registry: ToolRegistry,
    llm_registry: LlmRegistry,
    prompt_binding_name: str = "prompt",
    extra_bindings: Bindings | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> ProgramExecutionResult:
    """
    Create a fresh runtime state, inject the prompt as a binding, and execute
    one DSL program.

    Parameters
    ----------
    prompt : str
        Original user prompt or task description to preload into runtime state.
    program : Program
        Program AST to validate and execute.
    tool_registry : ToolRegistry
        Mapping from tool names to concrete tool callables.
    llm_registry : LlmRegistry
        Mapping from LLM function names to concrete LLM callables.
    prompt_binding_name : str
        Binding name under which the prompt should be stored in runtime state.
    extra_bindings : Bindings | None
        Optional additional bindings to preload alongside the prompt.
    runtime_config : RuntimeConfig | None
        Optional runtime policy config controlling recursion budgets.

    Returns
    -------
    ProgramExecutionResult
        Structured summary of successful program execution for the newly
        created runtime state.

    Raises
    ------
    RlmRuntimeError
        Native translated validation or execution error produced by the runtime
        error translation layer.

    Notes
    -----
    - The prompt is injected as a normal binding so programs can reference it
      through the bindings environment.
    """
    initial_bindings: Bindings = dict(extra_bindings) if extra_bindings is not None else {}
    initial_bindings[prompt_binding_name] = prompt

    runtime_state = create_runtime_state(
        tool_registry=tool_registry,
        llm_registry=llm_registry,
        initial_bindings=initial_bindings,
        runtime_config=runtime_config,
    )

    return await execute_program(program=program, runtime_state=runtime_state)
