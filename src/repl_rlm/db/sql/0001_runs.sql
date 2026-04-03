-- =============================================================================
-- 0001_runs.sql
--
-- Purpose
--   Creates the root `runs` table for one top-level REPL-RLM controller
--   session. This table stores the initial request, root-planner resource
--   descriptors, policy configuration, and coarse run
--   lifecycle state.
--
-- Row semantics
--   One row represents one root RLM run spanning zero or more turns.
--
-- Conventions
--   - `initial_user_text` stores the opening task text for the run.
--   - `resource_descriptors` stores attachment or environment handles for the
--     root planner contract and must remain a JSON array.
--   - `policy` stores host execution policy knobs such as iteration or
--     recursion limits and must remain a JSON object.
--
-- Keys & constraints
--   - Primary key: `run_id`
--   - Natural keys / uniqueness: none beyond the UUID primary key
--   - Checks: non-empty text, JSON shape checks, and cancellation-state
--     consistency checks
--
-- Relationships
--   - `turns`, `run_tools`, and `run_llm_functions` reference this table by
--     `run_id`.
--   - Deleting a run cascades to its turns and run-local capability snapshots
--     in later migrations.
--
-- Audit & provenance
--   This table is the durable home for root input text and resource metadata
--   visible to the root planner across the run.
--
-- Performance
--   The primary key index supports run lookups; lifecycle and time filtering
--   can be extended later if query patterns require dedicated secondary
--   indexes.
--
-- Change management
--   New run-level policy or provenance fields should be added additively so
--   existing run history remains readable.
-- =============================================================================

CREATE TABLE runs (

    -- ===========
    -- Identifiers
    -- ===========

    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ===============
    -- Planner Context
    -- ===============

    initial_user_text text NOT NULL,
    resource_descriptors jsonb NOT NULL DEFAULT '[]'::jsonb,
    policy jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- =========
    -- Lifecycle
    -- =========

    status text NOT NULL,
    cancelled_at timestamptz,
    cancellation_reason text,

    -- ==========
    -- Timestamps
    -- ==========
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT runs_initial_user_text_nonempty_chk
    CHECK (btrim(initial_user_text) <> ''),
    CONSTRAINT runs_status_nonempty_chk
    CHECK (btrim(status) <> ''),
    CONSTRAINT runs_status_allowed_chk
    CHECK (
        status IN (
            'active',
            'waiting_for_clarification',
            'completed',
            'cancelled'
        )
    ),
    CONSTRAINT runs_cancellation_reason_nonempty_chk
    CHECK (cancellation_reason IS NULL OR btrim(cancellation_reason) <> ''),
    CONSTRAINT runs_resource_descriptors_type_chk
    CHECK (jsonb_typeof(resource_descriptors) = 'array'),
    CONSTRAINT runs_policy_type_chk
    CHECK (jsonb_typeof(policy) = 'object'),
    CONSTRAINT runs_cancellation_state_consistency_chk
    CHECK (
        ((status = 'cancelled') = (cancelled_at IS NOT NULL))
        AND ((cancelled_at IS NOT NULL) = (cancellation_reason IS NOT NULL))
    )
);

COMMENT ON TABLE runs IS
'Root REPL-RLM controller runs, including the opening task text,
resource descriptors, policy, and lifecycle state.';

COMMENT ON COLUMN runs.run_id IS
'Primary key for one root REPL-RLM run.';

COMMENT ON COLUMN runs.initial_user_text IS
'Opening task text that started the run.';

COMMENT ON COLUMN runs.resource_descriptors IS
'JSON array of attachment or environment descriptors
from the root planner contract.';

COMMENT ON COLUMN runs.policy IS
'JSON object of run-level execution policy settings
such as iteration or recursion limits.';

COMMENT ON COLUMN runs.status IS
'Current lifecycle status of the run.';

COMMENT ON COLUMN runs.cancelled_at IS
'Timestamp when the run was cancelled, if it was cancelled.';

COMMENT ON COLUMN runs.cancellation_reason IS
'Optional host-supplied reason recorded when the run is cancelled.';

COMMENT ON COLUMN runs.created_at IS
'Timestamp when the run row was created.';

COMMENT ON COLUMN runs.updated_at IS
'Timestamp automatically refreshed whenever the run row is updated.';

CREATE TRIGGER runs_set_updated_at_trg
BEFORE UPDATE ON runs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
