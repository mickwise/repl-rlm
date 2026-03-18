"""
Purpose
-------
Expose the public experiments package API for deterministic REPL / RLM
experiment generation. This module exists to make the experiments directory an
explicit package and to re-export the package-facing generation entrypoints.

Key behaviors
-------------
- Marks `repl_rlm.experiments` as an explicit Python package.
- Re-exports the main experiment dataclass and generation functions.
- Keeps internal validation, formatting, and utility helpers out of the
  package-facing surface.

Conventions
-----------
- Only public experiment-generation symbols are re-exported here.
- Lower-level helper modules remain importable directly when needed by tests or
  internal code.

Downstream usage
----------------
Callers may import `GeneratedExperiment`, `generate_experiments`, or the
template-specific `generate_*` functions directly from `repl_rlm.experiments`.
"""

from repl_rlm.experiments.experiment_generator import (
    GeneratedExperiment,
    generate_experiments,
    generate_foreach_literal,
    generate_simple_aggregation,
    generate_single_tool_return,
    generate_spawn_join,
    generate_tool_assign_if,
    generate_two_step_branch,
)

__all__ = [
    "GeneratedExperiment",
    "generate_experiments",
    "generate_foreach_literal",
    "generate_simple_aggregation",
    "generate_single_tool_return",
    "generate_spawn_join",
    "generate_tool_assign_if",
    "generate_two_step_branch",
]
