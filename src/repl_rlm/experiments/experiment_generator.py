"""
Purpose
-------
Generate deterministic rolling-based synthetic experiments for the REPL / RLM
runtime. This module exists to define the public experiment dataclass plus the
`generate_*` entrypoints that sample valid gold `Program` ASTs first and only
then render aligned natural-language task prompts.

Key behaviors
-------------
- Builds bounded template-driven DSL programs using the real AST node types
  already supported by the runtime.
- Targets the deterministic structured rolling tool surface directly, not any
  natural-language parsing interface inside the tool layer.
- Mixes honest indexed access into `roll_result.instances` with real
  `ForEachStep` iteration over the `instances` list.
- Renders short English prompts from sampled program metadata after the gold
  program has already been constructed.
- Optionally validates every generated program and optionally runs a
  lightweight deterministic execution check through the real runtime.

Conventions
-----------
- Generation is deterministic under `base_seed` and never relies on global
  random state.
- Template order is fixed so output ordering remains stable across repeated
  calls.
- Generated rolling calls always use explicit structured tool arguments such as
  `dice`, `modifier`, `repeat`, `mode`, and `seed`.
- These experiments are intended to be translated later into
  `RootRlmRequest`-like inputs by placing `prompt_text` into the task-text
  field and using `program` as the gold target.

Downstream usage
----------------
Dataset builders, benchmark scripts, or planner-training pipelines should call
`generate_experiments(...)` or one of the template-specific `generate_*`
functions to obtain deterministic prompt/program pairs.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Dict, List, Tuple

from repl_rlm.experiments.experiment_formatting import (
    format_dice_spec,
    format_int_list,
    format_mode_phrase,
    format_modifier_phrase,
    format_repeat_phrase,
    render_prompt,
)
from repl_rlm.experiments.experiment_types import DiceTerms, TemplateGenerator
from repl_rlm.experiments.experiment_utils import (
    TEMPLATE_ORDER,
    build_roll_args,
    experiment_seed,
    indexed_instance_total_expr,
    program_metadata,
    resolve_template_names,
    roll_instances_expr,
    roll_total_bounds,
    sample_dice_terms,
    sample_mode,
    tool_seed,
)
from repl_rlm.experiments.experiment_validation import (
    assert_no_running_event_loop,
    execute_generated_programs,
    require_int,
    validate_generated_program,
)
from repl_rlm.repl.expressions.expressions import (
    AlgebraicExpr,
    AlgebraicOperator,
    ComparisonExpr,
    ComparisonOperator,
    FieldAccessExpr,
    ListExpr,
    Literal,
    Ref,
    TaskRef,
)
from repl_rlm.repl.steps.steps import (
    AssignmentStep,
    ForEachStep,
    IfStep,
    JoinStep,
    Program,
    ReturnStep,
    SpawnStep,
    ToolCallStep,
)


@dataclass(frozen=True)
class GeneratedExperiment:
    """
    Purpose
    -------
    Represent one deterministic synthetic prompt/program pair for the REPL /
    RLM system.

    Key behaviors
    -------------
    - Carries a stable experiment identifier derived from the template and
      deterministic seed.
    - Carries the template family name used to construct the program.
    - Carries the prompt text rendered from the sampled gold program.
    - Carries the gold `Program` AST and compact experiment metadata.

    Parameters
    ----------
    experiment_id : str
        Stable identifier for the generated experiment.
    template_name : str
        Template family used to construct the experiment.
    seed : int
        Deterministic experiment seed derived from `base_seed`.
    prompt_text : str
        Natural-language task prompt rendered from the sampled program.
    program : Program
        Gold DSL program corresponding to the prompt.
    metadata : Mapping[str, str]
        Compact experiment metadata useful for later filtering and analysis.

    Attributes
    ----------
    experiment_id : str
        Stable identifier for the generated experiment.
    template_name : str
        Template family used to construct the experiment.
    seed : int
        Deterministic experiment seed derived from `base_seed`.
    prompt_text : str
        Natural-language task prompt rendered from the sampled program.
    program : Program
        Gold DSL program corresponding to the prompt.
    metadata : Mapping[str, str]
        Compact experiment metadata useful for later filtering and analysis.

    Notes
    -----
    - `prompt_text` is rendered after the program is sampled; prompt text does
      not drive program generation.
    - Metadata is intentionally string-only so it can be serialized or logged
      easily by downstream tooling.
    """

    experiment_id: str
    template_name: str
    seed: int
    prompt_text: str
    program: Program
    metadata: Mapping[str, str]


def generate_single_tool_return(
    rng: random.Random,
    experiment_id: str,
    experiment_seed_value: int,
    tool_name: str,
) -> Tuple[Program, Dict[str, str]]:
    """
    Generate the `single_tool_return` experiment family.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    experiment_id : str
        Stable experiment identifier.
    experiment_seed_value : int
        Deterministic experiment seed.
    tool_name : str
        Registered runtime tool name used for tool calls.

    Returns
    -------
    Tuple[Program, Dict[str, str]]
        Generated program plus compact string metadata for prompt rendering and
        later filtering.

    Raises
    ------
    None

    Notes
    -----
    - This is the simplest valid program family: one structured tool call and
      one return.
    """
    dice_terms: DiceTerms = sample_dice_terms(rng)
    modifier: int = rng.randint(-1, 3)
    repeat: int = rng.choice((1, 2, 3))
    mode: str = sample_mode(rng, dice_terms)

    program: Program = Program(
        steps=(
            ToolCallStep(
                tool_name=tool_name,
                args=build_roll_args(
                    dice=dice_terms,
                    modifier=modifier,
                    repeat=repeat,
                    mode=mode,
                    seed=tool_seed(experiment_seed_value, 1),
                ),
                binding_target="roll_result",
            ),
            ReturnStep(value_expr=Ref(name="roll_result")),
        ),
        metadata=program_metadata(
            experiment_id=experiment_id,
            template_name="single_tool_return",
            seed=experiment_seed_value,
            tool_name=tool_name,
        ),
    )

    return program, {
        "tool_name": tool_name,
        "mode": mode,
        "dice_spec": format_dice_spec(dice_terms),
        "modifier": str(modifier),
        "modifier_phrase": format_modifier_phrase(modifier),
        "repeat": str(repeat),
        "repeat_phrase": format_repeat_phrase(repeat),
        "mode_phrase": format_mode_phrase(mode),
    }


def generate_tool_assign_if(
    rng: random.Random,
    experiment_id: str,
    experiment_seed_value: int,
    tool_name: str,
) -> Tuple[Program, Dict[str, str]]:
    """
    Generate the `tool_assign_if` experiment family.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    experiment_id : str
        Stable experiment identifier.
    experiment_seed_value : int
        Deterministic experiment seed.
    tool_name : str
        Registered runtime tool name used for tool calls.

    Returns
    -------
    Tuple[Program, Dict[str, str]]
        Generated program plus compact string metadata for prompt rendering and
        later filtering.

    Raises
    ------
    None

    Notes
    -----
    - This family exercises indexed access into the rolling result structure
      using a sampled safe instance index.
    """
    dice_terms: DiceTerms = sample_dice_terms(rng)
    modifier: int = rng.randint(-1, 2)
    repeat: int = rng.choice((2, 3, 4))
    selected_index: int = rng.randrange(repeat)
    mode: str = sample_mode(rng, dice_terms)
    minimum_total, maximum_total = roll_total_bounds(dice_terms, modifier)
    threshold: int = rng.randint(minimum_total, max(minimum_total, maximum_total - 1))

    program = Program(
        steps=(
            AssignmentStep(
                value_expr=Literal(value=selected_index),
                binding_target="selected_index",
            ),
            ToolCallStep(
                tool_name=tool_name,
                args=build_roll_args(
                    dice=dice_terms,
                    modifier=modifier,
                    repeat=repeat,
                    mode=mode,
                    seed=tool_seed(experiment_seed_value, 1),
                ),
                binding_target="roll_result",
            ),
            AssignmentStep(
                value_expr=indexed_instance_total_expr(
                    result_name="roll_result",
                    index_expr=Ref(name="selected_index"),
                ),
                binding_target="selected_total",
            ),
            IfStep(
                condition=ComparisonExpr(
                    lhs_expr=Ref(name="selected_total"),
                    rhs_expr=Literal(value=threshold),
                    operator=ComparisonOperator.GREATER_THAN,
                ),
                then_steps=(ReturnStep(value_expr=Literal(value="high")),),
                else_steps=(ReturnStep(value_expr=Literal(value="low")),),
            ),
        ),
        metadata=program_metadata(
            experiment_id=experiment_id,
            template_name="tool_assign_if",
            seed=experiment_seed_value,
            tool_name=tool_name,
        ),
    )

    return program, {
        "tool_name": tool_name,
        "mode": mode,
        "dice_spec": format_dice_spec(dice_terms),
        "modifier": str(modifier),
        "modifier_phrase": format_modifier_phrase(modifier),
        "repeat": str(repeat),
        "repeat_phrase": format_repeat_phrase(repeat),
        "mode_phrase": format_mode_phrase(mode),
        "selected_index": str(selected_index),
        "threshold": str(threshold),
    }


def generate_two_step_branch(
    rng: random.Random,
    experiment_id: str,
    experiment_seed_value: int,
    tool_name: str,
) -> Tuple[Program, Dict[str, str]]:
    """
    Generate the `two_step_branch` experiment family.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    experiment_id : str
        Stable experiment identifier.
    experiment_seed_value : int
        Deterministic experiment seed.
    tool_name : str
        Registered runtime tool name used for tool calls.

    Returns
    -------
    Tuple[Program, Dict[str, str]]
        Generated program plus compact string metadata for prompt rendering and
        later filtering.

    Raises
    ------
    None

    Notes
    -----
    - Both branches perform distinct follow-up roll actions, while the branch
      condition uses a sampled safe indexed access into the initial result.
    """
    first_dice_terms: DiceTerms = sample_dice_terms(rng)
    first_modifier: int = rng.randint(-1, 2)
    first_repeat: int = rng.choice((2, 3, 4))
    selected_index: int = rng.randrange(first_repeat)
    first_mode: str = sample_mode(rng, first_dice_terms)
    minimum_total, maximum_total = roll_total_bounds(first_dice_terms, first_modifier)
    threshold: int = rng.randint(minimum_total, max(minimum_total, maximum_total - 1))

    then_dice_terms: DiceTerms = sample_dice_terms(rng, include_d20=False)
    else_dice_terms: DiceTerms = sample_dice_terms(rng, include_d20=False)
    then_modifier: int = rng.randint(0, 3)
    else_modifier: int = rng.randint(-1, 2)
    then_mode: str = sample_mode(rng, then_dice_terms)
    else_mode: str = sample_mode(rng, else_dice_terms)

    program = Program(
        steps=(
            AssignmentStep(
                value_expr=Literal(value=selected_index),
                binding_target="selected_index",
            ),
            ToolCallStep(
                tool_name=tool_name,
                args=build_roll_args(
                    dice=first_dice_terms,
                    modifier=first_modifier,
                    repeat=first_repeat,
                    mode=first_mode,
                    seed=tool_seed(experiment_seed_value, 1),
                ),
                binding_target="initial_roll",
            ),
            AssignmentStep(
                value_expr=indexed_instance_total_expr(
                    result_name="initial_roll",
                    index_expr=Ref(name="selected_index"),
                ),
                binding_target="initial_total",
            ),
            IfStep(
                condition=ComparisonExpr(
                    lhs_expr=Ref(name="initial_total"),
                    rhs_expr=Literal(value=threshold),
                    operator=ComparisonOperator.GREATER_THAN,
                ),
                then_steps=(
                    ToolCallStep(
                        tool_name=tool_name,
                        args=build_roll_args(
                            dice=then_dice_terms,
                            modifier=then_modifier,
                            repeat=1,
                            mode=then_mode,
                            seed=tool_seed(experiment_seed_value, 2),
                        ),
                        binding_target="branch_roll",
                    ),
                    ReturnStep(value_expr=Ref(name="branch_roll")),
                ),
                else_steps=(
                    ToolCallStep(
                        tool_name=tool_name,
                        args=build_roll_args(
                            dice=else_dice_terms,
                            modifier=else_modifier,
                            repeat=1,
                            mode=else_mode,
                            seed=tool_seed(experiment_seed_value, 3),
                        ),
                        binding_target="branch_roll",
                    ),
                    ReturnStep(value_expr=Ref(name="branch_roll")),
                ),
            ),
        ),
        metadata=program_metadata(
            experiment_id=experiment_id,
            template_name="two_step_branch",
            seed=experiment_seed_value,
            tool_name=tool_name,
        ),
    )

    return program, {
        "tool_name": tool_name,
        "threshold": str(threshold),
        "selected_index": str(selected_index),
        "first_dice_spec": format_dice_spec(first_dice_terms),
        "first_modifier_phrase": format_modifier_phrase(first_modifier),
        "first_repeat_phrase": format_repeat_phrase(first_repeat),
        "first_mode_phrase": format_mode_phrase(first_mode),
        "then_dice_spec": format_dice_spec(then_dice_terms),
        "then_modifier_phrase": format_modifier_phrase(then_modifier),
        "then_mode_phrase": format_mode_phrase(then_mode),
        "else_dice_spec": format_dice_spec(else_dice_terms),
        "else_modifier_phrase": format_modifier_phrase(else_modifier),
        "else_mode_phrase": format_mode_phrase(else_mode),
    }


def generate_foreach_literal(
    rng: random.Random,
    experiment_id: str,
    experiment_seed_value: int,
    tool_name: str,
) -> Tuple[Program, Dict[str, str]]:
    """
    Generate the `foreach_literal` experiment family.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    experiment_id : str
        Stable experiment identifier.
    experiment_seed_value : int
        Deterministic experiment seed.
    tool_name : str
        Registered runtime tool name used for tool calls.

    Returns
    -------
    Tuple[Program, Dict[str, str]]
        Generated program plus compact string metadata for prompt rendering and
        later filtering.

    Raises
    ------
    None

    Notes
    -----
    - The loop variable is used directly as the tool modifier so iteration is
      semantically meaningful.
    """
    dice_terms: DiceTerms = sample_dice_terms(rng, include_d20=False)
    mode: str = sample_mode(rng, dice_terms)
    modifiers: Tuple[int] = tuple(sorted(rng.sample((0, 1, 2, 3, 4), k=rng.choice((2, 3, 4)))))

    program = Program(
        steps=(
            ForEachStep(
                iterable_expr=ListExpr(
                    values=tuple(Literal(value=modifier) for modifier in modifiers)
                ),
                loop_var_name="modifier",
                body_steps=(
                    ToolCallStep(
                        tool_name=tool_name,
                        args=build_roll_args(
                            dice=dice_terms,
                            modifier=Ref(name="modifier"),
                            repeat=1,
                            mode=mode,
                            seed=AlgebraicExpr(
                                lhs_expr=Literal(value=tool_seed(experiment_seed_value, 10)),
                                rhs_expr=Ref(name="modifier"),
                                operator=AlgebraicOperator.ADD,
                            ),
                        ),
                        binding_target="loop_result",
                    ),
                ),
            ),
            ReturnStep(value_expr=Ref(name="loop_result")),
        ),
        metadata=program_metadata(
            experiment_id=experiment_id,
            template_name="foreach_literal",
            seed=experiment_seed_value,
            tool_name=tool_name,
        ),
    )

    return program, {
        "tool_name": tool_name,
        "mode": mode,
        "dice_spec": format_dice_spec(dice_terms),
        "mode_phrase": format_mode_phrase(mode),
        "modifier_list": format_int_list(modifiers),
        "loop_length": str(len(modifiers)),
    }


def generate_simple_aggregation(
    rng: random.Random,
    experiment_id: str,
    experiment_seed_value: int,
    tool_name: str,
) -> Tuple[Program, Dict[str, str]]:
    """
    Generate the `simple_aggregation` experiment family.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    experiment_id : str
        Stable experiment identifier.
    experiment_seed_value : int
        Deterministic experiment seed.
    tool_name : str
        Registered runtime tool name used for tool calls.

    Returns
    -------
    Tuple[Program, Dict[str, str]]
        Generated program plus compact string metadata for prompt rendering and
        later filtering.

    Raises
    ------
    None

    Notes
    -----
    - This family is the canonical `ForEachStep`-over-tool-output template: it
      iterates over `roll_result.instances` and sums each instance total.
    """
    dice_terms: DiceTerms = sample_dice_terms(rng, include_d20=False)
    modifier: int = rng.randint(-1, 2)
    repeat: int = rng.choice((2, 3, 4))
    mode: str = sample_mode(rng, dice_terms)

    program = Program(
        steps=(
            AssignmentStep(
                value_expr=Literal(value=0),
                binding_target="running_total",
            ),
            ToolCallStep(
                tool_name=tool_name,
                args=build_roll_args(
                    dice=dice_terms,
                    modifier=modifier,
                    repeat=repeat,
                    mode=mode,
                    seed=tool_seed(experiment_seed_value, 20),
                ),
                binding_target="roll_result",
            ),
            ForEachStep(
                iterable_expr=roll_instances_expr("roll_result"),
                loop_var_name="instance",
                body_steps=(
                    AssignmentStep(
                        value_expr=FieldAccessExpr(
                            base_expr=Ref(name="instance"),
                            field_name="total",
                        ),
                        binding_target="current_total",
                    ),
                    AssignmentStep(
                        value_expr=AlgebraicExpr(
                            lhs_expr=Ref(name="running_total"),
                            rhs_expr=Ref(name="current_total"),
                            operator=AlgebraicOperator.ADD,
                        ),
                        binding_target="running_total",
                    ),
                ),
            ),
            ReturnStep(value_expr=Ref(name="running_total")),
        ),
        metadata=program_metadata(
            experiment_id=experiment_id,
            template_name="simple_aggregation",
            seed=experiment_seed_value,
            tool_name=tool_name,
        ),
    )

    return program, {
        "tool_name": tool_name,
        "mode": mode,
        "dice_spec": format_dice_spec(dice_terms),
        "modifier": str(modifier),
        "modifier_phrase": format_modifier_phrase(modifier),
        "repeat": str(repeat),
        "repeat_phrase": format_repeat_phrase(repeat),
        "mode_phrase": format_mode_phrase(mode),
    }


def generate_spawn_child_program(
    *,
    parent_experiment_id: str,
    child_index: int,
    tool_name: str,
    dice_terms: DiceTerms,
    modifier: int,
    repeat: int,
    selected_index: int,
    mode: str,
    seed: int,
) -> Program:
    """
    Build one spawned child program for the `spawn_join` template family.

    Parameters
    ----------
    parent_experiment_id : str
        Stable parent experiment identifier.
    child_index : int
        One-based child index.
    tool_name : str
        Registered runtime tool name used for tool calls.
    dice_terms : Tuple[Tuple[int, int], ...]
        Child roll dice specification.
    modifier : int
        Child roll modifier.
    repeat : int
        Child roll repeat count.
    selected_index : int
        Safe instance index selected from the child roll result.
    mode : str
        Child roll mode string.
    seed : int
        Explicit deterministic seed for the child tool call.

    Returns
    -------
    Program
        Spawnable child program returning one selected roll total.

    Raises
    ------
    None

    Notes
    -----
    - Each child program is fully valid on its own and carries compact string
      metadata derived from the parent experiment.
    """
    child_experiment_id: str = f"{parent_experiment_id}:task_{child_index}"

    return Program(
        steps=(
            AssignmentStep(
                value_expr=Literal(value=selected_index),
                binding_target="selected_index",
            ),
            ToolCallStep(
                tool_name=tool_name,
                args=build_roll_args(
                    dice=dice_terms,
                    modifier=modifier,
                    repeat=repeat,
                    mode=mode,
                    seed=seed,
                ),
                binding_target="roll_result",
            ),
            AssignmentStep(
                value_expr=indexed_instance_total_expr(
                    result_name="roll_result",
                    index_expr=Ref(name="selected_index"),
                ),
                binding_target="selected_total",
            ),
            ReturnStep(value_expr=Ref(name="selected_total")),
        ),
        metadata=program_metadata(
            experiment_id=child_experiment_id,
            template_name="spawn_join",
            seed=seed,
            tool_name=tool_name,
        ),
    )


def generate_spawn_join(
    rng: random.Random,
    experiment_id: str,
    experiment_seed_value: int,
    tool_name: str,
) -> Tuple[Program, Dict[str, str]]:
    """
    Generate the `spawn_join` experiment family.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    experiment_id : str
        Stable experiment identifier.
    experiment_seed_value : int
        Deterministic experiment seed.
    tool_name : str
        Registered runtime tool name used for tool calls.

    Returns
    -------
    Tuple[Program, Dict[str, str]]
        Generated program plus compact string metadata for prompt rendering and
        later filtering.

    Raises
    ------
    None

    Notes
    -----
    - Spawned child programs each return one selected instance total, and the
      parent joins them into a list.
    """
    child_count: int = rng.choice((2, 3))
    child_specs: List[Tuple[str, int, int, str, Program]] = []

    for child_index in range(child_count):
        dice_terms: DiceTerms = sample_dice_terms(rng)
        modifier: int = rng.randint(-1, 2)
        repeat: int = rng.choice((2, 3, 4))
        selected_index: int = rng.randrange(repeat)
        mode: str = sample_mode(rng, dice_terms)
        child_program: Program = generate_spawn_child_program(
            parent_experiment_id=experiment_id,
            child_index=child_index + 1,
            tool_name=tool_name,
            dice_terms=dice_terms,
            modifier=modifier,
            repeat=repeat,
            selected_index=selected_index,
            mode=mode,
            seed=tool_seed(experiment_seed_value, 30 + child_index),
        )
        child_specs.append(
            (
                format_dice_spec(dice_terms),
                repeat,
                selected_index,
                f"{format_modifier_phrase(modifier)}{format_mode_phrase(mode)}",
                child_program,
            )
        )

    spawn_steps: Tuple[SpawnStep] = tuple(
        SpawnStep(
            binding_target=f"task_{index + 1}",
            sub_program=child_program,
        )
        for index, (_, _, _, _, child_program) in enumerate(child_specs)
    )

    program: Program = Program(
        steps=spawn_steps
        + (
            JoinStep(
                tasks_ref=tuple(TaskRef(name=f"task_{index + 1}") for index in range(child_count)),
                binding_target="joined_totals",
            ),
            ReturnStep(value_expr=Ref(name="joined_totals")),
        ),
        metadata=program_metadata(
            experiment_id=experiment_id,
            template_name="spawn_join",
            seed=experiment_seed_value,
            tool_name=tool_name,
        ),
    )

    spawn_specs = ", ".join(
        f"{dice_spec} {format_repeat_phrase(repeat)} at index {selected_index}{suffix}"
        for dice_spec, repeat, selected_index, suffix, _ in child_specs
    )
    return program, {
        "tool_name": tool_name,
        "spawn_count": str(child_count),
        "spawn_specs": spawn_specs,
    }


def generate_experiments(
    base_seed: int,
    count_per_template: int,
    include_template_names: Tuple[str, ...] | None = None,
    tool_name: str = "roll",
    validate_generated_programs: bool = True,
    execution_check: bool = False,
) -> Tuple[GeneratedExperiment, ...]:
    """
    Generate a deterministic batch of rolling-based prompt/program pairs.

    Parameters
    ----------
    base_seed : int
        Base seed controlling deterministic template parameter sampling.
    count_per_template : int
        Number of experiments to generate for each included template family.
    include_template_names : Tuple[str, ...] | None
        Optional explicit subset of template families to include.
    tool_name : str
        Registered runtime tool name used in generated `ToolCallStep`s.
    validate_generated_programs : bool
        Whether to run `validate_program` on each generated program before
        returning it.
    execution_check : bool
        Whether to execute each generated program through the real runtime
        using the deterministic rolling tool.

    Returns
    -------
    Tuple[GeneratedExperiment, ...]
        Deterministically generated experiments in stable template order.

    Raises
    ------
    TypeError
        When one or more public arguments have the wrong type.
    ValueError
        When one or more public arguments violate simple invariants.
    RuntimeError
        When `execution_check=True` is used from inside an active event loop.

    Notes
    -----
    - Programs are always constructed first and prompts are rendered second.
    - Generation order is stable across repeated calls with the same inputs.
    - Execution checking uses the real runtime and rolling tool but does not
      store expected outputs in the returned experiments.
    """
    validated_base_seed: int = require_int(base_seed, "base_seed")
    validated_count_per_template: int = require_int(count_per_template, "count_per_template")
    if validated_count_per_template < 1:
        raise ValueError("count_per_template must be >= 1.")
    if not isinstance(tool_name, str):
        raise TypeError("tool_name must be a string.")
    if not tool_name.strip():
        raise ValueError("tool_name must be a non-empty string.")

    template_names: Tuple[str, ...] = resolve_template_names(include_template_names)
    template_generators: Dict[str, TemplateGenerator] = {
        "single_tool_return": generate_single_tool_return,
        "tool_assign_if": generate_tool_assign_if,
        "two_step_branch": generate_two_step_branch,
        "foreach_literal": generate_foreach_literal,
        "simple_aggregation": generate_simple_aggregation,
        "spawn_join": generate_spawn_join,
    }

    experiments: List[GeneratedExperiment] = []

    for template_name in template_names:
        template_index: int = TEMPLATE_ORDER.index(template_name)
        template_generator: TemplateGenerator = template_generators[template_name]

        for sample_index in range(validated_count_per_template):
            generated_seed: int = experiment_seed(
                base_seed=validated_base_seed,
                template_index=template_index,
                sample_index=sample_index,
            )
            experiment_id: str = f"{template_name}-{sample_index:04d}-{generated_seed}"
            experiment_rng: random.Random = random.Random(generated_seed)
            program, template_metadata = template_generator(
                experiment_rng,
                experiment_id,
                generated_seed,
                tool_name,
            )

            if validate_generated_programs:
                validate_generated_program(program)

            metadata: Dict[str, str] = {
                "tool_name": tool_name,
                "validation": str(validate_generated_programs),
                "execution_check": str(execution_check),
                **template_metadata,
            }
            experiments.append(
                GeneratedExperiment(
                    experiment_id=experiment_id,
                    template_name=template_name,
                    seed=generated_seed,
                    prompt_text=render_prompt(template_name, metadata),
                    program=program,
                    metadata=metadata,
                )
            )

    generated_experiments: Tuple[GeneratedExperiment] = tuple(experiments)

    if execution_check:
        assert_no_running_event_loop()
        asyncio.run(
            execute_generated_programs(
                experiments=generated_experiments,
                tool_name=tool_name,
            )
        )

    return generated_experiments
