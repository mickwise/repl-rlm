"""
Purpose
-------
Provide validation and execution helpers for experiment generation. This module
exists to keep public generator functions focused on sampling while centralizing
input validation and optional runtime-backed smoke execution.

Key behaviors
-------------
- Validates public integer generator arguments.
- Validates generated programs through the canonical runtime validator.
- Executes generated experiments through the real runtime using the
  deterministic rolling tool.
- Guards synchronous execution checks from running inside an active event loop.

Conventions
-----------
- Helpers in this module do not mutate repo-tracked state.
- Execution checking is intended only to prove that generated programs run
  successfully, not to capture expected outputs.

Downstream usage
----------------
The experiment generator imports these helpers to validate inputs, validate
generated programs, and optionally perform runtime-backed execution checks.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Tuple

from repl_rlm.repl.runtime.runtime import RuntimeState, create_runtime_state, execute_program
from repl_rlm.repl.steps.step_validator import validate_program
from repl_rlm.repl.steps.steps import Program
from repl_rlm.tools.rolling.rolling import roll

if TYPE_CHECKING:
    from repl_rlm.experiments.experiment_generator import GeneratedExperiment


def require_int(value: object, field_name: str) -> int:
    """
    Validate that a supplied generator argument is a non-bool integer.

    Parameters
    ----------
    value : object
        Value expected to be a non-bool integer.
    field_name : str
        Human-readable field name used in error messages.

    Returns
    -------
    int
        Validated integer value.

    Raises
    ------
    TypeError
        When the supplied value is not an integer or is a bool.

    Notes
    -----
    - This helper is used for public API argument validation and deterministic
      seed handling.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int.")
    return value


def validate_generated_program(program: Program) -> None:
    """
    Validate one generated program through the real program validator.

    Parameters
    ----------
    program : Program
        Generated DSL program to validate.

    Returns
    -------
    None
        This function returns nothing when validation succeeds.

    Raises
    ------
    RlmRuntimeError
        Native validation error raised by the existing runtime validator.

    Notes
    -----
    - This helper keeps validation logic local to the experiments package while
      still using the canonical validator implementation.
    """
    validate_program(program)


async def execute_generated_programs(
    experiments: Tuple["GeneratedExperiment", ...],
    tool_name: str,
) -> None:
    """
    Execute generated programs through the real runtime for smoke checking.

    Parameters
    ----------
    experiments : Tuple[GeneratedExperiment, ...]
        Generated experiments whose programs should be executed.
    tool_name : str
        Registered runtime tool name bound to the deterministic rolling tool.

    Returns
    -------
    None
        This coroutine returns nothing when all generated programs execute
        successfully.

    Raises
    ------
    Exception
        Propagates any execution failure raised by the existing runtime.

    Notes
    -----
    - The execution check is intentionally lightweight and does not store
      expected outputs in the experiment objects.
    """
    for experiment in experiments:
        runtime_state: RuntimeState = create_runtime_state(
            tool_registry={tool_name: roll},
            llm_registry={},
        )
        await execute_program(experiment.program, runtime_state)


def assert_no_running_event_loop() -> None:
    """
    Reject synchronous execution checking from inside an active event loop.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This function returns nothing when no loop is currently running.

    Raises
    ------
    RuntimeError
        When `execution_check=True` is used from inside an already-running
        event loop.

    Notes
    -----
    - The public API remains synchronous and uses `asyncio.run(...)` only when
      it is safe to do so.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return

    raise RuntimeError("execution_check=True cannot be used from an already-running event loop.")
