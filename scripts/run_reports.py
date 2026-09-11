"""Print, and save to docs/, the measured numbers behind every claim in
the README except suspect propagation and ReqIF round trip (which have
their own scripts because they mutate/export state). Run:
    venv\\Scripts\\python.exe scripts\\run_reports.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.db import connect
from trace_workbench.seed import N_ORPHAN, N_NON_VERIFYING, assign_defects, flatten_tree
from trace_workbench import reports


def main():
    conn = connect("data/trace.db")
    lines = []

    def out(s=""):
        lines.append(s)
        print(s)

    n_user_needs = conn.execute("SELECT COUNT(*) c FROM user_needs").fetchone()["c"]
    n_reqs = conn.execute("SELECT COUNT(*) c FROM requirements").fetchone()["c"]
    out(f"user needs: {n_user_needs}")
    out(f"requirements: {n_reqs}")
    out("")

    # --- trace coverage: every requirement has >=1 risk control; the
    # non-orphan requirements (86 - 11 seeded orphans) have >=1 test. ---
    n_reqs_with_rc = conn.execute(
        "SELECT COUNT(DISTINCT requirement_id) c FROM requirement_risk_controls"
    ).fetchone()["c"]
    n_reqs_with_test = conn.execute(
        "SELECT COUNT(DISTINCT requirement_id) c FROM requirement_tests"
    ).fetchone()["c"]
    out(f"requirements with >=1 linked risk control: {n_reqs_with_rc}/{n_reqs}")
    out(f"requirements with >=1 linked test: {n_reqs_with_test}/{n_reqs} "
        f"(expect {n_reqs - N_ORPHAN} = {n_reqs} - {N_ORPHAN} seeded orphans)")
    out("")

    # --- verification refusal ------------------------------------------
    report = reports.build_verification_report(conn)
    n_verified = sum(1 for s in report if s.verified)
    n_no_evidence = sum(1 for s in report if s.reason == "no evidence attached")
    n_failing = sum(1 for s in report if s.reason.startswith("failing evidence"))
    out(f"verification report: {n_verified}/{len(report)} VERIFIED")
    out(f"  NOT VERIFIED, no evidence attached: {n_no_evidence}")
    out(f"  NOT VERIFIED, failing evidence present: {n_failing}")
    out(f"  refusal check: every requirement with zero evidence reported NOT VERIFIED: "
        f"{n_no_evidence == N_ORPHAN}")
    out("")

    # --- ground truth, computed independently of the current db content
    # via the same deterministic assignment seed.py used to build it -----
    keys_in_order = [row[0] for row in flatten_tree()]
    true_orphans, true_non_verifying, _true_failing, _true_verified = assign_defects(
        keys_in_order
    )

    # --- orphan detection, fast vs reference oracle ---------------------
    fast = reports.find_orphans_fast(conn)
    ref = reports.find_orphans_reference(conn)
    fast_keys = {k for _id, k in fast}
    out(f"orphan detection (fast indexed scan): {len(fast)} found")
    out(f"orphan detection (slow reference oracle): {len(ref)} found")
    out(f"fast == reference oracle: {sorted(fast) == sorted(ref)}")
    caught = fast_keys & true_orphans
    false_positives = fast_keys - true_orphans
    missed = true_orphans - fast_keys
    out(f"orphan catch rate: {len(caught)}/{len(true_orphans)} seeded orphans caught "
        f"(missed: {sorted(missed)})")
    out(f"orphan false positives on the other {86 - len(true_orphans)} requirements: "
        f"{len(false_positives)} {sorted(false_positives)}")
    out("")

    # --- non-verifying test detection -----------------------------------
    nv = reports.find_non_verifying_tests(conn)
    nv_req_keys = {req_key for _rid, req_key, _tid, _tkey in nv}
    out(f"non-verifying test detection: {len(nv)} flagged")
    nv_caught = nv_req_keys & true_non_verifying
    nv_false_positives = nv_req_keys - true_non_verifying
    nv_missed = true_non_verifying - nv_req_keys
    out(f"non-verifying catch rate: {len(nv_caught)}/{len(true_non_verifying)} seeded "
        f"non-verifying tests caught (missed: {sorted(nv_missed)})")
    out(f"non-verifying false positives: {len(nv_false_positives)} {sorted(nv_false_positives)}")
    out("")
    out(reports.render_report_text(report))

    Path("docs").mkdir(exist_ok=True)
    Path("docs/traceability_stats.txt").write_text("\n".join(lines), encoding="utf-8")
    conn.close()


if __name__ == "__main__":
    main()
