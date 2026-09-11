"""Verification reporting, orphan detection, and non-verifying-test detection.

The verification-refusal rule mirrors the pattern in the sibling repo
projects/design-verification-sample-size-harness/dv_harness/requirements_report.py:
a requirement is reported VERIFIED if and only if it has at least one
piece of attached test evidence and every attached piece of evidence
passed. There is no silent-pass path: zero evidence is never VERIFIED
just because nothing contradicted it. This module is written fresh for
the traceability domain (SQLite-backed, keyword cross-check for
non-verifying tests, suspect-aware) rather than importing the harness
file, because the two domains disagree on what "evidence" is shaped
like (a dataclass list there, joined SQLite rows here) and mechanically
reusing the file would blur which fresh design decisions belong here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class TestEvidence:
    test_id: int
    test_key: str
    result: str  # 'pass' or 'fail'
    exercises_keyword: str
    non_verifying: bool  # True if linked+passing but keyword-mismatched
    suspect: bool


@dataclass(frozen=True)
class RequirementStatus:
    requirement_id: int
    requirement_key: str
    verified: bool
    status_label: str  # "VERIFIED" or "NOT VERIFIED"
    reason: str
    evidence: tuple


def _fetch_evidence(conn, requirement_id: int, requirement_keyword: str):
    rows = conn.execute(
        "SELECT t.id, t.key, t.result, t.exercises_keyword, rt.suspect "
        "FROM requirement_tests rt JOIN tests t ON t.id = rt.test_id "
        "WHERE rt.requirement_id = ?",
        (requirement_id,),
    ).fetchall()
    evidence = []
    for r in rows:
        non_verifying = (r["result"] == "pass" and r["exercises_keyword"] != requirement_keyword)
        evidence.append(
            TestEvidence(
                test_id=r["id"], test_key=r["key"], result=r["result"],
                exercises_keyword=r["exercises_keyword"], non_verifying=non_verifying,
                suspect=bool(r["suspect"]),
            )
        )
    return tuple(evidence)


def evaluate_requirement(requirement_id: int, requirement_key: str, evidence) -> RequirementStatus:
    """Verification-refusal rule: VERIFIED iff evidence is non-empty and every
    attached test passed. This check is deliberately naive about *whether*
    a passing test actually exercises the right behavior; that gap is what
    find_non_verifying_tests() exists to close as a separate cross-check,
    matching the "refuses to mark verified without evidence" pattern
    without silently absorbing a smarter check into the same function."""
    if len(evidence) == 0:
        return RequirementStatus(
            requirement_id=requirement_id, requirement_key=requirement_key, verified=False,
            status_label="NOT VERIFIED", reason="no evidence attached", evidence=evidence,
        )
    failing = [e for e in evidence if e.result != "pass"]
    if failing:
        detail = "; ".join(f"{e.test_key}: result={e.result}" for e in failing)
        return RequirementStatus(
            requirement_id=requirement_id, requirement_key=requirement_key, verified=False,
            status_label="NOT VERIFIED", reason=f"failing evidence present ({detail})",
            evidence=evidence,
        )
    return RequirementStatus(
        requirement_id=requirement_id, requirement_key=requirement_key, verified=True,
        status_label="VERIFIED", reason="all attached evidence passed", evidence=evidence,
    )


def build_verification_report(conn):
    reqs = conn.execute("SELECT id, key, keyword FROM requirements ORDER BY id").fetchall()
    report = []
    for r in reqs:
        evidence = _fetch_evidence(conn, r["id"], r["keyword"])
        report.append(evaluate_requirement(r["id"], r["key"], evidence))
    return report


def render_report_text(report) -> str:
    lines = []
    for status in report:
        lines.append(f"[{status.status_label}] {status.requirement_key}")
        lines.append(f"    reason: {status.reason}")
        if status.evidence:
            for e in status.evidence:
                mark = "PASS" if e.result == "pass" else "FAIL"
                nv = " NON-VERIFYING(keyword mismatch)" if e.non_verifying else ""
                lines.append(f"    evidence [{mark}] {e.test_key} exercises={e.exercises_keyword}{nv}")
        else:
            lines.append("    evidence: (none attached)")
        lines.append("")
    n_verified = sum(1 for s in report if s.verified)
    lines.append(f"summary: {n_verified}/{len(report)} requirements VERIFIED")
    return "\n".join(lines)


# --- orphan detection -----------------------------------------------------

def find_orphans_fast(conn):
    """Indexed approach: LEFT JOIN requirements to requirement_tests and
    select rows with no match. O(n) via the idx_req_tests_requirement
    index built in db.py."""
    rows = conn.execute(
        "SELECT r.id, r.key FROM requirements r "
        "LEFT JOIN requirement_tests rt ON rt.requirement_id = r.id "
        "WHERE rt.id IS NULL ORDER BY r.id"
    ).fetchall()
    return [(r["id"], r["key"]) for r in rows]


def find_orphans_reference(conn):
    """Deliberately slow, obviously-correct reference oracle: pull every
    requirement and every requirement_tests row into Python and do the
    orphan check with a plain set, no SQL join logic to get subtly wrong.
    Used only to cross-check find_orphans_fast in tests, never in the
    reporting path itself."""
    all_reqs = conn.execute("SELECT id, key FROM requirements").fetchall()
    linked_ids = set()
    for row in conn.execute("SELECT requirement_id FROM requirement_tests").fetchall():
        linked_ids.add(row["requirement_id"])
    orphans = [(r["id"], r["key"]) for r in all_reqs if r["id"] not in linked_ids]
    orphans.sort(key=lambda t: t[0])
    return orphans


# --- non-verifying test detection -----------------------------------------

def find_non_verifying_tests(conn):
    """A requirement_tests link is non-verifying if the linked test's
    recorded result is 'pass' but the test's exercises_keyword does not
    match the requirement's keyword: it looks like good evidence (linked,
    green) but does not actually check the requirement's stated
    behavior. Returns (requirement_id, requirement_key, test_id,
    test_key) tuples."""
    rows = conn.execute(
        "SELECT r.id AS req_id, r.key AS req_key, r.keyword AS req_kw, "
        "t.id AS test_id, t.key AS test_key, t.exercises_keyword AS test_kw, t.result "
        "FROM requirement_tests rt "
        "JOIN requirements r ON r.id = rt.requirement_id "
        "JOIN tests t ON t.id = rt.test_id"
    ).fetchall()
    flagged = []
    for r in rows:
        if r["result"] == "pass" and r["test_kw"] != r["req_kw"]:
            flagged.append((r["req_id"], r["req_key"], r["test_id"], r["test_key"]))
    flagged.sort(key=lambda t: t[0])
    return flagged
