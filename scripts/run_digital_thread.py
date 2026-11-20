"""Build the as-planned/as-built/as-maintained digital thread on top of
data/trace.db's existing 86-requirement tree, seed 180 unexplained
variances (30 per class, 6 classes) and 1,000 clean serialized records,
measure the audit's catch rate and false-hold rate, and print/save the
result. Run:
    venv\\Scripts\\python.exe scripts\\run_digital_thread.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.db import connect
from trace_workbench import digital_thread as dt
from trace_workbench import reports


def main():
    conn = connect("data/trace.db")
    lines = []

    def out(s=""):
        lines.append(s)
        print(s)

    # digital_thread tables are additive; wipe any prior run's rows so this
    # script is idempotent against the same trace.db.
    for table in ("as_maintained", "as_built", "deviations", "change_notices",
                  "units", "bom_lines"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()

    bom_line_ids = dt.build_bom(conn)
    n_reqs = conn.execute("SELECT COUNT(*) c FROM requirements").fetchone()["c"]
    n_l1 = len(bom_line_ids)
    linked = sum(1 for r in conn.execute("SELECT id FROM requirements").fetchall()
                 if dt.requirement_bom_line(conn, r["id"]) is not None)
    out(f"BOM lines (one per L1 requirement): {n_l1}")
    out(f"requirements linked to a BOM line via themselves or an L1 ancestor: {linked}/{n_reqs}")
    out("")

    serials = dt.build_fleet(conn, bom_line_ids)
    conn.commit()
    out(f"serialized units: {len(serials)}")
    out(f"as-built records (clean baseline): "
        f"{conn.execute('SELECT COUNT(*) c FROM as_built').fetchone()['c']}")
    out("")

    seeded = dt.seed_variances(conn, serials, bom_line_ids)
    seeded_pairs_early = {(s, b) for _cls, s, b in seeded}
    dt.seed_clean_maintenance(conn, serials, bom_line_ids, exclude_pairs=seeded_pairs_early)
    conn.commit()
    out(f"as-maintained records (clean baseline): "
        f"{conn.execute('SELECT COUNT(*) c FROM as_maintained').fetchone()['c']}")
    out("")
    by_class = {}
    for cls, serial, bid in seeded:
        by_class.setdefault(cls, []).append((serial, bid))

    caught_by_class = {cls: 0 for cls in dt.VARIANCE_CLASSES}
    named = []
    for cls, serial, bid in seeded:
        found = dt.audit_pair(conn, serial, bid)
        hit = [v for v in found if v.variance_class == cls]
        if hit:
            caught_by_class[cls] += 1
            named.append(hit[0])

    total_caught = sum(caught_by_class.values())
    out(f"seeded unexplained variances: {len(seeded)} across {len(dt.VARIANCE_CLASSES)} classes")
    for cls in dt.VARIANCE_CLASSES:
        out(f"  {cls}: {caught_by_class[cls]}/{dt.N_SEEDED_PER_CLASS} caught")
    out(f"total: {total_caught}/{len(seeded)} seeded variances caught, each named by class and item")
    out("")
    out("first 6 named variances (one per class):")
    seen_classes = set()
    for v in named:
        if v.variance_class not in seen_classes:
            out(f"  [{v.variance_class}] {v.item}: {v.detail}")
            seen_classes.add(v.variance_class)
    out("")

    seeded_pairs = {(s, b) for _cls, s, b in seeded}
    all_pairs = [(s, b) for s in serials for b in bom_line_ids]
    eligible = [p for p in all_pairs if p not in seeded_pairs]
    rng = random.Random(dt.SEED_CLEAN_SAMPLE)
    clean_sample = rng.sample(eligible, 1000)
    false_holds = [p for p in clean_sample if dt.audit_pair(conn, p[0], p[1])]
    out(f"false holds on {len(clean_sample)} clean serialized records: {len(false_holds)}")
    if false_holds:
        out(f"  e.g. {false_holds[:5]}")
    out("")

    # the fleet is only 50 units against 180 seeded variances, so almost
    # every unit has at least one bad line somewhere in its 45; publish()
    # is demonstrated here at the single-bom-line grain it actually checks,
    # on one seeded-clean pair and one seeded-bad pair, rather than on a
    # whole serial that happens to have zero variances across all 45 lines.
    clean_pair = clean_sample[0]
    refused_ok, variances = dt.publish(conn, clean_pair[0], [clean_pair[1]])
    out(f"publish({clean_pair[0]}, [{clean_pair[1]}]) on a clean pair: "
        f"{'PUBLISHED' if refused_ok else 'REFUSED'} ({len(variances)} variances)")
    seeded_cls, seeded_serial, seeded_bid = seeded[0]
    refused_ok2, variances2 = dt.publish(conn, seeded_serial, [seeded_bid])
    out(f"publish({seeded_serial}, [{seeded_bid}]) on the seeded {seeded_cls} pair: "
        f"{'PUBLISHED' if refused_ok2 else 'REFUSED'} ({len(variances2)} variances: "
        f"{[v.variance_class for v in variances2]})")
    out("")

    orphans = reports.find_orphans_fast(conn)
    out(f"requirements with no verifying record found by name: {len(orphans)}")
    for _id, key in orphans:
        out(f"  {key}")

    Path("docs").mkdir(exist_ok=True)
    Path("docs/digital_thread_output.txt").write_text("\n".join(lines), encoding="utf-8")
    conn.close()


if __name__ == "__main__":
    main()
