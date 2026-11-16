from trace_workbench import hazards, domain_data


def test_fourteen_hazards_one_per_user_need():
    assert len(hazards.HAZARDS) == 14
    un_keys = {row[0] for row in domain_data.USER_NEEDS}
    hazard_un_keys = {un_key for _hz_key, un_key, _text in hazards.HAZARDS}
    assert hazard_un_keys == un_keys  # total, 1:1 mapping, no gaps, no duplicates


def test_hazard_keys_and_texts_are_unique_and_non_empty():
    hz_keys = [row[0] for row in hazards.HAZARDS]
    assert len(hz_keys) == len(set(hz_keys))
    for _hz_key, _un_key, text in hazards.HAZARDS:
        assert text.strip()


def test_every_l1_requirement_has_a_hazard_matching_its_user_need(seeded_conn):
    conn = seeded_conn
    rows = conn.execute(
        "SELECT r.key, h.user_need_id AS hazard_un_id, r.user_need_id "
        "FROM requirements r JOIN hazards h ON h.id = r.hazard_id "
        "WHERE r.level = 'L1'"
    ).fetchall()
    assert len(rows) > 0
    for row in rows:
        assert row["hazard_un_id"] == row["user_need_id"]


def test_every_l2_requirement_has_no_direct_hazard(seeded_conn):
    conn = seeded_conn
    n = conn.execute(
        "SELECT COUNT(*) c FROM requirements WHERE level = 'L2' AND hazard_id IS NOT NULL"
    ).fetchone()["c"]
    assert n == 0


def test_every_requirement_reaches_a_hazard(seeded_conn):
    ok, unreachable = hazards.every_requirement_reaches_a_hazard(seeded_conn)
    assert ok, unreachable


def test_hazard_tree_contains_all_86_requirements(seeded_conn):
    tree = hazards.build_hazard_tree(seeded_conn)
    assert len(tree) == 14
    total = 0
    for hazard in tree:
        total += len(hazard["l1"])
        for l1 in hazard["l1"]:
            total += len(l1["l2"])
    assert total == 86
