"""
Purpose
-------
Provide prompt-rendering and formatting helpers for experiment generation. This
module exists to keep prompt text construction and human-readable metadata
formatting separate from AST sampling and validation logic.

Key behaviors
-------------
- Formats dice specifications, modifier phrases, mode phrases, and integer
  lists for prompt text and metadata.
- Renders aligned natural-language prompts from template metadata after the
  gold program has already been constructed.

Conventions
-----------
- Prompt rendering is metadata-driven rather than AST-reverse-engineered.
- Formatting helpers are deterministic and side-effect free.

Downstream usage
----------------
The experiment generator uses these helpers to turn sampled parameters into
short English task descriptions suitable for later planner supervision.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Tuple

from repl_rlm.tools.rolling.rolling import RollMode


def format_int_list(values: Tuple[int, ...]) -> str:
    """
    Render a deterministic tuple of integers as a compact list string.

    Parameters
    ----------
    values : Tuple[int, ...]
        Integer values to render.

    Returns
    -------
    str
        Compact list representation such as `[0, 2, 4]`.

    Raises
    ------
    None

    Notes
    -----
    - This helper keeps prompt rendering and metadata formatting aligned.
    """
    return "[" + ", ".join(str(value) for value in values) + "]"


def format_dice_spec(dice_terms: Tuple[Tuple[int, int], ...]) -> str:
    """
    Render dice terms into a compact NdS specification string.

    Parameters
    ----------
    dice_terms : Tuple[Tuple[int, int], ...]
        Ordered `(count, sides)` dice terms.

    Returns
    -------
    str
        Compact dice specification such as `2d6` or `1d6+1d4`.

    Raises
    ------
    None

    Notes
    -----
    - The output is intended for prompts and metadata, not for parsing back
      into the tool surface.
    """
    return "+".join(f"{count}d{sides}" for count, sides in dice_terms)


def format_modifier_phrase(modifier: int) -> str:
    """
    Render a modifier phrase for prompt text.

    Parameters
    ----------
    modifier : int
        Modifier applied once per roll instance.

    Returns
    -------
    str
        Prompt-ready modifier phrase.

    Raises
    ------
    None

    Notes
    -----
    - Zero modifiers render as an empty phrase to keep prompts concise.
    """
    if modifier == 0:
        return ""
    return f" with modifier {modifier}"


def format_mode_phrase(mode: str) -> str:
    """
    Render a roll-mode phrase for prompt text.

    Parameters
    ----------
    mode : str
        Roll mode string accepted by the deterministic rolling tool.

    Returns
    -------
    str
        Prompt-ready mode phrase.

    Raises
    ------
    None

    Notes
    -----
    - Normal mode renders as an empty phrase because it is the default.
    """
    if mode == RollMode.NORMAL.value:
        return ""
    return f" in {mode.lower()} mode"


def format_repeat_phrase(repeat: int) -> str:
    """
    Render a repeat-count phrase for prompt text.

    Parameters
    ----------
    repeat : int
        Number of roll instances to execute.

    Returns
    -------
    str
        Prompt-ready repeat phrase.

    Raises
    ------
    None

    Notes
    -----
    - Singular and plural cases are kept explicit for readability.
    """
    if repeat == 1:
        return "once"
    return f"{repeat} times"


def render_prompt(template_name: str, metadata: Mapping[str, str]) -> str:
    """
    Render a short English task prompt from sampled experiment metadata.

    Parameters
    ----------
    template_name : str
        Template family name used to select the prompt pattern.
    metadata : Mapping[str, str]
        Template-specific string metadata describing the sampled program.

    Returns
    -------
    str
        Prompt aligned with the generated gold program.

    Raises
    ------
    ValueError
        When the template name is unsupported.

    Notes
    -----
    - Prompts are rendered after program generation from the exact sampled
      parameters already used to build the program.
    """
    if template_name == "single_tool_return":
        return (
            f"Roll {metadata['dice_spec']}{metadata['modifier_phrase']} "
            f"{metadata['repeat_phrase']}{metadata['mode_phrase']} and return the "
            "full structured result."
        )

    if template_name == "tool_assign_if":
        return (
            f"Roll {metadata['dice_spec']}{metadata['modifier_phrase']} "
            f"{metadata['repeat_phrase']}{metadata['mode_phrase']}, inspect the "
            f"total at instance index {metadata['selected_index']}, and return "
            f"'high' if it is above {metadata['threshold']}, otherwise return 'low'."
        )

    if template_name == "two_step_branch":
        return (
            f"Roll {metadata['first_dice_spec']}{metadata['first_modifier_phrase']} "
            f"{metadata['first_repeat_phrase']}{metadata['first_mode_phrase']}, inspect "
            f"the total at instance index {metadata['selected_index']}, and if that "
            f"total is above {metadata['threshold']} then roll {metadata['then_dice_spec']}"
            f"{metadata['then_modifier_phrase']} once{metadata['then_mode_phrase']} and "
            "return that structured result; otherwise roll "
            f"{metadata['else_dice_spec']}{metadata['else_modifier_phrase']} once"
            f"{metadata['else_mode_phrase']} and return that structured result."
        )

    if template_name == "foreach_literal":
        return (
            f"Roll {metadata['dice_spec']} once for each modifier in "
            f"{metadata['modifier_list']}{metadata['mode_phrase']} and return the "
            "final structured roll result."
        )

    if template_name == "simple_aggregation":
        return (
            f"Roll {metadata['dice_spec']}{metadata['modifier_phrase']} "
            f"{metadata['repeat_phrase']}{metadata['mode_phrase']}, iterate over all "
            "returned instances, sum their totals, and return the final total."
        )

    if template_name == "spawn_join":
        return (
            f"Run {metadata['spawn_count']} rolls concurrently using "
            f"{metadata['spawn_specs']} and return the joined list of selected totals."
        )

    raise ValueError(f"Unsupported template name: {template_name}")
