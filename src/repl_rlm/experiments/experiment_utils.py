"""
Purpose
-------
Provide deterministic AST-building, sampling, and template-selection helpers
for experiment generation. This module exists to keep the public generator
module focused on `generate_*` functions while centralizing reusable internal
construction utilities.

Key behaviors
-------------
- Defines the stable template order and template-generator callable shape.
- Builds structured rolling-tool argument objects using the real tool contract.
- Builds indexed and iterable access expressions over rolling-tool results.
- Samples bounded dice specifications and compatible roll modes
  deterministically.
- Derives stable experiment and tool-call seeds.
- Resolves included template names in stable declaration order.

Conventions
-----------
- All helpers in this module are deterministic and side-effect free.
- Generated rolling calls always target the explicit structured tool surface.
- AST helpers construct only real runtime-supported expression nodes.

Downstream usage
----------------
The experiment generator imports these helpers to build valid `Program` ASTs
without duplicating seed handling, tool-argument construction, or expression
assembly logic across template families.
"""

from __future__ import annotations

import random
from typing import Dict, Set, Tuple

from repl_rlm.experiments.experiment_types import DiceTerms
from repl_rlm.repl.expressions.expressions import (
    AlgebraicExpr,
    AtomicType,
    ComparisonExpr,
    Expr,
    FieldAccessExpr,
    ListExpr,
    ListIndexExpr,
    Literal,
    LogicalExpr,
    ObjectExpr,
    Ref,
    TaskRef,
    UnaryExpr,
)
from repl_rlm.tools.rolling.rolling import RollMode

TEMPLATE_ORDER: Tuple[str, ...] = (
    "single_tool_return",
    "tool_assign_if",
    "two_step_branch",
    "foreach_literal",
    "simple_aggregation",
    "spawn_join",
)


def roll_total_bounds(dice_terms: DiceTerms, modifier: int) -> Tuple[int, int]:
    """
    Compute simple inclusive bounds for one repeated roll instance.

    Parameters
    ----------
    dice_terms : Tuple[Tuple[int, int], ...]
        Ordered `(count, sides)` dice terms.
    modifier : int
        Modifier applied once to one roll instance total.

    Returns
    -------
    Tuple[int, int]
        Inclusive minimum and maximum possible totals.

    Raises
    ------
    None

    Notes
    -----
    - Repeat count is intentionally ignored because indexed templates compare
      against one selected instance total, not a combined top-level value.
    """
    minimum: int = sum(count for count, _ in dice_terms) + modifier
    maximum: int = sum(count * sides for count, sides in dice_terms) + modifier
    return minimum, maximum


def as_expr(value: Expr | AtomicType) -> Expr:
    """
    Normalize a literal-or-expression value into an expression node.

    Parameters
    ----------
    value : Expr | AtomicType
        Value to normalize into an expression node.

    Returns
    -------
    Expr
        Existing expression node or wrapped literal expression.

    Raises
    ------
    TypeError
        When the supplied value is neither an existing expression node nor an
        atomic literal value supported by `Literal`.

    Notes
    -----
    - This helper keeps tool-argument construction concise while preserving
      the real AST node surface.
    """
    match value:
        case Literal() | Ref() | TaskRef() | ObjectExpr() | ListExpr():
            return value
        case ComparisonExpr() | AlgebraicExpr() | FieldAccessExpr() | ListIndexExpr():
            return value
        case LogicalExpr() | UnaryExpr():
            return value
        case int() | float() | str() | bool() | None:
            return Literal(value=value)
        case _:
            raise TypeError(f"Unsupported expression-compatible value: {type(value).__name__}")


def tool_seed(generated_experiment_seed: int, call_offset: int) -> int:
    """
    Derive a stable per-tool-call seed from one experiment seed.

    Parameters
    ----------
    generated_experiment_seed : int
        Deterministic seed assigned to the enclosing experiment.
    call_offset : int
        Stable positive offset identifying the tool call within the program.

    Returns
    -------
    int
        Deterministic seed for one tool invocation.

    Raises
    ------
    None

    Notes
    -----
    - Stable offsets prevent multi-call programs from accidentally reusing the
      same roll stream.
    """
    return generated_experiment_seed + (call_offset * 1_000)


