"""Hazard-anchored view of the requirements tree (Nov. 2026 extension).

The original tree (domain_data.py, seed.py) is anchored at 14 user
needs: "as a clinician, I need...". This module adds a second anchor,
14 hazards, one per user need, that names the loss event the need's
area exists to prevent rather than the capability the need asks for.
Nothing about the 86-requirement tree, the orphan/non-verifying
detectors, suspect propagation, or the ReqIF round trip changes: this
is a second root grafted onto the same L1 requirements, not a rebuild.

Each hazard text below is a direct recasting of its paired user need
already in domain_data.py, not new invented scope: the user need says
what a clinician needs the system to do; the hazard says what goes
wrong for the patient or clinician if the system fails to do it. The
mapping is 1:1 and total (every user need has exactly one hazard, every
hazard has exactly one user need), checked in tests/test_hazards.py.
"""
from __future__ import annotations

from . import domain_data

HAZARDS = [
    ("hz_needle", "un_needle",
     "Needle-stick injury to a clinician, or needle misinsertion into the "
     "patient, during contrast administration."),
    ("hz_catheter", "un_catheter",
     "Leakage or disconnection at the syringe-to-catheter connection during "
     "injection, causing contrast extravasation or line disconnection under "
     "pressure."),
    ("hz_flow", "un_flow",
     "Delivery of contrast at an incorrect flow rate or volume, producing a "
     "clinically inadequate or unsafe bolus."),
    ("hz_air", "un_air",
     "Injection of air into the patient's vasculature (air embolism)."),
    ("hz_reservoir", "un_reservoir",
     "Administration of expired, mismatched, or depleted contrast media due "
     "to untracked reservoir inventory or identity."),
    ("hz_occlusion", "un_occlusion",
     "Patient injury from a line occlusion or extravasation that goes "
     "undetected before injury occurs."),
    ("hz_alarm", "un_alarm",
     "A clinically significant alarm condition that goes unnoticed, is "
     "silenced too long, or is confused with a different alarm."),
    ("hz_ui", "un_ui",
     "Entry of a clinically unsafe injection parameter that the system "
     "accepts and executes."),
    ("hz_power", "un_power",
     "Unsafe pump behavior, or loss of in-progress protocol state, during a "
     "mains power interruption."),
    ("hz_data", "un_data",
     "An incomplete or tamper-undetectable injection record, compromising "
     "the patient record or a later audit."),
    ("hz_sterilization", "un_sterilization",
     "Cross-contamination between patients from a reusable component that "
     "was reused without validated, confirmed reprocessing."),
    ("hz_mechanical", "un_mechanical",
     "Loss of basic safety function from a mechanical or environmental "
     "event (drop, tip-over, fluid ingress) in the imaging suite."),
    ("hz_swsafety", "un_swsafety",
     "A runaway or hung main control loop that reaches the patient before "
     "an independent safety monitor can intervene."),
    ("hz_network", "un_network",
     "A network fault or EMR data mismatch that blocks a needed injection, "
     "or lets one proceed against unvalidated worklist data."),
]


def user_need_keys():
    return [row[0] for row in domain_data.USER_NEEDS]


def hazard_for_user_need(user_need_key: str):
    for hz_key, un_key, text in HAZARDS:
        if un_key == user_need_key:
            return hz_key, text
    raise KeyError(f"no hazard mapped to user need {user_need_key!r}")


def build_hazard_tree(conn):
    """Return the hazard-anchored tree: a list of
    {hazard_key, hazard_text, l1: [{key, text, l2: [{key, text}]}]}
    dicts, in HAZARDS order. Reads the same `requirements` rows the
    user-need-anchored view reads; only the grouping root differs."""
    tree = []
    for hz in conn.execute(
        "SELECT id, key, text FROM hazards ORDER BY id"
    ).fetchall():
        l1_rows = conn.execute(
            "SELECT id, key, text FROM requirements "
            "WHERE hazard_id = ? AND level = 'L1' ORDER BY id",
            (hz["id"],),
        ).fetchall()
        l1_nodes = []
        for l1 in l1_rows:
            l2_rows = conn.execute(
                "SELECT key, text FROM requirements WHERE parent_id = ? ORDER BY id",
                (l1["id"],),
            ).fetchall()
            l1_nodes.append({
                "key": l1["key"], "text": l1["text"],
                "l2": [{"key": r["key"], "text": r["text"]} for r in l2_rows],
            })
        tree.append({"hazard_key": hz["key"], "hazard_text": hz["text"], "l1": l1_nodes})
    return tree


def render_hazard_tree_text(conn) -> str:
    lines = []
    tree = build_hazard_tree(conn)
    n_req = 0
    for hazard in tree:
        lines.append(f"[{hazard['hazard_key']}] {hazard['hazard_text']}")
        for l1 in hazard["l1"]:
            n_req += 1
            lines.append(f"  - {l1['key']}: {l1['text']}")
            for l2 in l1["l2"]:
                n_req += 1
                lines.append(f"      - {l2['key']}: {l2['text']}")
        lines.append("")
    lines.append(f"hazards: {len(tree)}, requirements reachable from a hazard: {n_req}")
    return "\n".join(lines)


def every_requirement_reaches_a_hazard(conn):
    """Walk parent_id up from every requirement (mirroring
    test_domain_data.test_every_requirement_reachable_to_a_user_need) and
    confirm it terminates at a requirement whose hazard_id is set.
    Returns (True, []) or (False, [unreachable_keys])."""
    rows = conn.execute(
        "SELECT id, key, parent_id, hazard_id FROM requirements"
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    unreachable = []
    for row in rows:
        cur = row
        steps = 0
        while cur["hazard_id"] is None:
            if cur["parent_id"] is None:
                unreachable.append(row["key"])
                break
            cur = by_id[cur["parent_id"]]
            steps += 1
            if steps >= 10:
                unreachable.append(row["key"])
                break
    return (len(unreachable) == 0, unreachable)
