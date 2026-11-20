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
- `hazards` (Nov. 2026 extension) is a second root, one row per
  `user_needs` row, so the same 86-requirement tree can be walked from
  either anchor: `user_need_id` for the original feature-anchored view,
  `hazard_id` for the hazard-anchored view (`trace_workbench/hazards.py`).
  `seed.build()` sets `hazard_id` on every L1 requirement, mirroring
  `user_need_id`; an L2 requirement's hazard is reached by walking
  `parent_id` up to its L1 ancestor, the same way its user need already
  is. This is not a CHECK-enforced invariant, deliberately: `reqif_io.
  import_reqif` reconstructs the pre-extension model (user needs,
  requirements, tests, risk controls) from a ReqIF file that predates
  hazards and legitimately leaves `hazard_id` NULL throughout, which is
  the honest scope stated in the README ("ReqIF scope"); hazards were
  not added to the export format.
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

CREATE TABLE hazards (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    user_need_id INTEGER UNIQUE REFERENCES user_needs(id)
);

CREATE TABLE requirements (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    text TEXT NOT NULL,
    keyword TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('L1', 'L2')),
    user_need_id INTEGER REFERENCES user_needs(id),
    parent_id INTEGER REFERENCES requirements(id),
    hazard_id INTEGER REFERENCES hazards(id),
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
CREATE INDEX idx_requirements_hazard ON requirements(hazard_id);
CREATE INDEX idx_req_tests_requirement ON requirement_tests(requirement_id);
CREATE INDEX idx_req_rc_requirement ON requirement_risk_controls(requirement_id);

-- Nov. 2026 extension: a BOM-anchored digital thread grafted onto the same
-- 86-requirement tree, carrying it through as-planned (bom_lines), as-built
-- (as_built, one serialized unit per `units` row) and as-maintained
-- (as_maintained) views. See trace_workbench/digital_thread.py.
CREATE TABLE bom_lines (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id),
    part_number TEXT NOT NULL,
    revision TEXT NOT NULL,
    spec_attribute TEXT NOT NULL,
    nominal_value REAL NOT NULL,
    tolerance REAL NOT NULL,
    unit_of_measure TEXT NOT NULL
);

CREATE TABLE change_notices (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    bom_line_id INTEGER NOT NULL REFERENCES bom_lines(id),
    status TEXT NOT NULL CHECK (status IN ('approved', 'pending')),
    authorized_part_number TEXT NOT NULL,
    authorized_revision TEXT NOT NULL,
    authorized_value REAL NOT NULL
);

CREATE TABLE deviations (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    serial TEXT NOT NULL,
    bom_line_id INTEGER NOT NULL REFERENCES bom_lines(id),
    status TEXT NOT NULL CHECK (status IN ('signed', 'unsigned')),
    UNIQUE (serial, bom_line_id)
);

CREATE TABLE units (
    id INTEGER PRIMARY KEY,
    serial TEXT UNIQUE NOT NULL
);

CREATE TABLE as_built (
    id INTEGER PRIMARY KEY,
    serial TEXT NOT NULL,
    bom_line_id INTEGER NOT NULL REFERENCES bom_lines(id),
    part_number TEXT NOT NULL,
    revision TEXT NOT NULL,
    measured_value REAL NOT NULL,
    UNIQUE (serial, bom_line_id)
);

CREATE TABLE as_maintained (
    id INTEGER PRIMARY KEY,
    serial TEXT NOT NULL,
    bom_line_id INTEGER NOT NULL REFERENCES bom_lines(id),
    part_number TEXT NOT NULL,
    revision TEXT NOT NULL,
    measured_value REAL NOT NULL,
    UNIQUE (serial, bom_line_id)
);

CREATE INDEX idx_bom_lines_requirement ON bom_lines(requirement_id);
CREATE INDEX idx_change_notices_bom_line ON change_notices(bom_line_id);
CREATE INDEX idx_deviations_serial_bom_line ON deviations(serial, bom_line_id);
CREATE INDEX idx_as_built_serial ON as_built(serial);
CREATE INDEX idx_as_maintained_serial ON as_maintained(serial);
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
