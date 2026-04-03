-- =============================================================================
-- 0006_run_llm_functions.sql
--
-- Purpose
--   Creates the `run_llm_functions` snapshot-membership table linking runs to
--   the LLM-backed functions they can use. This table preserves run-local
--   function metadata so historical runs do not implicitly depend on later
--   edits to the global `llm_functions` catalog.
--
-- Row semantics
--   One row represents one LLM-backed function made available to one run,
--   together with the snapshot of function metadata captured for that run.
--
-- Conventions
--   - The composite key `(run_id, llm_function_id)` is the durable identity of
--     the run-local function membership; there is no surrogate association ID.
--   - Snapshot text fields preserve the function definition visible to the run
--     at association time.
--   - `argument_schema_snapshot` stores a JSON object when present.
--
-- Keys & constraints
--   - Primary key: `(run_id, llm_function_id)`
--   - Natural keys / uniqueness: the composite key is the only membership key
--   - Checks: non-empty text, allowed implementation-kind snapshots, and JSON
--     object checks
--
-- Relationships
--   - `run_id` references `runs(run_id)` with `ON DELETE CASCADE`.
--   - `llm_function_id` references `llm_functions(llm_function_id)` with
--     `ON DELETE RESTRICT`.
--
-- Audit & provenance
--   Snapshot columns preserve the exact function metadata attached to a run so
--   later global function edits do not rewrite history.
--
-- Performance
--   The composite primary key supports run-local membership lookups, and the
--   secondary index on `llm_function_id` supports reverse lookups by function.
--
-- Change management
--   New snapshot attributes should be added additively so older run-function
--   memberships remain readable and replayable.
-- =============================================================================

CREATE TABLE run_llm_functions (

    -- ===========
    -- Identifiers
    -- ===========

    run_id uuid REFERENCES runs (run_id) ON DELETE CASCADE,
    llm_function_id uuid REFERENCES llm_functions
    (llm_function_id) ON DELETE RESTRICT,

    -- ==================
    -- Snapshot Metadata
    -- ==================

    function_name_snapshot text NOT NULL,
    implementation_kind_snapshot text NOT NULL,
    description_snapshot text NOT NULL,
    implementation_ref_snapshot text NOT NULL,
    client_name_snapshot text NULL,
    argument_schema_snapshot jsonb NULL,
    returns_child_program_snapshot boolean NOT NULL,

    -- ==========
    -- Timestamps
    -- ==========

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT run_llm_functions_pkey PRIMARY KEY (run_id, llm_function_id),
    CONSTRAINT run_llm_functions_function_name_snapshot_nonempty_chk
    CHECK (btrim(function_name_snapshot) <> ''),
    CONSTRAINT run_llm_functions_implementation_kind_snapshot_nonempty_chk
    CHECK (btrim(implementation_kind_snapshot) <> ''),
    CONSTRAINT run_llm_functions_implementation_kind_snapshot_allowed_chk
    CHECK (implementation_kind_snapshot IN ('baml', 'local_python')),
    CONSTRAINT run_llm_functions_description_snapshot_nonempty_chk
    CHECK (btrim(description_snapshot) <> ''),
    CONSTRAINT run_llm_functions_implementation_ref_snapshot_nonempty_chk
    CHECK (btrim(implementation_ref_snapshot) <> ''),
    CONSTRAINT run_llm_functions_client_name_snapshot_nonempty_chk
    CHECK (client_name_snapshot IS NULL OR btrim(client_name_snapshot) <> ''),
    CONSTRAINT run_llm_functions_argument_schema_snapshot_type_chk
    CHECK (
        argument_schema_snapshot IS NULL
        OR jsonb_typeof(argument_schema_snapshot) = 'object'
    )
);

COMMENT ON TABLE run_llm_functions IS
'Run-local membership and snapshot metadata for LLM-backed
functions available to a specific REPL-RLM run.';

COMMENT ON COLUMN run_llm_functions.run_id IS
'Run that owns this LLM-function membership snapshot.';

COMMENT ON COLUMN run_llm_functions.llm_function_id IS
'Global LLM-function definition captured by this run-local snapshot.';

COMMENT ON COLUMN run_llm_functions.function_name_snapshot IS
'Function name as snapshotted for this run.';

COMMENT ON COLUMN run_llm_functions.implementation_kind_snapshot IS
'Implementation kind as snapshotted for this run.';

COMMENT ON COLUMN run_llm_functions.description_snapshot IS
'Function description as snapshotted for this run.';

COMMENT ON COLUMN run_llm_functions.implementation_ref_snapshot IS
'Implementation reference as snapshotted for this run.';

COMMENT ON COLUMN run_llm_functions.client_name_snapshot IS
'Optional client name as snapshotted for this run.';

COMMENT ON COLUMN run_llm_functions.argument_schema_snapshot IS
'Optional JSON object argument schema as snapshotted for this run.';

COMMENT ON COLUMN run_llm_functions.returns_child_program_snapshot IS
'Whether the snapshotted function returns a child program.';

COMMENT ON COLUMN run_llm_functions.created_at IS
'Timestamp when the run-function snapshot row was created.';

COMMENT ON COLUMN run_llm_functions.updated_at IS
'Timestamp automatically refreshed whenever the
run-function snapshot row is updated.';

CREATE INDEX run_llm_functions_llm_function_id_idx
ON run_llm_functions (llm_function_id);

CREATE TRIGGER run_llm_functions_set_updated_at_trg
BEFORE UPDATE ON run_llm_functions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
