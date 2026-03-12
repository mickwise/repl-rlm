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
  registries, and spawned task handles.
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

from rlm.repl.expressions.expressions import AtomicType

RuntimeValue: TypeAlias = (
    AtomicType | list["RuntimeValue"] | dict[str, "RuntimeValue"]
)
Bindings: TypeAlias = Dict[str, RuntimeValue]

TaskHandle: TypeAlias = Task["StepExecutionResult"]
ToolFunction: TypeAlias = Callable[..., RuntimeValue]
LlmFunction: TypeAlias = Callable[..., RuntimeValue]
ToolRegistry: TypeAlias = Dict[str, ToolFunction]
LlmRegistry: TypeAlias = Dict[str, LlmFunction]
TaskRegistry: TypeAlias = Dict[str, TaskHandle]

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
      nodes.
    - Stores the active task registry used for first-class concurrency features.
    - Provides a fork operation for constructing isolated child runtime states.

    Parameters
    ----------
    tool_registry : ToolRegistry
        Mapping from tool names to concrete Python callables.
    llm_registry : LlmRegistry
        Mapping from LLM function names to concrete Python callables.

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

    Notes
    -----
    - Runtime state is intentionally separate from the AST, which remains
      immutable.
    - Child runtime states should share callable registries but receive copied
      bindings and a fresh task registry.
    - This class does not enforce scope, rebinding rules, or registry completeness
      by itself.
    """

    def __init__(self, tool_registry: ToolRegistry, llm_registry: LlmRegistry) -> None:
        self.bindings: Bindings = {}
        self.tool_registry: ToolRegistry = tool_registry
        self.llm_registry: LlmRegistry = llm_registry
        self.task_registry: TaskRegistry = {}


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
            receives a shallow copy of the parent's bindings, and starts with an empty
            task registry.

        Raises
        ------
        None

        Notes
        -----
        - Bindings are shallow-copied so child rebinding does not mutate the parent
          bindings dictionary.
        - Tool and LLM registries are shared because they are treated as read-only
          capability tables.
        - The child task registry starts empty so spawned child execution does not
          inherit the parent's active task table.
        """
        child: RuntimeState =  RuntimeState(self.tool_registry, self.llm_registry)
        child.bindings = dict(self.bindings)
        return child
