"""
Purpose
-------
Verify the native error-translation layer used by the REPL runtime. This
module exists to keep the public error surface stable when lower-level code
raises built-in Python exceptions.

Key behaviors
-------------
- Confirms that native RLM exceptions pass through translation unchanged.
- Confirms that validation and execution phases map common Python exceptions to
  the expected native error codes.

Conventions
-----------
- Tests focus on the observable error code and preserved cause.
- Message-based heuristics are asserted only where callers depend on them.

Downstream usage
----------------
CI runs this module to catch regressions in the normalized exception surface
used by runtime callers and future adapters.
"""

from repl_rlm.repl.errors import (
    ErrorPhase,
    RlmErrorCode,
    RlmExecutionError,
    translate_exception,
)


def test_translate_exception_preserves_native_runtime_errors() -> None:
    """
    Preserve an existing native runtime error instance.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when translation leaves the native error
        object untouched.

    Raises
    ------
    AssertionError
        If translation wraps or mutates an already normalized runtime error.

    Notes
    -----
    - This keeps higher-level exception handling stable across translation
      boundaries.
    """
    error = RlmExecutionError(
        code=RlmErrorCode.INTERNAL_ERROR,
        message="already normalized",
    )

    translated = translate_exception(error, ErrorPhase.EXECUTION)

    assert translated is error


def test_translate_exception_maps_validation_type_errors() -> None:
    """
    Translate validation-phase type errors into validation error codes.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when validation type errors map to the
        expected native code.

    Raises
    ------
    AssertionError
        If the translated error code or cause does not match expectations.

    Notes
    -----
    - The validation layer uses built-in exceptions heavily, so this mapping is
      an important compatibility boundary.
    """
    error = TypeError("bad field type")

    translated = translate_exception(error, ErrorPhase.VALIDATION)

    assert translated.code is RlmErrorCode.VALIDATION_TYPE_ERROR
    assert translated.cause is error


def test_translate_exception_maps_reference_like_key_errors() -> None:
    """
    Translate binding-shaped key errors into unbound-reference failures.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when execution-phase key errors mentioning
        bindings map to the expected native code.

    Raises
    ------
    AssertionError
        If the translated execution error does not carry the unbound-reference
        code.

    Notes
    -----
    - The translation layer uses the error message as a heuristic here.
    """
    error = KeyError("binding missing")

    translated = translate_exception(error, ErrorPhase.EXECUTION)

    assert translated.code is RlmErrorCode.UNBOUND_REFERENCE
    assert translated.cause is error


def test_translate_exception_maps_not_iterable_type_errors() -> None:
    """
    Translate iteration-related type errors into invalid-iteration failures.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when iteration failures map to the expected
        native code.

    Raises
    ------
    AssertionError
        If the translated execution error does not carry the invalid-iteration
        code.

    Notes
    -----
    - Foreach execution depends on this mapping to surface a stable public
      error category.
    """
    error = TypeError("'int' object is not iterable")

    translated = translate_exception(error, ErrorPhase.EXECUTION)

    assert translated.code is RlmErrorCode.INVALID_ITERATION_OPERATION
    assert translated.cause is error
