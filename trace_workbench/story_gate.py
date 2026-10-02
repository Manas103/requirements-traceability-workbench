"""Release gate: every one of the 60 stories in a PostgreSQL schema must
carry all four links (acceptance_criteria, api_contract, test,
documentation). If any story is missing any link, the gate fails,
non-zero exit, naming the exact story key and the exact missing link
type for every gap found, not just a count.

Two independent implementations are provided and diffed against each
other, the same pattern as reports.find_orphans vs
reports.find_orphans_reference in the original 86-requirement tool:

- `find_missing_links_fast`: one indexed LEFT JOIN per link type.
- `find_missing_links_reference`: pulls every story and every link row
  into Python and checks membership with plain sets, no SQL join logic
  to get subtly wrong. Written independently from the fast version
  (it does not call it or share a query).

A real release gate would run this against CI on every push; here
`scripts/run_story_gate.py` runs it against both the seeded and the
clean PostgreSQL schema and commits the raw output.
"""
from __future__ import annotations

from dataclasses import dataclass

from psycopg import sql

LINK_TYPES = ("acceptance_criteria", "api_contract", "test", "documentation")

_LINK_TABLES = {
    "acceptance_criteria": "acceptance_criteria",
    "api_contract": "api_links",
    "test": "test_links",
    "documentation": "documentation",
}


@dataclass(frozen=True)
class Gap:
    story_key: str
    link_type: str

    def __str__(self):
        return f"{self.story_key}: missing {self.link_type}"


def find_missing_links_fast(conn, schema: str) -> set:
    """Indexed approach: one LEFT JOIN per link type against the primary
    key join column, selecting stories with no matching link row."""
    s = sql.Identifier(schema)
    gaps = set()
    for link_type, table in _LINK_TABLES.items():
        rows = conn.execute(sql.SQL(
            "SELECT st.key FROM {}.stories st "
            "LEFT JOIN {}.{} lt ON lt.story_id = st.id "
            "WHERE lt.story_id IS NULL"
        ).format(s, s, sql.Identifier(table))).fetchall()
        for (key,) in rows:
            gaps.add(Gap(key, link_type))
    return gaps


def find_missing_links_reference(conn, schema: str) -> set:
    """Deliberately naive, obviously-correct reference oracle: pull every
    story key and every (story_id -> present) row for each link table
    into plain Python sets, independent of the fast version's SQL."""
    s = sql.Identifier(schema)
    all_stories = conn.execute(
        sql.SQL("SELECT id, key FROM {}.stories").format(s)
    ).fetchall()
    gaps = set()
    for link_type, table in _LINK_TABLES.items():
        linked_story_ids = set()
        for (story_id,) in conn.execute(
            sql.SQL("SELECT story_id FROM {}.{}").format(s, sql.Identifier(table))
        ).fetchall():
            linked_story_ids.add(story_id)
        for story_id, key in all_stories:
            if story_id not in linked_story_ids:
                gaps.add(Gap(key, link_type))
    return gaps


def render_gate_report(gaps: set, total_stories: int) -> str:
    lines = []
    if not gaps:
        lines.append(f"RELEASE GATE: PASS. All {total_stories} stories have all 4 required links.")
        return "\n".join(lines)
    lines.append(f"RELEASE GATE: FAIL. {len(gaps)} missing link(s) found:")
    for gap in sorted(gaps, key=lambda g: (g.story_key, g.link_type)):
        lines.append(f"  - {gap}")
    lines.append(f"({total_stories} stories checked, {len(gaps)} link(s) missing)")
    return "\n".join(lines)


def run_gate(conn, schema: str):
    """Returns (gaps_fast, gaps_reference, total_stories, agree: bool)."""
    total_stories = conn.execute(
        sql.SQL("SELECT COUNT(*) FROM {}.stories").format(sql.Identifier(schema))
    ).fetchone()[0]
    gaps_fast = find_missing_links_fast(conn, schema)
    gaps_reference = find_missing_links_reference(conn, schema)
    agree = gaps_fast == gaps_reference
    return gaps_fast, gaps_reference, total_stories, agree
