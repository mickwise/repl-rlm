"""
Purpose
-------
Expose the public deterministic rolling-tool API. This module exists to provide
one package-level import surface for the rolling tool callable, async wrapper,
and the small set of structured rolling types.

Key behaviors
-------------
- Re-exports `roll` and `roll_async`.
- Re-exports `RollMode`, `DiceTerm`, and `RollPlan`.
- Keeps callers from needing to know the concrete module path for the rolling
  tool implementation.

Conventions
-----------
- This package-level surface is intended for external callers and tests.
- The deterministic execution implementation remains defined in `rolling.py`.

Downstream usage
----------------
Callers may import the rolling tool surface directly from
`repl_rlm.tools.rolling`.
"""

from repl_rlm.tools.rolling.rolling import DiceTerm, RollMode, RollPlan, roll, roll_async

__all__ = [
    "DiceTerm",
    "RollMode",
    "RollPlan",
    "roll",
    "roll_async",
]
