"""
Purpose
-------
Bridge natural-language D&D roll messages to deterministic execution.

Key behaviors
-------------
- Calls the generated BAML client to parse a free-form message into a typed
  `RollPlan` (sync and async variants).
- Executes the returned plan deterministically using a caller-supplied RNG.
- Returns structured roll outcomes without any narrative formatting.

Conventions
-----------
- Randomness comes only from the provided `random.Random` instance.
- `modifier` is applied once per instance, never per die.
- `repeat` is the number of independent instances (e.g., Magic Missile darts).
- Advantage/disadvantage applies only to d20 terms (sides == 20).
- This module performs no I/O and has no persistence side effects.

Downstream usage
----------------
Call `roll(message, context, rng)` from your Discord/CLI handler, then
format the returned structured result into user-facing text elsewhere.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, List

from baml_client.sync_client import b
from baml_client.types import RollPlan

RANDOM_SEED = 42

def parse_message_to_roll_plan(message: str, context: str | None = None) -> RollPlan:
    """
    Parse a natural-language roll message into a RollPlan by calling the BAML tool.

    Parameters
    ----------
    message : str
        Free-form roll instruction (e.g., "roll perception +5 at advantage").
    context : str | None
        Optional extra information (character sheet bonuses, system notes, etc.).

    Returns
    -------
    RollPlan
        A typed `RollPlan` returned by the generated BAML client.

    Raises
    ------
    Exception
        Propagates any exception raised by the BAML client.

    Notes
    -----
    - Your `rolling.baml` defines: `function Roll(request: string, context: string?) -> RollPlan`.
    - This function does not catch errors; callers should handle failures at the
      bot/application boundary.
    """

    return b.Roll(message, context)


async def parse_message_to_roll_plan_async(
    message: str,
    context: str | None = None,
) -> RollPlan:
    """
    Parse a natural-language roll message into a RollPlan asynchronously.

    Parameters
    ----------
    message : str
        Free-form roll instruction (e.g., "roll perception +5 at advantage").
    context : str | None
        Optional extra information (character sheet bonuses, system notes, etc.).

    Returns
    -------
    RollPlan
        A typed `RollPlan` produced by the generated BAML client.

    Raises
    ------
    Exception
        Propagates any exception raised by the BAML client.
    """
    # Keep async call-sites non-blocking while preserving the proven sync
    # parsing behavior by offloading to a worker thread.
    return await asyncio.to_thread(
        parse_message_to_roll_plan,
        message,
        context,
    )


def execute_roll_plan(plan: RollPlan, rng: random.Random) -> Dict[str, Any]:
    """
    Execute a RollPlan deterministically using the provided RNG.

    Parameters
    ----------
    plan : RollPlan
        Roll plan produced by BAML. Expected fields:
        - dice: list of DiceTerm {count:int, sides:int}
        - modifier: int
        - repeat: int
        - mode: RollMode (NORMAL, ADVANTAGE, DISADVANTAGE)
        - label: optional string
    rng : random.Random
        RNG used for all dice rolls. Seed it for reproducibility.

    Returns
    -------
    dict
        A structured execution result with keys:
        - label: str | None
        - mode: str
        - modifier: int
        - repeat: int
        - instances: list[dict] where each instance has:
            - terms: list[dict] per dice term
            - total_before_modifier: int
            - total: int

    Raises
    ------
    ValueError
        If the plan violates basic invariants.

    Notes
    -----
    - Advantage/disadvantage is applied only to d20 terms (sides == 20).
    - `modifier` is applied once per instance total.
    """

    mode: str = plan.mode.value

    if plan.repeat < 1:
        raise ValueError("plan.repeat must be >= 1")
    if not plan.dice:
        raise ValueError("plan.dice must be non-empty")

    if mode in ("ADVANTAGE", "DISADVANTAGE"):
        if not any(t.sides == 20 for t in plan.dice):
            raise ValueError("advantage/disadvantage requires at least one d20 term")

    instances: List[Dict[str, Any]] = []

    for _ in range(plan.repeat):
        terms_out: List[Dict[str, Any]] = []
        subtotal: int = 0

        for t in plan.dice:
            if t.count < 1:
                raise ValueError("each dice term count must be >= 1")
            if t.sides < 2:
                raise ValueError("each dice term sides must be >= 2")

            term_result: Dict[str, Any] = _roll_term(
                count=t.count, sides=t.sides, mode=mode, rng=rng
            )
            terms_out.append(term_result)
            subtotal += int(term_result["sum"])

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
    message: str,
    rng: random.Random | None = None,
    context: str | None = None,
) -> Dict[str, Any]:
    """
    Parse a message via BAML and execute the resulting RollPlan.

    Parameters
    ----------
    message : str
        Natural-language roll message.
    context : str | None
        Optional context string forwarded to BAML.
    rng : random.Random
        RNG used for deterministic execution.

    Returns
    -------
    dict
        Structured roll execution result (see `execute_roll_plan`).

    Raises
    ------
    Exception
        Propagates any exception raised by BAML parsing.
    ValueError
        If the parsed plan is invalid.

    Notes
    -----
    - This is the intended entry point for your bot.
    """

    rng: random.Random = rng if rng else random.Random(RANDOM_SEED)
    plan = parse_message_to_roll_plan(message=message, context=context)
    return execute_roll_plan(plan=plan, rng=rng)


async def roll_async(
    message: str,
    rng: random.Random | None = None,
    context: str | None = None,
) -> Dict[str, Any]:
    """
    Parse a message via BAML asynchronously and execute the resulting RollPlan.

    Parameters
    ----------
    message : str
        Natural-language roll message.
    rng : random.Random | None
        RNG used for deterministic execution.
    context : str | None
        Optional context string forwarded to BAML.

    Returns
    -------
    dict
        Structured roll execution result (see `execute_roll_plan`).

    Raises
    ------
    Exception
        Propagates any exception raised by BAML parsing.
    ValueError
        If the parsed plan is invalid.
    """

    effective_rng: random.Random = rng if rng else random.Random(RANDOM_SEED)
    plan = await parse_message_to_roll_plan_async(message=message, context=context)
    return execute_roll_plan(plan=plan, rng=effective_rng)


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
    dict
        Per-term result with keys:
        - count: int
        - sides: int
        - rolls: list[int] (kept rolls)
        - raw_rolls: list[int] | None (only for d20 adv/dis)
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

    if sides == 20 and mode in ("ADVANTAGE", "DISADVANTAGE"):
        kept: List[int] = []
        raw: List[int] = []

        for _ in range(count):
            first_die = rng.randint(1, 20)
            second_die = rng.randint(1, 20)
            raw.extend([first_die, second_die])
            kept.append(
                max(first_die, second_die) if mode == "ADVANTAGE" else min(first_die, second_die)
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
