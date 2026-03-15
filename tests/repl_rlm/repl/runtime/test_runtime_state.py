"""
Purpose
-------
Exercise runtime-state behavior that underpins recursion, child execution, and
mutable bindings. This module exists to keep the runtime-state contract stable
for step execution and recursive subprograms.

Key behaviors
-------------
- Verifies child-state forking semantics for bindings, registries, and tasks.
- Verifies recursive child registration and enforcement of recursion budgets.

Conventions
-----------
- Tests focus on the public runtime-state methods rather than direct mutation
  of internal counters.
- Assertions prefer stable observable state over implementation details.

Downstream usage
----------------
CI runs this module to protect the runtime-state behavior consumed by the step
interpreter and top-level runtime entrypoints.
"""

import pytest

from repl_rlm.repl.errors import RlmErrorCode, RlmExecutionError
from repl_rlm.repl.runtime.config import RuntimeConfig
from repl_rlm.repl.runtime.runtime_state import RuntimeState


def test_fork_child_copies_bindings_and_clears_task_registry() -> None:
    """
    Fork a child runtime with isolated bindings and a fresh task table.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when child-state forking preserves the
        expected isolation and registry-sharing behavior.

    Raises
    ------
    AssertionError
        If the child runtime mutates parent bindings directly or inherits the
        parent task registry.

    Notes
    -----
    - Spawned subprograms rely on this isolation contract.
    """
    runtime_state = RuntimeState(tool_registry={"tool": lambda: None}, llm_registry={})
    runtime_state.bindings["value"] = 1

    child = runtime_state.fork_child()
    child.bindings["value"] = 2
    child.bindings["child_only"] = True

    assert runtime_state.bindings == {"value": 1}
    assert child.bindings == {"value": 2, "child_only": True}
    assert not child.task_registry
    assert child.tool_registry is runtime_state.tool_registry
    assert child.llm_registry is runtime_state.llm_registry


def test_register_recursive_call_and_fork_child_updates_depth_and_count() -> None:
    """
    Register a recursive child call and produce a deeper child runtime.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when recursive child registration increments
        the shared call count and child depth as expected.

    Raises
    ------
    AssertionError
        If recursion accounting or child-depth behavior regresses.

    Notes
    -----
    - Recursive-call accounting is a critical safety boundary for the runtime.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})

    child = runtime_state.register_recursive_call_and_fork_child()

    assert runtime_state.current_recursive_call_count == 1
    assert child.current_recursive_call_count == 1
    assert child.current_recursive_depth == 1
    assert runtime_state.current_recursive_depth == 0


@pytest.mark.parametrize(
    ("config", "expected_code"),
    [
        (
            RuntimeConfig(max_recursive_call_depth=0, max_recursive_calls=5),
            RlmErrorCode.RECURSION_DEPTH_EXCEEDED,
        ),
        (
            RuntimeConfig(max_recursive_call_depth=5, max_recursive_calls=0),
            RlmErrorCode.RECURSION_CALL_LIMIT_EXCEEDED,
        ),
    ],
)
def test_register_recursive_call_and_fork_child_enforces_limits(
    config: RuntimeConfig,
    expected_code: RlmErrorCode,
) -> None:
    """
    Enforce recursion depth and total-call limits before child execution.

    Parameters
    ----------
    config : RuntimeConfig
        Runtime policy configuration used to trigger one of the limit guards.
    expected_code : RlmErrorCode
        Native execution error code expected from the triggered limit.

    Returns
    -------
    None
        This test returns nothing when recursion-budget violations raise the
        expected native execution errors.

    Raises
    ------
    AssertionError
        If a recursion-budget guard fails to trigger or maps to the wrong code.

    Notes
    -----
    - Parameterization keeps both recursion-budget guards covered without
      duplicating setup.
    """
    runtime_state = RuntimeState(
        tool_registry={},
        llm_registry={},
        runtime_config=config,
    )

    with pytest.raises(RlmExecutionError) as excinfo:
        runtime_state.register_recursive_call_and_fork_child()

    assert excinfo.value.code is expected_code
