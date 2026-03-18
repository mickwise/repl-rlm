"""
Purpose
-------
Provide deterministic dice-roll execution for the REPL / RLM runtime. This
module exists to execute explicit structured roll parameters emitted by the
planner, without depending on BAML, natural-language parsing, or any hidden
planning layer inside the tool itself.

Key behaviors
-------------
- Accepts explicit structured roll parameters suitable for direct runtime tool
  invocation.
- Normalizes those parameters into a small local roll-plan structure before
  execution.
- Executes dice rolls deterministically using either a caller-supplied RNG or a
  caller-supplied seed.
- Returns structured runtime-friendly dictionaries describing totals and
  underlying rolls.
- Preserves the existing lower-level rolling semantics for repeat, modifier,
  and d20 advantage/disadvantage handling.

Conventions
-----------
- Natural-language interpretation belongs to the planner layer, not this tool.
- Randomness comes only from the provided `random.Random` instance or a locally
  constructed RNG seeded from `seed` or `RANDOM_SEED`.
- `modifier` is applied once per instance, never per die.
- `repeat` is the number of independent instances (e.g., Magic Missile darts).
- Advantage/disadvantage applies only to d20 terms (sides == 20).
- This module performs no I/O and has no persistence side effects.

Downstream usage
----------------
Register `roll` in the runtime tool registry and call it from a `ToolCallStep`
with structured named arguments such as `dice`, `modifier`, `repeat`, `mode`,
and `label`.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple, TypeAlias

RANDOM_SEED = 42

DiceTermInput: TypeAlias = "DiceTerm | Mapping[str, Any]"


class RollMode(str, Enum):
    """
    Purpose
    -------
    Enumerate the legal roll modes supported by the deterministic rolling tool.
    This enum exists to constrain caller-supplied roll-mode values to the
    currently implemented execution semantics.

    Key behaviors
    -------------
    - Provides stable symbolic values for normal rolls and d20
      advantage/disadvantage.
    - Prevents arbitrary free-form mode strings from flowing through execution
      without validation.

    Parameters
    ----------
    None

    Attributes
    ----------
    NORMAL : RollMode
        Execute rolls normally without special d20 handling.
    ADVANTAGE : RollMode
        Roll two d20s per d20 die and keep the higher result.
    DISADVANTAGE : RollMode
        Roll two d20s per d20 die and keep the lower result.

    Notes
    -----
    - Enum members inherit from `str` for convenient serialization and display.
    - Advantage and disadvantage affect only d20 terms, matching existing tool
      semantics.
    """

    NORMAL = "NORMAL"
    ADVANTAGE = "ADVANTAGE"
    DISADVANTAGE = "DISADVANTAGE"


@dataclass(frozen=True)
class DiceTerm:
    """
    Purpose
    -------
    Represent one explicit dice term for deterministic roll execution. This
    class exists to normalize caller-supplied structured term arguments before
    the rolling logic runs.

    Key behaviors
    -------------
    - Stores the number of dice to roll.
    - Stores the number of sides per die.

    Parameters
    ----------
    count : int
        Number of dice to roll for the term.
    sides : int
        Number of sides on each die for the term.

    Attributes
    ----------
    count : int
        Number of dice to roll for the term.
    sides : int
        Number of sides on each die for the term.

    Notes
    -----
    - Structural validation happens through helper functions in this module.
    - This class is execution-focused and intentionally small.
    """

    count: int
    sides: int


@dataclass(frozen=True)
class RollPlan:
    """
    Purpose
    -------
    Represent a normalized deterministic roll plan inside the rolling tool.

    Key behaviors
    -------------
    - Stores normalized dice terms, modifier, repeat count, roll mode, and an
      optional label.
    - Provides one explicit structural object for the deterministic execution
      layer.

    Parameters
    ----------
    dice : Tuple[DiceTerm, ...]
        Ordered dice terms that make up the plan.
    modifier : int
        Modifier applied once per repeated instance.
    repeat : int
        Number of independent plan instances to execute.
    mode : RollMode
        Roll mode controlling normal or d20 advantage/disadvantage behavior.
    label : str | None
        Optional caller-supplied label carried through to the result.

    Attributes
    ----------
    dice : Tuple[DiceTerm, ...]
        Ordered dice terms that make up the plan.
    modifier : int
        Modifier applied once per repeated instance.
    repeat : int
        Number of independent plan instances to execute.
    mode : RollMode
        Roll mode controlling normal or d20 advantage/disadvantage behavior.
    label : str | None
        Optional caller-supplied label carried through to the result.

    Notes
    -----
    - This class is a deterministic execution plan, not a parsing target.
    - Planner/runtime code should usually call `roll(...)` directly with
      explicit named arguments rather than constructing this class manually.
    """

    dice: Tuple[DiceTerm, ...]
    modifier: int = 0
    repeat: int = 1
    mode: RollMode = RollMode.NORMAL
    label: str | None = None


def _require_int(value: object, field_name: str) -> int:
    """
    Validate that a supplied value is a non-bool integer.

    Parameters
    ----------
    value : object
        Value expected to be an integer.
    field_name : str
        Human-readable field name used in error messages.

    Returns
    -------
    int
        Validated integer value.

    Raises
    ------
    TypeError
        When the supplied value is not an integer or is a bool.

    Notes
    -----
    - `bool` is rejected explicitly even though it subclasses `int`.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int.")
    return value


