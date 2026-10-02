"""Draft first-pass user documentation for every endpoint discovered in
the live OpenAPI schema (never a hardcoded 48) and report how many got a
non-trivial draft. Acceptance-criteria text is read from the real
PostgreSQL `story_clean` schema (every operation has acceptance-criteria
text there); if PostgreSQL is not reachable, falls back to the same
acceptance-criteria text from the pure-Python seed module and says so,
so this script still runs offline but discloses the weaker claim.

    venv\\Scripts\\python scripts\\run_doc_coverage.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench import docgen, story_db
from trace_workbench.api_app import app, endpoint_count
from trace_workbench.stories_seed import STORY_DEFS


def ac_pairs_from_postgres():
    conn = story_db.connect()
    try:
        return story_db.fetch_operation_ac_pairs(conn, "story_clean")
    finally:
        conn.close()


def ac_pairs_from_python_seed():
    return [(s["operation_id"], s["acceptance_criteria"]) for s in STORY_DEFS]


def main():
    schema = app.openapi()
    n_endpoints = endpoint_count(schema)

    if story_db.is_available():
        source = "PostgreSQL (story_clean schema)"
        ac_pairs = ac_pairs_from_postgres()
    else:
        source = "Python seed module (PostgreSQL not reachable, disclosed)"
        ac_pairs = ac_pairs_from_python_seed()

    ac_index = docgen.build_acceptance_criteria_index(ac_pairs)
    drafts = docgen.draft_all_endpoints(schema, ac_index)

    print(f"acceptance-criteria source: {source}")
    print(f"live endpoints discovered from OpenAPI schema: {n_endpoints}")
    print(f"endpoints with a drafted paragraph: {len(drafts)}")

    non_trivial = 0
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = operation["operationId"]
            draft = drafts[op_id]
            ok = docgen.is_non_trivial(draft, path, method)
            non_trivial += int(ok)
            print(f"[{'OK' if ok else 'TRIVIAL'}] {method.upper():6s} {path:35s} "
                  f"len={len(draft):4d}  {draft[:90]}...")

    print(f"\nnon-trivial drafts: {non_trivial}/{n_endpoints}")
    return 0 if non_trivial == n_endpoints else 1


if __name__ == "__main__":
    raise SystemExit(main())
