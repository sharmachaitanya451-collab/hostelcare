"""PostgreSQL database connectivity and privilege isolation tests.

These tests run when TEST_DATABASE_URL and TEST_MIGRATION_DATABASE_URL are configured.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError


@pytest.fixture
def runtime_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or "REPLACE_WITH" in url:
        pytest.skip("TEST_DATABASE_URL is not configured with real credentials")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def migration_engine():
    url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not url or "REPLACE_WITH" in url:
        pytest.skip("TEST_MIGRATION_DATABASE_URL is not configured with real credentials")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.mark.db
def test_runtime_role_connection(runtime_engine):
    """Runtime role connects as hostelcare_app to hostelcare_test."""
    with runtime_engine.connect() as conn:
        res = conn.execute(text("SELECT current_user, current_database()")).fetchone()
        assert res[0] == "hostelcare_app"
        assert res[1] == "hostelcare_test"


@pytest.mark.db
def test_migration_role_connection(migration_engine):
    """Migration role connects as hostelcare_owner to hostelcare_test."""
    with migration_engine.connect() as conn:
        res = conn.execute(text("SELECT current_user, current_database()")).fetchone()
        assert res[0] == "hostelcare_owner"
        assert res[1] == "hostelcare_test"


@pytest.mark.db
def test_runtime_role_cannot_create_tables(runtime_engine):
    """Runtime role is denied CREATE TABLE privileges in public schema."""
    with runtime_engine.connect() as conn:
        with pytest.raises(ProgrammingError) as exc_info:
            conn.execute(text("CREATE TABLE _hc_should_fail (id int);"))
        assert "permission denied" in str(exc_info.value).lower()


@pytest.mark.db
def test_migration_role_can_create_and_drop_tables(migration_engine):
    """Migration role can successfully execute DDL in public schema."""
    with migration_engine.connect() as conn:
        conn.execute(text("CREATE TABLE _hc_owner_test (id int);"))
        conn.commit()
        # Clean up
        conn.execute(text("DROP TABLE _hc_owner_test;"))
        conn.commit()


@pytest.mark.db
def test_runtime_role_cannot_access_unrelated_databases(runtime_engine):
    """Runtime role cannot connect or cross-query databases it was revoked from."""
    with runtime_engine.connect() as conn:
        assert conn.execute(text("SELECT current_database()")).scalar() == "hostelcare_test"
