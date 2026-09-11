from trace_workbench.seed import (
    N_ORPHAN, N_NON_VERIFYING, N_FAILING, assign_defects, flatten_tree,
)


def test_seeded_counts(seeded_conn):
    conn = seeded_conn
    assert conn.execute("SELECT COUNT(*) c FROM user_needs").fetchone()["c"] == 14
    assert conn.execute("SELECT COUNT(*) c FROM requirements").fetchone()["c"] == 86
    n_tests = conn.execute("SELECT COUNT(*) c FROM tests").fetchone()["c"]
    assert n_tests == 86 - N_ORPHAN  # exactly one test per non-orphan requirement
    n_req_rc_links = conn.execute(
        "SELECT COUNT(*) c FROM requirement_risk_controls"
    ).fetchone()["c"]
    assert n_req_rc_links == 86  # every requirement traces to exactly one risk control


def test_every_requirement_reachable_to_a_user_need(seeded_conn):
    """Walk parent_id up from every requirement and confirm it terminates
    at a user need (the tree has no cycles and no dangling parents)."""
    conn = seeded_conn
    rows = conn.execute(
        "SELECT id, parent_id, user_need_id FROM requirements"
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    for row in rows:
        steps = 0
        cur = row
        while cur["user_need_id"] is None:
            cur = by_id[cur["parent_id"]]
            steps += 1
            assert steps < 10, "unexpectedly deep or cyclic parent chain"
        assert cur["user_need_id"] is not None


def test_defect_assignment_is_deterministic():
    keys = [row[0] for row in flatten_tree()]
    a = assign_defects(keys, seed=1234)
    b = assign_defects(keys, seed=1234)
    assert a == b


def test_defect_assignment_partitions_all_86_keys_disjointly():
    keys = [row[0] for row in flatten_tree()]
    orphan, non_verifying, failing, verified = assign_defects(keys, seed=1234)
    assert len(orphan) == N_ORPHAN
    assert len(non_verifying) == N_NON_VERIFYING
    assert len(failing) == N_FAILING
    assert len(verified) == 86 - N_ORPHAN - N_NON_VERIFYING - N_FAILING
    union = orphan | non_verifying | failing | verified
    assert len(union) == 86  # disjoint: no key appears in two buckets
