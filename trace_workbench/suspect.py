"""Suspect-link propagation.

Why implemented this way: when a parent requirement's baseline text
changes, every piece of evidence anywhere below it in the decomposition
tree was reviewed against the *old* wording and can no longer be trusted
without a human re-look. The honest scope of "downstream" is therefore
transitive (grandchildren and beyond, not just direct children) and
covers three kinds of artifact: the descendant requirements themselves,
the tests linked to them, and the risk controls linked to them. A
shallower implementation that only suspected direct children, or only
suspected requirements and not their linked tests/risk controls, would
under-report exactly the items a reviewer most needs to be told about.

The edited requirement itself is not added to the "downstream" count
returned by propagate_suspect: it was the thing that changed, not
something caught in the blast radius, and the caller already knows it
changed because the caller is the one who changed it. Its own linked
tests and risk controls, however, DO need re-review (the requirement
text they were checked against just moved), so they ARE counted.
"""
from __future__ import annotations


def get_descendants(conn, requirement_id: int):
    """Transitive strict descendants of requirement_id (not including
    itself), via breadth-first walk over parent_id."""
    descendants = []
    frontier = [requirement_id]
    while frontier:
        rows = conn.execute(
            "SELECT id FROM requirements WHERE parent_id IN ({})".format(
                ",".join("?" * len(frontier))
            ),
            frontier,
        ).fetchall()
        next_frontier = [r["id"] for r in rows]
        descendants.extend(next_frontier)
        frontier = next_frontier
    return descendants


def edit_requirement_text(conn, requirement_key: str, new_text: str) -> int:
    """Apply a baseline text edit to one requirement. Returns its id."""
    row = conn.execute(
        "SELECT id FROM requirements WHERE key = ?", (requirement_key,)
    ).fetchone()
    if row is None:
        raise KeyError(f"no such requirement: {requirement_key}")
    conn.execute(
        "UPDATE requirements SET text = ?, baseline_version = baseline_version + 1 "
        "WHERE id = ?",
        (new_text, row["id"]),
    )
    return row["id"]


def propagate_suspect(conn, edited_requirement_ids):
    """Mark every descendant requirement (and every test/risk-control link
    attached to the edited requirements and their descendants) suspect.
    Returns a dict with the distinct counts, and the total "downstream
    item" count as defined in the module docstring (descendants + their
    links + the edited requirements' own links, NOT the edited
    requirements themselves)."""
    edited_requirement_ids = list(edited_requirement_ids)
    all_descendants = set()
    for rid in edited_requirement_ids:
        all_descendants.update(get_descendants(conn, rid))

    scope_for_links = set(edited_requirement_ids) | all_descendants

    if all_descendants:
        conn.executemany(
            "UPDATE requirements SET suspect = 1 WHERE id = ?",
            [(rid,) for rid in all_descendants],
        )

    suspect_test_links = set()
    suspect_rc_links = set()
    if scope_for_links:
        placeholders = ",".join("?" * len(scope_for_links))
        rt_rows = conn.execute(
            f"SELECT id FROM requirement_tests WHERE requirement_id IN ({placeholders})",
            list(scope_for_links),
        ).fetchall()
        suspect_test_links = {r["id"] for r in rt_rows}
        if suspect_test_links:
            conn.executemany(
                "UPDATE requirement_tests SET suspect = 1 WHERE id = ?",
                [(i,) for i in suspect_test_links],
            )
        rc_rows = conn.execute(
            f"SELECT id FROM requirement_risk_controls WHERE requirement_id IN ({placeholders})",
            list(scope_for_links),
        ).fetchall()
        suspect_rc_links = {r["id"] for r in rc_rows}
        if suspect_rc_links:
            conn.executemany(
                "UPDATE requirement_risk_controls SET suspect = 1 WHERE id = ?",
                [(i,) for i in suspect_rc_links],
            )

    conn.commit()

    downstream_count = len(all_descendants) + len(suspect_test_links) + len(suspect_rc_links)
    return {
        "edited_ids": edited_requirement_ids,
        "descendant_requirement_ids": all_descendants,
        "suspect_test_link_ids": suspect_test_links,
        "suspect_risk_control_link_ids": suspect_rc_links,
        "downstream_count": downstream_count,
    }


def downstream_count_for(conn, edited_requirement_ids):
    """Pure computation (no writes) of what propagate_suspect's
    downstream_count would be for a candidate set of edited requirement
    ids. Used by the scenario search to try combinations without
    mutating the database."""
    all_descendants = set()
    for rid in edited_requirement_ids:
        all_descendants.update(get_descendants(conn, rid))
    scope_for_links = set(edited_requirement_ids) | all_descendants
    if not scope_for_links:
        return 0
    placeholders = ",".join("?" * len(scope_for_links))
    n_tests = conn.execute(
        f"SELECT COUNT(*) AS c FROM requirement_tests WHERE requirement_id IN ({placeholders})",
        list(scope_for_links),
    ).fetchone()["c"]
    n_rc = conn.execute(
        f"SELECT COUNT(*) AS c FROM requirement_risk_controls "
        f"WHERE requirement_id IN ({placeholders})",
        list(scope_for_links),
    ).fetchone()["c"]
    return len(all_descendants) + n_tests + n_rc
