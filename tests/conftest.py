import sys
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
