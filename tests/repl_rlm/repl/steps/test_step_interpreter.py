"""
Purpose
-------
Exercise executable step interpretation for the REPL runtime. This module
exists to keep the operational semantics of tool calls, model calls, recursive
calls, loops, and concurrency stable.

Key behaviors
-------------
- Verifies deterministic and model-backed call execution.
- Verifies recursive child-program execution, return propagation, and
  spawn/join behavior.

Conventions
-----------
- Tests use small hand-built programs and registries instead of mocking the
  step interpreter internals.
- Assertions focus on stable runtime state and native execution outcomes.

Downstream usage
----------------
CI runs this module to guard the behavior-heavy execution paths that matter
most for real planner-driven programs.
"""

import pytest

from repl_rlm.repl.expressions.expressions import (
    ListExpr,
    Literal,
    ObjectExpr,
    Ref,
    TaskRef,
)
from repl_rlm.repl.runtime.runtime_state import RuntimeState
from repl_rlm.repl.steps.step_interpreter import interpret_step, interpret_step_tuple
from repl_rlm.repl.steps.steps import (
    AssignmentStep,
    ForEachStep,
    JoinStep,
    LlmCallStep,
    Program,
    RecursiveCallStep,
    ReturnStep,
    SpawnStep,
    ToolCallStep,
)


@pytest.mark.asyncio
async def test_interpret_step_executes_async_tool_calls_and_binds_result() -> None:
    """
    Execute an async tool call and bind the awaited result into runtime state.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when async tool-call execution stores the
        awaited result under the configured binding target.

    Raises
    ------
    AssertionError
        If async tool execution or result binding regresses.

    Notes
    -----
    - Awaitable tool support is part of the public runtime contract.
    """

    async def double(value: int) -> int:
        return value * 2

    runtime_state = RuntimeState(tool_registry={"double": double}, llm_registry={})
    step = ToolCallStep(
        tool_name="double",
        args=ObjectExpr(fields={"value": Literal(value=2)}),
        binding_target="result",
    )

    result = await interpret_step(step, runtime_state)

    assert result.did_return is False
    assert runtime_state.bindings["result"] == 4


@pytest.mark.asyncio
async def test_interpret_step_executes_llm_calls_and_binds_result() -> None:
    """
    Execute an async model-backed value call and bind its result.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when LLM-call execution stores the awaited
        value under the configured binding target.

    Raises
    ------
    AssertionError
        If LLM-call execution or result binding regresses.

    Notes
    -----
    - Plain model-backed value calls are distinct from recursive child-program
      generation and should remain covered separately.
    """

    async def answer(question: str) -> str:
        return f"answer:{question}"

    runtime_state = RuntimeState(tool_registry={}, llm_registry={"answer": answer})
    step = LlmCallStep(
        baml_func_name="answer",
        args=ObjectExpr(fields={"question": Literal(value="q")}),
        binding_target="result",
    )

    result = await interpret_step(step, runtime_state)

    assert result.did_return is False
    assert runtime_state.bindings["result"] == "answer:q"


@pytest.mark.asyncio
async def test_interpret_step_executes_recursive_child_programs_isolates_bindings() -> (
    None
):
    """
    Execute a recursive child program and bind only its return value in parent state.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when recursive child execution returns a
        value without leaking child-only bindings into the parent.

    Raises
    ------
    AssertionError
        If recursive child execution mutates parent bindings incorrectly or
        fails to bind the child return value.

    Notes
    -----
    - This covers one of the most important behavioral differences between a
      plain model call and a recursive child-program call.
    """

    def planner() -> Program:
        return Program(
            steps=(
                AssignmentStep(
                    value_expr=Literal(value="child"),
                    binding_target="child_only",
                ),
                ReturnStep(value_expr=Ref(name="seed")),
            ),
            metadata={},
        )

    runtime_state = RuntimeState(tool_registry={}, llm_registry={"planner": planner})
    runtime_state.bindings["seed"] = "parent-value"
    step = RecursiveCallStep(
        baml_func_name="planner",
        args=None,
        binding_target="child_result",
    )

    result = await interpret_step(step, runtime_state)

    assert result.did_return is False
    assert runtime_state.bindings["child_result"] == "parent-value"
    assert "child_only" not in runtime_state.bindings
    assert runtime_state.current_recursive_call_count == 1


@pytest.mark.asyncio
async def test_interpret_step_propagates_return_from_foreach_body() -> None:
    """
    Stop foreach execution when a nested body step returns.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when foreach execution propagates a nested
        return value immediately.

    Raises
    ------
    AssertionError
        If foreach execution ignores a nested return or propagates the wrong
        value.

    Notes
    -----
    - Early return propagation is critical for nested control-flow semantics.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    step = ForEachStep(
        iterable_expr=ListExpr(values=(Literal(value=1), Literal(value=2))),
        loop_var_name="item",
        body_steps=(ReturnStep(value_expr=Ref(name="item")),),
    )

    result = await interpret_step(step, runtime_state)

    assert result.did_return is True
    assert result.return_value == 1


@pytest.mark.asyncio
async def test_interpret_step_tuple_spawns_and_joins_subprograms() -> None:
    """
    Spawn child programs concurrently and join their returned results.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when spawn and join steps cooperate to
        collect subprogram return values.

    Raises
    ------
    AssertionError
        If spawned subprograms are not joined or their return payloads are not
        collected correctly.

    Notes
    -----
    - This covers the runtime's first-class concurrency surface.
    """
    runtime_state = RuntimeState(tool_registry={}, llm_registry={})
    program = (
        SpawnStep(
            binding_target="task_1",
            sub_program=Program(
                steps=(ReturnStep(value_expr=Literal(value="a")),),
                metadata={},
            ),
        ),
        SpawnStep(
            binding_target="task_2",
            sub_program=Program(
                steps=(ReturnStep(value_expr=Literal(value="b")),),
                metadata={},
            ),
        ),
        JoinStep(
            tasks_ref=(TaskRef(name="task_1"), TaskRef(name="task_2")),
            binding_target="joined",
        ),
    )

    result = await interpret_step_tuple(program, runtime_state)

    assert result.did_return is False
    assert runtime_state.bindings["joined"] == ["a", "b"]
