"""Populate a fresh SQLite database with the simulated contrast-injector
requirement set and its deliberately seeded defects.

All of the "which requirement is an orphan / has a non-verifying test /
has a failing test" decisions below are made by a single seeded
`random.Random(SEED)` shuffle of the 86 requirement keys in tree order,
not by hand-picking convenient IDs. The seed is fixed (1234) so a re-run
of `python -m trace_workbench.seed` always reproduces byte-identical
defect placement; that determinism is what lets the pytest suite assert
exact counts (11 orphans, 7 non-verifying tests, 3 failing tests) instead
of re-deriving them.

Two precise, checkable defect definitions used throughout this project:

- Orphan requirement: a requirement with zero rows in requirement_tests
  (no verifying test evidence attached at all, pass or fail). This is the
  definition `reports.find_orphans` checks against.
- Non-verifying test: a requirement_tests row where the linked test's
  result is 'pass' but the test's `exercises_keyword` does not match the
  requirement's `keyword`. In this simulated domain, `keyword` is the
  short tag for the physical behavior a requirement is about (for
  example `occlusion_pressure` or `air_bubble`); a test that recorded a
  pass but exercised a different keyword did not actually exercise the
  requirement's stated condition, so its "pass" is not evidence for that
  requirement, even though it is linked and green. This is exactly the
  gap the naive verification-refusal check (evidence attached + all
  passed) cannot see on its own; `reports.find_non_verifying_tests` is
  the additional oracle for it.
"""
from __future__ import annotations

import random

from . import domain_data
from .db import fresh_db

SEED = 1234
N_ORPHAN = 11
N_NON_VERIFYING = 7
N_FAILING = 3


def assign_defects(keys_in_order, seed: int = SEED):
    """Pure function (no db, no side effects): given the 86 requirement
    keys in tree-walk order, return (orphan_keys, non_verifying_keys,
    failing_keys, verified_keys) exactly as build() will apply them.
    Exposed so reports/tests can compute ground truth independently of
    whatever is currently sitting in data/trace.db, and cross-check the
    detectors against it."""
    rng = random.Random(seed)
    shuffled = list(keys_in_order)
    rng.shuffle(shuffled)
    orphan_keys = set(shuffled[:N_ORPHAN])
    non_verifying_keys = set(shuffled[N_ORPHAN:N_ORPHAN + N_NON_VERIFYING])
    failing_keys = set(
        shuffled[N_ORPHAN + N_NON_VERIFYING:N_ORPHAN + N_NON_VERIFYING + N_FAILING]
    )
    verified_keys = set(shuffled[N_ORPHAN + N_NON_VERIFYING + N_FAILING:])
    return orphan_keys, non_verifying_keys, failing_keys, verified_keys


def flatten_tree():
    """Return a flat list of (key, text, keyword, level, parent_key,
    user_need_key) in a stable, deterministic tree-walk order."""
    flat = []

    def walk(nodes, parent_key, user_need_key, level):
        for key, text, keyword, children in nodes:
            flat.append((key, text, keyword, level, parent_key, user_need_key))
            walk(children, key, None, "L2")

    for un_key, top_nodes in domain_data.REQ_TREE.items():
        walk(top_nodes, None, un_key, "L1")
    return flat


