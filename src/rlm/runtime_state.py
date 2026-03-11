"""
Purpose
-------
Define the runtime state structures used during AST interpretation and program
execution. This module exists to centralize mutable interpreter state outside
the AST itself.

Key behaviors
-------------
- Defines the recursive runtime value type produced by expression evaluation.
- Defines the bindings mapping shape used for name resolution.
- Defines the runtime state container that stores current bindings.

Conventions
-----------
- Runtime state is distinct from AST structure and should hold evaluated values
  only.
- Bindings are keyed by DSL reference names and map to concrete runtime values.
- Runtime values may be atomic values, nested lists, or nested dictionaries.

Downstream usage
----------------
Expression and step interpreters should consume `RuntimeState` when resolving
references and storing evaluated values. Higher-level runtime loops should own
and mutate a single `RuntimeState` instance during execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias, Dict

from rlm.rlm_ast import AtomicType

RuntimeValue: TypeAlias = (
    AtomicType | list["RuntimeValue"] | dict[str, "RuntimeValue"]
)
Bindings: TypeAlias = Dict[str, RuntimeValue]


@dataclass
class RuntimeState:
    """
    Purpose
    -------
    Represent the mutable runtime environment used while interpreting DSL
    programs. This class exists to store the current set of bound runtime
    values available to reference expressions and step execution.

    Key behaviors
    -------------
    - Stores the current bindings mapping used for reference resolution.
    - Provides a single mutable state object that can be threaded through
      interpreter passes.

    Parameters
    ----------
    bindings : Bindings
        Mapping from binding names to concrete runtime values.

    Attributes
    ----------
    bindings : Bindings
        Mapping from binding names to concrete runtime values.

    Notes
    -----
    - Runtime state is intentionally separate from the AST, which remains
      immutable.
    - This class does not enforce scope or rebinding rules by itself.
    """
    bindings: Bindings = field(default_factory=dict)
