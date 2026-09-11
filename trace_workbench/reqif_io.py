"""Honestly-scoped ReqIF export/import.

Real ReqIF (OMG formal spec 1.1) is a large interchange format built
around SPEC-OBJECT-TYPE / SPEC-TYPES definitions, typed attribute
definitions (XHTML, enumeration, datatype), SPEC-RELATION-TYPE
definitions, RELATION-GROUP, and a TOOL-EXTENSION section, all wrapped
in a CORE-CONTENT / REQ-IF-CONTENT envelope with a HEADER block.

What this module implements (and what it does not) is stated in the
README under "ReqIF scope"; the short version:

Implemented: SPEC-OBJECT elements (one per user need, requirement, test,
and risk control, each with plain-text ATTR children), SPEC-RELATION
elements (Verifies and Implements edges with a SUSPECT flag), and a
SPEC-HIERARCHY section that captures the requirement decomposition tree
as a flat list of nodes each carrying its own parent reference.

Not implemented: SPEC-OBJECT-TYPE/attribute-definition schemas (attribute
names are plain strings, not typed/validated against a declared type),
XHTML rich text in attribute values (plain text only), RELATION-GROUP,
TOOL-EXTENSION, and OMG's nested SPEC-HIERARCHY-NODE containment (a
real ReqIF file nests child SPEC-HIERARCHY-NODE elements inside their
parent; this module uses a flat list with a PARENT-REF attribute
instead, because it carries the identical tree information with far
less recursive XML-building and parsing code, at the cost of not being
byte-for-byte what a DOORS/Jama export would look like).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom


def _attr(parent, name, value):
    el = ET.SubElement(parent, "ATTR", {"NAME": name})
    el.text = "" if value is None else str(value)
    return el


def export_reqif(conn, path):
    root = ET.Element("REQ-IF", {"SCHEMA-NOTE": "honestly-scoped subset, see reqif_io.py"})

    spec_objects = ET.SubElement(root, "SPEC-OBJECTS")
    for r in conn.execute("SELECT id, key, text FROM user_needs ORDER BY id").fetchall():
        so = ET.SubElement(spec_objects, "SPEC-OBJECT", {
            "IDENTIFIER": f"un:{r['key']}", "TYPE": "UserNeed",
        })
        _attr(so, "text", r["text"])

    for r in conn.execute(
        "SELECT id, key, text, keyword, level, baseline_version, suspect "
        "FROM requirements ORDER BY id"
    ).fetchall():
        so = ET.SubElement(spec_objects, "SPEC-OBJECT", {
            "IDENTIFIER": f"req:{r['key']}", "TYPE": "Requirement",
        })
        _attr(so, "text", r["text"])
        _attr(so, "keyword", r["keyword"])
        _attr(so, "level", r["level"])
        _attr(so, "baseline_version", r["baseline_version"])
        _attr(so, "suspect", r["suspect"])

    for r in conn.execute(
        "SELECT id, key, name, exercises_keyword, procedure_text, result FROM tests ORDER BY id"
    ).fetchall():
        so = ET.SubElement(spec_objects, "SPEC-OBJECT", {
            "IDENTIFIER": f"test:{r['key']}", "TYPE": "Test",
        })
        _attr(so, "name", r["name"])
        _attr(so, "exercises_keyword", r["exercises_keyword"])
        _attr(so, "procedure_text", r["procedure_text"])
        _attr(so, "result", r["result"])

    for r in conn.execute("SELECT id, key, text FROM risk_controls ORDER BY id").fetchall():
        so = ET.SubElement(spec_objects, "SPEC-OBJECT", {
            "IDENTIFIER": f"rc:{r['key']}", "TYPE": "RiskControl",
        })
        _attr(so, "text", r["text"])

    spec_relations = ET.SubElement(root, "SPEC-RELATIONS")
    for r in conn.execute(
        "SELECT rt.suspect AS suspect, t.key AS test_key, req.key AS req_key "
        "FROM requirement_tests rt "
        "JOIN tests t ON t.id = rt.test_id JOIN requirements req ON req.id = rt.requirement_id "
        "ORDER BY rt.id"
    ).fetchall():
        ET.SubElement(spec_relations, "SPEC-RELATION", {
            "TYPE": "Verifies", "SOURCE": f"test:{r['test_key']}",
            "TARGET": f"req:{r['req_key']}", "SUSPECT": str(r["suspect"]),
        })
    for r in conn.execute(
        "SELECT rrc.suspect AS suspect, rc.key AS rc_key, req.key AS req_key "
        "FROM requirement_risk_controls rrc "
        "JOIN risk_controls rc ON rc.id = rrc.risk_control_id "
        "JOIN requirements req ON req.id = rrc.requirement_id "
        "ORDER BY rrc.id"
    ).fetchall():
        ET.SubElement(spec_relations, "SPEC-RELATION", {
            "TYPE": "Implements", "SOURCE": f"rc:{r['rc_key']}",
            "TARGET": f"req:{r['req_key']}", "SUSPECT": str(r["suspect"]),
        })

    spec_hierarchy = ET.SubElement(root, "SPEC-HIERARCHY")
    for r in conn.execute(
        "SELECT req.key AS req_key, un.key AS un_key, p.key AS parent_key "
        "FROM requirements req "
        "LEFT JOIN user_needs un ON un.id = req.user_need_id "
        "LEFT JOIN requirements p ON p.id = req.parent_id "
        "ORDER BY req.id"
    ).fetchall():
        parent_ref = f"un:{r['un_key']}" if r["un_key"] is not None else f"req:{r['parent_key']}"
        ET.SubElement(spec_hierarchy, "SPEC-HIERARCHY-NODE", {
            "REF": f"req:{r['req_key']}", "PARENT-REF": parent_ref,
        })

    xml_bytes = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(xml_bytes).toprettyxml(indent="  ")
    with open(path, "w", encoding="utf-8") as f:
        f.write(pretty)


def import_reqif(path, conn):
    """Populate an already-schema'd, empty connection from a ReqIF file
    written by export_reqif. Processes SPEC-HIERARCHY-NODE entries in
    file order, which is parent-before-child (see export_reqif), so a
    child's parent row always already exists by the time it is needed."""
    tree = ET.parse(path)
    root = tree.getroot()

    un_key_to_id = {}
    req_key_to_id = {}
    test_key_to_id = {}
    rc_key_to_id = {}
    so_attrs = {}  # identifier -> {name: text}

    for so in root.find("SPEC-OBJECTS"):
        identifier = so.attrib["IDENTIFIER"]
        so_type = so.attrib["TYPE"]
        attrs = {a.attrib["NAME"]: (a.text or "") for a in so.findall("ATTR")}
        so_attrs[identifier] = (so_type, attrs)

    for identifier, (so_type, attrs) in so_attrs.items():
        if so_type == "UserNeed":
            key = identifier.split(":", 1)[1]
            cur = conn.execute(
                "INSERT INTO user_needs (key, text) VALUES (?, ?)", (key, attrs["text"])
            )
            un_key_to_id[key] = cur.lastrowid
        elif so_type == "Test":
            key = identifier.split(":", 1)[1]
            cur = conn.execute(
                "INSERT INTO tests (key, name, exercises_keyword, procedure_text, result) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, attrs["name"], attrs["exercises_keyword"], attrs["procedure_text"],
                 attrs["result"]),
            )
            test_key_to_id[key] = cur.lastrowid
        elif so_type == "RiskControl":
            key = identifier.split(":", 1)[1]
            cur = conn.execute(
                "INSERT INTO risk_controls (key, text) VALUES (?, ?)", (key, attrs["text"])
            )
            rc_key_to_id[key] = cur.lastrowid
        # Requirement SPEC-OBJECTs are inserted below, driven by
        # SPEC-HIERARCHY order, since they need parent/user_need ids.

    for node in root.find("SPEC-HIERARCHY"):
        ref = node.attrib["REF"]
        parent_ref = node.attrib["PARENT-REF"]
        req_key = ref.split(":", 1)[1]
        _so_type, attrs = so_attrs[ref]
        if parent_ref.startswith("un:"):
            un_key = parent_ref.split(":", 1)[1]
            cur = conn.execute(
                "INSERT INTO requirements "
                "(key, text, keyword, level, user_need_id, parent_id, baseline_version, "
                "suspect) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
                (req_key, attrs["text"], attrs["keyword"], attrs["level"],
                 un_key_to_id[un_key], int(attrs["baseline_version"]), int(attrs["suspect"])),
            )
        else:
            parent_key = parent_ref.split(":", 1)[1]
            cur = conn.execute(
                "INSERT INTO requirements "
                "(key, text, keyword, level, user_need_id, parent_id, baseline_version, "
                "suspect) VALUES (?, ?, ?, ?, NULL, ?, ?, ?)",
                (req_key, attrs["text"], attrs["keyword"], attrs["level"],
                 req_key_to_id[parent_key], int(attrs["baseline_version"]),
                 int(attrs["suspect"])),
            )
        req_key_to_id[req_key] = cur.lastrowid

    for rel in root.find("SPEC-RELATIONS"):
        rel_type = rel.attrib["TYPE"]
        source = rel.attrib["SOURCE"]
        target = rel.attrib["TARGET"]
        suspect = int(rel.attrib["SUSPECT"])
        req_key = target.split(":", 1)[1]
        if rel_type == "Verifies":
            test_key = source.split(":", 1)[1]
            conn.execute(
                "INSERT INTO requirement_tests (requirement_id, test_id, suspect) "
                "VALUES (?, ?, ?)",
                (req_key_to_id[req_key], test_key_to_id[test_key], suspect),
            )
        elif rel_type == "Implements":
            rc_key = source.split(":", 1)[1]
            conn.execute(
                "INSERT INTO requirement_risk_controls "
                "(requirement_id, risk_control_id, suspect) VALUES (?, ?, ?)",
                (req_key_to_id[req_key], rc_key_to_id[rc_key], suspect),
            )

    conn.commit()


