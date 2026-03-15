"""
Purpose
-------
Exercise the top-level runtime entrypoints that validate and execute programs.
This module exists to keep the public runtime API stable for callers that want
fresh-state execution and normalized failures.

Key behaviors
-------------
- Verifies runtime-state creation and binding preloading.
- Verifies successful program execution and phase-aware validation failures.
- Verifies prompt injection for fresh-state execution from user input.

Conventions
-----------
- Tests use small hand-built programs rather than mocking internal runtime
  helpers.
- Assertions focus on the returned execution summary and native errors.

Downstream usage
----------------
CI runs this module to guard the main execution entrypoints that adapters and
benchmark harnesses are expected to call.
"""

import pytest

from repl_rlm.repl.errors import RlmErrorCode, RlmValidationError
from repl_rlm.repl.expressions.expressions import Literal, Ref
from repl_rlm.repl.runtime.runtime import (
    create_runtime_state,
    execute_program,
    execute_program_from_prompt,
)
from repl_rlm.repl.steps.steps import AssignmentStep, Program, ReturnStep


def test_create_runtime_state_copies_initial_bindings() -> None:
    """
    Copy initial bindings into a new runtime state without aliasing the mapping.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when initial bindings are copied into the new
        runtime state.

    Raises
    ------
    AssertionError
        If later mutations to the caller's mapping leak into the runtime state.

    Notes
    -----
    - This keeps runtime initialization predictable for callers preparing
      prompt or corpus metadata.
    """
    initial_bindings = {"count": 1}

    runtime_state = create_runtime_state(
        tool_registry={},
        llm_registry={},
        initial_bindings=initial_bindings,
    )
    initial_bindings["count"] = 2

    assert runtime_state.bindings == {"count": 1}


@pytest.mark.asyncio
async def test_execute_program_returns_bindings_and_return_value() -> None:
    """
    Execute a valid program and return a stable execution summary.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when the runtime produces the expected return
        value and binding snapshot.

    Raises
    ------
    AssertionError
        If the execution summary does not reflect the executed program.

    Notes
    -----
    - This is the main success-path contract for callers that already manage
      runtime state themselves.
    """
    program = Program(
        steps=(
            AssignmentStep(value_expr=Literal(value="value"), binding_target="saved"),
            ReturnStep(value_expr=Ref(name="saved")),
        ),
        metadata={},
    )
    runtime_state = create_runtime_state(tool_registry={}, llm_registry={})

    result = await execute_program(program=program, runtime_state=runtime_state)

    assert result.did_return is True
    assert result.return_value == "value"
    assert result.bindings["saved"] == "value"
    assert result.active_task_names == ()


@pytest.mark.asyncio
async def test_execute_program_translates_validation_failures() -> None:
    """
    Translate structural program failures as validation errors before execution.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when invalid program structure surfaces as a
        native validation error.

    Raises
    ------
    AssertionError
        If structural validation failures are not normalized correctly.

    Notes
    -----
    - Phase-aware normalization is a key part of the runtime API.
    """
    program = Program(
        steps=(ReturnStep(value_expr=Literal(value="ok")),),
        metadata=[],
    )
    runtime_state = create_runtime_state(tool_registry={}, llm_registry={})

    with pytest.raises(RlmValidationError) as excinfo:
        await execute_program(program=program, runtime_state=runtime_state)

    assert excinfo.value.code is RlmErrorCode.VALIDATION_TYPE_ERROR


@pytest.mark.asyncio
async def test_execute_program_from_prompt_injects_prompt_binding() -> None:
    """
    Inject a prompt binding into a fresh runtime before execution.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when prompt-based execution exposes the
        prompt through the configured binding name.

    Raises
    ------
    AssertionError
        If the prompt binding is not injected correctly.

    Notes
    -----
    - Prompt injection is part of the public convenience API used by higher
      level planners.
    """
    program = Program(
        steps=(ReturnStep(value_expr=Ref(name="task_prompt")),),
        metadata={},
    )

    result = await execute_program_from_prompt(
        prompt="inspect this",
        program=program,
        tool_registry={},
        llm_registry={},
        prompt_binding_name="task_prompt",
    )

    assert result.return_value == "inspect this"
    assert result.bindings["task_prompt"] == "inspect this"
