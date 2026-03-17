/// =============================================================================
/// rolling.baml
///
/// Purpose
/// -------
/// Defines typed LLM functions that parse natural-language D&D 5e roll requests
/// into deterministic RollPlan objects executed by the host runtime.
/// This module performs structured parsing only and never generates randomness.
///
/// Key behaviors
/// -------------
/// - Converts free-form roll requests into a strictly typed RollPlan schema.
/// - Encodes 5e dice semantics including advantage, flat modifiers, and repeats.
/// - Does NOT execute dice rolls or produce narrative output.
/// - Produces no side effects; execution happens in host application code.
///
/// Conventions
/// -----------
/// - Output must be strictly machine-parseable and conform to schema.
/// - No narrative text is allowed in outputs.
/// - Unspecified modifiers default to 0.
/// - Unspecified repeat defaults to 1.
/// - Advantage/disadvantage applies only to d20 terms.
/// - Flat modifiers apply once per roll instance.
///
/// Downstream usage
/// ----------------
/// Host code calls Roll(...), receives a RollPlan, executes RNG deterministically,
/// logs structured results, and formats user-facing summaries.
///
/// Notes
/// -----
/// - Designed for use with a structured-output capable LLM client.
/// - Ambiguous inputs should resolve to the simplest valid interpretation.
/// - All randomness and persistence must be handled outside this module.
///
/// =============================================================================


enum RollMode {
  /// RollMode
  ///
  /// Purpose
  /// -------
  /// Represents how a d20 roll should be resolved under D&D 5e rules.
  ///
  /// Fields
  /// ------
  /// - NORMAL: single d20 roll.
  /// - ADVANTAGE: roll two d20 and keep the higher.
  /// - DISADVANTAGE: roll two d20 and keep the lower.
  ///
  /// Invariants
  /// ----------
  /// - Only meaningful if at least one DiceTerm has sides=20.
  ///
  /// Notes
  /// -----
  /// Host runtime is responsible for enforcing advantage mechanics.

  NORMAL
  ADVANTAGE
  DISADVANTAGE
}


class DiceTerm {
  /// DiceTerm
  /// Purpose
  /// -------
  /// Represents a single dice term NdS (e.g., 2d6).
  ///
  /// Fields
  /// ------
  /// - count: number of dice (>= 1)
  /// - sides: number of sides per die (>= 2)
  ///
  /// Invariants
  /// ----------
  /// - count must be >= 1.
  /// - sides must be >= 2.
  ///
  /// Notes
  /// -----
  /// Multiple DiceTerm entries may be combined within a RollPlan.

  count int
  sides int
}


class RollPlan {
  /// RollPlan
  ///
  /// Purpose
  /// -------
  /// Encodes a fully specified, deterministic dice execution plan that can be
  /// executed by host runtime code.
  ///
  /// Fields
  /// ------
  /// - dice: list of DiceTerm entries defining all dice rolled per instance.
  /// - modifier: flat integer modifier applied once per instance.
  /// - repeat: number of independent instances to execute (>= 1).
  /// - mode: RollMode indicating d20 resolution behavior.
  /// - label: optional short description for UI/logging.
  ///
  /// Invariants
  /// ----------
  /// - repeat must be >= 1.
  /// - modifier applies once per instance, never per die.
  /// - mode affects only d20 terms.
  ///
  /// Notes
  /// -----
  /// RollPlan must be directly executable without additional inference.

  dice DiceTerm[]
  modifier int
  repeat int
  mode RollMode
  label string?
}


function Roll(request: string, context: string?) -> RollPlan {
  /// function Roll(request: string, context: string?) -> RollPlan
  ///
  /// Summary
  /// -------
  /// Parses a natural-language D&D 5e roll request into a deterministic RollPlan.
  ///
  /// Inputs
  /// ------
  /// - request: free-form user roll instruction (e.g., "roll a perception check +5").
  /// - context: optional supplemental information such as character bonuses or
  ///   system state; may be null or empty.
  /// - If context is empty, the function must rely solely on request.
  ///
  /// Output contract
  /// ---------------
  /// - Must output ONLY a RollPlan (no prose).
  /// - Must follow schema exactly (use {{ ctx.output_format }}).
  /// - Must obey all type invariants.
  ///
  /// Failure / ambiguity policy
  /// --------------------------
  /// - If multiple rolls are mentioned, select the single most relevant roll.
  /// - If ambiguous, choose the simplest valid interpretation.
  /// - Never fabricate randomness or narrative results.
  ///
  /// Notes
  /// -----
  /// Host code is responsible for RNG execution, persistence, and formatting.

  client "CustomOllama"
  prompt #"
  You are a Dungeons & Dragons 5e dice assistant.

  Your job: convert the user's request into a RollPlan that can be executed by code.
  Do NOT invent random results. Do NOT output narrative. Output ONLY a RollPlan.

  Rules and modeling requirements:
  1) Treat "modifiers" as FLAT modifiers applied once per instance total (not per die).
  2) Use repeat for multiple separate instances (e.g., Magic Missile darts).
  3) Advantage/disadvantage only applies to d20 rolls. If not relevant, use NORMAL.
  4) Keep it minimal and executable. If the user didn't specify a modifier, use 0.
  5) If the user asks for multiple different rolls, return the single most relevant roll
    (the one explicitly requested). If ambiguous, choose the simplest valid interpretation.

  Examples of correct plans:
  - "roll a perception check with +5 at advantage"
    dice=[{count:1,sides:20}], modifier=5, repeat=1, mode=ADVANTAGE, label="Perception"
  - "greatsword damage with +4 strength"
    dice=[{count:2,sides:6}], modifier=4, repeat=1, mode=NORMAL, label="Greatsword damage"
  - "cast magic missile (3 darts)"
    dice=[{count:1,sides:4}], modifier=1, repeat=3, mode=NORMAL, label="Magic Missile"

  User request:
  {{ request }}

  Optional context (may be null/empty; includes character bonuses, system notes, etc.):
  {{ context }}

  Return output in this exact schema:
  {{ ctx.output_format }}
  "#
}