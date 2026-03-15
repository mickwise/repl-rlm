"""
Purpose
-------
Exercise structural validation for executable step nodes and programs. This
module exists to keep the step-level DSL contract stable before runtime
execution.

Key behaviors
-------------
- Verifies that representative recursive, spawn, and join structures validate.
- Verifies that malformed join inputs, metadata, and unsupported nodes fail
  with native validation errors.

Conventions
-----------
- Tests focus on stable DSL contracts rather than every individual dataclass
  field in isolation.
- Assertions prefer native error codes over raw Python exception classes.

Downstream usage
----------------
CI runs this module to protect the step-validation boundary used by the top-
level runtime entrypoints.
"""

import pytest

from repl_rlm.repl.errors import RlmErrorCode, RlmValidationError
from repl_rlm.repl.expressions.expressions import Literal, Ref, TaskRef
from repl_rlm.repl.steps.step_validator import validate_program, validate_step
from repl_rlm.repl.steps.steps import (
    JoinStep,
    Program,
    RecursiveCallStep,
    ReturnStep,
    SpawnStep,
)


def test_validate_program_accepts_recursive_spawn_and_join_structure() -> None:
    """
    Accept a representative program containing recursive, spawn, and join work.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when a structurally valid composite program
        passes validation.

    Raises
    ------
    AssertionError
        If a representative valid program unexpectedly fails validation.

    Notes
    -----
    - This keeps the high-level DSL shape stable for planners that emit
      composite work.
    """
    sub_program = Program(
        steps=(ReturnStep(value_expr=Literal(value="done")),),
        metadata={},
    )
    program = Program(
        steps=(
            RecursiveCallStep(
                baml_func_name="planner",
                args=None,
                binding_target="child_result",
            ),
            SpawnStep(binding_target="task_1", sub_program=sub_program),
            JoinStep(tasks_ref=(TaskRef(name="task_1"),), binding_target="joined"),
        ),
        metadata={},
    )

    validate_program(program)


def test_validate_step_rejects_join_refs_that_are_not_task_refs() -> None:
    """
    Reject join steps whose task tuple contains ordinary references.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when non-task references in join steps raise
        the expected validation error.

    Raises
    ------
    AssertionError
        If join validation accepts ordinary references or maps the failure to
        the wrong code.

    Notes
    -----
    - The runtime expects `TaskRef` semantics here, so validation must enforce
      that contract.
    """
    step = JoinStep(tasks_ref=(Ref(name="task_1"),), binding_target=None)

    with pytest.raises(RlmValidationError) as excinfo:
        validate_step(step)

    assert excinfo.value.code is RlmErrorCode.VALIDATION_TYPE_ERROR


def test_validate_program_rejects_non_mapping_metadata() -> None:
    """
    Reject top-level programs whose metadata container is not a mapping.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when malformed program metadata raises the
        expected validation error.

    Raises
    ------
    AssertionError
        If invalid program metadata is accepted or mapped incorrectly.

    Notes
    -----
    - Program metadata shape is part of the top-level validation contract.
    """
    program = Program(
        steps=(ReturnStep(value_expr=Literal(value="ok")),),
        metadata=[],
    )

    with pytest.raises(RlmValidationError) as excinfo:
        validate_program(program)

    assert excinfo.value.code is RlmErrorCode.VALIDATION_TYPE_ERROR


def test_validate_step_rejects_unsupported_nodes() -> None:
    """
    Reject unsupported step node instances during validation dispatch.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when unsupported step objects produce the
        expected validation code.

    Raises
    ------
    AssertionError
        If unsupported step objects are accepted or mapped incorrectly.

    Notes
    -----
    - This preserves a stable failure mode for malformed planner output.
    """
    with pytest.raises(RlmValidationError) as excinfo:
        validate_step(object())  # type: ignore[arg-type]

    assert excinfo.value.code is RlmErrorCode.UNSUPPORTED_STEP_NODE
