"""
Purpose
-------
Define the runtime state structures used during AST interpretation and program
execution. This module exists to centralize mutable interpreter state, callable
registries, and step-execution control-flow results outside the AST itself.

Key behaviors
-------------
- Defines the recursive runtime value type produced by expression evaluation.
- Defines the bindings mapping shape used for name resolution.
- Defines tool and LLM callable registry shapes used during step execution.
- Defines the runtime state container that stores current bindings and
  executable registries.
- Defines the step-execution result type used to propagate return control flow.

Conventions
-----------
- Runtime state is distinct from AST structure and should hold evaluated values
  and executable registries only.
- Bindings are keyed by DSL reference names and map to concrete runtime values.
- Tool and LLM registries are keyed by symbolic names from AST step nodes.
- Runtime values may be atomic values, nested lists, or nested dictionaries.

Downstream usage
----------------
Expression and step interpreters should consume `RuntimeState` when resolving
references, invoking tools and LLM functions, and storing evaluated values.
Higher-level runtime loops should own and mutate a single `RuntimeState`
instance during execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias, Dict, Callable

from rlm.repl.expressions.expressions import AtomicType

RuntimeValue: TypeAlias = (
    AtomicType | list["RuntimeValue"] | dict[str, "RuntimeValue"]
)
Bindings: TypeAlias = Dict[str, RuntimeValue]

ToolFunction: TypeAlias = Callable[..., RuntimeValue]
LlmFunction: TypeAlias = Callable[..., RuntimeValue]
ToolRegistry: TypeAlias = Dict[str, ToolFunction]
LlmRegistry: TypeAlias = Dict[str, LlmFunction]


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


@dataclass
class RuntimeState:
    """
    Purpose
    -------
    Represent the mutable runtime environment used while interpreting DSL
    programs. This class exists to store the current bindings and executable
    registries available to reference expressions and step execution.

    Key behaviors
    -------------
    - Stores the current bindings mapping used for reference resolution.
    - Stores the registered tool callables available to tool-call steps.
    - Stores the registered LLM callables available to LLM-call steps.
    - Provides a single mutable state object that can be threaded through
      interpreter passes.

    Parameters
    ----------
    bindings : Bindings
        Mapping from binding names to concrete runtime values.
    tool_registry : ToolRegistry
        Mapping from tool names to concrete Python callables.
    llm_registry : LlmRegistry
        Mapping from LLM function names to concrete Python callables.

    Attributes
    ----------
    bindings : Bindings
        Mapping from binding names to concrete runtime values.
    tool_registry : ToolRegistry
        Mapping from tool names to concrete Python callables.
    llm_registry : LlmRegistry
        Mapping from LLM function names to concrete Python callables.

    Notes
    -----
    - Runtime state is intentionally separate from the AST, which remains
      immutable.
    - This class does not enforce scope, rebinding rules, or registry
      completeness by itself.
    """
    bindings: Bindings = field(default_factory=dict)
    tool_registry: ToolRegistry = field(default_factory=dict)
    llm_registry: LlmRegistry = field(default_factory=dict)
