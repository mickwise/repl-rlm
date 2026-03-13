"""
Purpose
-------
Define runtime configuration for REPL execution policy. This module exists to
centralize recursion-budget settings that constrain recursive child-program
execution.

Key behaviors
-------------
- Defines default global recursion-budget limits for runtime execution.
- Provides one immutable config object that can be attached to `RuntimeState`.
- Keeps recursion-depth and recursive-call-count policy out of interpreter
  control-flow code.

Conventions
-----------
- Limits apply to recursive child-program calls only, not to ordinary LLM
  value calls or spawned deterministic sub-programs.
- Depth is zero-based at the root runtime state.
- Total recursive-call count is incremented each time a recursive child-program
  call is attempted successfully.

Downstream usage
----------------
Runtime creation helpers should construct or accept `RuntimeConfig` and attach
it to `RuntimeState`. Recursive-call execution should consult these limits
before creating a child runtime.
"""
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MAX_RECURSIVE_CALL_DEPTH = 4
DEFAULT_MAX_RECURSIVE_CALLS = 32


@dataclass(frozen=True)
class RuntimeConfig:
    """
    Purpose
    -------
    Represent immutable runtime policy limits for REPL execution. This class
    exists to carry recursion-budget settings through runtime creation and
    child-runtime forking.

    Key behaviors
    -------------
    - Stores the maximum allowed recursive child-program depth.
    - Stores the maximum allowed total recursive child-program call count.

    Parameters
    ----------
    max_recursive_call_depth : int
        Maximum allowed recursive child-program depth. The root runtime starts
        at depth zero.
    max_recursive_calls : int
        Maximum allowed recursive child-program call count tracked in runtime
        state.

    Attributes
    ----------
    max_recursive_call_depth : int
        Maximum allowed recursive child-program depth.
    max_recursive_calls : int
        Maximum allowed recursive child-program call count.

    Notes
    -----
    - These limits are runtime policy, not AST structure.
    - Validation of positivity is handled by `__post_init__`.
    """

    max_recursive_call_depth: int = DEFAULT_MAX_RECURSIVE_CALL_DEPTH
    max_recursive_calls: int = DEFAULT_MAX_RECURSIVE_CALLS

    def __post_init__(self) -> None:
        if self.max_recursive_call_depth < 0:
            raise ValueError("max_recursive_call_depth must be >= 0")
        if self.max_recursive_calls < 0:
            raise ValueError("max_recursive_calls must be >= 0")
