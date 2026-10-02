from trace_workbench import docgen
from trace_workbench.api_app import app, endpoint_count
from trace_workbench.stories_seed import STORY_DEFS


def _ac_index():
    pairs = [(s["operation_id"], s["acceptance_criteria"]) for s in STORY_DEFS]
    return docgen.build_acceptance_criteria_index(pairs)


def test_draft_count_matches_live_endpoint_count_not_a_hardcoded_48():
    schema = app.openapi()
    drafts = docgen.draft_all_endpoints(schema, _ac_index())
    assert len(drafts) == endpoint_count(schema)
    assert endpoint_count(schema) == 48  # true today; the assertion above is the real invariant


def test_all_48_endpoints_get_a_non_trivial_draft():
    schema = app.openapi()
    drafts = docgen.draft_all_endpoints(schema, _ac_index())
    non_trivial = 0
    total = 0
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            total += 1
            draft = drafts[operation["operationId"]]
            if docgen.is_non_trivial(draft, path, method):
                non_trivial += 1
    assert total == 48
    assert non_trivial == 48


def test_draft_cites_its_own_acceptance_criteria_when_available():
    schema = app.openapi()
    drafts = docgen.draft_all_endpoints(schema, _ac_index())
    # every operation has >=1 story in this design, so every draft should
    # carry an "Acceptance criteria:" clause
    for op_id, draft in drafts.items():
        assert "Acceptance criteria:" in draft, op_id


def test_without_acceptance_criteria_draft_is_still_non_trivial_from_schema_alone():
    schema = app.openapi()
    drafts = docgen.draft_all_endpoints(schema, {})  # empty AC index
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            draft = drafts[operation["operationId"]]
            assert docgen.is_non_trivial(draft, path, method)
            assert "Acceptance criteria:" not in draft
