"""(Re)build the two PostgreSQL story-layer schemas used by the release
gate: `story_seeded` (60 stories, 22 seeded gaps) and `story_clean` (the
same 60 stories, every link present). Run after confirming PostgreSQL is
reachable; exits with a clear message instead of a traceback if it is
not (see README "Building and running").

    venv\\Scripts\\python scripts\\build_story_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench import story_db
from trace_workbench.stories_seed import STORY_DEFS, GAP_PAIRS


def main():
    if not story_db.is_available():
        print(f"PostgreSQL not reachable at {story_db.database_url()}; "
              f"see README for the WSL2 stand-up commands. Skipping.")
        return 1

    conn = story_db.connect()
    try:
        seeded_counts = story_db.build_schema(conn, "story_seeded", STORY_DEFS, GAP_PAIRS)
        clean_counts = story_db.build_schema(conn, "story_clean", STORY_DEFS, set())
    finally:
        conn.close()

    print(f"story_seeded: {len(STORY_DEFS)} stories, links = {seeded_counts}, "
          f"gaps applied = {len(GAP_PAIRS)}")
    print(f"story_clean: {len(STORY_DEFS)} stories, links = {clean_counts}, gaps applied = 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
