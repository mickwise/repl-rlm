-- =============================================================================
-- 0005_run_tools.sql
--
-- Purpose
--   Creates the `run_tools` snapshot-membership table linking runs to the tool
--   definitions they can use. This table preserves run-local tool metadata so
--   historical runs do not implicitly depend on later edits to the global
--   `tools` catalog.
--
-- Row semantics
--   One row represents one tool made available to one run, together with the
--   snapshot of tool metadata captured for that run.
--
-- Conventions
--   - The composite key `(run_id, tool_id)` is the durable identity of the
--     run-local capability membership; there is no surrogate association ID.
--   - Snapshot text fields preserve the tool definition visible to the run at
--     association time.
--   - `argument_schema_snapshot` stores a JSON object when present.
--
-- Keys & constraints
--   - Primary key: `(run_id, tool_id)`
--   - Natural keys / uniqueness: the composite key is the only membership key
--   - Checks: non-empty text, allowed tool-kind snapshots, and JSON object
--     checks
--
-- Relationships
--   - `run_id` references `runs(run_id)` with `ON DELETE CASCADE`.
--   - `tool_id` references `tools(tool_id)` with `ON DELETE RESTRICT`.
--
-- Audit & provenance
--   Snapshot columns preserve the exact tool metadata attached to a run so
--   later global tool edits do not rewrite history.
--
-- Performance
--   The composite primary key supports run-local membership lookups, and the
--   secondary index on `tool_id` supports reverse lookups by tool.
--
-- Change management
--   New snapshot attributes should be added additively so older run-tool
--   memberships remain readable and replayable.
-- =============================================================================

CREATE TABLE run_tools (

    -- ===========
    -- Identifiers
    -- ===========

    run_id uuid REFERENCES runs (run_id) ON DELETE CASCADE,
    tool_id uuid REFERENCES tools (tool_id) ON DELETE CASCADE,

    -- ==================
    -- Snapshot Metadata
    -- ==================

    tool_name_snapshot text NOT NULL,
    tool_kind_snapshot text NOT NULL,
    description_snapshot text NOT NULL,
    implementation_ref_snapshot text NOT NULL,
    argument_schema_snapshot jsonb,

    -- ==========
    -- Timestamps
    -- ==========

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT run_tools_pkey PRIMARY KEY (run_id, tool_id),
    CONSTRAINT run_tools_tool_name_snapshot_nonempty_chk
    CHECK (btrim(tool_name_snapshot) <> ''),
    CONSTRAINT run_tools_tool_kind_snapshot_nonempty_chk
    CHECK (btrim(tool_kind_snapshot) <> ''),
    CONSTRAINT run_tools_tool_kind_snapshot_allowed_chk
    CHECK (tool_kind_snapshot IN ('local_python', 'mcp')),
    CONSTRAINT run_tools_description_snapshot_nonempty_chk
    CHECK (btrim(description_snapshot) <> ''),
    CONSTRAINT run_tools_implementation_ref_snapshot_nonempty_chk
    CHECK (btrim(implementation_ref_snapshot) <> ''),
    CONSTRAINT run_tools_argument_schema_snapshot_type_chk
    CHECK (
        argument_schema_snapshot IS NULL
        OR jsonb_typeof(argument_schema_snapshot) = 'object'
    )
);

COMMENT ON TABLE run_tools IS
'Run-local membership and snapshot metadata for
tools available to a specific REPL-RLM run.';

COMMENT ON COLUMN run_tools.run_id IS
'Run that owns this tool membership snapshot.';

COMMENT ON COLUMN run_tools.tool_id IS
'Global tool definition captured by this run-local snapshot.';

COMMENT ON COLUMN run_tools.tool_name_snapshot IS
'Tool name as snapshotted for this run.';

COMMENT ON COLUMN run_tools.tool_kind_snapshot IS
'Tool kind as snapshotted for this run.';

COMMENT ON COLUMN run_tools.description_snapshot IS
'Tool description as snapshotted for this run.';

COMMENT ON COLUMN run_tools.implementation_ref_snapshot IS
'Implementation reference as snapshotted for this run.';

COMMENT ON COLUMN run_tools.argument_schema_snapshot IS
'Optional JSON object argument schema as snapshotted for this run.';

COMMENT ON COLUMN run_tools.created_at IS
'Timestamp when the run-tool snapshot row was created.';

COMMENT ON COLUMN run_tools.updated_at IS
'Timestamp automatically refreshed whenever
the run-tool snapshot row is updated.';

CREATE INDEX run_tools_tool_id_idx ON run_tools (tool_id);

CREATE TRIGGER run_tools_set_updated_at_trg
BEFORE UPDATE ON run_tools
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