def snapshot(conn):
    """A comparable, id-independent view of the whole model, keyed by the
    natural `key` columns, used to prove the ReqIF round trip is
    lossless: snapshot(original) == snapshot(reimported)."""
    un = {
        r["key"]: r["text"]
        for r in conn.execute("SELECT key, text FROM user_needs").fetchall()
    }
    reqs = {}
    for r in conn.execute(
        "SELECT req.key AS key, req.text AS text, req.keyword AS keyword, "
        "req.level AS level, req.baseline_version AS baseline_version, "
        "req.suspect AS suspect, un.key AS un_key, p.key AS parent_key "
        "FROM requirements req "
        "LEFT JOIN user_needs un ON un.id = req.user_need_id "
        "LEFT JOIN requirements p ON p.id = req.parent_id"
    ).fetchall():
        reqs[r["key"]] = {
            "text": r["text"], "keyword": r["keyword"], "level": r["level"],
            "baseline_version": r["baseline_version"], "suspect": r["suspect"],
            "un_key": r["un_key"], "parent_key": r["parent_key"],
        }
    tests = {
        r["key"]: {
            "name": r["name"], "exercises_keyword": r["exercises_keyword"],
            "procedure_text": r["procedure_text"], "result": r["result"],
        }
        for r in conn.execute(
            "SELECT key, name, exercises_keyword, procedure_text, result FROM tests"
        ).fetchall()
    }
    rcs = {
        r["key"]: r["text"]
        for r in conn.execute("SELECT key, text FROM risk_controls").fetchall()
    }
    rt_links = sorted(
        (r["req_key"], r["test_key"], r["suspect"])
        for r in conn.execute(
            "SELECT req.key AS req_key, t.key AS test_key, rt.suspect AS suspect "
            "FROM requirement_tests rt "
            "JOIN requirements req ON req.id = rt.requirement_id "
            "JOIN tests t ON t.id = rt.test_id"
        ).fetchall()
    )
    rc_links = sorted(
        (r["req_key"], r["rc_key"], r["suspect"])
        for r in conn.execute(
            "SELECT req.key AS req_key, rc.key AS rc_key, rrc.suspect AS suspect "
            "FROM requirement_risk_controls rrc "
            "JOIN requirements req ON req.id = rrc.requirement_id "
            "JOIN risk_controls rc ON rc.id = rrc.risk_control_id"
        ).fetchall()
    )
    return {
        "user_needs": un, "requirements": reqs, "tests": tests, "risk_controls": rcs,
        "requirement_tests": rt_links, "requirement_risk_controls": rc_links,
    }
