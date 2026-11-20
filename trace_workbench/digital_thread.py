"""
A BOM-anchored digital thread grafted onto the same 86-requirement tree:
as-designed is the existing requirement decomposition, as-planned is one
BOM line per L1 requirement (a subsystem requirement's L2 children trace
to the same BOM line as their L1 parent, via `requirement_bom_line`), and
as-built/as-maintained are per-serial-unit records against that plan for
a simulated fleet of one product.

Six independent ways a unit's views can disagree, each either explained
by an approved change notice (a standing, bom-line-level authorization)
or a signed deviation (a one-off, per-serial authorization) or flagged:

  part_substitution        as-built part number != the effective plan's
  revision_mismatch        as-built revision != the effective plan's
  spec_out_of_tolerance    as-built measured value outside the effective
                            plan's tolerance band
  missing_build_record     a (serial, bom_line) pair with neither an
                            as-built nor an as-maintained record at all
  unauthorized_rework      as-maintained differs from as-built with no
                            signed deviation for that (serial, bom_line)
  orphaned_maintenance_record   an as-maintained record exists for a
                            (serial, bom_line) with no as-built record

"The effective plan" is the bom_line's own nominal/part/revision, unless
an *approved* change_notices row exists for that bom_line, in which case
its authorized_* values are the effective plan instead; this is what
"disagree without an approved change notice" means in code. A deviation
is checked second, and only ever clears one specific (serial, bom_line).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

SEED_BOM = 20260901
SEED_FLEET = 20260902
SEED_MAINTENANCE = 20260903
SEED_VARIANCES = 20260904
SEED_CLEAN_SAMPLE = 20260905

N_UNITS = 50
N_SEEDED_PER_CLASS = 30
VARIANCE_CLASSES = [
    "part_substitution",
    "revision_mismatch",
    "spec_out_of_tolerance",
    "missing_build_record",
    "unauthorized_rework",
    "orphaned_maintenance_record",
]


@dataclass
class Variance:
    variance_class: str
    serial: str
    bom_line_key: str
    detail: str

    @property
    def item(self) -> str:
        return f"{self.serial}/{self.bom_line_key}"


# --- as-planned: one BOM line per L1 requirement ---------------------------

def build_bom(conn, seed: int = SEED_BOM) -> List[int]:
    rng = random.Random(seed)
    l1_reqs = conn.execute(
        "SELECT id, key FROM requirements WHERE level='L1' ORDER BY id"
    ).fetchall()
    bom_line_ids = []
    for req in l1_reqs:
        part_number = f"PN-{req['key'][:12].upper().replace('_', '-')}"
        nominal = round(rng.uniform(10.0, 500.0), 2)
        tolerance = round(nominal * 0.05, 2)
        cur = conn.execute(
            "INSERT INTO bom_lines (key, requirement_id, part_number, revision, "
            "spec_attribute, nominal_value, tolerance, unit_of_measure) "
            "VALUES (?, ?, ?, 'A', 'spec_value', ?, ?, 'su')",
            (f"bom_{req['key']}", req["id"], part_number, nominal, tolerance),
        )
        bom_line_ids.append(cur.lastrowid)
    return bom_line_ids


def requirement_bom_line(conn, requirement_id: int) -> Optional[dict]:
    """Walk up to the L1 ancestor (a requirement already is one, or its
    parent is) and return that ancestor's bom_line row, or None if the
    tree has no L1 ancestor (should not happen for a well-formed tree)."""
    row = conn.execute(
        "SELECT id, level, parent_id FROM requirements WHERE id=?", (requirement_id,)
    ).fetchone()
    while row is not None and row["level"] != "L1":
        row = conn.execute(
            "SELECT id, level, parent_id FROM requirements WHERE id=?", (row["parent_id"],)
        ).fetchone()
    if row is None:
        return None
    return conn.execute("SELECT * FROM bom_lines WHERE requirement_id=?", (row["id"],)).fetchone()


# --- as-built: a fleet of serialized units, clean by construction ----------

def build_fleet(conn, bom_line_ids: List[int], n_units: int = N_UNITS, seed: int = SEED_FLEET):
    rng = random.Random(seed)
    serials = [f"SN-{i:04d}" for i in range(1, n_units + 1)]
    for s in serials:
        conn.execute("INSERT INTO units (serial) VALUES (?)", (s,))
    bom_lines = {bid: conn.execute("SELECT * FROM bom_lines WHERE id=?", (bid,)).fetchone()
                 for bid in bom_line_ids}
    for serial in serials:
        for bid in bom_line_ids:
            plan = bom_lines[bid]
            noise = rng.uniform(-0.3, 0.3) * plan["tolerance"]
            conn.execute(
                "INSERT INTO as_built (serial, bom_line_id, part_number, revision, measured_value) "
                "VALUES (?, ?, ?, ?, ?)",
                (serial, bid, plan["part_number"], plan["revision"], plan["nominal_value"] + noise),
            )
    return serials


def seed_clean_maintenance(conn, serials: List[int], bom_line_ids: List[int],
                            exclude_pairs=frozenset(),
                            n_records: int = 300, seed: int = SEED_MAINTENANCE):
    """Routine, fully-explained maintenance: either an exact reinspection
    (identical to as-built) or a signed, deviation-covered part swap."""
    rng = random.Random(seed)
    eligible = [(s, b) for s in serials for b in bom_line_ids if (s, b) not in exclude_pairs]
    pairs = rng.sample(eligible, n_records)
    for i, (serial, bid) in enumerate(pairs):
        built = conn.execute(
            "SELECT * FROM as_built WHERE serial=? AND bom_line_id=?", (serial, bid)
        ).fetchone()
        if built is None:
            continue
        if i % 3 == 0:
            # a legitimate, signed one-off substitution
            conn.execute(
                "INSERT INTO deviations (key, serial, bom_line_id, status) VALUES (?, ?, ?, 'signed')",
                (f"dev_{serial}_{bid}", serial, bid),
            )
            conn.execute(
                "INSERT INTO as_maintained (serial, bom_line_id, part_number, revision, measured_value) "
                "VALUES (?, ?, ?, ?, ?)",
                (serial, bid, built["part_number"] + "-R", built["revision"], built["measured_value"]),
            )
        else:
            conn.execute(
                "INSERT INTO as_maintained (serial, bom_line_id, part_number, revision, measured_value) "
                "VALUES (?, ?, ?, ?, ?)",
                (serial, bid, built["part_number"], built["revision"], built["measured_value"]),
            )


# --- seeded, unexplained variances, 30 per class, 180 total ----------------

def seed_variances(conn, serials: List[str], bom_line_ids: List[int],
                    seed: int = SEED_VARIANCES) -> List[Tuple[str, str, int]]:
    """Deliberately break 180 distinct (serial, bom_line) pairs, 30 per
    class, each left unexplained (no approved change notice, no signed
    deviation). Returns the (class, serial, bom_line_id) triples seeded,
    for scoring against what the auditor actually reports."""
    rng = random.Random(seed)
    all_pairs = [(s, b) for s in serials for b in bom_line_ids]
    rng.shuffle(all_pairs)
    chosen = all_pairs[: N_SEEDED_PER_CLASS * len(VARIANCE_CLASSES)]
    groups = {
        cls: chosen[i * N_SEEDED_PER_CLASS:(i + 1) * N_SEEDED_PER_CLASS]
        for i, cls in enumerate(VARIANCE_CLASSES)
    }
    seeded = []

    for serial, bid in groups["part_substitution"]:
        conn.execute(
            "UPDATE as_built SET part_number = part_number || '-UNAUTH' WHERE serial=? AND bom_line_id=?",
            (serial, bid),
        )
        seeded.append(("part_substitution", serial, bid))

    for serial, bid in groups["revision_mismatch"]:
        conn.execute(
            "UPDATE as_built SET revision = 'Z' WHERE serial=? AND bom_line_id=?", (serial, bid)
        )
        seeded.append(("revision_mismatch", serial, bid))

    for serial, bid in groups["spec_out_of_tolerance"]:
        plan = conn.execute("SELECT * FROM bom_lines WHERE id=?", (bid,)).fetchone()
        bad_value = plan["nominal_value"] + plan["tolerance"] * 5.0
        conn.execute(
            "UPDATE as_built SET measured_value=? WHERE serial=? AND bom_line_id=?",
            (bad_value, serial, bid),
        )
        seeded.append(("spec_out_of_tolerance", serial, bid))

    for serial, bid in groups["missing_build_record"]:
        conn.execute("DELETE FROM as_built WHERE serial=? AND bom_line_id=?", (serial, bid))
        seeded.append(("missing_build_record", serial, bid))

    for serial, bid in groups["unauthorized_rework"]:
        built = conn.execute(
            "SELECT * FROM as_built WHERE serial=? AND bom_line_id=?", (serial, bid)
        ).fetchone()
        conn.execute(
            "INSERT INTO as_maintained (serial, bom_line_id, part_number, revision, measured_value) "
            "VALUES (?, ?, ?, ?, ?)",
            (serial, bid, built["part_number"] + "-REWORK", built["revision"], built["measured_value"]),
        )
        seeded.append(("unauthorized_rework", serial, bid))

    for serial, bid in groups["orphaned_maintenance_record"]:
        conn.execute("DELETE FROM as_built WHERE serial=? AND bom_line_id=?", (serial, bid))
        plan = conn.execute("SELECT * FROM bom_lines WHERE id=?", (bid,)).fetchone()
        conn.execute(
            "INSERT INTO as_maintained (serial, bom_line_id, part_number, revision, measured_value) "
            "VALUES (?, ?, ?, ?, ?)",
            (serial, bid, plan["part_number"], plan["revision"], plan["nominal_value"]),
        )
        seeded.append(("orphaned_maintenance_record", serial, bid))

    conn.commit()
    return seeded


def apply_approved_ecn(conn, bom_line_id: int, authorized_part_number: str,
                        authorized_revision: str, authorized_value: float) -> int:
    """Issue an approved change notice that redefines a bom_line's effective
    plan. Returns the change_notices row id."""
    bom_line = conn.execute("SELECT key FROM bom_lines WHERE id=?", (bom_line_id,)).fetchone()
    cur = conn.execute(
        "INSERT INTO change_notices (key, bom_line_id, status, authorized_part_number, "
        "authorized_revision, authorized_value) VALUES (?, ?, 'approved', ?, ?, ?)",
        (f"ecn_{bom_line['key']}", bom_line_id, authorized_part_number,
         authorized_revision, authorized_value),
    )
    return cur.lastrowid


# --- the audit itself --------------------------------------------------

def _effective_plan(conn, bom_line) -> dict:
    ecn = conn.execute(
        "SELECT * FROM change_notices WHERE bom_line_id=? AND status='approved'", (bom_line["id"],)
    ).fetchone()
    if ecn is not None:
        return {"part_number": ecn["authorized_part_number"], "revision": ecn["authorized_revision"],
                "nominal_value": ecn["authorized_value"], "tolerance": bom_line["tolerance"]}
    return {"part_number": bom_line["part_number"], "revision": bom_line["revision"],
            "nominal_value": bom_line["nominal_value"], "tolerance": bom_line["tolerance"]}


def _has_signed_deviation(conn, serial: str, bom_line_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM deviations WHERE serial=? AND bom_line_id=? AND status='signed'",
        (serial, bom_line_id),
    ).fetchone()
    return row is not None


def audit_pair(conn, serial: str, bom_line_id: int) -> List[Variance]:
    bom_line = conn.execute("SELECT * FROM bom_lines WHERE id=?", (bom_line_id,)).fetchone()
    built = conn.execute(
        "SELECT * FROM as_built WHERE serial=? AND bom_line_id=?", (serial, bom_line_id)
    ).fetchone()
    maintained = conn.execute(
        "SELECT * FROM as_maintained WHERE serial=? AND bom_line_id=?", (serial, bom_line_id)
    ).fetchone()
    variances: List[Variance] = []

    if built is None:
        if maintained is None:
            variances.append(Variance("missing_build_record", serial, bom_line["key"],
                                       "no as-built record for a planned BOM line"))
        else:
            variances.append(Variance("orphaned_maintenance_record", serial, bom_line["key"],
                                       "as-maintained record with no as-built record"))
        return variances

    plan = _effective_plan(conn, bom_line)
    deviated = _has_signed_deviation(conn, serial, bom_line_id)

    if built["part_number"] != plan["part_number"] and not deviated:
        variances.append(Variance("part_substitution", serial, bom_line["key"],
                                   f"as-built part {built['part_number']} vs plan {plan['part_number']}"))
    if built["revision"] != plan["revision"] and not deviated:
        variances.append(Variance("revision_mismatch", serial, bom_line["key"],
                                   f"as-built revision {built['revision']} vs plan {plan['revision']}"))
    if abs(built["measured_value"] - plan["nominal_value"]) > plan["tolerance"] and not deviated:
        variances.append(Variance("spec_out_of_tolerance", serial, bom_line["key"],
                                   f"as-built {built['measured_value']} outside "
                                   f"{plan['nominal_value']}+/-{plan['tolerance']}"))

    if maintained is not None:
        changed = (maintained["part_number"], maintained["revision"], maintained["measured_value"]) != \
                  (built["part_number"], built["revision"], built["measured_value"])
        if changed and not deviated:
            variances.append(Variance("unauthorized_rework", serial, bom_line["key"],
                                       "as-maintained differs from as-built with no signed deviation"))

    return variances


def publish(conn, serial: str, bom_line_ids: List[int]) -> Tuple[bool, List[Variance]]:
    """Refuse to publish `serial`'s configuration if any BOM line it is
    responsible for has an unexplained variance; return (ok, variances)."""
    found: List[Variance] = []
    for bid in bom_line_ids:
        found.extend(audit_pair(conn, serial, bid))
    return (len(found) == 0, found)
