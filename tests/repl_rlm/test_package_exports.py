"""
Purpose
-------
Verify the public package-level re-export surfaces across the handwritten
runtime packages. This module exists to keep the intended import boundaries
stable as the internal module layout evolves.

Key behaviors
-------------
- Confirms expression-layer symbols are re-exported from the expressions
  package.
- Confirms step-layer symbols are re-exported from the steps package.
- Confirms runtime execution helpers are re-exported from the runtime package.
- Confirms the deterministic rolling tool surface is re-exported from the
  rolling package.

Conventions
-----------
- Tests assert object identity where possible so package exports stay aligned
  with their underlying implementation modules.
- Coverage focuses on the package API surface rather than internal helper
  layout.

Downstream usage
----------------
CI runs this module to catch regressions in the public import surfaces intended
for downstream callers and examples.
"""

from repl_rlm.repl.expressions import (
    ListIndexExpr,
    validate_expression,
)
from repl_rlm.repl.expressions.expression_validator import validate_expression as direct_validate
from repl_rlm.repl.expressions.expressions import ListIndexExpr as DirectListIndexExpr
from repl_rlm.repl.runtime import create_runtime_state
from repl_rlm.repl.runtime.runtime import create_runtime_state as direct_create_runtime_state
from repl_rlm.repl.steps import Program, interpret_step_tuple, validate_program
from repl_rlm.repl.steps.step_interpreter import interpret_step_tuple as direct_interpret_step_tuple
from repl_rlm.repl.steps.step_validator import validate_program as direct_validate_program
from repl_rlm.repl.steps.steps import Program as DirectProgram
from repl_rlm.tools.rolling import RollMode, roll
from repl_rlm.tools.rolling.rolling import RollMode as DirectRollMode
from repl_rlm.tools.rolling.rolling import roll as direct_roll


def test_expressions_package_reexports_expression_surface() -> None:
    """
    Re-export expression nodes and validator entrypoints from the package.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when the expressions package exposes the
        intended public symbols.

    Raises
    ------
    AssertionError
        If package-level expression exports drift from their implementation
        modules.

    Notes
    -----
    - This keeps callers from needing to know the internal AST/validator file
      split.
    """
    assert ListIndexExpr is DirectListIndexExpr
    assert validate_expression is direct_validate


def test_steps_package_reexports_step_surface() -> None:
    """
    Re-export program/step nodes and step helpers from the package.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when the steps package exposes the intended
        public symbols.

    Raises
    ------
    AssertionError
        If package-level step exports drift from their implementation modules.

    Notes
    -----
    - This keeps callers from needing to know the internal AST/interpreter
      file split.
    """
    assert Program is DirectProgram
    assert interpret_step_tuple is direct_interpret_step_tuple
    assert validate_program is direct_validate_program


def test_runtime_package_reexports_runtime_surface() -> None:
    """
    Re-export runtime execution helpers from the runtime package.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when the runtime package exposes the intended
        execution helpers.

    Raises
    ------
    AssertionError
        If package-level runtime exports drift from their implementation
        modules.

    Notes
    -----
    - This keeps callers from needing to import directly from `runtime.py` for
      the common execution entrypoints.
    """
    assert create_runtime_state is direct_create_runtime_state


def test_rolling_package_reexports_tool_surface() -> None:
    """
    Re-export the rolling tool callable and mode enum from the package.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when the rolling package exposes the intended
        public tool surface.

    Raises
    ------
    AssertionError
        If package-level rolling exports drift from their implementation
        module.

    Notes
    -----
    - This keeps external callers from needing the extra `.rolling` module hop.
    """
    assert roll is direct_roll
    assert RollMode is DirectRollMode
