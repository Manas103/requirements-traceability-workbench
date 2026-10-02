"""The "test" link every story claims in the PostgreSQL story layer
points at a node id in this file: one real, in-process TestClient
exercise of that story's linked operation, parametrized by story key so
every node_id stored in story_db (`tests/test_story_endpoints.py::
test_story_endpoint[<key>]`) is an actual, collectible pytest node id,
not just a string sitting in a database column.
scripts/run_story_gate.py cross-checks every recorded node id against
real `pytest --collect-only` output for exactly this reason.

All 60 stories are parametrized here, deliberately including the 9
whose (key, "test") pair is in GAP_PAIRS: the seeded gap for the "test"
link type models a backlog bookkeeping gap (the story's test_links row
was never recorded), not a missing test in the suite, since the
engineering practice of testing every endpoint should not regress just
because a tracker row is missing. The gate still fails those 9 stories
for a missing "test" link, because story_db.populate_schema does not
insert their test_links row regardless of this file; see README.
"""
import pytest
from fastapi.testclient import TestClient

from trace_workbench.api_app import app
from trace_workbench.stories_seed import STORY_DEFS

EXAMPLE_PAYLOADS = {
    "protocols": {"name": "chest_ct_contrast", "exam_type": "CT", "flow_rate_ml_s": 4.0, "volume_ml": 100.0},
    "injections": {"protocol_id": 1, "patient_ref": "sim-patient-001", "delivered_volume_ml": 80.0, "status": "complete"},
    "alarms": {"code": "AIR_IN_LINE", "priority": "high", "message": "air column detected", "acknowledged": False},
    "devices": {"serial_number": "INJ-0001", "model": "CI-200", "firmware_version": "3.4.1", "status": "ready"},
    "reservoirs": {"lot_number": "LOT-5521", "concentration_mg_ml": 320.0, "volume_remaining_ml": 150.0, "expiration_date": "2027-01-01"},
    "calibrations": {"device_id": 1, "calibration_type": "flow_rate", "reference_value": 4.0, "measured_value": 3.98},
    "maintenance-records": {"device_id": 1, "service_type": "reprocessing", "technician": "J. Alvarez", "cycle_count": 42},
    "audit-events": {"actor": "operator-07", "action": "parameter_change", "entity": "protocol:3", "timestamp": "2026-07-01T10:00:00Z"},
    "network-configs": {"device_id": 1, "hostname": "injector-07.lan", "tls_enabled": True, "emr_endpoint": "https://emr.example.local"},
    "operators": {"badge_id": "B-1042", "name": "J. Alvarez", "role": "technologist", "active": True},
    "occlusion-events": {"injection_id": 1, "pressure_psi": 210.0, "threshold_psi": 200.0, "resolved": False},
    "reports": {"report_type": "monthly_service_review", "period_start": "2026-06-01", "period_end": "2026-06-30", "generated_by": "scheduler"},
}


def _exercise(client: TestClient, story: dict):
    resource = story["resource"]
    operation = story["operation"]
    payload = EXAMPLE_PAYLOADS[resource]

    if operation == "list":
        resp = client.get(f"/{resource}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        return

    if operation == "create":
        resp = client.post(f"/{resource}", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] is not None
        return

    created = client.post(f"/{resource}", json=payload).json()
    item_id = created["id"]

    if operation == "get":
        resp = client.get(f"/{resource}/{item_id}")
        assert resp.status_code == 200
        return

    if operation == "update":
        resp = client.put(f"/{resource}/{item_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["id"] == item_id
        return

    raise AssertionError(f"unknown operation {operation!r}")


@pytest.mark.parametrize("story", STORY_DEFS, ids=[s["key"] for s in STORY_DEFS])
def test_story_endpoint(story):
    client = TestClient(app)
    _exercise(client, story)
