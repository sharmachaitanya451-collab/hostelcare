-- =============================================================================
-- HostelCare - PostgreSQL setup (run ONCE by the database administrator)
-- =============================================================================
-- Run as the postgres superuser, connected to the maintenance database:
--
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -p 5432 `
--       -U postgres -d postgres -f C:\Projects\HostelCare\database\setup_postgres.sql
--
-- PRIVILEGE MODEL
--   hostelcare_owner : owns both databases and their "public" schema. Used ONLY by
--                      Flask-Migrate/Alembic (DDL: create/alter/drop tables).
--   hostelcare_app   : runtime role used by the running Flask app. Can connect and use
--                      the schema, and has ONLY the table privileges that individual
--                      Alembic migrations grant it. Cannot create, alter or drop
--                      objects, and owns nothing.
--   The two roles have separate passwords, are NOINHERIT, and have NO memberships
--   (neither is a member of any role, and no role is a member of either).
--
-- TABLE AND SEQUENCE PRIVILEGES ARE NEVER GRANTED BY THIS SCRIPT
--   * No grants on existing tables/sequences, and NO DEFAULT PRIVILEGES for future
--     tables or sequences. A new table is therefore invisible to hostelcare_app until
--     its own Alembic migration grants access explicitly. This keeps internal tables
--     (above all alembic_version) inaccessible by construction.
--   * Re-running this script cannot restore any privilege a migration has revoked.
--   * The script actively REMOVES any default privileges previously configured for
--     hostelcare_app by earlier versions of this script (section 4); this changes no
--     existing table.
--
--   RULES FOR MIGRATIONS (each application table is granted in its own migration):
--     * Ordinary application table  : GRANT SELECT, INSERT, UPDATE, DELETE ON <table>
--                                     TO hostelcare_app;   (nothing else)
--     * Sequences                   : identity columns need no sequence grant. For any
--                                     standalone sequence or serial column, grant
--                                     USAGE explicitly (and SELECT only if required).
--     * audit_log                   : REVOKE ALL ON audit_log FROM hostelcare_app;
--                                     GRANT SELECT, INSERT ON audit_log TO hostelcare_app;
--                                     (append-only: no UPDATE, DELETE, TRUNCATE,
--                                      REFERENCES, TRIGGER).
--     * alembic_version             : hostelcare_app must hold NO privilege at all (not
--                                     even SELECT). Alembic creates this table itself,
--                                     so migrations do not manage it; the migration
--                                     environment (migrations/env.py) runs
--                                     REVOKE ALL ON alembic_version FROM hostelcare_app
--                                     after every upgrade as a defensive measure.
--   The verification section at the end of this script checks these rules and prints
--   warnings if any is violated.
--
-- HOW EXISTING OBJECTS ARE HANDLED (script is safe to re-run)
--   Pre-flight checks run FIRST and ABORT with an explanation (nothing is changed,
--   no existing role or database is altered) if:
--     * an existing hostelcare_* role is superuser/createdb/createrole/replication/
--       bypassrls, cannot log in, or has INHERIT enabled;
--     * an existing hostelcare_* role has ANY membership (as member or as group);
--     * a HostelCare database already exists with an owner other than hostelcare_owner
--       (ownership is NEVER reassigned automatically);
--     * an existing HostelCare database has explicit privileges granted to any role
--       other than hostelcare_owner / hostelcare_app, or hostelcare_app holds any
--       explicit database privilege other than CONNECT (i.e. CREATE or TEMPORARY).
--   Otherwise: missing roles/databases are created; existing ones are left as they are.
--   The only privilege changes made to an existing HostelCare database are the
--   documented REVOKEs from PUBLIC in section 3 (PUBLIC grants are reported first).
--   The script does NOT claim that only HostelCare roles can connect: section 5 lists
--   every non-superuser role that can actually connect (directly, via PUBLIC, or via
--   membership) and warns about any other than the two HostelCare roles.
--   Nothing here touches postgres, template0/1, or any unrelated role or database.
--   No passwords appear in this file.
--
--   Requires PostgreSQL 17+ (the verification uses the MAINTAIN table privilege);
--   the installed server is 18.4.
-- =============================================================================

\set ON_ERROR_STOP on
\echo '--- HostelCare setup: start ---'

-- -----------------------------------------------------------------------------
-- 1. PRE-FLIGHT CHECKS (read-only; abort on any problem)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    problems text := '';
    r record;
BEGIN
    -- 1a. Attributes of existing roles (expected: LOGIN + NOINHERIT, nothing else).
    FOR r IN
        SELECT rolname,
               concat_ws(', ',
                   CASE WHEN rolsuper       THEN 'SUPERUSER' END,
                   CASE WHEN rolcreatedb    THEN 'CREATEDB' END,
                   CASE WHEN rolcreaterole  THEN 'CREATEROLE' END,
                   CASE WHEN rolreplication THEN 'REPLICATION' END,
                   CASE WHEN rolbypassrls   THEN 'BYPASSRLS' END,
                   CASE WHEN rolinherit     THEN 'INHERIT (expected NOINHERIT)' END,
                   CASE WHEN NOT rolcanlogin THEN 'NOLOGIN (expected LOGIN)' END) AS bad
        FROM pg_roles
        WHERE rolname IN ('hostelcare_owner', 'hostelcare_app')
    LOOP
        IF r.bad <> '' THEN
            problems := problems || format(E'\n  - role %s has unexpected attributes: %s', r.rolname, r.bad);
        END IF;
    END LOOP;

    -- 1b. Memberships: none allowed, in either direction, involving either role.
    FOR r IN
        SELECT g.rolname AS grp, m.rolname AS member
        FROM pg_auth_members am
        JOIN pg_roles g ON g.oid = am.roleid
        JOIN pg_roles m ON m.oid = am.member
        WHERE g.rolname IN ('hostelcare_owner', 'hostelcare_app')
           OR m.rolname IN ('hostelcare_owner', 'hostelcare_app')
    LOOP
        problems := problems || format(E'\n  - unexpected membership: %s is a member of %s', r.member, r.grp);
    END LOOP;

    -- 1c. Existing databases must already be owned by hostelcare_owner.
    FOR r IN
        SELECT d.datname, o.rolname AS owner
        FROM pg_database d JOIN pg_roles o ON o.oid = d.datdba
        WHERE d.datname IN ('hostelcare', 'hostelcare_test')
          AND o.rolname <> 'hostelcare_owner'
    LOOP
        problems := problems || format(E'\n  - database %s is owned by %s, not hostelcare_owner (ownership is never changed automatically)', r.datname, r.owner);
    END LOOP;

    -- 1d. Explicit database privileges to roles other than the two HostelCare roles.
    --     (Grants to PUBLIC are reported below; NULL ACLs yield no rows.)
    FOR r IN
        SELECT d.datname, a.privilege_type, gr.rolname AS grantee
        FROM pg_database d
        CROSS JOIN LATERAL aclexplode(d.datacl) a
        JOIN pg_roles gr ON gr.oid = a.grantee
        WHERE d.datname IN ('hostelcare', 'hostelcare_test')
          AND gr.rolname NOT IN ('hostelcare_owner', 'hostelcare_app')
    LOOP
        problems := problems || format(E'\n  - database %s: explicit %s privilege granted to role %s', r.datname, r.privilege_type, r.grantee);
    END LOOP;

    -- 1e. hostelcare_app may hold only CONNECT (no CREATE / TEMPORARY).
    FOR r IN
        SELECT d.datname, a.privilege_type
        FROM pg_database d
        CROSS JOIN LATERAL aclexplode(d.datacl) a
        JOIN pg_roles gr ON gr.oid = a.grantee
        WHERE d.datname IN ('hostelcare', 'hostelcare_test')
          AND gr.rolname = 'hostelcare_app'
          AND a.privilege_type <> 'CONNECT'
    LOOP
        problems := problems || format(E'\n  - database %s: hostelcare_app has explicit %s privilege (only CONNECT allowed)', r.datname, r.privilege_type);
    END LOOP;

    -- 1f. Report (not abort) privileges currently granted to PUBLIC; section 3 revokes them.
    FOR r IN
        SELECT d.datname, a.privilege_type
        FROM pg_database d
        CROSS JOIN LATERAL aclexplode(d.datacl) a
        WHERE d.datname IN ('hostelcare', 'hostelcare_test') AND a.grantee = 0
    LOOP
        RAISE NOTICE 'Database % has explicit % privilege for PUBLIC; it will be revoked in section 3.', r.datname, r.privilege_type;
    END LOOP;

    IF problems <> '' THEN
        RAISE EXCEPTION E'Pre-flight check failed. NOTHING was changed. Review manually:%\n', problems
            USING HINT = 'Fix or remove the listed items manually, then re-run this script.';
    END IF;

    RAISE NOTICE 'Pre-flight checks passed.';
END
$$;

-- -----------------------------------------------------------------------------
-- 2. ROLES (created only if missing; existing roles are never altered)
--    Both: LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION,
--    NOBYPASSRLS, NOINHERIT. No passwords here.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hostelcare_owner') THEN
        CREATE ROLE hostelcare_owner
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
        RAISE NOTICE 'Created role hostelcare_owner';
    ELSE
        RAISE NOTICE 'Role hostelcare_owner already exists - verified, left unchanged';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hostelcare_app') THEN
        CREATE ROLE hostelcare_app
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
        RAISE NOTICE 'Created role hostelcare_app';
    ELSE
        RAISE NOTICE 'Role hostelcare_app already exists - verified, left unchanged';
    END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- 3. DATABASES owned by hostelcare_owner (created only if missing).
--    CREATE DATABASE cannot run in a DO block, so each statement is generated only
--    when the database is absent and then run with \gexec.
-- -----------------------------------------------------------------------------
SELECT 'CREATE DATABASE hostelcare OWNER hostelcare_owner ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'hostelcare')
\gexec

SELECT 'CREATE DATABASE hostelcare_test OWNER hostelcare_owner ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'hostelcare_test')
\gexec

-- Database-level privileges: remove everything PUBLIC has (CONNECT, CREATE, TEMPORARY),
-- then allow CONNECT for the two HostelCare roles. The runtime role gets no CREATE and
-- no TEMPORARY. These statements only touch the two HostelCare databases.
REVOKE ALL ON DATABASE hostelcare      FROM PUBLIC;
REVOKE ALL ON DATABASE hostelcare_test FROM PUBLIC;
GRANT  CONNECT ON DATABASE hostelcare      TO hostelcare_owner, hostelcare_app;
GRANT  CONNECT ON DATABASE hostelcare_test TO hostelcare_owner, hostelcare_app;

-- -----------------------------------------------------------------------------
-- 4. SCHEMA PRIVILEGES - applied inside EACH database
--    a) Schema "public" is owned by hostelcare_owner (the database owner, verified in
--       pre-flight); PUBLIC is stripped of all access to it.
--    b) hostelcare_app gets USAGE only; CREATE is explicitly revoked.
--    c) NO table or sequence privileges are granted, and NO default privileges are
--       created. The two ALTER DEFAULT PRIVILEGES ... REVOKE statements only remove
--       default grants an earlier version of this script may have set; they affect
--       future objects only and change nothing that already exists.
-- -----------------------------------------------------------------------------
\connect hostelcare

ALTER SCHEMA public OWNER TO hostelcare_owner;
REVOKE ALL    ON SCHEMA public FROM PUBLIC;
GRANT  ALL    ON SCHEMA public TO hostelcare_owner;
GRANT  USAGE  ON SCHEMA public TO hostelcare_app;
REVOKE CREATE ON SCHEMA public FROM hostelcare_app;

ALTER DEFAULT PRIVILEGES FOR ROLE hostelcare_owner IN SCHEMA public
    REVOKE ALL ON TABLES FROM hostelcare_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hostelcare_owner IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM hostelcare_app;

\connect hostelcare_test

ALTER SCHEMA public OWNER TO hostelcare_owner;
REVOKE ALL    ON SCHEMA public FROM PUBLIC;
GRANT  ALL    ON SCHEMA public TO hostelcare_owner;
GRANT  USAGE  ON SCHEMA public TO hostelcare_app;
REVOKE CREATE ON SCHEMA public FROM hostelcare_app;

ALTER DEFAULT PRIVILEGES FOR ROLE hostelcare_owner IN SCHEMA public
    REVOKE ALL ON TABLES FROM hostelcare_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hostelcare_owner IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM hostelcare_app;

-- -----------------------------------------------------------------------------
-- 5. VERIFICATION REPORT (read-only; changes nothing)
-- -----------------------------------------------------------------------------
\connect postgres
\echo '--- Roles (expect login=t, inherit=f, all other flags f) ---'
SELECT rolname, rolcanlogin AS login, rolinherit AS inherit, rolsuper AS super,
       rolcreatedb AS createdb, rolcreaterole AS createrole,
       rolreplication AS repl, rolbypassrls AS bypassrls
FROM pg_roles WHERE rolname IN ('hostelcare_owner', 'hostelcare_app') ORDER BY rolname;

\echo '--- Databases (expect owner = hostelcare_owner) ---'
SELECT d.datname, r.rolname AS owner, pg_encoding_to_char(d.encoding) AS encoding
FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
WHERE d.datname IN ('hostelcare', 'hostelcare_test') ORDER BY d.datname;

\echo '--- Explicit database ACL entries (grantee NULL = PUBLIC) ---'
SELECT d.datname, gr.rolname AS grantee, a.privilege_type
FROM pg_database d
CROSS JOIN LATERAL aclexplode(d.datacl) a
LEFT JOIN pg_roles gr ON gr.oid = a.grantee
WHERE d.datname IN ('hostelcare', 'hostelcare_test')
ORDER BY d.datname, grantee, a.privilege_type;

\echo '--- EFFECTIVE access: non-superuser roles other than the HostelCare roles that can CONNECT, or non-owner roles with CREATE/TEMP (expect 0 rows) ---'
SELECT d.datname, r.rolname,
       has_database_privilege(r.oid, d.oid, 'CONNECT')   AS connect,
       has_database_privilege(r.oid, d.oid, 'CREATE')    AS "create",
       has_database_privilege(r.oid, d.oid, 'TEMPORARY') AS temp
FROM pg_database d CROSS JOIN pg_roles r
WHERE d.datname IN ('hostelcare', 'hostelcare_test')
  AND NOT r.rolsuper
  AND r.rolname <> 'hostelcare_owner'
  AND ( (r.rolname <> 'hostelcare_app' AND has_database_privilege(r.oid, d.oid, 'CONNECT'))
        OR has_database_privilege(r.oid, d.oid, 'CREATE')
        OR has_database_privilege(r.oid, d.oid, 'TEMPORARY') )
ORDER BY d.datname, r.rolname;

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n
    FROM pg_database d CROSS JOIN pg_roles r
    WHERE d.datname IN ('hostelcare', 'hostelcare_test')
      AND NOT r.rolsuper AND r.rolname <> 'hostelcare_owner'
      AND ( (r.rolname <> 'hostelcare_app' AND has_database_privilege(r.oid, d.oid, 'CONNECT'))
            OR has_database_privilege(r.oid, d.oid, 'CREATE')
            OR has_database_privilege(r.oid, d.oid, 'TEMPORARY') );
    IF n > 0 THEN
        RAISE WARNING 'MANUAL REVIEW NEEDED: % unexpected effective database privilege(s) listed above.', n;
    ELSE
        RAISE NOTICE 'No unexpected effective database privileges for non-superuser roles.';
    END IF;
    RAISE NOTICE 'Note: superusers can always connect regardless of grants.';
END
$$;

-- Per-database table checks (tables only exist after migrations; on a fresh install the
-- matrix is empty and the checks are skipped). Privilege checks are EFFECTIVE: they
-- include grants via PUBLIC and column-level grants.
-- Expected: alembic_version -> no privilege at all; audit_log -> SELECT and INSERT only;
-- no table anywhere -> TRUNCATE, REFERENCES, TRIGGER or MAINTAIN for hostelcare_app.
\connect hostelcare
\echo '--- hostelcare: hostelcare_app privileges per table ---'
SELECT c.relname AS "table", pg_get_userbyid(c.relowner) AS owner,
       has_table_privilege('hostelcare_app', c.oid, 'SELECT')     AS sel,
       has_table_privilege('hostelcare_app', c.oid, 'INSERT')     AS ins,
       has_table_privilege('hostelcare_app', c.oid, 'UPDATE')     AS upd,
       has_table_privilege('hostelcare_app', c.oid, 'DELETE')     AS del,
       has_table_privilege('hostelcare_app', c.oid, 'TRUNCATE')   AS trunc,
       has_table_privilege('hostelcare_app', c.oid, 'REFERENCES') AS refs,
       has_table_privilege('hostelcare_app', c.oid, 'TRIGGER')    AS trig,
       has_table_privilege('hostelcare_app', c.oid, 'MAINTAIN')   AS maint
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 1;
DO $$
DECLARE
    p text;
    r record;
    ok boolean := true;
BEGIN
    -- alembic_version: NO privileges whatsoever (table-level or column-level).
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] LOOP
            IF has_table_privilege('hostelcare_app', 'public.alembic_version', p) THEN
                RAISE WARNING 'alembic_version: hostelcare_app has % (must have NO privileges)', p;
                ok := false;
            END IF;
        END LOOP;
        FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','REFERENCES'] LOOP
            IF has_any_column_privilege('hostelcare_app', 'public.alembic_version', p) THEN
                RAISE WARNING 'alembic_version: hostelcare_app has column-level % (must have NO privileges)', p;
                ok := false;
            END IF;
        END LOOP;
        IF ok THEN RAISE NOTICE 'alembic_version: OK (hostelcare_app has no privileges)'; END IF;
    ELSE
        RAISE NOTICE 'alembic_version does not exist yet (migrations not applied)';
    END IF;

    -- audit_log: exactly SELECT and INSERT.
    IF to_regclass('public.audit_log') IS NOT NULL THEN
        ok := true;
        FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] LOOP
            IF has_table_privilege('hostelcare_app', 'public.audit_log', p) <> (p IN ('SELECT','INSERT')) THEN
                RAISE WARNING 'audit_log: hostelcare_app % = % (expected %)', p,
                    has_table_privilege('hostelcare_app', 'public.audit_log', p), p IN ('SELECT','INSERT');
                ok := false;
            END IF;
        END LOOP;
        IF has_any_column_privilege('hostelcare_app', 'public.audit_log', 'UPDATE')
           OR has_any_column_privilege('hostelcare_app', 'public.audit_log', 'REFERENCES') THEN
            RAISE WARNING 'audit_log: hostelcare_app has column-level UPDATE or REFERENCES (must not)';
            ok := false;
        END IF;
        IF ok THEN RAISE NOTICE 'audit_log: OK (append-only: SELECT and INSERT only)'; END IF;
    ELSE
        RAISE NOTICE 'audit_log does not exist yet (migrations not applied)';
    END IF;

    -- Any table: hostelcare_app must never hold these privileges.
    FOR r IN
        SELECT c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND (has_table_privilege('hostelcare_app', c.oid, 'TRUNCATE')
            OR has_table_privilege('hostelcare_app', c.oid, 'REFERENCES')
            OR has_table_privilege('hostelcare_app', c.oid, 'TRIGGER')
            OR has_table_privilege('hostelcare_app', c.oid, 'MAINTAIN'))
    LOOP
        RAISE WARNING 'table %: hostelcare_app holds TRUNCATE/REFERENCES/TRIGGER/MAINTAIN (not allowed)', r.relname;
    END LOOP;
END
$$;

\connect hostelcare_test
\echo '--- hostelcare_test: hostelcare_app privileges per table ---'
SELECT c.relname AS "table", pg_get_userbyid(c.relowner) AS owner,
       has_table_privilege('hostelcare_app', c.oid, 'SELECT')     AS sel,
       has_table_privilege('hostelcare_app', c.oid, 'INSERT')     AS ins,
       has_table_privilege('hostelcare_app', c.oid, 'UPDATE')     AS upd,
       has_table_privilege('hostelcare_app', c.oid, 'DELETE')     AS del,
       has_table_privilege('hostelcare_app', c.oid, 'TRUNCATE')   AS trunc,
       has_table_privilege('hostelcare_app', c.oid, 'REFERENCES') AS refs,
       has_table_privilege('hostelcare_app', c.oid, 'TRIGGER')    AS trig,
       has_table_privilege('hostelcare_app', c.oid, 'MAINTAIN')   AS maint
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 1;
DO $$
DECLARE
    p text;
    r record;
    ok boolean := true;
BEGIN
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] LOOP
            IF has_table_privilege('hostelcare_app', 'public.alembic_version', p) THEN
                RAISE WARNING 'alembic_version: hostelcare_app has % (must have NO privileges)', p;
                ok := false;
            END IF;
        END LOOP;
        FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','REFERENCES'] LOOP
            IF has_any_column_privilege('hostelcare_app', 'public.alembic_version', p) THEN
                RAISE WARNING 'alembic_version: hostelcare_app has column-level % (must have NO privileges)', p;
                ok := false;
            END IF;
        END LOOP;
        IF ok THEN RAISE NOTICE 'alembic_version: OK (hostelcare_app has no privileges)'; END IF;
    ELSE
        RAISE NOTICE 'alembic_version does not exist yet (migrations not applied)';
    END IF;

    IF to_regclass('public.audit_log') IS NOT NULL THEN
        ok := true;
        FOREACH p IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'] LOOP
            IF has_table_privilege('hostelcare_app', 'public.audit_log', p) <> (p IN ('SELECT','INSERT')) THEN
                RAISE WARNING 'audit_log: hostelcare_app % = % (expected %)', p,
                    has_table_privilege('hostelcare_app', 'public.audit_log', p), p IN ('SELECT','INSERT');
                ok := false;
            END IF;
        END LOOP;
        IF has_any_column_privilege('hostelcare_app', 'public.audit_log', 'UPDATE')
           OR has_any_column_privilege('hostelcare_app', 'public.audit_log', 'REFERENCES') THEN
            RAISE WARNING 'audit_log: hostelcare_app has column-level UPDATE or REFERENCES (must not)';
            ok := false;
        END IF;
        IF ok THEN RAISE NOTICE 'audit_log: OK (append-only: SELECT and INSERT only)'; END IF;
    ELSE
        RAISE NOTICE 'audit_log does not exist yet (migrations not applied)';
    END IF;

    FOR r IN
        SELECT c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND (has_table_privilege('hostelcare_app', c.oid, 'TRUNCATE')
            OR has_table_privilege('hostelcare_app', c.oid, 'REFERENCES')
            OR has_table_privilege('hostelcare_app', c.oid, 'TRIGGER')
            OR has_table_privilege('hostelcare_app', c.oid, 'MAINTAIN'))
    LOOP
        RAISE WARNING 'table %: hostelcare_app holds TRUNCATE/REFERENCES/TRIGGER/MAINTAIN (not allowed)', r.relname;
    END LOOP;
END
$$;

\connect postgres
\echo '--- Server version (expect 17 or newer) ---'
SHOW server_version;

\echo '--- HostelCare setup: done ---'
\echo 'NEXT STEP (manual, interactive; passwords are never written to any file).'
\echo 'Use a DIFFERENT strong password for each role:'
\echo '  psql -h localhost -U postgres -d postgres'
\echo '  \password hostelcare_owner'
\echo '  \password hostelcare_app'
\echo 'Then put them in C:\Projects\HostelCare\backend\.env yourself:'
\echo '  MIGRATION_DATABASE_URL (owner) and DATABASE_URL (app).'

-- =============================================================================
-- Optional hardening (NOT run here): in postgresql.conf set
--   listen_addresses = 'localhost'
-- so PostgreSQL does not listen on all network interfaces.
-- =============================================================================
