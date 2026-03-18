"""
Purpose
-------
Expose the public runtime API for validated REPL program execution. This module
exists to provide one package-level import surface for runtime config/state
types and the top-level execution entrypoints.

Key behaviors
-------------
- Re-exports runtime config and runtime-state types lazily.
- Re-exports `create_runtime_state`, `execute_program`, and
  `execute_program_from_prompt` lazily.
- Re-exports `ProgramExecutionResult` lazily for callers that inspect
  successful execution output.

Conventions
-----------
- This package-level surface is intended for external callers and tests.
- Symbols are resolved lazily through `__getattr__` so deep internal imports do
  not pay for heavy package-level imports.

Downstream usage
----------------
Callers may import runtime config/state types and execution helpers directly
from `repl_rlm.repl.runtime`.
"""

from importlib import import_module
from typing import Dict, List, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "Bindings": ("repl_rlm.repl.runtime.runtime_state", "Bindings"),
    "LlmFunction": ("repl_rlm.repl.runtime.runtime_state", "LlmFunction"),
    "LlmRegistry": ("repl_rlm.repl.runtime.runtime_state", "LlmRegistry"),
    "ProgramExecutionResult": ("repl_rlm.repl.runtime.runtime", "ProgramExecutionResult"),
    "RuntimeConfig": ("repl_rlm.repl.runtime.config", "RuntimeConfig"),
    "RuntimeState": ("repl_rlm.repl.runtime.runtime_state", "RuntimeState"),
    "RuntimeValue": ("repl_rlm.repl.runtime.runtime_state", "RuntimeValue"),
    "TaskHandle": ("repl_rlm.repl.runtime.runtime_state", "TaskHandle"),
    "ToolFunction": ("repl_rlm.repl.runtime.runtime_state", "ToolFunction"),
    "ToolRegistry": ("repl_rlm.repl.runtime.runtime_state", "ToolRegistry"),
    "create_runtime_state": ("repl_rlm.repl.runtime.runtime", "create_runtime_state"),
    "execute_program": ("repl_rlm.repl.runtime.runtime", "execute_program"),
    "execute_program_from_prompt": (
        "repl_rlm.repl.runtime.runtime",
        "execute_program_from_prompt",
    ),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str) -> object:
    """
    Resolve public runtime-package exports lazily.

    Parameters
    ----------
    name : str
        Public attribute name requested from the package.

    Returns
    -------
    object
        Exported object resolved from the underlying implementation module.

    Raises
    ------
    AttributeError
        When the requested name is not part of the public package surface.

    Notes
    -----
    - Lazy resolution avoids import cycles when runtime internals import one
      another during startup.
    """
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from error

    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> List[str]:
    """
    Return the public runtime-package attribute names.

    Parameters
    ----------
    None

    Returns
    -------
    list[str]
        Sorted package attribute names including the lazy public exports.

    Raises
    ------
    None

    Notes
    -----
    - This keeps interactive discovery aligned with the lazy `__all__`
      surface.
    """
    return sorted(list(globals().keys()) + __all__)