def _normalize_roll_mode(mode: RollMode | str) -> RollMode:
    """
    Normalize a caller-supplied roll-mode value into a RollMode enum member.

    Parameters
    ----------
    mode : RollMode | str
        Caller-supplied roll-mode value.

    Returns
    -------
    RollMode
        Normalized roll mode.

    Raises
    ------
    TypeError
        When the supplied mode is not a string or RollMode.
    ValueError
        When the supplied mode string is not a supported roll mode.

    Notes
    -----
    - String modes are normalized by stripping whitespace and uppercasing.
    """
    if isinstance(mode, RollMode):
        return mode
    if not isinstance(mode, str):
        raise TypeError("mode must be a RollMode or string.")

    normalized_mode = mode.strip().upper()
    if not normalized_mode:
        raise ValueError("mode must be a non-empty string.")

    try:
        return RollMode(normalized_mode)
    except ValueError as error:
        raise ValueError(f"Unsupported roll mode: {mode}") from error


def _normalize_dice_term(term: DiceTermInput) -> DiceTerm:
    """
    Normalize one caller-supplied dice term into a DiceTerm instance.

    Parameters
    ----------
    term : DiceTerm | Mapping[str, Any]
        Caller-supplied dice term.

    Returns
    -------
    DiceTerm
        Normalized dice-term object.

    Raises
    ------
    TypeError
        When the supplied term is not a DiceTerm or mapping.
    KeyError
        When a mapping term omits `count` or `sides`.

    Notes
    -----
    - Mapping terms are expected to use the same field names that planner tool
      calls would naturally emit: `count` and `sides`.
    """
    if isinstance(term, DiceTerm):
        return term
    if not isinstance(term, Mapping):
        raise TypeError("Each dice term must be a DiceTerm or mapping.")

    return DiceTerm(
        count=_require_int(term["count"], "dice term count"),
        sides=_require_int(term["sides"], "dice term sides"),
    )


def _normalize_roll_plan(
    dice: Sequence[DiceTermInput],
    modifier: int,
    repeat: int,
    mode: RollMode | str,
    label: str | None,
) -> RollPlan:
    """
    Normalize caller-supplied structured arguments into a RollPlan.

    Parameters
    ----------
    dice : Sequence[DiceTerm | Mapping[str, Any]]
        Structured dice terms describing what should be rolled.
    modifier : int
        Modifier applied once per repeated instance.
    repeat : int
        Number of independent plan instances to execute.
    mode : RollMode | str
        Roll mode controlling normal or d20 advantage/disadvantage behavior.
    label : str | None
        Optional caller-supplied label carried through to the result.

    Returns
    -------
    RollPlan
        Normalized deterministic roll plan.

    Raises
    ------
    TypeError
        When one or more structured arguments have the wrong type.
    ValueError
        When one or more structured arguments violate basic invariants.

    Notes
    -----
    - `dice` is accepted as any non-string sequence so list-valued runtime tool
      arguments work naturally.
    - Term-level range validation is performed by `execute_roll_plan`.
    """
    if isinstance(dice, (str, bytes, bytearray)) or not isinstance(dice, Sequence):
        raise TypeError("dice must be a sequence of DiceTerm objects or mappings.")

    normalized_dice = tuple(_normalize_dice_term(term) for term in dice)
    normalized_modifier = _require_int(modifier, "modifier")
    normalized_repeat = _require_int(repeat, "repeat")
    normalized_mode = _normalize_roll_mode(mode)

    if label is not None and not isinstance(label, str):
        raise TypeError("label must be a string or None.")

    return RollPlan(
        dice=normalized_dice,
        modifier=normalized_modifier,
        repeat=normalized_repeat,
        mode=normalized_mode,
        label=label,
    )


