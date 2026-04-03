-- =============================================================================
-- 0000_shared.sql
--
-- Purpose
--   Creates shared database primitives used by the first REPL-RLM schema
--   slice. This migration enables UUID generation through `pgcrypto` and
--   defines one reusable trigger function for maintaining `updated_at`.
--
-- Row semantics
--   This migration does not create a row-bearing table. It installs shared
--   database objects that later tables depend on.
--
-- Conventions
--   - Shared objects are created in `public` because the current schema slice
--     does not introduce a custom schema namespace.
--   - The `set_updated_at()` trigger function always overwrites
--     `NEW.updated_at` with `now()` during row updates.
--   - UUID primary keys in downstream tables should use `gen_random_uuid()`.
--
-- Relationships
--   - Downstream tables attach `BEFORE UPDATE` triggers that call
--     `public.set_updated_at()`.
--   - Downstream UUID primary keys depend on `pgcrypto`.
--
-- Audit & provenance
--   This migration establishes only shared infrastructure; table-level audit
--   and provenance semantics are defined in later migrations.
--
-- Performance
--   The trigger function is intentionally tiny and row-local so later updates
--   pay only the cost of assigning one timestamp.
--
-- Change management
--   Shared objects here should remain backward compatible because later
--   migrations and application code may depend on their names directly.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION set_updated_at() IS
'Reusable BEFORE UPDATE trigger function that
overwrites NEW.updated_at with now().';
