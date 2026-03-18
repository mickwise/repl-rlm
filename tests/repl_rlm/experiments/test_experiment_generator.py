"""
Purpose
-------
Exercise the experiments package and deterministic experiment generator. This
module exists to keep the public package surface, prompt/program determinism,
indexed access patterns, and runtime-backed execution checks stable.

Key behaviors
-------------
- Verifies the explicit experiments package re-exports the public generator
  API.
- Verifies repeated generation with the same seed returns identical outputs.
- Verifies indexed templates use a bound index expression rather than
  hard-coded `instances[0]` access.
- Verifies simple aggregation iterates over `roll_result.instances`.
- Verifies `execution_check=True` still succeeds across all template families.

Conventions
-----------
- Tests assert on real AST structure rather than helper implementation
  details.
- Determinism checks compare IDs, prompts, and program representations.

Downstream usage
----------------
CI runs this module to guard the experiments package API and the current
generator template semantics.
"""

import random
from typing import Tuple

from repl_rlm.experiments import (
    GeneratedExperiment,
    generate_experiments,
    generate_simple_aggregation,
    generate_tool_assign_if,
    generate_two_step_branch,
)
from repl_rlm.experiments.experiment_generator import (
    GeneratedExperiment as DirectGeneratedExperiment,
)
from repl_rlm.experiments.experiment_generator import (
    generate_spawn_join,
)
from repl_rlm.repl.expressions.expressions import FieldAccessExpr, ListIndexExpr, Ref
from repl_rlm.repl.steps.steps import AssignmentStep, ForEachStep, IfStep, JoinStep, SpawnStep


def test_experiments_package_reexports_public_generator_api() -> None:
    """
    Re-export the public generator API from the explicit experiments package.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when the explicit package marker re-exports
        the expected public symbols.

    Raises
    ------
    AssertionError
        If package imports no longer expose the expected public API.

    Notes
    -----
    - This protects the new `experiments/__init__.py` contract.
    """
    assert GeneratedExperiment is DirectGeneratedExperiment
    assert callable(generate_experiments)
    assert callable(generate_tool_assign_if)
    assert callable(generate_simple_aggregation)


def test_generate_experiments_is_deterministic_for_repeated_calls() -> None:
    """
    Return identical IDs, prompts, and program reprs for the same seed.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when repeated generation stays stable.

    Raises
    ------
    AssertionError
        If repeated generation with the same inputs drifts.

    Notes
    -----
    - This pins the generator to explicit seeded sampling rather than global
      random state.
    """
    batch_a: Tuple[GeneratedExperiment, ...] = generate_experiments(
        base_seed=17, count_per_template=1
    )
    batch_b: Tuple[GeneratedExperiment, ...] = generate_experiments(
        base_seed=17, count_per_template=1
    )

    assert [item.experiment_id for item in batch_a] == [item.experiment_id for item in batch_b]
    assert [item.prompt_text for item in batch_a] == [item.prompt_text for item in batch_b]
    assert [repr(item.program) for item in batch_a] == [repr(item.program) for item in batch_b]


def test_indexed_templates_bind_and_use_safe_instance_indices() -> None:
    """
    Use bound safe index expressions instead of hard-coded first-instance access.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when indexed templates bind a safe index and
        use it via `Ref(...)` in `ListIndexExpr`.

    Raises
    ------
    AssertionError
        If indexed templates revert to hard-coded `instances[0]` access or
        sample unsafe indices.

    Notes
    -----
    - This covers the two condition-driven indexed templates directly.
    """
    tool_assign_program, tool_assign_metadata = generate_tool_assign_if(
        random.Random(5),
        "tool-assign-if",
        5,
        "roll",
    )
    two_step_program, _ = generate_two_step_branch(
        random.Random(9),
        "two-step-branch",
        9,
        "roll",
    )

    tool_assign_index_step = tool_assign_program.steps[0]
    tool_assign_total_step = tool_assign_program.steps[2]
    assert isinstance(tool_assign_index_step, AssignmentStep)
    assert isinstance(tool_assign_total_step, AssignmentStep)
    assert int(tool_assign_metadata["selected_index"]) < int(tool_assign_metadata["repeat"])
    assert isinstance(tool_assign_total_step.value_expr, FieldAccessExpr)
    assert isinstance(tool_assign_total_step.value_expr.base_expr, ListIndexExpr)
    assert tool_assign_total_step.value_expr.base_expr.index_expr == Ref(name="selected_index")

    two_step_index_step = two_step_program.steps[0]
    two_step_total_step = two_step_program.steps[2]
    assert isinstance(two_step_index_step, AssignmentStep)
    assert isinstance(two_step_total_step, AssignmentStep)
    assert isinstance(two_step_program.steps[3], IfStep)
    assert isinstance(two_step_total_step.value_expr, FieldAccessExpr)
    assert isinstance(two_step_total_step.value_expr.base_expr, ListIndexExpr)
    assert two_step_total_step.value_expr.base_expr.index_expr == Ref(name="selected_index")


def test_generate_simple_aggregation_iterates_over_roll_instances() -> None:
    """
    Iterate over `roll_result.instances` when building the aggregation template.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when simple aggregation uses a `ForEachStep`
        over the tool output instances list.

    Raises
    ------
    AssertionError
        If simple aggregation stops iterating over tool output instances.

    Notes
    -----
    - This pins the intended “foreach over tool output” behavior directly in
      the generated AST.
    """
    program, metadata = generate_simple_aggregation(
        random.Random(13),
        "simple-aggregation",
        13,
        "roll",
    )

    assert int(metadata["repeat"]) >= 2
    assert isinstance(program.steps[2], ForEachStep)
    assert program.steps[2].iterable_expr == FieldAccessExpr(
        base_expr=Ref(name="roll_result"),
        field_name="instances",
    )


def test_generate_spawn_join_uses_indexed_child_programs() -> None:
    """
    Generate spawned child programs that return selected indexed totals.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when spawned child programs bind an index and
        return a selected instance total.

    Raises
    ------
    AssertionError
        If spawned child programs stop using indexed total extraction.

    Notes
    -----
    - This protects the indexed access pattern inside the concurrency template.
    """
    program, _ = generate_spawn_join(
        random.Random(19),
        "spawn-join",
        19,
        "roll",
    )

    assert isinstance(program.steps[-2], JoinStep)
    first_spawn = program.steps[0]
    assert isinstance(first_spawn, SpawnStep)
    child_steps = first_spawn.sub_program.steps
    assert isinstance(child_steps[0], AssignmentStep)
    assert isinstance(child_steps[2], AssignmentStep)
    assert isinstance(child_steps[2].value_expr, FieldAccessExpr)
    assert isinstance(child_steps[2].value_expr.base_expr, ListIndexExpr)
    assert child_steps[2].value_expr.base_expr.index_expr == Ref(name="selected_index")


def test_generate_experiments_execution_check_succeeds() -> None:
    """
    Execute all generated template families successfully through the real runtime.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test returns nothing when `execution_check=True` succeeds for one
        sample from every template family.

    Raises
    ------
    AssertionError
        If execution checking raises or returns the wrong experiment count.

    Notes
    -----
    - This is a smoke-level test for the real runtime/tool integration path.
    """
    experiments = generate_experiments(
        base_seed=23,
        count_per_template=1,
        execution_check=True,
    )

    assert len(experiments) == 6
