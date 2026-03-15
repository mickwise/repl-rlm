# Python

## Module doc:

"""
Purpose
-------
<What this module does and why it exists.>

Key behaviors
-------------
- <List the main operations or responsibilities.>
- <Include any important side effects, like writing to DB.>

Conventions
-----------
- <Assumptions, like timezone, unique keys, batching rules.>
- <Anything that downstream code can safely rely on.>

Downstream usage
----------------
<How other parts of the project should use this module.>
"""

## Function doc:
"""
<One-sentence summary of what the function does.>

Parameters
----------
param1 : <type>
    <Description of param1>
param2 : <type>
    <Description of param2>

Returns
-------
<type>
    <What is returned and under what conditions.>

Raises
------
<ExceptionType>
    <When this error is raised and why.>

Notes
-----
- <Any important implementation details, assumptions, or constraints.>
"""

## Class doc:
"""
Purpose
-------
<What this class represents and why it exists. One or two sentences.>

Key behaviors
-------------
- <Behavior #1>
- <Behavior #2>

Parameters
----------
param1 : <type>
    <Meaning, units, constraints.>
param2 : <type>
    <Meaning, units, constraints.>

Attributes
----------
attr1 : <type>
    <What it stores and when it changes.>
attr2 : <type>
    <What it stores and when it changes.>

Notes
-----
- <Important invariants or performance characteristics.>
- <Thread/process-safety expectations.>
"""


# Bash

## Module doc: 

# =============================================================================
# Name - description
#
# Purpose
#
# Assumptions
#
# Conventions
#
# IAM required (minimum)
#
# Usage
# 
# =============================================================================

## Function doc:

# Name
# -----------------------------
# Purpose
#
# Contract
#
# Effects
#
# Fails
#
# IAM required (minimum)
#
# Notes
#

# PostGres

## Module doc:
-- =============================================================================
-- <filename>.sql
--
-- Purpose
--   <What this table is for and why it exists. One to three sentences.>
--
-- Row semantics
--   <What one row represents. Clarify entity vs. episode vs. fact.>
--
-- Conventions
--   - <Key normalization rules (e.g., UPPER tickers, zero-padded CIKs).>
--   - <Timezone or date span policy (e.g., half-open [start, end)).>
--   - <Immutability/append-only expectations, if any.>
--
-- Keys & constraints
--   - Primary key: <column(s)>
--   - Natural keys / uniqueness: <notes>
--   - Checks: <format/quality guards worth calling out>
--
-- Relationships
--   - <FKs this table owns or is expected to receive in downstream tables.>
--   - <How other tables are expected to join to this one.>
--
-- Audit & provenance
--   <What lineage is (or is not) stored here; where full provenance lives.>
--
-- Performance
--   <Indexes or partitioning choices and the query patterns they serve.>
--
-- Change management
--   <How to extend this schema without breaking downstream (e.g., add-only).>
-- =============================================================================

# BAML

## Module doc:
/// =============================================================================
/// <filename>.baml
///
/// Purpose
/// -------
/// <What this BAML module does and why it exists. One to three sentences.>
/// <E.g., "Defines typed LLM functions that parse natural-language D&D roll requests
/// into deterministic RollPlans executed by the Discord bot runtime.">
///
/// Key behaviors
/// -------------
/// - <What functions in this file do at a high level.>
/// - <What they explicitly do NOT do (e.g., do not generate randomness).>
/// - <Any side effects, if any exist in your setup (usually none; execution happens
///   in your host language).>
///
/// Conventions
/// -----------
/// - Output must be strictly machine-parseable and conform to schema.
/// - No narrative in outputs unless explicitly requested.
/// - Defaulting rules (e.g., unspecified modifiers -> 0; repeat -> 1).
/// - 5e semantics assumptions (e.g., flat modifiers apply once per instance).
///
/// Downstream usage
/// ----------------
/// <How host code should call these functions and what it should do next.>
/// <E.g., "Discord bot calls roll_plan(); host code executes RNG, logs results,
/// updates Postgres state, and posts a summary message.">
///
/// Notes
/// -----
/// - <Model/client configuration expectations if relevant.>
/// - <Known limitations, ambiguous cases, or safety guardrails.>
///
/// =============================================================================


## Class doc:
/// <TypeName>
/// Purpose
/// -------
/// <What this type represents and why it exists. One or two sentences.>
///
/// Fields
/// ------
/// - <field1>: <meaning, units, constraints>
/// - <field2>: <meaning, units, constraints>
///
/// Invariants
/// ----------
/// - <Important invariants you want the model to respect.>
///
/// Notes
/// -----
/// - <Serialization expectations, defaults, etc.>
///

/// Example:
/// DiceTerm
/// Purpose
/// -------
/// Represents a single dice term NdS (e.g., 2d6).
///
/// Fields
/// ------
/// - count: number of dice (>= 1)
/// - sides: number of sides (>= 2)

## Function doc:
/// function <name>(...) -> <ReturnType>
///
/// Summary
/// -------
/// <One sentence: what this function produces and for whom.>
///
/// Inputs
/// ------
/// - <param1>: <what it contains / how it is used>
/// - <param2>: <optional context / constraints>
/// - <Any defaulting behavior if param omitted or empty>
///
/// Output contract
/// ---------------
/// - Must output ONLY a <ReturnType> (no prose) unless explicitly requested.
/// - Must follow schema exactly (use {{ ctx.output_format }}).
/// - Must obey constraints/invariants from types.
///
/// Failure / ambiguity policy
/// --------------------------
/// - <What to do when input is ambiguous: choose simplest valid interpretation,
///   or return a sentinel plan, or require clarifying question if you allow that.>
/// - <If you want a structured error type, document it here.>
///
/// Notes
/// -----
/// - <Examples of inputs and the expected structured outputs.>
/// - <What should be handled by host code instead of BAML.>
///


/// -----------------------------------------------------------------------------
/// Prompt block formatting convention (inside the function body)
/// -----------------------------------------------------------------------------
///
/// 1) Start with role + task
/// 2) Hard rules (what NOT to do)
/// 3) Defaulting rules
/// 4) Examples
/// 5) User input
/// 6) Output schema: {{ ctx.output_format }}
///
/// Keep instructions short, imperative, and testable.
///