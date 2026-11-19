-- =============================================================================
-- HostelCare — Managed PostgreSQL Least-Privilege Setup (Neon / Managed PG)
-- =============================================================================
-- Run ONCE in your managed PostgreSQL SQL console (e.g., Neon SQL Editor) or
-- via psql as your provisioned database owner role (e.g., neondb_owner).
--
-- NEVER commit real passwords to version control. Set the runtime password ONLY
-- in the live database console when executing this script.
--
-- Privilege Separation Preserved:
--   * Provisioned owner (e.g., neondb_owner): used ONLY for `MIGRATION_DATABASE_URL`
--     when running `flask --app wsgi db upgrade`.
--   * Runtime role (`hostelcare_app`): used by `DATABASE_URL` in Gunicorn/Flask.
--     Cannot create/alter/drop objects, cannot access `alembic_version`, holds
--     zero DELETE grants across all 21 tables, and has explicit column UPDATEs.
-- =============================================================================

-- 1. Create restricted runtime role `hostelcare_app` if missing
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hostelcare_app') THEN
        CREATE ROLE hostelcare_app
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
            PASSWORD 'REPLACE_WITH_STRONG_APP_PASSWORD';
        RAISE NOTICE 'Created role hostelcare_app';
    ELSE
        RAISE NOTICE 'Role hostelcare_app already exists';
    END IF;
END
$$;

-- 2. Install required extension for room_allocations exclusion constraints
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 3. Restrict schema `public` so `hostelcare_app` can use objects but never DDL
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM hostelcare_app;
GRANT USAGE ON SCHEMA public TO hostelcare_app;

-- 4. Next step (from local machine or Render Shell after setting env vars):
--    Set DB_MIGRATION_ROLE=<your_owner_role> (e.g. neondb_owner)
--    Set DB_APP_ROLE=hostelcare_app
--    Set MIGRATION_DATABASE_URL=postgresql+psycopg://<owner>:<pwd>@<host>/<db>?sslmode=require
--    Set DATABASE_URL=postgresql+psycopg://hostelcare_app:<pwd>@<host>/<db>?sslmode=require
--    Run: flask --app wsgi db upgrade
--    Run: flask --app wsgi create-admin --email <admin-email> --name "<Warden Name>"
