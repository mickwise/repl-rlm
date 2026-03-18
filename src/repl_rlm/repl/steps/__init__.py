"""
Purpose
-------
Expose the public step-layer API for the REPL runtime. This module exists to
provide one package-level import surface for step AST nodes plus the step and
program validation/interpreter entrypoints.

Key behaviors
-------------
- Re-exports the top-level `Program` node and concrete step node classes
  lazily.
- Re-exports `validate_step`, `validate_program`, `interpret_step`, and
  `interpret_step_tuple` lazily.
- Keeps callers from needing to know the internal file split between AST,
  validator, and interpreter modules while avoiding eager import cycles.

Conventions
-----------
- This package-level surface is intended for external callers and tests.
- Symbols are resolved lazily through `__getattr__` so deep internal imports do
  not pay for heavy package-level imports.

Downstream usage
----------------
Callers may import program/step nodes and step helpers directly from
`repl_rlm.repl.steps`.
"""

from importlib import import_module
from typing import Dict, List, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "AssignmentStep": ("repl_rlm.repl.steps.steps", "AssignmentStep"),
    "ForEachStep": ("repl_rlm.repl.steps.steps", "ForEachStep"),
    "IfStep": ("repl_rlm.repl.steps.steps", "IfStep"),
    "JoinStep": ("repl_rlm.repl.steps.steps", "JoinStep"),
    "LlmCallStep": ("repl_rlm.repl.steps.steps", "LlmCallStep"),
    "Program": ("repl_rlm.repl.steps.steps", "Program"),
    "RecursiveCallStep": ("repl_rlm.repl.steps.steps", "RecursiveCallStep"),
    "ReturnStep": ("repl_rlm.repl.steps.steps", "ReturnStep"),
    "SpawnStep": ("repl_rlm.repl.steps.steps", "SpawnStep"),
    "Step": ("repl_rlm.repl.steps.steps", "Step"),
    "ToolCallStep": ("repl_rlm.repl.steps.steps", "ToolCallStep"),
    "interpret_step": ("repl_rlm.repl.steps.step_interpreter", "interpret_step"),
    "interpret_step_tuple": (
        "repl_rlm.repl.steps.step_interpreter",
        "interpret_step_tuple",
    ),
    "validate_program": ("repl_rlm.repl.steps.step_validator", "validate_program"),
    "validate_step": ("repl_rlm.repl.steps.step_validator", "validate_step"),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str) -> object:
    """
    Resolve public steps-package exports lazily.

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
    - Lazy resolution avoids import cycles when runtime modules import step
      internals during startup.
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
    Return the public steps-package attribute names.

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
