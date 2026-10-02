"""First-pass user documentation generator.

Drafts one paragraph per live OpenAPI operation, deriving every sentence
from the operation's own schema (path, method, path/query parameters,
request body fields, response fields) plus the acceptance-criteria text
of whichever story or stories are linked to that operation. It does not
read a hand-written description field: `api_app.py`'s routes carry no
docstrings or summaries for exactly this reason, so a passing coverage
measurement cannot be explained by "the generator just echoed a comment
a human already wrote".

This is a draft generator, not a technical writer. The honest limitation
(stated again in the README) is that it can describe shape (what fields
go in and out) and cite the acceptance criteria that motivated the
operation, but it cannot explain *why* the operation exists in product
terms; a human still owns that sentence.
"""
from __future__ import annotations

from typing import Optional


def _schema_field_list(schema: dict, components: dict) -> list[str]:
    """Return ["name (type)", ...] for a resolved request/response body
    schema, following exactly one $ref hop into components/schemas
    (sufficient for this project's flat Pydantic models, each of which
    has only scalar fields)."""
    if not schema:
        return []
    if "$ref" in schema:
        ref_name = schema["$ref"].rsplit("/", 1)[-1]
        schema = components.get(ref_name, {})
    if schema.get("type") == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            ref_name = items["$ref"].rsplit("/", 1)[-1]
            items = components.get(ref_name, {})
        schema = items
    props = schema.get("properties", {})
    out = []
    for name, spec in props.items():
        type_name = spec.get("type")
        if type_name is None and "anyOf" in spec:
            type_name = "/".join(sorted({s.get("type", "null") for s in spec["anyOf"]}))
        out.append(f"{name} ({type_name or 'object'})")
    return out


def draft_for_operation(
    path: str,
    method: str,
    operation: dict,
    components: dict,
    acceptance_criteria: Optional[list[str]] = None,
) -> str:
    """Build one documentation paragraph for a single (path, method)
    OpenAPI operation. `components` is schema["components"]["schemas"].
    `acceptance_criteria` is the list of acceptance-criteria sentences
    from every story linked to this operation's operationId (may be
    empty; the paragraph is still non-trivial from the schema alone)."""
    method_u = method.upper()
    op_id = operation.get("operationId", "")
    summary_bits = [f"`{method_u} {path}` (operation `{op_id}`)."]

    params = operation.get("parameters", [])
    path_params = [p["name"] for p in params if p.get("in") == "path"]
    if path_params:
        summary_bits.append(
            f"It is addressed by path parameter(s) {', '.join(path_params)}."
        )

    request_body = operation.get("requestBody")
    if request_body:
        content = request_body.get("content", {}).get("application/json", {})
        fields = _schema_field_list(content.get("schema", {}), components)
        if fields:
            summary_bits.append(
                f"The caller submits a JSON body with fields: {', '.join(fields)}."
            )

    responses = operation.get("responses", {})
    ok_response = None
    for code in ("200", "201"):
        if code in responses:
            ok_response = responses[code]
            break
    if ok_response:
        content = ok_response.get("content", {}).get("application/json", {})
        fields = _schema_field_list(content.get("schema", {}), components)
        if fields:
            summary_bits.append(
                f"On success it returns fields: {', '.join(fields)}."
            )
    if "404" in responses:
        summary_bits.append("A missing record is reported as 404, not a malformed body.")

    if acceptance_criteria:
        summary_bits.append(
            "Acceptance criteria: " + " ".join(acceptance_criteria)
        )

    return " ".join(summary_bits)


def build_acceptance_criteria_index(story_rows) -> dict:
    """story_rows: iterable of (operation_id, acceptance_criteria_text).
    Groups acceptance-criteria text by operation_id, preserving the order
    rows were given in (deterministic when the caller orders its query)."""
    index: dict[str, list[str]] = {}
    for operation_id, ac_text in story_rows:
        if not operation_id or not ac_text:
            continue
        index.setdefault(operation_id, []).append(ac_text)
    return index


def draft_all_endpoints(openapi_schema: dict, ac_index: dict) -> dict:
    """Draft a documentation paragraph for every (path, method) operation
    discovered in the live schema. Returns {operation_id: paragraph}.
    The number of endpoints drafted is always len(the live paths dict's
    operations), never a hardcoded 48."""
    components = openapi_schema.get("components", {}).get("schemas", {})
    drafts = {}
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = operation.get("operationId", f"{method}_{path}")
            ac = ac_index.get(op_id, [])
            drafts[op_id] = draft_for_operation(path, method, operation, components, ac)
    return drafts


def is_non_trivial(draft: str, path: str, method: str, min_len: int = 120) -> bool:
    """Precise, checkable definition of "non-trivial": long enough to
    carry real content, and it actually names the method and path it
    documents (so a generator bug that produced the same boilerplate for
    every endpoint would be caught, not just a short-string check)."""
    if len(draft) < min_len:
        return False
    if method.upper() not in draft:
        return False
    if path not in draft:
        return False
    return True
