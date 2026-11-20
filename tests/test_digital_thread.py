from trace_workbench import db, digital_thread as dt, seed


def _built_conn():
    conn = db.fresh_db(":memory:")
    seed.build(conn)
    return conn


def test_bom_has_one_line_per_l1_requirement():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    n_l1 = conn.execute("SELECT COUNT(*) c FROM requirements WHERE level='L1'").fetchone()["c"]
    assert len(bom_line_ids) == n_l1


def test_every_requirement_resolves_to_a_bom_line():
    conn = _built_conn()
    dt.build_bom(conn)
    all_ids = [r["id"] for r in conn.execute("SELECT id FROM requirements").fetchall()]
    assert len(all_ids) == 86
    for rid in all_ids:
        assert dt.requirement_bom_line(conn, rid) is not None


def test_l2_requirement_resolves_to_its_l1_parents_bom_line():
    conn = _built_conn()
    dt.build_bom(conn)
    l2 = conn.execute("SELECT id, parent_id FROM requirements WHERE level='L2' LIMIT 1").fetchone()
    l1_line = dt.requirement_bom_line(conn, l2["parent_id"])
    l2_line = dt.requirement_bom_line(conn, l2["id"])
    assert l1_line["id"] == l2_line["id"]


def test_clean_built_record_has_no_variance():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    assert dt.audit_pair(conn, serials[0], bom_line_ids[0]) == []


def test_missing_built_record_is_flagged():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    conn.execute("DELETE FROM as_built WHERE serial=? AND bom_line_id=?", (serials[0], bom_line_ids[0]))
    variances = dt.audit_pair(conn, serials[0], bom_line_ids[0])
    assert [v.variance_class for v in variances] == ["missing_build_record"]


def test_part_substitution_is_flagged_and_named():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    conn.execute(
        "UPDATE as_built SET part_number='BOGUS' WHERE serial=? AND bom_line_id=?",
        (serials[0], bom_line_ids[0]),
    )
    variances = dt.audit_pair(conn, serials[0], bom_line_ids[0])
    assert len(variances) == 1
    assert variances[0].variance_class == "part_substitution"
    assert variances[0].item == f"{serials[0]}/{conn.execute('SELECT key FROM bom_lines WHERE id=?', (bom_line_ids[0],)).fetchone()['key']}"


def test_approved_ecn_clears_a_plan_level_variance():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    bid = bom_line_ids[0]
    serial = serials[0]
    conn.execute(
        "UPDATE as_built SET part_number='PN-NEW-REV2', measured_value=999.0 WHERE serial=? AND bom_line_id=?",
        (serial, bid),
    )
    assert dt.audit_pair(conn, serial, bid) != []  # unexplained before the ECN
    dt.apply_approved_ecn(conn, bid, "PN-NEW-REV2", "A", 999.0)
    assert dt.audit_pair(conn, serial, bid) == []  # the ECN makes it the new effective plan


def test_signed_deviation_clears_a_one_off_variance():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    bid, serial = bom_line_ids[0], serials[0]
    conn.execute("UPDATE as_built SET revision='Z' WHERE serial=? AND bom_line_id=?", (serial, bid))
    assert dt.audit_pair(conn, serial, bid) != []
    conn.execute(
        "INSERT INTO deviations (key, serial, bom_line_id, status) VALUES ('dev1', ?, ?, 'signed')",
        (serial, bid),
    )
    assert dt.audit_pair(conn, serial, bid) == []
    # a deviation only clears the one serial it names, not the rest of the fleet
    assert dt.audit_pair(conn, serials[1], bid) == []  # serials[1] was never mutated


def test_unsigned_deviation_does_not_clear_a_variance():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    bid, serial = bom_line_ids[0], serials[0]
    conn.execute("UPDATE as_built SET revision='Z' WHERE serial=? AND bom_line_id=?", (serial, bid))
    conn.execute(
        "INSERT INTO deviations (key, serial, bom_line_id, status) VALUES ('dev1', ?, ?, 'unsigned')",
        (serial, bid),
    )
    variances = dt.audit_pair(conn, serial, bid)
    assert [v.variance_class for v in variances] == ["revision_mismatch"]


def test_orphaned_maintenance_record_is_flagged():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    bid, serial = bom_line_ids[0], serials[0]
    conn.execute("DELETE FROM as_built WHERE serial=? AND bom_line_id=?", (serial, bid))
    plan = conn.execute("SELECT * FROM bom_lines WHERE id=?", (bid,)).fetchone()
    conn.execute(
        "INSERT INTO as_maintained (serial, bom_line_id, part_number, revision, measured_value) "
        "VALUES (?, ?, ?, 'A', ?)",
        (serial, bid, plan["part_number"], plan["nominal_value"]),
    )
    variances = dt.audit_pair(conn, serial, bid)
    assert [v.variance_class for v in variances] == ["orphaned_maintenance_record"]


def test_publish_refuses_on_any_unexplained_variance_and_passes_when_clean():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    ok, variances = dt.publish(conn, serials[0], bom_line_ids)
    assert ok and variances == []
    conn.execute(
        "UPDATE as_built SET part_number='BOGUS' WHERE serial=? AND bom_line_id=?",
        (serials[0], bom_line_ids[3]),
    )
    ok2, variances2 = dt.publish(conn, serials[0], bom_line_ids)
    assert not ok2
    assert len(variances2) == 1


def test_seed_variances_produces_180_across_6_distinct_classes():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    seeded = dt.seed_variances(conn, serials, bom_line_ids)
    assert len(seeded) == 180
    by_class = {}
    for cls, _s, _b in seeded:
        by_class[cls] = by_class.get(cls, 0) + 1
    assert by_class == {cls: 30 for cls in dt.VARIANCE_CLASSES}
    pairs = [(s, b) for _cls, s, b in seeded]
    assert len(set(pairs)) == 180  # every seeded pair is distinct


def _brute_force_audit(conn, serial, bom_line_id):
    """Reference oracle: re-derive the effective plan and every comparison
    from the raw rows with no helper functions shared with audit_pair,
    for the one path audit_pair's own logic is least obvious on (an
    approved ECN overriding the original plan)."""
    bom_line = conn.execute("SELECT * FROM bom_lines WHERE id=?", (bom_line_id,)).fetchone()
    built = conn.execute(
        "SELECT * FROM as_built WHERE serial=? AND bom_line_id=?", (serial, bom_line_id)
    ).fetchone()
    if built is None:
        return "missing_or_orphan"
    ecn = conn.execute(
        "SELECT * FROM change_notices WHERE bom_line_id=? AND status='approved'", (bom_line_id,)
    ).fetchone()
    part = ecn["authorized_part_number"] if ecn else bom_line["part_number"]
    return "match" if built["part_number"] == part else "mismatch"


def test_audit_pair_agrees_with_a_brute_force_oracle_on_the_ecn_path():
    conn = _built_conn()
    bom_line_ids = dt.build_bom(conn)
    serials = dt.build_fleet(conn, bom_line_ids)
    bid, serial = bom_line_ids[0], serials[0]
    conn.execute("UPDATE as_built SET part_number='PN-NEW' WHERE serial=? AND bom_line_id=?", (serial, bid))
    dt.apply_approved_ecn(conn, bid, "PN-NEW", "A",
                           conn.execute("SELECT nominal_value FROM bom_lines WHERE id=?", (bid,)).fetchone()[0])
    oracle = _brute_force_audit(conn, serial, bid)
    audited = dt.audit_pair(conn, serial, bid)
    assert oracle == "match"
    assert audited == []