def _resolve_rng(
    rng: random.Random | None,
    seed: int | None,
) -> random.Random:
    """
    Resolve the effective RNG used for deterministic roll execution.

    Parameters
    ----------
    rng : random.Random | None
        Optional caller-supplied RNG instance.
    seed : int | None
        Optional caller-supplied RNG seed.

    Returns
    -------
    random.Random
        RNG that should be used for the roll execution.

    Raises
    ------
    TypeError
        When `rng` is not a `random.Random` instance or `seed` is not an int.
    ValueError
        When both `rng` and `seed` are supplied.

    Notes
    -----
    - Passing `seed` creates a fresh deterministic RNG for that call.
    - When neither argument is supplied, a new RNG is created from
      `RANDOM_SEED` to preserve deterministic default behavior.
    """
    if rng is not None and seed is not None:
        raise ValueError("Provide either rng or seed, not both.")
    if rng is not None:
        if not isinstance(rng, random.Random):
            raise TypeError("rng must be a random.Random instance.")
        return rng
    if seed is not None:
        return random.Random(_require_int(seed, "seed"))
    return random.Random(RANDOM_SEED)


def _execute_roll_plan(plan: RollPlan, rng: random.Random) -> Dict[str, Any]:
    """
    Execute a normalized RollPlan deterministically using the provided RNG.

    Parameters
    ----------
    plan : RollPlan
        Normalized deterministic roll plan.
    rng : random.Random
        RNG used for all dice rolls. Seed it for reproducibility.

    Returns
    -------
    Dict[str, Any]
        Structured execution result with keys:
        - label: str | None
        - mode: str
        - modifier: int
        - repeat: int
        - instances: List[Dict[str, Any]] where each instance has:
            - terms: List[Dict[str, Any]]
            - total_before_modifier: int
            - total: int

    Raises
    ------
    ValueError
        When the plan violates basic deterministic rolling invariants.

    Notes
    -----
    - Advantage/disadvantage is applied only to d20 terms.
    - `modifier` is applied once per instance total.
    """
    mode: str = plan.mode.value

    if plan.repeat < 1:
        raise ValueError("plan.repeat must be >= 1")
    if not plan.dice:
        raise ValueError("plan.dice must be non-empty")

    if mode in (RollMode.ADVANTAGE.value, RollMode.DISADVANTAGE.value):
        if not any(term.sides == 20 for term in plan.dice):
            raise ValueError("advantage/disadvantage requires at least one d20 term")

    instances: List[Dict[str, Any]] = []

    for _ in range(plan.repeat):
        terms_out: List[Dict[str, Any]] = []
        subtotal = 0

        for term in plan.dice:
            if term.count < 1:
                raise ValueError("each dice term count must be >= 1")
            if term.sides < 2:
                raise ValueError("each dice term sides must be >= 2")

            term_result: Dict[str, Any] = _roll_term(
                count=term.count,
                sides=term.sides,
                mode=mode,
                rng=rng,
            )
            terms_out.append(term_result)
            subtotal += term_result["sum"]

        total: int = subtotal + plan.modifier
        instances.append(
            {
                "terms": terms_out,
                "total_before_modifier": subtotal,
                "total": total,
            }
        )

    return {
        "label": plan.label,
        "mode": mode,
        "modifier": plan.modifier,
        "repeat": plan.repeat,
        "instances": instances,
    }


