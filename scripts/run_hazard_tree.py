"""Render the hazard-anchored view of the 86-requirement tree and
confirm every requirement reaches a hazard. Run:
    venv\\Scripts\\python.exe scripts\\run_hazard_tree.py > docs\\hazard_tree_output.txt
Read-only: does not mutate data/trace.db.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.db import connect
from trace_workbench.hazards import every_requirement_reaches_a_hazard, render_hazard_tree_text


def main():
    conn = connect("data/trace.db")
    print(render_hazard_tree_text(conn))
    ok, unreachable = every_requirement_reaches_a_hazard(conn)
    print(f"every requirement reaches a hazard: {ok}")
    if not ok:
        print(f"unreachable: {unreachable}")
    conn.close()


if __name__ == "__main__":
    main()
