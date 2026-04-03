-- =============================================================================
-- 0004_llm_functions.sql
--
-- Purpose
--   Creates the global `llm_functions` catalog for registered model-backed
--   callable functions available to REPL-RLM runs. This table stores metadata,
--   implementation references, client names, optional argument schemas, and
--   whether a function returns a child program.
--
-- Row semantics
--   One row represents one globally registered LLM-backed function definition.
--
-- Conventions
--   - `implementation_ref` stores either a BAML function name or another
--     host-resolvable function reference.
--   - `client_name` is optional because some local Python functions may not be
--     tied to one named model client.
--   - `returns_child_program` distinguishes plain value-returning calls from
--     recursive child-program generators.
--
-- Keys & constraints
--   - Primary key: `llm_function_id`
--   - Natural keys / uniqueness: `function_name` must be unique
--   - Checks: non-empty text, allowed implementation kinds, JSON object
--     checks, and API-key consistency checks
--
-- Relationships
--   - `run_llm_functions` references this table by `llm_function_id` and
--     snapshots function details for run-local execution.
--   - Planner-visible LLM function descriptors should map to rows in this
--     table or their run-local snapshots.
--
-- Audit & provenance
--   This table captures the mutable global definition of an LLM-backed
--   function, while run-local snapshots preserve the version used for a run.
--
-- Performance
--   The primary key and unique function-name constraint support catalog
--   lookups by UUID or runtime-visible function name.
--
-- Change management
--   New implementation metadata should be added additively so older runs can
--   still be interpreted through their snapshot tables.
-- =============================================================================

CREATE TABLE llm_functions (

    -- ===========
    -- Identifiers
    -- ===========

    llm_function_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    function_name text UNIQUE NOT NULL,

    -- =================
    -- Function Metadata
    -- =================

    implementation_kind text NOT NULL,
    description text NOT NULL,
    implementation_ref text NOT NULL,
    client_name text,
    argument_schema jsonb,
    returns_child_program boolean NOT NULL DEFAULT false,
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

    CONSTRAINT llm_functions_function_name_nonempty_chk
    CHECK (btrim(function_name) <> ''),
    CONSTRAINT llm_functions_implementation_kind_nonempty_chk
    CHECK (btrim(implementation_kind) <> ''),
    CONSTRAINT llm_functions_implementation_kind_allowed_chk
    CHECK (implementation_kind IN ('baml', 'local_python')),
    CONSTRAINT llm_functions_description_nonempty_chk
    CHECK (btrim(description) <> ''),
    CONSTRAINT llm_functions_implementation_ref_nonempty_chk
    CHECK (btrim(implementation_ref) <> ''),
    CONSTRAINT llm_functions_client_name_nonempty_chk
    CHECK (client_name IS NULL OR btrim(client_name) <> ''),
    CONSTRAINT llm_functions_argument_schema_type_chk
    CHECK (
        argument_schema IS NULL
        OR jsonb_typeof(argument_schema) = 'object'
    ),
    CONSTRAINT llm_functions_api_key_env_var_nonempty_chk
    CHECK (api_key_env_var IS NULL OR btrim(api_key_env_var) <> ''),
    CONSTRAINT llm_functions_requires_api_key_consistency_chk
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

COMMENT ON TABLE llm_functions IS
'Global catalog of registered LLM-backed functions available to REPL-RLM runs.';

COMMENT ON COLUMN llm_functions.llm_function_id IS
'Primary key for one global LLM-backed function definition.';

COMMENT ON COLUMN llm_functions.function_name IS
'Unique runtime-visible function name.';

COMMENT ON COLUMN llm_functions.implementation_kind IS
'Implementation family for the function definition.';

COMMENT ON COLUMN llm_functions.description IS
'Human-readable description of the function and its intended use.';

COMMENT ON COLUMN llm_functions.implementation_ref IS
'BAML function name or other host-resolvable implementation reference.';

COMMENT ON COLUMN llm_functions.client_name IS
'Optional named model client associated with this function.';

COMMENT ON COLUMN llm_functions.argument_schema IS
'Optional JSON object describing the structured
argument contract for the function.';

COMMENT ON COLUMN llm_functions.returns_child_program IS
'Whether the function is intended to return a
child program for recursive execution.';

COMMENT ON COLUMN llm_functions.requires_api_key IS
'Whether the function requires an API key to be available at execution time.';

COMMENT ON COLUMN llm_functions.api_key_env_var IS
'Environment-variable name holding the required API key when one is needed.';

COMMENT ON COLUMN llm_functions.is_enabled IS
'Whether the function is currently enabled for use.';

COMMENT ON COLUMN llm_functions.created_at IS
'Timestamp when the function row was created.';

COMMENT ON COLUMN llm_functions.updated_at IS
'Timestamp automatically refreshed whenever the function row is updated.';

CREATE TRIGGER llm_functions_set_updated_at_trg
BEFORE UPDATE ON llm_functions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
