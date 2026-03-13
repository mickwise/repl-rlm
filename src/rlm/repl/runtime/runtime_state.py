"""
Purpose
-------
Define the runtime state structures used during AST interpretation and program
execution. This module exists to centralize mutable interpreter state,
callable registries, task tracking, and step-execution control-flow results
outside the AST itself.

Key behaviors
-------------
- Defines the recursive runtime value type produced by expression evaluation.
- Defines bindings, tool-registry, LLM-registry, and task-registry shapes used
  during runtime execution.
- Defines the runtime state container that stores current bindings, callable
  registries, spawned task handles, and recursion-budget counters.
- Defines the step-execution result type used to propagate return control flow.

Conventions
-----------
- Runtime state is distinct from AST structure and should hold evaluated values,
  registries, and task bookkeeping only.
- Bindings are keyed by DSL reference names and map to concrete runtime values.
- Tool and LLM registries are keyed by symbolic names from AST step nodes.
- Task registries are keyed by runtime binding names that store spawned task
  handles.
- Runtime values may be atomic values, nested lists, or nested dictionaries.
- Runtime values may also include task handles when task references are
  interpreted.
- LLM registry callables may produce plain runtime values or generated child
  programs depending on the calling step semantics.
- Recursion-budget config and counters live on runtime state so child runtime
  creation can inherit the current recursive execution position.

Downstream usage
----------------
Expression and step interpreters should consume `RuntimeState` when resolving
references, invoking tools and LLM functions, storing evaluated values, and
tracking spawned tasks. Higher-level runtime loops should own and mutate a
single `RuntimeState` instance during execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, Dict, Callable
from asyncio import Task

from rlm.repl.errors import RlmErrorCode, RlmExecutionError
from rlm.repl.expressions.expressions import AtomicType
from rlm.repl.runtime.config import RuntimeConfig
from rlm.repl.steps.steps import Program

TaskHandle: TypeAlias = Task["StepExecutionResult"]
RuntimeValue: TypeAlias = (
    AtomicType | list["RuntimeValue"] | dict[str, "RuntimeValue"] | TaskHandle
)
LlmResult: TypeAlias = RuntimeValue | Program
Bindings: TypeAlias = Dict[str, RuntimeValue]
ToolFunction: TypeAlias = Callable[..., RuntimeValue]
LlmFunction: TypeAlias = Callable[..., LlmResult]
ToolRegistry: TypeAlias = Dict[str, ToolFunction]
LlmRegistry: TypeAlias = Dict[str, LlmFunction]
TaskRegistry: TypeAlias = Dict[str, TaskHandle]

@dataclass
class RecursiveCallCounter:
    """
    Purpose
    -------
    Represent the shared recursive-call counter for one runtime lineage. This
    class exists to let parent and child runtime states observe the same total
    recursive-call count while keeping recursive depth runtime-local.

    Key behaviors
    -------------
    - Stores the total recursive-call count observed across a runtime lineage.
    - Is shared by forked child runtime states.

    Parameters
    ----------
    count : int
        Current total recursive-call count.

    Attributes
    ----------
    count : int
        Current total recursive-call count.
    """

    count: int = 0


@dataclass(frozen=True)
class StepExecutionResult:
    """
    Purpose
    -------
    Represent the result of executing a single step or step sequence. This
    class exists to distinguish normal execution from propagated return
    control flow.

    Key behaviors
    -------------
    - Carries a flag indicating whether execution encountered a return.
    - Carries the runtime value associated with a propagated return.
    - Provides convenience constructors for normal and returning results.

    Parameters
    ----------
    did_return : bool
        Whether execution encountered a return that should stop surrounding
        execution.
    return_value : RuntimeValue | None
        Runtime value associated with the propagated return, if any.

    Attributes
    ----------
    did_return : bool
        Whether execution encountered a return that should stop surrounding
        execution.
    return_value : RuntimeValue | None
        Runtime value associated with the propagated return, if any.

    Notes
    -----
    - Non-returning steps should use `did_return=False`.
    - This class is a control-flow carrier, not a general-purpose step output
      container.
    """

    did_return: bool
    return_value: RuntimeValue | None

    @classmethod
    def normal(cls) -> "StepExecutionResult":
        """
        Construct a non-returning step-execution result.

        Parameters
        ----------
        None

        Returns
        -------
        StepExecutionResult
            Result indicating normal execution with no propagated return.

        Raises
        ------
        None

        Notes
        -----
        - This constructor is used for steps that mutate state or perform calls
          without terminating execution.
        """
        return cls(did_return=False, return_value=None)

    @classmethod
    def with_return(cls, return_value: RuntimeValue) -> "StepExecutionResult":
        """
        Construct a returning step-execution result.

        Parameters
        ----------
        return_value : RuntimeValue
            Runtime value to propagate upward as the result of a return step.

        Returns
        -------
        StepExecutionResult
            Result indicating that execution should terminate and propagate the
            supplied return value.

        Raises
        ------
        None

        Notes
        -----
        - This constructor is used by return-step execution and by callers
          propagating nested return results upward.
        """
        return cls(did_return=True, return_value=return_value)


class RuntimeState:
    """
    Purpose
    -------
    Represent the mutable runtime environment used while interpreting DSL
    programs. This class exists to store the current bindings, callable
    registries, and spawned-task handles available during execution.

    Key behaviors
    -------------
    - Stores the current bindings mapping used for reference resolution and
      assignment.
    - Stores the registered tool and LLM callables available to executable step
      nodes, including plain LLM-value calls and recursive child-program
      generators.
    - Stores the active task registry used for first-class concurrency features.
    - Stores current recursive depth and recursive-call count.
    - Provides a fork operation for constructing isolated child runtime states.

    Parameters
    ----------
    tool_registry : ToolRegistry
        Mapping from tool names to concrete Python callables.
    llm_registry : LlmRegistry
        Mapping from LLM function names to concrete Python callables.
    runtime_config : RuntimeConfig | None
        Optional runtime policy config. Defaults to `RuntimeConfig()`.

    Attributes
    ----------
    bindings : Bindings
        Mapping from binding names to concrete runtime values currently visible in
        this runtime state.
    tool_registry : ToolRegistry
        Mapping from tool names to concrete Python callables shared by this
        runtime state.
    llm_registry : LlmRegistry
        Mapping from LLM function names to concrete Python callables shared by
        this runtime state.
    task_registry : TaskRegistry
        Mapping from task-handle binding names to spawned async task handles owned
        by this runtime state.
    runtime_config : RuntimeConfig
        Runtime policy config that constrains recursive child-program
        execution.
    current_recursive_depth : int
        Current recursive child-program depth for this runtime state.
    recursive_call_counter : RecursiveCallCounter
        Shared total recursive-call counter for this runtime lineage.

    Notes
    -----
    - Runtime state is intentionally separate from the AST, which remains
      immutable.
    - Child runtime states should share callable registries but receive copied
      bindings, copied recursion counters, and a fresh task registry.
    - This class does not enforce scope, rebinding rules, or registry completeness
      by itself.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_registry: LlmRegistry,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:
        self.bindings: Bindings = {}
        self.tool_registry: ToolRegistry = tool_registry
        self.llm_registry: LlmRegistry = llm_registry
        self.task_registry: TaskRegistry = {}
        self.runtime_config: RuntimeConfig = (
            runtime_config if runtime_config is not None else RuntimeConfig()
        )
        self.current_recursive_depth: int = 0
        self.recursive_call_counter: RecursiveCallCounter = RecursiveCallCounter()


    def fork_child(self) -> RuntimeState:
        """
        Create a child runtime state for spawned concurrent execution.

        Parameters
        ----------
        None

        Returns
        -------
        RuntimeState
            A new runtime state that shares tool and LLM registries with the parent,
            receives a shallow copy of the parent's bindings and recursion
            counters, and starts with an empty task registry.

        Raises
        ------
        None

        Notes
        -----
        - Bindings are shallow-copied so child rebinding does not mutate the parent
          bindings dictionary.
        - Tool and LLM registries are shared because they are treated as read-only
          capability tables.
        - Recursion counters are copied so child execution inherits the current
          recursive execution position.
        - The child task registry starts empty so spawned child execution does not
          inherit the parent's active task table.
        """
        child: RuntimeState = RuntimeState(
            self.tool_registry,
            self.llm_registry,
            runtime_config=self.runtime_config,
        )
        child.bindings = dict(self.bindings)
        child.current_recursive_depth = self.current_recursive_depth
        child.recursive_call_counter = self.recursive_call_counter
        return child

    @property
    def current_recursive_call_count(self) -> int:
        """
        Return the current total recursive-call count for this runtime
        lineage.
        """
        return self.recursive_call_counter.count

    def register_recursive_call_and_fork_child(self) -> RuntimeState:
        """
        Register one recursive child-program call and fork a child runtime
        state for it.

        Parameters
        ----------
        None

        Returns
        -------
        RuntimeState
            Child runtime state whose recursive depth is one greater than the
            parent and whose recursive-call count matches the parent's
            incremented count.

        Raises
        ------
        RlmExecutionError
            When the configured maximum recursive depth or total recursive-call
            count would be exceeded.

        Notes
        -----
        - The parent runtime's recursive depth is unchanged.
        - The parent runtime's recursive-call count is incremented because the
          recursive call has been issued from the parent.
        - The child inherits the incremented call count and incremented depth.
        """
        if self.current_recursive_depth >= self.runtime_config.max_recursive_call_depth:
            raise RlmExecutionError(
                code=RlmErrorCode.RECURSION_DEPTH_EXCEEDED,
                message=(
                    "Recursive call depth limit exceeded: "
                    f"{self.current_recursive_depth} >= "
                    f"{self.runtime_config.max_recursive_call_depth}"
                ),
            )

        if self.current_recursive_call_count >= self.runtime_config.max_recursive_calls:
            raise RlmExecutionError(
                code=RlmErrorCode.RECURSION_CALL_LIMIT_EXCEEDED,
                message=(
                    "Recursive call count limit exceeded: "
                    f"{self.current_recursive_call_count} >= "
                    f"{self.runtime_config.max_recursive_calls}"
                ),
            )

        self.recursive_call_counter.count += 1
        child = self.fork_child()
        child.current_recursive_depth = self.current_recursive_depth + 1
        return child
