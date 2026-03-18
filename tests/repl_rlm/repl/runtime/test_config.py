"""
Purpose
-------
Verify runtime configuration objects that control recursive execution policy.
This module exists to keep the recursion-budget contract stable and explicit.

Key behaviors
-------------
- Confirms that negative recursion limits are rejected.
- Confirms that valid explicit limits are stored unchanged.

Conventions
-----------
- Tests assert on public construction behavior only.
- Coverage is intentionally small because the configuration object is simple.

Downstream usage
----------------
CI runs this module to catch regressions in the recursion-budget policy surface
used by runtime-state creation and recursive calls.
"""

from typing import Dict

import pytest

from repl_rlm.repl.runtime.config import RuntimeConfig


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"max_recursive_call_depth": -1}, "max_recursive_call_depth"),
        ({"max_recursive_calls": -1}, "max_recursive_calls"),
    ],
)
def test_runtime_config_rejects_negative_limits(
    kwargs: Dict[str, int],
    expected_message: str,
) -> None:
    """
    Reject negative recursion-budget values during configuration construction.

    Parameters
    ----------
    kwargs : Dict[str, int]
        Keyword arguments applied to the runtime configuration constructor.
    expected_message : str
        Substring expected to appear in the raised error message.

    Returns
    -------
    None
        This test returns nothing when negative limits are rejected.

    Raises
    ------
    AssertionError
        If invalid negative limits are accepted or produce the wrong message.

    Notes
    -----
    - Parameterization keeps both budget guards covered without duplicating
      setup.
    """
    with pytest.raises(ValueError, match=expected_message):
        RuntimeConfig(**kwargs)


def test_runtime_config_preserves_explicit_valid_limits() -> None:
    """
    Preserve explicit positive recursion-budget values.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when valid explicit limits are stored
        unchanged.

    Raises
    ------
    AssertionError
        If explicit recursion-budget values are altered during construction.

    Notes
    -----
    - Stable configuration storage matters for deterministic benchmark runs.
    """
    config = RuntimeConfig(max_recursive_call_depth=3, max_recursive_calls=7)

    assert config.max_recursive_call_depth == 3
    assert config.max_recursive_calls == 7
