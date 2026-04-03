-- =============================================================================
-- 0002_turns.sql
--
-- Purpose
--   Creates the `turns` table for one-to-many planner/execution turns under a
--   root run. This table stores the per-turn input shape, generic planner
--   output, and execution summaries or clarification results.
--
-- Row semantics
--   One row represents one ordered turn within one root run.
--
-- Conventions
--   - Turns belong directly to runs through `run_id`.
--   - `planner_output` stores generic normalized planner output and is kept
--     distinct from execution summaries.
--   - `binding_snapshot` stores durable post-turn runtime bindings only when
--     the host decides they are worth persisting.
--
-- Keys & constraints
--   - Primary key: `turn_id`
--   - Natural keys / uniqueness: one unique `turn_index` per `run_id`
--   - Checks: non-empty text, JSON object checks, pending-state checks, and
--     program-result execution-summary checks
--
-- Relationships
--   - `run_id` references `runs(run_id)` with `ON DELETE CASCADE`.
--   - Downstream host code should join turns back to runs by `run_id`.
--
-- Audit & provenance
--   `planner_output`, `execution_summary`, and `binding_snapshot` preserve the
--   durable host-visible state emitted or observed during each turn.
--
-- Performance
--   The unique key and explicit lookup index on `(run_id, turn_index)` support
--   ordered turn retrieval within a run.
--
-- Change management
--   Additional normalized turn payloads should be added additively while
--   preserving the generic `planner_output` and `execution_summary` split.
-- =============================================================================

CREATE TABLE turns (

    -- ===========
    -- Identifiers
    -- ===========

    turn_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid REFERENCES runs (run_id) ON DELETE CASCADE,
    turn_index integer NOT NULL,

    -- ============
    -- Turn Inputs
    -- ============

    input_kind text NOT NULL,
    user_text text,

    -- ===============
    -- Turn Outcomes
    -- ===============

    status text NOT NULL,
    result_kind text,
    planner_output jsonb,
    execution_summary jsonb,
    binding_snapshot jsonb,

    -- ==========
    -- Timestamps
    -- ==========

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT turns_turn_index_min_chk CHECK (turn_index >= 1),
    CONSTRAINT turns_input_kind_nonempty_chk CHECK (btrim(input_kind) <> ''),
    CONSTRAINT turns_input_kind_allowed_chk
    CHECK (
        input_kind IN (
            'user_message',
            'clarification_response',
            'continue'
        )
    ),
    CONSTRAINT turns_user_text_nonempty_chk
    CHECK (user_text IS NULL OR btrim(user_text) <> ''),
    CONSTRAINT turns_status_nonempty_chk CHECK (btrim(status) <> ''),
    CONSTRAINT turns_status_allowed_chk
    CHECK (
        status IN (
            'pending',
            'program_result',
            'clarification_requested',
            'final_answer',
            'cancelled'
        )
    ),
    CONSTRAINT turns_result_kind_nonempty_chk
    CHECK (result_kind IS NULL OR btrim(result_kind) <> ''),
    CONSTRAINT turns_result_kind_allowed_chk
    CHECK (
        result_kind IS NULL
        OR result_kind IN (
            'program_result',
            'final_answer',
            'clarification_requested'
        )
    ),
    CONSTRAINT turns_planner_output_type_chk
    CHECK (
        planner_output IS NULL
        OR jsonb_typeof(planner_output) = 'object'
    ),
    CONSTRAINT turns_execution_summary_type_chk
    CHECK (
        execution_summary IS NULL
        OR jsonb_typeof(execution_summary) = 'object'
    ),
    CONSTRAINT turns_binding_snapshot_type_chk
    CHECK (
        binding_snapshot IS NULL
        OR jsonb_typeof(binding_snapshot) = 'object'
    ),
    CONSTRAINT turns_status_result_kind_consistency_chk
    CHECK (
        (status = 'pending' AND result_kind IS NULL)
        OR (status = 'cancelled' AND result_kind IS NULL)
        OR (status = 'program_result' AND result_kind = 'program_result')
        OR (status = 'final_answer' AND result_kind = 'final_answer')
        OR (
            status = 'clarification_requested'
            AND result_kind = 'clarification_requested'
        )
    ),
    CONSTRAINT turns_execution_summary_result_kind_consistency_chk
    CHECK (
        (execution_summary IS NOT NULL)
        = COALESCE(result_kind = 'program_result', false)
    ),
    CONSTRAINT turns_binding_snapshot_result_kind_consistency_chk
    CHECK (
        binding_snapshot IS NULL
        OR result_kind = 'program_result'
    ),
    CONSTRAINT turns_pending_state_shape_chk
    CHECK (
        status <> 'pending'
        OR (
            planner_output IS NULL
            AND result_kind IS NULL
        )
    ),
    CONSTRAINT turns_run_id_turn_index_key UNIQUE (run_id, turn_index)
);

COMMENT ON TABLE turns IS
'Ordered planner and execution turns that belong to one root REPL-RLM run.';

COMMENT ON COLUMN turns.turn_id IS
'Primary key for one run-local turn.';

COMMENT ON COLUMN turns.run_id IS
'Owning run for this turn.';

COMMENT ON COLUMN turns.turn_index IS
'One-based turn order within the owning run.';

COMMENT ON COLUMN turns.input_kind IS
'Kind of input that initiated this turn.';

COMMENT ON COLUMN turns.user_text IS
'Optional user-provided text associated with this turn.';

COMMENT ON COLUMN turns.status IS
'Current durable turn status.';

COMMENT ON COLUMN turns.result_kind IS
'Kind of planner result persisted for this turn when present.';

COMMENT ON COLUMN turns.planner_output IS
'Generic normalized planner output object for this turn.';

COMMENT ON COLUMN turns.execution_summary IS
'Host/runtime execution summary for program-result turns.';

COMMENT ON COLUMN turns.binding_snapshot IS
'Durable runtime binding snapshot captured after execution when applicable.';

COMMENT ON COLUMN turns.created_at IS
'Timestamp when the turn row was created.';

COMMENT ON COLUMN turns.updated_at IS
'Timestamp automatically refreshed whenever the turn row is updated.';

CREATE INDEX turns_run_id_turn_index_idx ON turns (run_id, turn_index);

CREATE TRIGGER turns_set_updated_at_trg
BEFORE UPDATE ON turns
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
