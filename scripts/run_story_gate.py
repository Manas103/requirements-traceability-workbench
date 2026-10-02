"""Run the release gate against a PostgreSQL story schema, print the
fast-vs-reference-oracle agreement, and print every missing link by
name. Exit code is 1 if any link is missing, 0 if the backlog is clean
(so this script is a real, CI-shaped release gate, not just a report).

    venv\\Scripts\\python scripts\\run_story_gate.py --schema story_seeded
    venv\\Scripts\\python scripts\\run_story_gate.py --schema story_clean
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_workbench import story_db, story_gate
from trace_workbench.stories_seed import GAP_PAIRS


def collected_test_node_ids() -> set:
    """Cross-check: actually run `pytest --collect-only` against
    test_story_endpoints.py and return the set of node ids pytest itself
    reports, so the "a test exists" claim behind each story's test_links
    row is checked against real pytest collection, not trusted as a
    string sitting in a database column."""
    # --rootdir is pinned explicitly: this project sits inside a larger
    # pipeline checkout that has its own top-level pytest.ini, and
    # pytest's rootdir discovery climbs parent directories looking for
    # one. Without pinning it here, node ids printed by --collect-only
    # come back prefixed with this project's path relative to that outer
    # root (e.g. "projects/requirements-traceability-workbench/tests/...")
    # instead of the "tests/..." form stored in test_links.node_id,
    # making every recorded node id look unmatched even though the test
    # really is collected. Found by running this cross-check for the
    # first time and seeing 51 "unmatched" node ids that were, in fact,
    # all being collected (see README Findings).
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "--rootdir", str(ROOT), "tests/test_story_endpoints.py"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    node_ids = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("tests/test_story_endpoints.py::"):
            node_ids.add(line)
    return node_ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", default="story_seeded", choices=["story_seeded", "story_clean"])
    args = parser.parse_args()

    if not story_db.is_available():
        print(f"PostgreSQL not reachable at {story_db.database_url()}; "
              f"run scripts\\build_story_db.py first. Skipping.")
        return 1

    conn = story_db.connect()
    try:
        gaps_fast, gaps_reference, total_stories, agree = story_gate.run_gate(conn, args.schema)
    finally:
        conn.close()

    print(f"schema: {args.schema}")
    print(f"fast == reference oracle: {agree}")
    print(story_gate.render_gate_report(gaps_fast, total_stories))

    if args.schema == "story_seeded":
        seeded_gap_names = {f"{k}:{t}" for (k, t) in GAP_PAIRS}
        found_gap_names = {f"{g.story_key}:{g.link_type}" for g in gaps_fast}
        caught = seeded_gap_names & found_gap_names
        missed = seeded_gap_names - found_gap_names
        extra = found_gap_names - seeded_gap_names
        print(f"seeded gaps caught by name: {len(caught)}/{len(seeded_gap_names)}")
        if missed:
            print(f"seeded gaps MISSED: {sorted(missed)}")
        if extra:
            print(f"gaps flagged that were NOT seeded (false positive): {sorted(extra)}")

    conn = story_db.connect()
    try:
        recorded_node_ids = {row[0] for row in conn.execute(
            f"SELECT node_id FROM {args.schema}.test_links"
        ).fetchall()}
    finally:
        conn.close()
    collected = collected_test_node_ids()
    unmatched = recorded_node_ids - collected
    print(f"test_links node ids recorded: {len(recorded_node_ids)}, "
          f"actually collected by pytest: {len(recorded_node_ids & collected)}, "
          f"recorded-but-not-collected: {len(unmatched)}")
    if unmatched:
        print(f"  WARNING: recorded test links with no matching collected test: {sorted(unmatched)}")

    return 1 if gaps_fast else 0


if __name__ == "__main__":
    raise SystemExit(main())
