"""Tests against the real PostgreSQL server. Skip cleanly (not fail) if
PostgreSQL is not reachable at DATABASE_URL, matching this project's
documented convention for services that are not guaranteed to be
running. On this development machine a real WSL2 PostgreSQL 14 server is
reachable and these tests run for real against it; see README
"PostgreSQL, stated honestly"."""
from trace_workbench import story_db, story_gate
from trace_workbench.stories_seed import GAP_PAIRS, STORY_DEFS


def test_build_schema_with_seeded_gaps_and_gate_catches_all_22_by_name(pg_temp_schema):
    conn, schema = pg_temp_schema
    story_db.build_schema(conn, schema, STORY_DEFS, GAP_PAIRS)

    gaps_fast, gaps_reference, total_stories, agree = story_gate.run_gate(conn, schema)

    assert total_stories == 60
    assert agree, "fast gate and reference-oracle gate disagree"
    found_names = {(g.story_key, g.link_type) for g in gaps_fast}
    assert found_names == GAP_PAIRS
    assert len(found_names) == 22


def test_build_schema_clean_has_zero_false_blocks(pg_temp_schema):
    conn, schema = pg_temp_schema
    story_db.build_schema(conn, schema, STORY_DEFS, set())

    gaps_fast, gaps_reference, total_stories, agree = story_gate.run_gate(conn, schema)

    assert total_stories == 60
    assert agree
    assert gaps_fast == set()
    assert gaps_reference == set()


def test_gate_exit_semantics_fail_then_pass(pg_temp_schema):
    """The release gate's pass/fail boolean, exercised directly rather
    than by parsing scripts/run_story_gate.py's stdout: a backlog with
    any seeded gap must produce a non-empty gap set (fail), and the same
    backlog with gaps healed must produce an empty gap set (pass)."""
    conn, schema = pg_temp_schema
    story_db.build_schema(conn, schema, STORY_DEFS, {("story_protocol_create", "acceptance_criteria")})
    gaps_fast, _ref, _total, _agree = story_gate.run_gate(conn, schema)
    assert len(gaps_fast) == 1
    release_would_fail = bool(gaps_fast)
    assert release_would_fail is True

    story_db.build_schema(conn, schema, STORY_DEFS, set())
    gaps_fast2, _ref2, _total2, _agree2 = story_gate.run_gate(conn, schema)
    release_would_fail2 = bool(gaps_fast2)
    assert release_would_fail2 is False


def test_fetch_operation_ac_pairs_covers_all_48_operations_on_clean_schema(pg_temp_schema):
    conn, schema = pg_temp_schema
    story_db.build_schema(conn, schema, STORY_DEFS, set())
    pairs = story_db.fetch_operation_ac_pairs(conn, schema)
    op_ids = {op_id for op_id, _text in pairs}
    assert len(op_ids) == 48
