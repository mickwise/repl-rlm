"""
Purpose
-------
Define shared type aliases for the experiments subsystem. This module exists to
centralize the small number of reusable typing contracts used across generator,
utility, formatting, and validation modules.

Key behaviors
-------------
- Defines the canonical dice-specification alias used by the experiment
  templates and utilities.
- Defines the callable shape for template generator functions that sample one
  `Program` plus prompt-rendering metadata.

Conventions
-----------
- Type aliases in this module are intentionally small and package-local.
- These aliases describe deterministic experiment-generation structure, not
  runtime execution semantics.

Downstream usage
----------------
Experiments package modules should import these aliases rather than duplicating
the same `Tuple[...]` or generator-callable shapes in multiple places.
"""

import random
from typing import Callable, Dict, Tuple, TypeAlias

from repl_rlm.repl.steps.steps import Program

DiceTerms: TypeAlias = Tuple[Tuple[int, int], ...]

TemplateGenerator: TypeAlias = Callable[
    [random.Random, str, int, str],
    Tuple[Program, Dict[str, str]],
]
