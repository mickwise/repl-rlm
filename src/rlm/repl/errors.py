"""
Purpose
-------
Define native validation and execution error structures for the RLM REPL
runtime. This module exists to normalize raw Python exceptions from validation,
expression interpretation, step interpretation, and task execution into a
stable RLM-specific error surface.

Key behaviors
-------------
- Defines stable machine-readable error codes for validation, execution,
  reference-resolution, task, and implicit runtime-operation failures.
- Defines native exception types carrying an error code, message, and original
  exception cause.
- Provides translation helpers that map raw Python exceptions into native RLM
  exceptions with explicit validation-vs-execution phase awareness.

Conventions
-----------
- Validation and execution are translated differently because both layers may
  raise `TypeError` and `ValueError` for different reasons.
- Native exceptions preserve the original exception as `cause` for debugging.
- Error codes are stable `str` enum values suitable for logging, planner
  feedback, and future programmatic handling.

Downstream usage
----------------
The runtime loop should wrap validation and execution in separate `try` /
`except` blocks and call `translate_exception(..., phase=...)` on any caught
exception before re-raising or returning a normalized failure surface to the
outer planner loop.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum


class ErrorPhase(str, Enum):
    """
    Purpose
    -------
    Enumerate the major phases of RLM program handling that can raise
    exceptions. This enum exists to let translation distinguish structural
    validation failures from runtime execution failures.

    Key behaviors
    -------------
    - Marks whether translation is happening during validation or execution.
    - Allows identical Python exception classes to map to different native
      categories depending on phase.

    Parameters
    ----------
    None

    Attributes
    ----------
    VALIDATION : ErrorPhase
        Exception occurred while structurally validating the AST.
    EXECUTION : ErrorPhase
        Exception occurred while interpreting or executing a validated AST.

    Notes
    -----
    - This enum is intentionally small because the most important distinction
      in the current architecture is validation vs execution.
    """

    VALIDATION = "validation"
    EXECUTION = "execution"


class RlmErrorCode(str, Enum):
    """
    Purpose
    -------
    Enumerate the stable native error codes used by the RLM runtime. This enum
    exists to give validation and execution failures machine-readable identity
    independent of raw Python exception classes.

    Key behaviors
    -------------
    - Provides stable symbolic codes for validation, runtime, reference,
      callable, and task failures.
    - Covers both explicitly raised DSL errors and implicit host-language
      runtime-operation failures.

    Parameters
    ----------
    None

    Attributes
    ----------
    VALIDATION_TYPE_ERROR : RlmErrorCode
        Structural validation failed because a field had the wrong type.
    VALIDATION_VALUE_ERROR : RlmErrorCode
        Structural validation failed because a field had an invalid value.
    UNSUPPORTED_EXPRESSION_NODE : RlmErrorCode
        Expression validation or interpretation encountered an unsupported AST
        node class.
    UNSUPPORTED_STEP_NODE : RlmErrorCode
        Step validation or interpretation encountered an unsupported AST node
        class.
    UNSUPPORTED_OPERATOR : RlmErrorCode
        Interpretation encountered an operator not supported by the DSL.
    UNBOUND_REFERENCE : RlmErrorCode
        Execution failed because a normal reference could not be resolved from
        runtime bindings.
    UNBOUND_TASK_REFERENCE : RlmErrorCode
        Execution failed because a task reference could not be resolved from
        runtime task registry state.
    REGISTRY_LOOKUP_ERROR : RlmErrorCode
        Execution failed during a registry lookup such as tool, LLM, or task
        lookup when the exact registry source is not otherwise disambiguated.
    INVALID_COMPARISON_OPERATION : RlmErrorCode
        Execution failed because a comparison operator was applied to
        incompatible runtime values.
    INVALID_UNARY_OPERATION : RlmErrorCode
        Execution failed because a unary operator was applied to an invalid
        runtime value.
    INVALID_ITERATION_OPERATION : RlmErrorCode
        Execution failed because foreach iteration was attempted on a
        non-iterable runtime value.
    INVALID_CALL_OPERATION : RlmErrorCode
        Execution failed while invoking a tool or LLM callable with bad
        arguments or bad runtime call semantics.
    TASK_SPAWN_ERROR : RlmErrorCode
        Execution failed while creating or registering a spawned async task.
    TASK_JOIN_ERROR : RlmErrorCode
        Execution failed while awaiting or collecting one or more spawned
        tasks.
    RECURSION_DEPTH_EXCEEDED : RlmErrorCode
        Execution failed because a recursive child-program call would exceed
        the configured maximum recursion depth.
    RECURSION_CALL_LIMIT_EXCEEDED : RlmErrorCode
        Execution failed because a recursive child-program call would exceed
        the configured maximum recursive-call count.
    INTERNAL_ERROR : RlmErrorCode
        An unexpected internal runtime failure occurred that does not fit a
        more specific native category.

    Notes
    -----
    - Enum members inherit from `str` for convenient serialization and logging.
    - These codes are intended to remain stable even if underlying
      implementation details change.
    """

    VALIDATION_TYPE_ERROR = "validation_type_error"
    VALIDATION_VALUE_ERROR = "validation_value_error"
    UNSUPPORTED_EXPRESSION_NODE = "unsupported_expression_node"
    UNSUPPORTED_STEP_NODE = "unsupported_step_node"
    UNSUPPORTED_OPERATOR = "unsupported_operator"
    UNBOUND_REFERENCE = "unbound_reference"
    UNBOUND_TASK_REFERENCE = "unbound_task_reference"
    REGISTRY_LOOKUP_ERROR = "registry_lookup_error"
    INVALID_COMPARISON_OPERATION = "invalid_comparison_operation"
    INVALID_UNARY_OPERATION = "invalid_unary_operation"
    INVALID_ITERATION_OPERATION = "invalid_iteration_operation"
    INVALID_CALL_OPERATION = "invalid_call_operation"
    TASK_SPAWN_ERROR = "task_spawn_error"
    TASK_JOIN_ERROR = "task_join_error"
    RECURSION_DEPTH_EXCEEDED = "recursion_depth_exceeded"
    RECURSION_CALL_LIMIT_EXCEEDED = "recursion_call_limit_exceeded"
    INTERNAL_ERROR = "internal_error"


@dataclass(eq=False)
class RlmRuntimeError(Exception):
    """
    Purpose
    -------
    Represent a native RLM exception carrying a stable error code and original
    exception context. This class exists to provide one normalized exception
    surface for the runtime loop.

    Key behaviors
    -------------
    - Stores a machine-readable error code.
    - Stores a human-readable message.
    - Stores the original low-level exception as `cause`.

    Parameters
    ----------
    code : RlmErrorCode
        Stable native error code identifying the failure category.
    message : str
        Human-readable explanation of the failure.
    cause : Exception | None
        Original low-level exception that triggered translation, if any.

    Attributes
    ----------
    code : RlmErrorCode
        Stable native error code identifying the failure category.
    message : str
        Human-readable explanation of the failure.
    cause : Exception | None
        Original low-level exception that triggered translation, if any.

    Notes
    -----
    - This class subclasses `Exception` so it can be raised directly.
    - Equality is disabled so exception identity and traceback behavior remain
      unsurprising.
    """

    code: RlmErrorCode
    message: str
    cause: Exception | None = None

    def __post_init__(self) -> None:
        super().__init__(self.message)


class RlmValidationError(RlmRuntimeError):
    """
    Purpose
    -------
    Represent a native validation-stage failure in the RLM runtime.

    Key behaviors
    -------------
    - Distinguishes structural validation failures from execution failures.
    - Reuses the base native-error payload shape.

    Parameters
    ----------
    code : RlmErrorCode
        Stable native validation error code.
    message : str
        Human-readable explanation of the validation failure.
    cause : Exception | None
        Original low-level exception that triggered translation, if any.

    Attributes
    ----------
    code : RlmErrorCode
        Stable native validation error code.
    message : str
        Human-readable explanation of the validation failure.
    cause : Exception | None
        Original low-level exception that triggered translation, if any.

    Notes
    -----
    - This subclass exists so callers can catch validation failures separately
      from execution failures when desired.
    """


class RlmExecutionError(RlmRuntimeError):
    """
    Purpose
    -------
    Represent a native execution-stage failure in the RLM runtime.

    Key behaviors
    -------------
    - Distinguishes interpreter/runtime failures from validation failures.
    - Reuses the base native-error payload shape.

    Parameters
    ----------
    code : RlmErrorCode
        Stable native execution error code.
    message : str
        Human-readable explanation of the execution failure.
    cause : Exception | None
        Original low-level exception that triggered translation, if any.

    Attributes
    ----------
    code : RlmErrorCode
        Stable native execution error code.
    message : str
        Human-readable explanation of the execution failure.
    cause : Exception | None
        Original low-level exception that triggered translation, if any.

    Notes
    -----
    - This subclass exists so callers can catch execution failures separately
      from validation failures when desired.
    """


def translate_exception(error: Exception, phase: ErrorPhase) -> RlmRuntimeError:
    """
    Translate a raw Python or interpreter-layer exception into a native RLM
    exception.

    Parameters
    ----------
    error : Exception
        Raw exception raised by validation or execution layers.
    phase : ErrorPhase
        Major phase in which the exception occurred.

    Returns
    -------
    RlmRuntimeError
        Native translated exception carrying a stable error code, normalized
        message, and original cause.

    Raises
    ------
    None
        This function returns a translated exception object rather than raising
        it directly.

    Notes
    -----
    - Phase-aware translation is necessary because validators and interpreters
      both use built-in Python exception classes.
    - The current translation is partly message-based because the lower-level
      files still raise mostly built-in exceptions rather than a richer
      internal exception hierarchy.
    """
    if isinstance(error, RlmRuntimeError):
        return error

    message = str(error)

    if phase is ErrorPhase.VALIDATION:
        if isinstance(error, TypeError):
            return RlmValidationError(
                code=RlmErrorCode.VALIDATION_TYPE_ERROR,
                message=message,
                cause=error,
            )
        if isinstance(error, ValueError):
            return RlmValidationError(
                code=RlmErrorCode.VALIDATION_VALUE_ERROR,
                message=message,
                cause=error,
            )
        return RlmValidationError(
            code=RlmErrorCode.INTERNAL_ERROR,
            message=message or error.__class__.__name__,
            cause=error,
        )

    lowered = message.lower()

    if isinstance(error, KeyError):
        if "task" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.UNBOUND_TASK_REFERENCE,
                message=message,
                cause=error,
            )
        if "reference" in lowered or "binding" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.UNBOUND_REFERENCE,
                message=message,
                cause=error,
            )
        return RlmExecutionError(
            code=RlmErrorCode.REGISTRY_LOOKUP_ERROR,
            message=message,
            cause=error,
        )

    if isinstance(error, ValueError):
        if "unsupported expression node" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.UNSUPPORTED_EXPRESSION_NODE,
                message=message,
                cause=error,
            )
        if "unsupported step node" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.UNSUPPORTED_STEP_NODE,
                message=message,
                cause=error,
            )
        if "unsupported" in lowered and "operator" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.UNSUPPORTED_OPERATOR,
                message=message,
                cause=error,
            )
        return RlmExecutionError(
            code=RlmErrorCode.INTERNAL_ERROR,
            message=message,
            cause=error,
        )

    if isinstance(error, TypeError):
        if "not iterable" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.INVALID_ITERATION_OPERATION,
                message=message,
                cause=error,
            )
        if "unary" in lowered or "bad operand type for unary" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.INVALID_UNARY_OPERATION,
                message=message,
                cause=error,
            )
        if (
            ">" in lowered
            or "<" in lowered
            or "not supported between instances" in lowered
        ):
            return RlmExecutionError(
                code=RlmErrorCode.INVALID_COMPARISON_OPERATION,
                message=message,
                cause=error,
            )
        if "argument" in lowered or "call" in lowered or "await" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.INVALID_CALL_OPERATION,
                message=message,
                cause=error,
            )
        return RlmExecutionError(
            code=RlmErrorCode.INTERNAL_ERROR,
            message=message,
            cause=error,
        )

    if isinstance(error, RuntimeError):
        if "task" in lowered or "event loop" in lowered:
            return RlmExecutionError(
                code=RlmErrorCode.TASK_SPAWN_ERROR,
                message=message,
                cause=error,
            )
        return RlmExecutionError(
            code=RlmErrorCode.INTERNAL_ERROR,
            message=message,
            cause=error,
        )

    if isinstance(error, asyncio.CancelledError):
        return RlmExecutionError(
            code=RlmErrorCode.TASK_JOIN_ERROR,
            message=message or "Task join was cancelled.",
            cause=error,
        )

    return RlmExecutionError(
        code=RlmErrorCode.INTERNAL_ERROR,
        message=message or error.__class__.__name__,
        cause=error,
    )