def roll(
    dice: Sequence[DiceTermInput],
    modifier: int = 0,
    repeat: int = 1,
    mode: RollMode | str = RollMode.NORMAL,
    label: str | None = None,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> Dict[str, Any]:
    """
    Execute an explicit structured dice roll deterministically.

    Parameters
    ----------
    dice : Sequence[DiceTerm | Mapping[str, Any]]
        Structured dice terms describing what should be rolled. Each term must
        provide `count` and `sides`.
    modifier : int
        Modifier applied once per repeated instance. Defaults to `0`.
    repeat : int
        Number of independent plan instances to execute. Defaults to `1`.
    mode : RollMode | str
        Roll mode controlling normal or d20 advantage/disadvantage behavior.
        Defaults to `RollMode.NORMAL`.
    label : str | None
        Optional caller-supplied label carried through to the result.
    seed : int | None
        Optional deterministic seed used to construct a fresh RNG for this
        call.
    rng : random.Random | None
        Optional caller-supplied RNG instance used directly for execution.

    Returns
    -------
    Dict[str, Any]
        Structured roll execution result (see `execute_roll_plan`).

    Raises
    ------
    TypeError
        When one or more inputs have the wrong type.
    ValueError
        When the structured plan is invalid or contradictory.

    Notes
    -----
    - This is the main public runtime tool surface for deterministic rolling.
    - Natural-language interpretation is intentionally out of scope for this
      function.
    """
    plan = _normalize_roll_plan(
        dice=dice,
        modifier=modifier,
        repeat=repeat,
        mode=mode,
        label=label,
    )
    effective_rng = _resolve_rng(rng=rng, seed=seed)
    return _execute_roll_plan(plan=plan, rng=effective_rng)


async def roll_async(
    dice: Sequence[DiceTermInput],
    modifier: int = 0,
    repeat: int = 1,
    mode: RollMode | str = RollMode.NORMAL,
    label: str | None = None,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> Dict[str, Any]:
    """
    Execute an explicit structured dice roll through an async-compatible wrapper.

    Parameters
    ----------
    dice : Sequence[DiceTerm | Mapping[str, Any]]
        Structured dice terms describing what should be rolled. Each term must
        provide `count` and `sides`.
    modifier : int
        Modifier applied once per repeated instance. Defaults to `0`.
    repeat : int
        Number of independent plan instances to execute. Defaults to `1`.
    mode : RollMode | str
        Roll mode controlling normal or d20 advantage/disadvantage behavior.
        Defaults to `RollMode.NORMAL`.
    label : str | None
        Optional caller-supplied label carried through to the result.
    seed : int | None
        Optional deterministic seed used to construct a fresh RNG for this
        call.
    rng : random.Random | None
        Optional caller-supplied RNG instance used directly for execution.

    Returns
    -------
    Dict[str, Any]
        Structured roll execution result (see `execute_roll_plan`).

    Raises
    ------
    TypeError
        When one or more inputs have the wrong type.
    ValueError
        When the structured plan is invalid or contradictory.

    Notes
    -----
    - This wrapper exists only for async call sites that want a coroutine
      interface around the same deterministic execution path.
    """
    return roll(
        dice=dice,
        modifier=modifier,
        repeat=repeat,
        mode=mode,
        label=label,
        seed=seed,
        rng=rng,
    )


def _roll_term(count: int, sides: int, mode: str, rng: random.Random) -> Dict[str, Any]:
    """
    Roll a single NdS term, applying advantage/disadvantage for d20 terms.

    Parameters
    ----------
    count : int
        Number of dice.
    sides : int
        Sides per die.
    mode : str
        One of NORMAL, ADVANTAGE, DISADVANTAGE.
    rng : random.Random
        RNG used for sampling.

    Returns
    -------
    Dict[str, Any]
        Per-term result with keys:
        - count: int
        - sides: int
        - rolls: List[int] (kept rolls)
        - raw_rolls: List[int] | None (only for d20 adv/dis)
        - sum: int

    Raises
    ------
    ValueError
        If inputs are invalid.

    Notes
    -----
    - For d20 with advantage/disadvantage, each die is resolved by rolling two
      d20 and keeping the higher/lower.
    """
    if count < 1 or sides < 2:
        raise ValueError("invalid dice term")

    if sides == 20 and mode in (RollMode.ADVANTAGE.value, RollMode.DISADVANTAGE.value):
        kept: List[int] = []
        raw: List[int] = []

        for _ in range(count):
            first_die = rng.randint(1, 20)
            second_die = rng.randint(1, 20)
            raw.extend([first_die, second_die])
            kept.append(
                max(first_die, second_die)
                if mode == RollMode.ADVANTAGE.value
                else min(first_die, second_die)
            )

        return {
            "count": count,
            "sides": sides,
            "rolls": kept,
            "raw_rolls": raw,
            "sum": sum(kept),
        }

    rolls = [rng.randint(1, sides) for _ in range(count)]
    return {
        "count": count,
        "sides": sides,
        "rolls": rolls,
        "raw_rolls": None,
        "sum": sum(rolls),
    }
