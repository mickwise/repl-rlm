"""
Purpose
-------
Expose the public expression-layer API for the REPL runtime. This module exists
to provide one package-level import surface for expression AST nodes, operator
enums, and the expression validation and interpretation entrypoints.

Key behaviors
-------------
- Re-exports the expression AST node classes and operator enums lazily.
- Re-exports `validate_expression` and `interpret_expression` lazily.
- Keeps callers from needing to know the internal file split between AST,
  validator, and interpreter modules while avoiding eager import cycles.

Conventions
-----------
- This package-level surface is intended for external callers and tests.
- Symbols are resolved lazily through `__getattr__` so deep internal imports do
  not pay for heavy package-level imports.

Downstream usage
----------------
Callers may import expression nodes and expression helpers directly from
`repl_rlm.repl.expressions`.
"""

from importlib import import_module
from typing import Dict, List, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "AlgebraicExpr": ("repl_rlm.repl.expressions.expressions", "AlgebraicExpr"),
    "AlgebraicOperator": ("repl_rlm.repl.expressions.expressions", "AlgebraicOperator"),
    "AtomicType": ("repl_rlm.repl.expressions.expressions", "AtomicType"),
    "ComparisonExpr": ("repl_rlm.repl.expressions.expressions", "ComparisonExpr"),
    "ComparisonOperator": ("repl_rlm.repl.expressions.expressions", "ComparisonOperator"),
    "Expr": ("repl_rlm.repl.expressions.expressions", "Expr"),
    "FieldAccessExpr": ("repl_rlm.repl.expressions.expressions", "FieldAccessExpr"),
    "ListExpr": ("repl_rlm.repl.expressions.expressions", "ListExpr"),
    "ListIndexExpr": ("repl_rlm.repl.expressions.expressions", "ListIndexExpr"),
    "Literal": ("repl_rlm.repl.expressions.expressions", "Literal"),
    "LogicalExpr": ("repl_rlm.repl.expressions.expressions", "LogicalExpr"),
    "LogicalOperator": ("repl_rlm.repl.expressions.expressions", "LogicalOperator"),
    "ObjectExpr": ("repl_rlm.repl.expressions.expressions", "ObjectExpr"),
    "Ref": ("repl_rlm.repl.expressions.expressions", "Ref"),
    "TaskRef": ("repl_rlm.repl.expressions.expressions", "TaskRef"),
    "UnaryExpr": ("repl_rlm.repl.expressions.expressions", "UnaryExpr"),
    "UnaryOperator": ("repl_rlm.repl.expressions.expressions", "UnaryOperator"),
    "interpret_expression": (
        "repl_rlm.repl.expressions.expression_interpreter",
        "interpret_expression",
    ),
    "validate_expression": (
        "repl_rlm.repl.expressions.expression_validator",
        "validate_expression",
    ),
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name: str) -> object:
    """
    Resolve public expression-package exports lazily.

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
    - Lazy resolution avoids import cycles when deep runtime modules import
      each other during startup.
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
    Return the public expression-package attribute names.

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
