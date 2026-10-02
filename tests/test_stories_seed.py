from trace_workbench.api_app import app
from trace_workbench.seed import flatten_tree
from trace_workbench.stories_seed import (
    GAP_PAIRS, LINK_TYPES, RESOURCE_REQUIREMENT_LINK, STORY_DEFS, compute_gaps,
)


def test_exactly_60_stories_with_unique_keys():
    assert len(STORY_DEFS) == 60
    keys = [s["key"] for s in STORY_DEFS]
    assert len(set(keys)) == 60


def test_every_story_operation_id_exists_in_the_live_schema():
    schema = app.openapi()
    real_op_ids = {op["operationId"] for methods in schema["paths"].values() for op in methods.values()}
    story_op_ids = {s["operation_id"] for s in STORY_DEFS}
    assert story_op_ids <= real_op_ids
    # every one of the 48 live operations has at least one story, so the
    # documentation generator always has acceptance-criteria text to draw on
    assert story_op_ids == real_op_ids


def test_every_story_has_nonempty_acceptance_criteria_text():
    for s in STORY_DEFS:
        assert len(s["acceptance_criteria"]) > 20


def test_soft_requirement_links_point_at_real_requirement_keys():
    """RESOURCE_REQUIREMENT_LINK is a cross-store soft reference (the
    story layer lives in PostgreSQL, the requirement tree in SQLite);
    this is the independent check that every key it names actually
    exists in the 86-requirement tree, since there is no database-level
    foreign key to enforce it."""
    real_requirement_keys = {row[0] for row in flatten_tree()}
    assert len(RESOURCE_REQUIREMENT_LINK) == 12
    for resource, req_key in RESOURCE_REQUIREMENT_LINK.items():
        assert req_key in real_requirement_keys, f"{resource} -> {req_key} does not exist"


def test_gap_selection_is_exactly_22_and_deterministic():
    assert len(GAP_PAIRS) == 22
    a = compute_gaps()
    b = compute_gaps()
    assert a == b == GAP_PAIRS


def test_gap_selection_pairs_are_valid_and_disjoint():
    story_keys = {s["key"] for s in STORY_DEFS}
    seen = set()
    for key, link_type in GAP_PAIRS:
        assert key in story_keys
        assert link_type in LINK_TYPES
        assert (key, link_type) not in seen  # set already guarantees this, but assert explicitly
        seen.add((key, link_type))
    assert len(seen) == 22


def test_gap_selection_changes_with_a_different_seed():
    """Not a claim, just a sanity check that the shuffle is actually seed
    dependent rather than accidentally constant."""
    alt = compute_gaps(seed=1)
    assert alt != GAP_PAIRS
