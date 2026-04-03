-- =============================================================================
-- 0003_tools.sql
--
-- Purpose
--   Creates the global `tools` catalog for deterministic host tools available
--   to REPL-RLM runs. This table stores descriptive metadata, implementation
--   references, optional argument schemas, and API-key requirements.
--
-- Row semantics
--   One row represents one globally registered tool definition.
--
-- Conventions
--   - `implementation_ref` stores a host-resolvable reference such as a Python
--     import path or MCP-facing tool reference.
--   - `argument_schema` stores a JSON object when present.
--   - API-key requirements are expressed through the
--     `requires_api_key` / `api_key_env_var` pair.
--
-- Keys & constraints
--   - Primary key: `tool_id`
--   - Natural keys / uniqueness: `tool_name` must be unique
--   - Checks: non-empty text, allowed tool kinds, JSON object checks, and
--     API-key consistency checks
--
-- Relationships
--   - `run_tools` references this table by `tool_id` and snapshots tool fields
--     for run-local execution.
--   - Tool descriptors in planner-facing payloads should correspond to rows in
--     this table or their run-local snapshots.
--
-- Audit & provenance
--   This table captures the mutable global definition of a tool, while
--   run-local snapshot tables preserve the definition used by a specific run.
--
-- Performance
--   The primary key and unique tool-name constraint support catalog lookups by
--   UUID or registry-visible name.
--
-- Change management
--   Tool definitions may evolve over time; run-local snapshot tables are the
--   stable provenance surface for historical executions.
-- =============================================================================

CREATE TABLE tools (

    -- ===========
    -- Identifiers
    -- ===========

    tool_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name text UNIQUE NOT NULL,

    -- ==================
    -- Tool Registration
    -- ==================

    tool_kind text NOT NULL,
    description text NOT NULL,
    implementation_ref text NOT NULL,
    argument_schema jsonb,
    requires_api_key boolean NOT NULL DEFAULT false,
    api_key_env_var text,
    is_enabled boolean NOT NULL DEFAULT true,

    -- ==========
    -- Timestamps
    -- ==========

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT tools_tool_name_nonempty_chk
    CHECK (btrim(tool_name) <> ''),
    CONSTRAINT tools_tool_kind_nonempty_chk
    CHECK (btrim(tool_kind) <> ''),
    CONSTRAINT tools_tool_kind_allowed_chk
    CHECK (tool_kind IN ('local_python', 'mcp')),
    CONSTRAINT tools_description_nonempty_chk
    CHECK (btrim(description) <> ''),
    CONSTRAINT tools_implementation_ref_nonempty_chk
    CHECK (btrim(implementation_ref) <> ''),
    CONSTRAINT tools_argument_schema_type_chk
    CHECK (
        argument_schema IS NULL
        OR jsonb_typeof(argument_schema) = 'object'
    ),
    CONSTRAINT tools_api_key_env_var_nonempty_chk
    CHECK (api_key_env_var IS NULL OR btrim(api_key_env_var) <> ''),
    CONSTRAINT tools_requires_api_key_consistency_chk
    CHECK (
        (
            requires_api_key = true
            AND api_key_env_var IS NOT NULL
            AND btrim(api_key_env_var) <> ''
        )
        OR (
            requires_api_key = false
            AND api_key_env_var IS NULL
        )
    )
);

COMMENT ON TABLE tools IS
'Global catalog of deterministic host tools that can be
exposed to REPL-RLM runs.';

COMMENT ON COLUMN tools.tool_id IS
'Primary key for one global tool definition.';

COMMENT ON COLUMN tools.tool_name IS
'Unique registry-visible tool name.';

COMMENT ON COLUMN tools.tool_kind IS
'Implementation family for the tool definition.';

COMMENT ON COLUMN tools.description IS
'Human-readable description of the tool and its intended use.';

COMMENT ON COLUMN tools.implementation_ref IS
'Host-resolvable implementation reference such as an 
import path or MCP identifier.';

COMMENT ON COLUMN tools.argument_schema IS
'Optional JSON object describing the structured 
argument contract for the tool.';

COMMENT ON COLUMN tools.requires_api_key IS
'Whether the tool requires an API key to be available at execution time.';

COMMENT ON COLUMN tools.api_key_env_var IS
'Environment-variable name holding the required API key when one is needed.';

COMMENT ON COLUMN tools.is_enabled IS
'Whether the tool is currently enabled for use.';

COMMENT ON COLUMN tools.created_at IS
'Timestamp when the tool row was created.';

COMMENT ON COLUMN tools.updated_at IS
'Timestamp automatically refreshed whenever the tool row is updated.';

CREATE TRIGGER tools_set_updated_at_trg
BEFORE UPDATE ON tools
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
