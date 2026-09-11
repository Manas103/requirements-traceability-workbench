"""SQLite schema and connection helper for the traceability workbench.

Schema shape and why:

- `user_needs` and `requirements` are split into two tables (rather than one
  polymorphic "node" table) because a user need and a requirement have
  different fields in a real tool (a user need has no verification
  evidence, a requirement does) and because the decomposition tree needs a
  clean root: every top-level requirement points at a user_need_id, every
  child requirement points at a parent_id (another requirement). A
  requirement never has both set, and every requirement has exactly one of
  them set (CHECK constraint below), so "walk to the root" always
  terminates at a user need.
- `tests` and `risk_controls` are independent entities linked to
  requirements through join tables (`requirement_tests`,
  `requirement_risk_controls`) because the spec allows a requirement to
  link to *one or more* tests and *one or more* risk controls (a many-to-
  many relationship), and because a single test or risk control can, in a
  real system, cover more than one requirement.
- `suspect` is a column on the join tables and on `requirements`, not a
  separate "suspect events" table, because the current implementation only
  needs "is this suspect right now" (a boolean gate other reports read),
  not a full history of suspect/cleared transitions. If that history were
  needed later, an append-only `suspect_events` table would be the honest
  next step instead of overloading these columns; see README Limitations.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE user_needs (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE requirements (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    keyword TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('L1', 'L2')),
    user_need_id INTEGER REFERENCES user_needs(id),
    parent_id INTEGER REFERENCES requirements(id),
    baseline_version INTEGER NOT NULL DEFAULT 1,
    suspect INTEGER NOT NULL DEFAULT 0,
    CHECK ((user_need_id IS NULL) != (parent_id IS NULL))
);

CREATE TABLE risk_controls (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE tests (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    exercises_keyword TEXT NOT NULL,
    procedure_text TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('pass', 'fail'))
);

CREATE TABLE requirement_tests (
    id INTEGER PRIMARY KEY,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id),
    test_id INTEGER NOT NULL REFERENCES tests(id),
    suspect INTEGER NOT NULL DEFAULT 0,
    UNIQUE (requirement_id, test_id)
);

CREATE TABLE requirement_risk_controls (
    id INTEGER PRIMARY KEY,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id),
    risk_control_id INTEGER NOT NULL REFERENCES risk_controls(id),
    suspect INTEGER NOT NULL DEFAULT 0,
    UNIQUE (requirement_id, risk_control_id)
);

CREATE INDEX idx_requirements_parent ON requirements(parent_id);
CREATE INDEX idx_requirements_user_need ON requirements(user_need_id);
CREATE INDEX idx_req_tests_requirement ON requirement_tests(requirement_id);
CREATE INDEX idx_req_rc_requirement ON requirement_risk_controls(requirement_id);
"""


def connect(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def fresh_db(db_path) -> sqlite3.Connection:
    """Create db_path from scratch, deleting any existing file. Used only by
    seed.py; report code always opens an existing db read-mostly."""
    p = Path(db_path)
    if p.exists():
        p.unlink()
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