def build_roll_args(
    *,
    dice: DiceTerms,
    modifier: Expr | int = 0,
    repeat: Expr | int = 1,
    mode: str = RollMode.NORMAL.value,
    label: str | None = None,
    seed: Expr | int | None = None,
) -> ObjectExpr:
    """
    Build a structured rolling-tool argument object using the real tool shape.

    Parameters
    ----------
    dice : Tuple[Tuple[int, int], ...]
        Ordered dice terms represented as `(count, sides)` tuples.
    modifier : Expr | int
        Expression or literal supplying the roll modifier.
    repeat : Expr | int
        Expression or literal supplying the repeat count.
    mode : str
        Roll mode string compatible with the deterministic rolling tool.
    label : str | None
        Optional structured label passed through to the tool.
    seed : Expr | int | None
        Optional explicit deterministic seed argument.

    Returns
    -------
    ObjectExpr
        Structured tool argument object compatible with `roll(...)`.

    Raises
    ------
    None

    Notes
    -----
    - Argument names match the current deterministic rolling tool exactly.
    - Dice terms are emitted as a list of structured mapping expressions so the
      runtime tool call evaluates to the expected list-of-dicts input.
    """
    fields: Dict[str, Expr] = {
        "dice": ListExpr(
            values=tuple(
                ObjectExpr(
                    fields={
                        "count": Literal(value=count),
                        "sides": Literal(value=sides),
                    }
                )
                for count, sides in dice
            )
        ),
        "modifier": as_expr(modifier),
        "repeat": as_expr(repeat),
        "mode": Literal(value=mode),
    }

    if label is not None:
        fields["label"] = Literal(value=label)
    if seed is not None:
        fields["seed"] = as_expr(seed)

    return ObjectExpr(fields=fields)


def program_metadata(
    experiment_id: str,
    template_name: str,
    seed: int,
    tool_name: str,
) -> Dict[str, str]:
    """
    Build compact string metadata for a generated program root node.

    Parameters
    ----------
    experiment_id : str
        Stable experiment identifier.
    template_name : str
        Template family used to build the program.
    seed : int
        Deterministic experiment seed.
    tool_name : str
        Registered runtime tool name used by the program.

    Returns
    -------
    Dict[str, str]
        Compact string metadata mapping suitable for `Program.metadata`.

    Raises
    ------
    None

    Notes
    -----
    - Program metadata is intentionally minimal and string-only.
    """
    return {
        "experiment_id": experiment_id,
        "template_name": template_name,
        "seed": str(seed),
        "tool_name": tool_name,
    }


def roll_instances_expr(result_name: str) -> FieldAccessExpr:
    """
    Build the expression extracting the `instances` list from a roll result.

    Parameters
    ----------
    result_name : str
        Binding name that stores one rolling-tool result object.

    Returns
    -------
    FieldAccessExpr
        Expression extracting the top-level `instances` field.

    Raises
    ------
    None

    Notes
    -----
    - This helper reflects the real rolling-tool result shape rather than an
      invented convenience field.
    """
    return FieldAccessExpr(
        base_expr=Ref(name=result_name),
        field_name="instances",
    )


def indexed_instance_total_expr(result_name: str, index_expr: Expr) -> FieldAccessExpr:
    """
    Build the expression extracting `instances[index].total`.

    Parameters
    ----------
    result_name : str
        Binding name that stores one rolling-tool result object.
    index_expr : Expr
        Expression selecting which roll instance should be read.

    Returns
    -------
    FieldAccessExpr
        Expression extracting the selected instance total.

    Raises
    ------
    None

    Notes
    -----
    - This helper relies on `ListIndexExpr` so indexed access remains explicit
      and honest in the DSL.
    """
    return FieldAccessExpr(
        base_expr=ListIndexExpr(
            base_expr=roll_instances_expr(result_name),
            index_expr=index_expr,
        ),
        field_name="total",
    )


