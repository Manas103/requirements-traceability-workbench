import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from trace_workbench.db import fresh_db
from trace_workbench.seed import build


@pytest.fixture()
def seeded_conn(tmp_path):
    """A freshly seeded database in a throwaway tmp_path file, isolated
    from data/trace.db so tests never depend on, or corrupt, the
    checked-in demo database."""
    db_path = tmp_path / "test_trace.db"
    conn = fresh_db(str(db_path))
    build(conn)
    yield conn
    conn.close()


@pytest.fixture()
def pg_conn():
    """A connection to the real PostgreSQL server this project was built
    against. Skips cleanly (does not fail) when PostgreSQL is not
    reachable, matching the project's documented convention for services
    that are not guaranteed to be running (README "Building and
    running")."""
    from trace_workbench import story_db

    if not story_db.is_available():
        pytest.skip(f"PostgreSQL not reachable at {story_db.database_url()}")
    conn = story_db.connect()
    yield conn
    conn.close()


@pytest.fixture()
def pg_temp_schema(pg_conn):
    """A uniquely-named PostgreSQL schema, dropped after the test, the
    schema-level equivalent of seeded_conn's tmp_path isolation: tests
    never depend on, or corrupt, the checked-in story_seeded/story_clean
    demo schemas."""
    schema_name = f"story_test_{uuid.uuid4().hex[:12]}"
    yield pg_conn, schema_name
    from trace_workbench import story_db
    story_db.drop_schema(pg_conn, schema_name)
