from fastapi.testclient import TestClient

from trace_workbench.api_app import RESOURCES, app, endpoint_count


def test_live_schema_has_48_endpoints():
    schema = app.openapi()
    assert endpoint_count(schema) == 48


def test_every_resource_has_all_four_crud_operations():
    schema = app.openapi()
    op_ids = set()
    for methods in schema["paths"].values():
        for op in methods.values():
            op_ids.add(op["operationId"])
    for resource, singular, _Model in RESOURCES:
        list_op = f"list_{resource.replace('-', '_')}"
        assert list_op in op_ids
        assert f"create_{singular}" in op_ids
        assert f"get_{singular}" in op_ids
        assert f"update_{singular}" in op_ids
    assert len(RESOURCES) == 12


def test_crud_round_trip_in_process():
    """In-process TestClient, no real socket (per project resource rules):
    create a protocol, read it back by id, update it, confirm the update
    stuck, and confirm list contains it."""
    client = TestClient(app)
    payload = {"name": "chest_ct_contrast", "exam_type": "CT", "flow_rate_ml_s": 4.0, "volume_ml": 100.0}
    created = client.post("/protocols", json=payload).json()
    assert created["id"] is not None

    fetched = client.get(f"/protocols/{created['id']}").json()
    assert fetched["name"] == "chest_ct_contrast"

    updated_payload = dict(payload, name="chest_ct_contrast_v2")
    updated = client.put(f"/protocols/{created['id']}", json=updated_payload).json()
    assert updated["name"] == "chest_ct_contrast_v2"
    assert updated["id"] == created["id"]

    listed = client.get("/protocols").json()
    assert any(p["id"] == created["id"] for p in listed)


def test_get_missing_id_returns_404():
    client = TestClient(app)
    resp = client.get("/protocols/999999")
    assert resp.status_code == 404
