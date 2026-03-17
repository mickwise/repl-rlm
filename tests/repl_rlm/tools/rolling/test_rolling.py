"""
Purpose
-------
Exercise deterministic structured execution for the rolling tool. This module
exists to keep the rolling tool aligned with the REPL runtime contract where
the planner emits explicit tool arguments and the tool returns structured
results without any natural-language parsing layer.

Key behaviors
-------------
- Verifies deterministic structured output when a seed is supplied.
- Verifies d20 advantage execution details in the returned term structure.
- Verifies clean validation errors for invalid explicit input combinations.

Conventions
-----------
- Tests call the public deterministic tool surface directly rather than any
  parsing layer.
- Assertions focus on stable structured values and explicit Python validation
  errors.

Downstream usage
----------------
CI runs this module to protect the rolling tool surface intended for runtime
tool-registry registration.
"""

import random

import pytest

from repl_rlm.tools.rolling.rolling import RollMode, roll, roll_async


def test_roll_returns_deterministic_structured_output_with_seed() -> None:
    """
    Return identical structured results for identical seeded tool calls.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when seeded calls produce stable structured
        output.

    Raises
    ------
    AssertionError
        If repeated seeded calls diverge or return an unexpected structure.

    Notes
    -----
    - This protects the runtime-facing deterministic execution contract.
    """
    first = roll(
        dice=[{"count": 2, "sides": 6}],
        modifier=3,
        repeat=2,
        label="damage",
        seed=7,
    )
    second = roll(
        dice=[{"count": 2, "sides": 6}],
        modifier=3,
        repeat=2,
        label="damage",
        seed=7,
    )

    assert first == second
    assert first["label"] == "damage"
    assert first["modifier"] == 3
    assert first["repeat"] == 2
    assert len(first["instances"]) == 2


def test_roll_returns_advantage_details_for_d20_terms() -> None:
    """
    Include kept and raw rolls for d20 advantage execution.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when d20 advantage produces the expected
        structured term detail.

    Raises
    ------
    AssertionError
        If advantage execution does not preserve raw and kept roll details.

    Notes
    -----
    - The planner can use this output structure later for explicit reasoning
      about underlying tool outcomes.
    """
    result = roll(
        dice=[{"count": 2, "sides": 20}],
        mode=RollMode.ADVANTAGE,
        seed=5,
    )

    term = result["instances"][0]["terms"][0]

    assert result["mode"] == RollMode.ADVANTAGE.value
    assert len(term["rolls"]) == 2
    assert len(term["raw_rolls"]) == 4
    assert term["sum"] == sum(term["rolls"])


def test_roll_rejects_advantage_without_a_d20_term() -> None:
    """
    Reject advantage/disadvantage when no d20 term is present.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when invalid explicit mode usage raises the
        expected validation error.

    Raises
    ------
    AssertionError
        If invalid advantage input is accepted.

    Notes
    -----
    - This preserves an existing execution invariant from the original tool.
    """
    with pytest.raises(ValueError, match="requires at least one d20 term"):
        roll(
            dice=[{"count": 1, "sides": 6}],
            mode="ADVANTAGE",
        )


def test_roll_rejects_both_seed_and_rng() -> None:
    """
    Reject calls that supply both a seed and an explicit RNG.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when contradictory RNG inputs raise the
        expected validation error.

    Raises
    ------
    AssertionError
        If contradictory RNG inputs are accepted.

    Notes
    -----
    - The deterministic tool surface should make the random source explicit.
    """
    with pytest.raises(ValueError, match="either rng or seed"):
        roll(
            dice=[{"count": 1, "sides": 20}],
            seed=1,
            rng=random.Random(1),
        )


@pytest.mark.asyncio
async def test_roll_async_uses_the_same_structured_execution_path() -> None:
    """
    Return the same structured result from the async compatibility wrapper.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when the async wrapper delegates to the same
        deterministic execution path.

    Raises
    ------
    AssertionError
        If the async wrapper returns a different structured result.

    Notes
    -----
    - This keeps async call sites aligned with the same runtime-facing tool
      semantics.
    """
    sync_result = roll(
        dice=[{"count": 1, "sides": 20}],
        modifier=2,
        seed=9,
    )
    async_result = await roll_async(
        dice=[{"count": 1, "sides": 20}],
        modifier=2,
        seed=9,
    )

    assert async_result == sync_result
