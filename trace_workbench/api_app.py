"""A real, inspectable FastAPI service exposing the 48-endpoint OpenAPI
contract that the Agile story layer (stories_seed.py), the release gate
(story_gate.py), and the documentation generator (docgen.py) all read
from the live schema.

Scope, stated precisely: this is a thin CRUD surface over twelve
in-memory resources from the same simulated contrast-injector domain as
the original 86-requirement tree in domain_data.py (protocols, injection
records, alarms, devices, reservoirs, calibrations, maintenance records,
audit events, network configs, operators, occlusion events, and
reports). Each resource gets four real operations (list, create, get by
id, update), 12 x 4 = 48. The business logic is deliberately shallow (an
in-memory dict per resource, no persistence, no auth): the point of this
module is a real, inspectable OpenAPI contract with genuine path
parameters, request bodies, and response schemas that a documentation
generator and a story-to-contract linker can read directly from
`app.openapi()`, not a hand-maintained duplicate list of 48 endpoint
names. Nothing here is read by the pre-existing SQLite traceability
tool; it is new surface for the story layer only.
"""
# Deliberately no `from __future__ import annotations` here: make_crud_router
# builds each resource's routes with `Model` as a local closure variable, and
# FastAPI/Pydantic resolve type hints against a function's module globals, not
# its closure. With postponed evaluation the annotations become the string
# "Model" and resolve to an unbound ForwardRef instead of the real class
# (found by running this module directly; see README Findings). Keeping
# annotations eager (the Python 3.12 default) makes each annotation the
# actual Pydantic model object at function-definition time.

from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field


# --- resource models --------------------------------------------------
# (resource_plural, resource_singular, Pydantic model, example factory)

class Protocol(BaseModel):
    id: Optional[int] = None
    name: str
    exam_type: str
    flow_rate_ml_s: float
    volume_ml: float


class Injection(BaseModel):
    id: Optional[int] = None
    protocol_id: int
    patient_ref: str
    delivered_volume_ml: float
    status: str = Field(description="one of: pending, in_progress, complete, halted")


class Alarm(BaseModel):
    id: Optional[int] = None
    code: str
    priority: str = Field(description="one of: high, medium, low")
    message: str
    acknowledged: bool = False


class Device(BaseModel):
    id: Optional[int] = None
    serial_number: str
    model: str
    firmware_version: str
    status: str = Field(description="one of: ready, in_use, service, fault")


class Reservoir(BaseModel):
    id: Optional[int] = None
    lot_number: str
    concentration_mg_ml: float
    volume_remaining_ml: float
    expiration_date: str


class Calibration(BaseModel):
    id: Optional[int] = None
    device_id: int
    calibration_type: str
    reference_value: float
    measured_value: float


class MaintenanceRecord(BaseModel):
    id: Optional[int] = None
    device_id: int
    service_type: str
    technician: str
    cycle_count: int


class AuditEvent(BaseModel):
    id: Optional[int] = None
    actor: str
    action: str
    entity: str
    timestamp: str


class NetworkConfig(BaseModel):
    id: Optional[int] = None
    device_id: int
    hostname: str
    tls_enabled: bool = True
    emr_endpoint: str


class Operator(BaseModel):
    id: Optional[int] = None
    badge_id: str
    name: str
    role: str
    active: bool = True


class OcclusionEvent(BaseModel):
    id: Optional[int] = None
    injection_id: int
    pressure_psi: float
    threshold_psi: float
    resolved: bool = False


class Report(BaseModel):
    id: Optional[int] = None
    report_type: str
    period_start: str
    period_end: str
    generated_by: str


RESOURCES = [
    ("protocols", "protocol", Protocol),
    ("injections", "injection", Injection),
    ("alarms", "alarm", Alarm),
    ("devices", "device", Device),
    ("reservoirs", "reservoir", Reservoir),
    ("calibrations", "calibration", Calibration),
    ("maintenance-records", "maintenance_record", MaintenanceRecord),
    ("audit-events", "audit_event", AuditEvent),
    ("network-configs", "network_config", NetworkConfig),
    ("operators", "operator", Operator),
    ("occlusion-events", "occlusion_event", OcclusionEvent),
    ("reports", "report", Report),
]


def make_crud_router(resource: str, singular: str, Model) -> APIRouter:
    """Four real operations for one resource, backed by a fresh in-memory
    dict closed over by this call (not a module-level shared loop
    variable, so there is no late-binding hazard across the 12 calls in
    build_app()). operation_id is set explicitly so the story layer links
    to a stable name instead of FastAPI's generated one."""
    router = APIRouter()
    store: dict[int, Model] = {}

    @router.get(f"/{resource}", response_model=list[Model], operation_id=f"list_{resource.replace('-', '_')}")
    def list_items():
        return list(store.values())

    @router.post(f"/{resource}", response_model=Model, status_code=201, operation_id=f"create_{singular}")
    def create_item(item: Model):
        new_id = max(store.keys(), default=0) + 1
        obj = item.model_copy(update={"id": new_id})
        store[new_id] = obj
        return obj

    @router.get(f"/{resource}/{{item_id}}", response_model=Model, operation_id=f"get_{singular}")
    def get_item(item_id: int):
        if item_id not in store:
            raise HTTPException(status_code=404, detail=f"{singular} {item_id} not found")
        return store[item_id]

    @router.put(f"/{resource}/{{item_id}}", response_model=Model, operation_id=f"update_{singular}")
    def update_item(item_id: int, item: Model):
        if item_id not in store:
            raise HTTPException(status_code=404, detail=f"{singular} {item_id} not found")
        obj = item.model_copy(update={"id": item_id})
        store[item_id] = obj
        return obj

    return router


def build_app() -> FastAPI:
    app = FastAPI(
        title="Contrast Injector Operations API (simulated)",
        description=(
            "A simulated operations API for the contrast-injector product used as the "
            "traced artifact for the Agile story-to-release gate. Twelve resources, four "
            "operations each (list, create, get, update): 48 endpoints total."
        ),
        version="1.0.0",
    )
    for resource, singular, Model in RESOURCES:
        app.include_router(make_crud_router(resource, singular, Model))
    return app


app = build_app()


def endpoint_count(openapi_schema: dict) -> int:
    """Count real operations (path, method) pairs in a live OpenAPI schema,
    excluding the schema's own non-operation keys. Used everywhere this
    project needs "48" so the number is always counted from the live
    schema, never hardcoded."""
    count = 0
    for _path, methods in openapi_schema.get("paths", {}).items():
        for method in methods:
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                count += 1
    return count


if __name__ == "__main__":
    schema = app.openapi()
    print(f"{endpoint_count(schema)} endpoints across {len(schema.get('paths', {}))} paths")