def sample_dice_terms(
    rng: random.Random,
    *,
    include_d20: bool = True,
) -> DiceTerms:
    """
    Sample one bounded deterministic dice specification from fixed options.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    include_d20 : bool
        Whether d20-containing options should be eligible.

    Returns
    -------
    Tuple[Tuple[int, int], ...]
        Sampled dice terms.

    Raises
    ------
    None

    Notes
    -----
    - Sampling is bounded to readable canonical forms rather than arbitrary
      random AST generation.
    """
    options: Tuple[DiceTerms, ...] = (
        ((1, 4),),
        ((1, 6),),
        ((2, 6),),
        ((1, 8),),
        ((1, 10),),
        ((1, 12),),
        ((1, 6), (1, 4)),
    )
    d20_options: Tuple[DiceTerms, ...] = (
        ((1, 20),),
        ((2, 20),),
    )

    candidate_options: Tuple[DiceTerms, ...] = options + d20_options if include_d20 else options
    return rng.choice(candidate_options)


def sample_mode(
    rng: random.Random,
    dice_terms: DiceTerms,
) -> str:
    """
    Sample a deterministic roll mode compatible with the dice specification.

    Parameters
    ----------
    rng : random.Random
        Seeded RNG used for deterministic sampling.
    dice_terms : Tuple[Tuple[int, int], ...]
        Dice terms to inspect for d20 eligibility.

    Returns
    -------
    str
        Mode string accepted by the deterministic rolling tool.

    Raises
    ------
    None

    Notes
    -----
    - Advantage and disadvantage are sampled only when at least one d20 term
      is present.
    """
    if any(sides == 20 for _, sides in dice_terms):
        return rng.choice(
            (
                RollMode.NORMAL.value,
                RollMode.ADVANTAGE.value,
                RollMode.DISADVANTAGE.value,
            )
        )
    return RollMode.NORMAL.value


def resolve_template_names(include_template_names: Tuple[str, ...] | None) -> Tuple[str, ...]:
    """
    Resolve the effective template set in stable declared order.

    Parameters
    ----------
    include_template_names : Tuple[str, ...] | None
        Optional explicit subset of template names to include.

    Returns
    -------
    Tuple[str, ...]
        Effective template names in fixed generator order.

    Raises
    ------
    TypeError
        When `include_template_names` is neither `None` nor a tuple.
    ValueError
        When an unknown template name is requested.

    Notes
    -----
    - The returned order is always aligned with `TEMPLATE_ORDER` so output
      ordering stays stable even when a subset is requested.
    """
    if include_template_names is None:
        return TEMPLATE_ORDER
    if not isinstance(include_template_names, tuple):
        raise TypeError("include_template_names must be a tuple of template names or None.")

    requested_names: Set[str] = set(include_template_names)
    unknown_names: Set[str] = requested_names.difference(TEMPLATE_ORDER)
    if unknown_names:
        unknown_name = sorted(unknown_names)[0]
        raise ValueError(f"Unsupported template name: {unknown_name}")

    return tuple(
        template_name for template_name in TEMPLATE_ORDER if template_name in requested_names
    )


def experiment_seed(base_seed: int, template_index: int, sample_index: int) -> int:
    """
    Derive a stable experiment seed from base seed, template index, and offset.

    Parameters
    ----------
    base_seed : int
        Public generator base seed.
    template_index : int
        Zero-based index of the template in fixed order.
    sample_index : int
        Zero-based index of the sample within that template family.

    Returns
    -------
    int
        Deterministic per-experiment seed.

    Raises
    ------
    None

    Notes
    -----
    - This seed is independent of sampling order so subset generation remains
      stable.
    """
    return base_seed + (template_index * 10_000) + (sample_index * 101)
