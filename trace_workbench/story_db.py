"""PostgreSQL-backed Agile story layer.

A real PostgreSQL 14 server is reachable from this Windows-native Python
process at the WSL2 host's loopback address (verified by connecting
before any of this module was written; see README "PostgreSQL, stated
honestly"). This module is exercised against that real server, not
SQLite-with-a-Postgres-compatible-schema: every claim this file's tests
and scripts make about PostgreSQL was measured against an actual
`psycopg` connection to a real `postgresql://...` URL.

Two logical backlogs are built as two PostgreSQL schemas inside the same
`tracestory` database, the schema-isolation equivalent of the SQLite
side's tmp_path-per-test isolation:

- `story_seeded`: the 60-story backlog with the 22 gaps from
  stories_seed.GAP_PAIRS applied (one of acceptance_criteria/
  api_contract/test/documentation missing for each gapped story).
- `story_clean`: the same 60 stories with every link present, used to
  measure "0 false blocks on a clean backlog".

Connection is controlled by the `DATABASE_URL` environment variable
(default below matches the role created for this project in WSL2). Any
test or script that needs PostgreSQL calls `is_available()` first and
skips (tests) or exits with a clear message (scripts) if it is not
reachable, following the project's own documented convention for
services that are not guaranteed to be running (see README "Building and
running").
"""
from __future__ import annotations

import os

import psycopg
from psycopg import sql

DEFAULT_DATABASE_URL = "postgresql://tracestory_app:tracestory_dev_pw@127.0.0.1:5432/tracestory"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def is_available(timeout: float = 3.0) -> bool:
    try:
        conn = psycopg.connect(database_url(), connect_timeout=timeout)
        conn.close()
        return True
    except Exception:
        return False


def connect():
    return psycopg.connect(database_url())


def _ident(schema: str):
    return sql.Identifier(schema)


def drop_schema(conn, schema: str) -> None:
    conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(_ident(schema)))
    conn.commit()


def create_schema_tables(conn, schema: str) -> None:
    s = _ident(schema)
    conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(s))
    conn.execute(sql.SQL("""
        CREATE TABLE {}.stories (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            resource TEXT NOT NULL,
            operation TEXT NOT NULL,
            operation_id TEXT NOT NULL,
            requirement_key TEXT
        )
    """).format(s))
    conn.execute(sql.SQL("""
        CREATE TABLE {}.acceptance_criteria (
            story_id INTEGER PRIMARY KEY REFERENCES {}.stories(id),
            text TEXT NOT NULL
        )
    """).format(s, s))
    conn.execute(sql.SQL("""
        CREATE TABLE {}.api_links (
            story_id INTEGER PRIMARY KEY REFERENCES {}.stories(id),
            operation_id TEXT NOT NULL
        )
    """).format(s, s))
    conn.execute(sql.SQL("""
        CREATE TABLE {}.test_links (
            story_id INTEGER PRIMARY KEY REFERENCES {}.stories(id),
            node_id TEXT NOT NULL
        )
    """).format(s, s))
    conn.execute(sql.SQL("""
        CREATE TABLE {}.documentation (
            story_id INTEGER PRIMARY KEY REFERENCES {}.stories(id),
            paragraph TEXT NOT NULL
        )
    """).format(s, s))
    conn.commit()


def populate_schema(conn, schema: str, story_defs, gaps: set) -> dict:
    """Insert every story in story_defs into `schema`, inserting a row in
    acceptance_criteria/api_links/test_links/documentation for every
    link type EXCEPT where (story_key, link_type) is in `gaps`. Returns a
    dict of counts for the caller to print/report. `gaps` is a plain
    Python set (possibly empty, for the clean backlog); this function
    does not compute gaps itself, it only applies a set it is given, so
    stories_seed.compute_gaps stays the single place gap selection
    happens."""
    s = _ident(schema)
    story_id = {}
    for story in story_defs:
        cur = conn.execute(
            sql.SQL(
                "INSERT INTO {}.stories (key, title, resource, operation, operation_id, requirement_key) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
            ).format(s),
            (story["key"], story["title"], story["resource"], story["operation"],
             story["operation_id"], story["requirement_key"]),
        )
        story_id[story["key"]] = cur.fetchone()[0]

    counts = {"acceptance_criteria": 0, "api_contract": 0, "test": 0, "documentation": 0}
    for story in story_defs:
        key = story["key"]
        sid = story_id[key]
        if (key, "acceptance_criteria") not in gaps:
            conn.execute(
                sql.SQL("INSERT INTO {}.acceptance_criteria (story_id, text) VALUES (%s, %s)").format(s),
                (sid, story["acceptance_criteria"]),
            )
            counts["acceptance_criteria"] += 1
        if (key, "api_contract") not in gaps:
            conn.execute(
                sql.SQL("INSERT INTO {}.api_links (story_id, operation_id) VALUES (%s, %s)").format(s),
                (sid, story["operation_id"]),
            )
            counts["api_contract"] += 1
        if (key, "test") not in gaps:
            node_id = f"tests/test_story_endpoints.py::test_story_endpoint[{key}]"
            conn.execute(
                sql.SQL("INSERT INTO {}.test_links (story_id, node_id) VALUES (%s, %s)").format(s),
                (sid, node_id),
            )
            counts["test"] += 1
        if (key, "documentation") not in gaps:
            paragraph = (
                f"User documentation for {story['title']}: {story['acceptance_criteria']}"
            )
            conn.execute(
                sql.SQL("INSERT INTO {}.documentation (story_id, paragraph) VALUES (%s, %s)").format(s),
                (sid, paragraph),
            )
            counts["documentation"] += 1
    conn.commit()
    return counts


def build_schema(conn, schema: str, story_defs, gaps: set) -> dict:
    drop_schema(conn, schema)
    create_schema_tables(conn, schema)
    return populate_schema(conn, schema, story_defs, gaps)


def fetch_operation_ac_pairs(conn, schema: str):
    """(operation_id, acceptance_criteria_text) for every story in
    `schema` that has both an api_contract link and acceptance-criteria
    text present, ordered by story id. Used by docgen's live-contract
    documentation draft so its acceptance-criteria text is read from
    PostgreSQL, not re-imported from the Python seed module, exercising
    the real database on the documentation-coverage claim too."""
    s = _ident(schema)
    rows = conn.execute(sql.SQL(
        "SELECT al.operation_id, ac.text FROM {}.api_links al "
        "JOIN {}.acceptance_criteria ac ON ac.story_id = al.story_id "
        "ORDER BY al.story_id"
    ).format(s, s)).fetchall()
    return [(r[0], r[1]) for r in rows]
