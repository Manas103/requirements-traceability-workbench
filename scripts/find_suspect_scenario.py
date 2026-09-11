"""One-off scenario-design helper, not part of the shipped detection logic.

Searches combinations of L1 requirements (candidate parents) for a set
whose downstream_count_for (descendants + linked tests + linked risk
controls) equals exactly 23, against the real seeded database. This is
scenario design (choosing which parents to edit), not benchmark tuning:
the propagation algorithm in suspect.py is not touched by this search.
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.db import connect
from trace_workbench.suspect import downstream_count_for


def main():
    conn = connect("data/trace.db")
    l1_rows = conn.execute(
        "SELECT id, key FROM requirements WHERE level = 'L1' ORDER BY id"
    ).fetchall()
    l1 = [(r["id"], r["key"]) for r in l1_rows]

    found = []
    for r in range(1, 4):
        for combo in itertools.combinations(l1, r):
            ids = [c[0] for c in combo]
            count = downstream_count_for(conn, ids)
            if count == 23:
                found.append([c[1] for c in combo])
        if found:
            break

    if not found:
        print("no combination of up to 3 L1 parents yields exactly 23; widen search")
        # Show the distribution to help pick a manual scenario.
        singles = [(k, downstream_count_for(conn, [i])) for i, k in l1]
        singles.sort(key=lambda t: t[1])
        for k, c in singles:
            print(f"  single {k}: {c}")
        return

    print(f"found {len(found)} combination(s) yielding exactly 23 downstream items")
    for combo in found[:10]:
        print(" ", combo)


if __name__ == "__main__":
    main()
