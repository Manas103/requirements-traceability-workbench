"""Pure-Python seed content for the Agile story layer: 60 user stories,
each nominally tied (in the intended, pre-gap design) to an acceptance
criteria text, one of the 48 live API operations, a pytest node id, and
a documentation paragraph, plus a deterministic 22-of-240 gap selection
across those four link types.

This module has no database or network dependency, by design: the
60-story backlog, the per-story acceptance-criteria text, and the gap
selection are all plain Python data and a pure function, the same way
seed.py's assign_defects() is a pure function over the 86-requirement
tree. trace_workbench.story_db loads this data into PostgreSQL; it does
not invent any of it.

Twelve resources x 4 base operations (list, create, get, update) = 48
stories at minimum, one per operation. Twelve more stories add a second,
distinct scenario to one operation per resource (an edge case: an empty
list, a validation-adjacent create, a not-found get, or a partial
update), for 60 stories total covering 48 operations with 12 operations
doubly covered. Every operation has at least one story, so documentation
coverage (handled in docgen.py) always has acceptance-criteria text
available for every one of the 48 endpoints.
"""
from __future__ import annotations

import random

from trace_workbench.api_app import RESOURCES

# resource_plural -> an existing requirement key from domain_data.py that
# this resource's functionality is a soft, cross-store realization of.
# This is a *soft* reference (a text key, not a foreign key: the story
# layer lives in PostgreSQL and the requirement tree lives in SQLite, two
# different stores, which is the honest shape of how a backlog tool and a
# requirements tool actually relate in practice) exercised by
# test_stories_seed.py, which confirms every key named here really
# exists in the 86-requirement tree.
RESOURCE_REQUIREMENT_LINK = {
    "protocols": "protocol_library",
    "injections": "injection_record_completeness",
    "alarms": "alarm_priority_levels",
    "devices": "ip_rating_fluid_ingress",
    "reservoirs": "reservoir_level_sensing",
    "calibrations": "flow_rate_calibration",
    "maintenance-records": "reprocessing_cycle_validation",
    "audit-events": "audit_trail_user_actions",
    "network-configs": "network_isolation_degrade",
    "operators": "ui_lockout_cleaning",
    "occlusion-events": "occlusion_pressure_threshold",
    "reports": "alarm_log_export",
}

LINK_TYPES = ("acceptance_criteria", "api_contract", "test", "documentation")

OPERATIONS = ("list", "create", "get", "update")

# A short, human-readable acceptance-criteria sentence per (resource,
# operation), written as Given/When/Then, naming the resource plainly.
_AC_TEMPLATES = {
    "list": "Given {n} {resource} records exist, when a caller lists {resource}, "
            "then every record is returned in a stable order with no record omitted.",
    "create": "Given a valid {singular} payload, when a caller creates a {singular}, "
               "then the service assigns an id and the created record is retrievable by that id.",
    "get": "Given a {singular} id, when a caller requests that {singular}, then the full "
           "record is returned, or a 404 is returned if the id does not exist.",
    "update": "Given an existing {singular} id and a revised payload, when a caller updates "
               "that {singular}, then the stored record reflects every changed field and the "
               "id is unchanged.",
}

_EXTRA_AC_TEMPLATES = {
    "list": "Given zero {resource} records exist, when a caller lists {resource}, then an "
            "empty list is returned rather than an error.",
    "create": "Given a {singular} payload that reuses fields from an existing record, when a "
               "caller creates a second {singular}, then a distinct id is assigned and both "
               "records remain independently retrievable.",
    "get": "Given a {singular} id that was never created, when a caller requests that "
           "{singular}, then the service returns 404 rather than a malformed record.",
    "update": "Given an existing {singular} id and a payload that changes only one field, when "
               "a caller updates that {singular}, then the unspecified fields keep their prior "
               "values rather than being cleared.",
}


def _build_story_defs():
    """Build the 60 story definitions deterministically from RESOURCES
    (imported from the live FastAPI app's resource list, not retyped),
    so the story count and the operation coverage can never drift out of
    sync with the actual API surface."""
    stories = []
    for resource, singular, _Model in RESOURCES:
        requirement_key = RESOURCE_REQUIREMENT_LINK.get(resource)
        for op in OPERATIONS:
            key = f"story_{singular}_{op}"
            stories.append({
                "key": key,
                "title": f"{op.capitalize()} {resource}",
                "resource": resource,
                "singular": singular,
                "operation": op,
                "operation_id": f"{op}_{singular}" if op != "list" else f"list_{resource.replace('-', '_')}",
                "acceptance_criteria": _AC_TEMPLATES[op].format(
                    resource=resource.replace("-", " "), singular=singular, n=3,
                ),
                "requirement_key": requirement_key,
            })
    # 12 extra stories: one additional, distinct scenario per resource,
    # attached to that resource's "list" operation's edge case the first
    # time around, rotating which operation gets the extra scenario so
    # the 12 extra stories are not all "list" (keeps the 60-over-48
    # distribution varied rather than mechanical).
    for i, (resource, singular, _Model) in enumerate(RESOURCES):
        op = OPERATIONS[i % len(OPERATIONS)]
        requirement_key = RESOURCE_REQUIREMENT_LINK.get(resource)
        key = f"story_{singular}_{op}_edge"
        stories.append({
            "key": key,
            "title": f"{op.capitalize()} {resource} (edge case)",
            "resource": resource,
            "singular": singular,
            "operation": op,
            "operation_id": f"{op}_{singular}" if op != "list" else f"list_{resource.replace('-', '_')}",
            "acceptance_criteria": _EXTRA_AC_TEMPLATES[op].format(
                resource=resource.replace("-", " "), singular=singular,
            ),
            "requirement_key": requirement_key,
        })
    return stories


STORY_DEFS = _build_story_defs()

GAP_SEED = 9000
N_GAPS = 22


def compute_gaps(seed: int = GAP_SEED, n: int = N_GAPS):
    """Pure function: given the 60 story keys (in STORY_DEFS order) and
    the 4 link types, deterministically shuffle all 240 (story, type)
    pairs and return the first n as the seeded gap set. Mirrors
    seed.assign_defects: the seed is fixed so a rebuild always reproduces
    the same 22 gaps, and the detector code in story_gate.py was written
    once, against this fixed set, not adjusted after seeing results."""
    pairs = [(s["key"], t) for s in STORY_DEFS for t in LINK_TYPES]
    rng = random.Random(seed)
    rng.shuffle(pairs)
    return set(pairs[:n])


GAP_PAIRS = compute_gaps()


if __name__ == "__main__":
    print(f"{len(STORY_DEFS)} stories across {len(RESOURCES)} resources")
    print(f"{len(GAP_PAIRS)} seeded gaps out of {len(STORY_DEFS) * len(LINK_TYPES)} possible links")