def build(conn, seed: int = SEED):
    flat = flatten_tree()
    assert len(flat) == 86, f"expected 86 requirements, got {len(flat)}"

    # --- user needs -----------------------------------------------------
    un_id = {}
    for key, text in domain_data.USER_NEEDS:
        cur = conn.execute(
            "INSERT INTO user_needs (key, text) VALUES (?, ?)", (key, text)
        )
        un_id[key] = cur.lastrowid

    # --- requirements: single insert pass. `flatten_tree` walks parent
    # before children, so a child's parent_id is always already known. ---
    req_id = {}
    req_row = {}
    for key, text, keyword, level, parent_key, user_need_key in flat:
        cur = conn.execute(
            "INSERT INTO requirements "
            "(key, text, keyword, level, user_need_id, parent_id) VALUES (?, ?, ?, ?, ?, ?)",
            (
                key, text, keyword, level,
                un_id[user_need_key] if parent_key is None else None,
                req_id[parent_key] if parent_key is not None else None,
            ),
        )
        req_id[key] = cur.lastrowid
        req_row[key] = (key, text, keyword, level, parent_key, user_need_key)

    # --- risk controls: one per unique keyword, linked to every
    # requirement that carries that keyword. Every requirement gets
    # exactly one risk control; this is not a seeded-defect axis. -------
    keywords = sorted({row[2] for row in flat})
    rc_id = {}
    for kw in keywords:
        cur = conn.execute(
            "INSERT INTO risk_controls (key, text) VALUES (?, ?)",
            (f"rc_{kw}", f"Risk control mitigating the hazard associated with '{kw}'."),
        )
        rc_id[kw] = cur.lastrowid
    for key, text, keyword, level, parent_key, user_need_key in flat:
        conn.execute(
            "INSERT INTO requirement_risk_controls (requirement_id, risk_control_id) "
            "VALUES (?, ?)",
            (req_id[key], rc_id[keyword]),
        )

    # --- deterministic defect assignment ---------------------------------
    keys_in_order = [row[0] for row in flat]
    orphan_keys, non_verifying_keys, failing_keys, verified_keys = assign_defects(
        keys_in_order, seed
    )

    other_keywords = keywords  # reuse the same pool; mismatch is picked below
    tests_created = 0
    for key in keys_in_order:
        _text, _txt2, keyword, _level, _pk, _unk = req_row[key]
        if key in orphan_keys:
            continue  # no test at all: this IS the orphan defect
        elif key in non_verifying_keys:
            # pick a keyword that is NOT this requirement's own keyword,
            # deterministically (first candidate after keyword in the
            # sorted, wrapped-around keyword list), so the mismatch is
            # guaranteed and reproducible.
            idx = other_keywords.index(keyword)
            mismatch_kw = other_keywords[(idx + 1) % len(other_keywords)]
            tests_created += 1
            tcur = conn.execute(
                "INSERT INTO tests (key, name, exercises_keyword, procedure_text, result) "
                "VALUES (?, ?, ?, ?, 'pass')",
                (
                    f"test_{key}",
                    f"Verification test for {key}",
                    mismatch_kw,
                    f"Procedure records a passing result, but the procedure text and "
                    f"acceptance check actually exercise '{mismatch_kw}' behavior, not "
                    f"'{keyword}'.",
                ),
            )
            conn.execute(
                "INSERT INTO requirement_tests (requirement_id, test_id) VALUES (?, ?)",
                (req_id[key], tcur.lastrowid),
            )
        elif key in failing_keys:
            tests_created += 1
            tcur = conn.execute(
                "INSERT INTO tests (key, name, exercises_keyword, procedure_text, result) "
                "VALUES (?, ?, ?, ?, 'fail')",
                (
                    f"test_{key}",
                    f"Verification test for {key}",
                    keyword,
                    f"Procedure correctly exercises '{keyword}' behavior; recorded result "
                    f"is a failure (acceptance criterion not met on this run).",
                ),
            )
            conn.execute(
                "INSERT INTO requirement_tests (requirement_id, test_id) VALUES (?, ?)",
                (req_id[key], tcur.lastrowid),
            )
        else:
            tests_created += 1
            tcur = conn.execute(
                "INSERT INTO tests (key, name, exercises_keyword, procedure_text, result) "
                "VALUES (?, ?, ?, ?, 'pass')",
                (
                    f"test_{key}",
                    f"Verification test for {key}",
                    keyword,
                    f"Procedure correctly exercises '{keyword}' behavior and passes.",
                ),
            )
            conn.execute(
                "INSERT INTO requirement_tests (requirement_id, test_id) VALUES (?, ?)",
                (req_id[key], tcur.lastrowid),
            )

    conn.commit()
    return {
        "req_id": req_id,
        "un_id": un_id,
        "rc_id": rc_id,
        "orphan_keys": orphan_keys,
        "non_verifying_keys": non_verifying_keys,
        "failing_keys": failing_keys,
        "verified_keys": verified_keys,
        "tests_created": tests_created,
    }


def main(db_path="data/trace.db"):
    conn = fresh_db(db_path)
    info = build(conn)
    print(f"seeded {len(info['req_id'])} requirements, {len(info['un_id'])} user needs, "
          f"{info['tests_created']} tests, {len(info['rc_id'])} risk controls")
    print(f"orphans: {len(info['orphan_keys'])}, non-verifying: "
          f"{len(info['non_verifying_keys'])}, failing: {len(info['failing_keys'])}")
    conn.close()


if __name__ == "__main__":
    main()
