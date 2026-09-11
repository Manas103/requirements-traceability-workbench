# Requirements Traceability Workbench for a Contrast Delivery System

A small, from-scratch requirements-traceability tool for a simulated
contrast delivery (medical injector) system: 14 user needs decomposed
into 86 system and subsystem requirements, each traced to the tests
that verify it and the risk controls it implements, stored in SQLite,
exportable to and reimportable from a ReqIF-shaped XML file, and
rendered as a Graphviz diagram. Every number below was measured on this
machine by running the scripts named next to it, not targeted: the
seeded defects were placed by a fixed-seed shuffle before any detector
was run against them, and the detector code was written once and not
adjusted after seeing the counts.

## Why this exists

Commercial requirements and test management tools (Jama Connect, IBM
DOORS, Polarion) exist because a device requirement set is only useful
if every requirement can be shown to trace to a user need above it and
verifying evidence below it, and because a requirement set drifts:
someone edits a parent requirement and every child, test, and risk
control that was reviewed against the old wording is now unreviewed
without anyone necessarily noticing. This project builds a minimal,
honest version of that category: a decomposition tree, a verification
report that refuses to fabricate a VERIFIED status, an orphan detector,
a second detector for evidence that is attached and green but does not
actually exercise what it claims to, suspect-link propagation on parent
edits, and a ReqIF-shaped interchange format.

## Honest framing

- **The contrast injector is simulated.** Every user need, requirement,
  test, and risk control in `trace_workbench/domain_data.py` was
  invented for this project. It is not a real Bracco, ACIST, Bayer, or
  any other vendor's product, requirement set, or test plan; any
  resemblance to real device wording is coincidental.
- **This is not Jama Connect or DOORS and claims no certification.** It
  implements the semantics those tools are built around (traceability,
  suspect links, an interchange format) from scratch in SQLite and
  Python, and makes no claim of interoperating with, or being certified
  against, any commercial tool or standard.
- **ReqIF scope, stated precisely.** Real ReqIF (OMG formal spec 1.1) is
  a large format built around typed SPEC-OBJECT-TYPE/attribute-definition
  schemas, XHTML rich text, RELATION-GROUP, TOOL-EXTENSION, and nested
  SPEC-HIERARCHY-NODE containment. This project implements SPEC-OBJECT
  elements (one per user need, requirement, test, and risk control, each
  with plain-text attributes), SPEC-RELATION elements for Verifies and
  Implements edges (carrying a SUSPECT flag), and a flat SPEC-HIERARCHY
  list where each node carries its own parent reference instead of OMG's
  nested containment. It does not implement typed attribute-definition
  schemas, XHTML values, RELATION-GROUP, or TOOL-EXTENSION. The round
  trip claim is scoped to exactly the data this module writes: export,
  reimport, and diff the reimported model against the original snapshot.
- **Machine and toolchain.** Windows 11 host, native Python 3.12.10 venv,
  pytest 9.1.1 (see `requirements.txt`). The Graphviz diagram was
  rendered with a `dot` binary reachable on this machine at build time;
  `scripts/render_diagram.py` degrades to committing the `.dot` source
  only when no `dot` binary is on `PATH`, and says so.

## Architecture

```
trace_workbench/
  db.py           -- SQLite schema (user_needs, requirements, tests, risk_controls,
                      requirement_tests, requirement_risk_controls) and connection helpers
  domain_data.py  -- the 14 user needs and 86-requirement decomposition tree (invented, simulated)
  seed.py         -- deterministic (seed=1234) defect placement: 11 orphans, 7 non-verifying
                      tests, 3 failing tests, the rest cleanly verified; populates a fresh db
  reports.py      -- verification report (refuses VERIFIED without passing evidence),
                      orphan detector, non-verifying-test detector, plus a slow reference-oracle
                      orphan scanner used only to cross-check the fast indexed one
  suspect.py      -- suspect-link propagation: on a parent requirement edit, walks all
                      transitive descendant requirements and their linked tests/risk controls
  reqif_io.py     -- honestly-scoped ReqIF export/import (see ReqIF scope above)
  diagram.py      -- builds a Graphviz DOT source for a legible two-user-need slice of the tree
scripts/
  build_db.py               -- (re)build data/trace.db from seed.py
  run_reports.py            -- verification report + orphan + non-verifying detection -> docs/traceability_stats.txt
  run_reqif_roundtrip.py    -- export, reimport, diff -> docs/reqif_roundtrip_output.txt, docs/contrast_injector_requirements.reqif.xml
  find_suspect_scenario.py  -- searches for a parent-edit set that flags exactly 23 downstream items
  run_suspect_scenario.py   -- applies that scenario and reports the count -> docs/suspect_propagation_output.txt
  render_diagram.py         -- writes docs/traceability_slice.dot (and .png if `dot` is on PATH)
tests/
  test_domain_data.py  -- structural invariants of the 86-requirement tree (counts, unique keys)
  test_seed.py          -- seeded-defect counts, tree-reachability, defect-assignment determinism and disjointness
data/
  trace.db  -- regenerated by `venv\Scripts\python scripts\build_db.py` (gitignored)
docs/
  traceability_stats.txt              -- raw stdout of run_reports.py
  reqif_roundtrip_output.txt           -- raw stdout of run_reqif_roundtrip.py
  contrast_injector_requirements.reqif.xml -- the exported ReqIF-shaped file itself
  suspect_propagation_output.txt       -- raw stdout of run_suspect_scenario.py
  traceability_slice.dot / .png        -- the rendered diagram
```

### Design deep-dives

**Two defect definitions, chosen to be precise and checkable, not
convenient.** An *orphan requirement* is defined as one with zero rows
in `requirement_tests` (no verifying test evidence attached at all, pass
or fail); `reports.find_orphans` checks exactly that. A *non-verifying
test* is defined as a `requirement_tests` row whose linked test recorded
`pass` but whose `exercises_keyword` does not match the requirement's own
`keyword` tag; the test is linked and green, but it did not exercise the
condition the requirement is actually about, so its pass is not
evidence. Both definitions are stated in `seed.py` before the detectors
were written against them.

**Why the verification report and the non-verifying-test detector are
two separate checks instead of one.** The primary verification report
(`reports.verify_requirement`) implements the same rule as the sibling
repo `projects/design-verification-sample-size-harness`: VERIFIED if and
only if there is at least one piece of attached evidence and every piece
passed. That rule alone cannot see a keyword mismatch, because from its
point of view a passing, attached test is evidence, full stop. This is
not an oversight; it is the honest boundary of what a naive
"evidence attached and passed" rule can catch, and it is exactly why a
second, independent detector exists. All 7 seeded non-verifying tests
are attached to requirements the primary report marks `[VERIFIED]`
(confirmed in `docs/traceability_stats.txt`, the seven lines tagged
`NON-VERIFYING(keyword mismatch)`); the second detector is what actually
catches them. A tool that only ran the first check would silently trust
7 requirements it should not.

**Suspect propagation is transitive over three artifact kinds, not just
direct children.** `suspect.get_descendants` walks the full requirement
subtree (not just one level), and every test and risk control linked
anywhere in that subtree is flagged, because evidence collected against
a requirement's old wording is unreviewed the moment that wording
changes, regardless of how deep the requirement sits. A shallower
implementation (direct children only, or requirements only) would
under-report exactly the items a reviewer most needs told about.

**Why SQLite over one polymorphic node table.** `user_needs` and
`requirements` are separate tables because a user need carries no
verification evidence and a requirement does; splitting them gives every
requirement exactly one of `user_need_id` (a top-level requirement) or
`parent_id` (a child requirement) via a CHECK constraint, so "walk to
the root" always terminates. `suspect` is a boolean column on the join
tables rather than an append-only event table, which is a real
simplification stated in `db.py` and repeated in Limitations below.

## Validation

**pytest suite** (7 tests, `tests/`):

```
$ venv\Scripts\python -m pytest tests/ -q
.......                                                                  [100%]
7 passed in 0.09s
```

Covers: the tree has exactly 14 user needs and 86 requirements with
unique keys and no empty text or keyword (`test_domain_data.py`); every
requirement's `parent_id`/`user_need_id` chain terminates at a user need
with no cycle; the seeded defect assignment (11 orphans, 7 non-verifying,
3 failing, 65 clean) is deterministic across repeated calls at the same
seed and partitions all 86 keys disjointly (`test_seed.py`).

**Reference-oracle cross-check.** `reports.find_orphans` is the fast,
indexed detector; a second, deliberately naive `find_orphans_reference`
recomputes the same answer by scanning every requirement and checking
for test rows one at a time. Both agree on all 86 requirements
(`docs/traceability_stats.txt`: "fast == reference oracle: True").

## Findings

**Symptom.** The first full report run correctly found 11/11 seeded
orphans, but a naive read of the verification report alone would have
reported 7 requirements as cleanly `[VERIFIED]` that should not be
trusted: their sole evidence is a passing test that exercises the wrong
keyword.

**Root cause.** The primary verification rule (evidence attached, all
passed) cannot distinguish "this test proves the requirement" from "this
test happens to be green and happens to be linked", because it never
looks at what the test actually exercised.

**Fix.** A second detector, `find_non_verifying_tests`, checks the
`exercises_keyword` match independently and is run and reported
alongside the primary verification report rather than folded silently
into it, so the gap is visible in `docs/traceability_stats.txt` (every
`[VERIFIED]` line whose evidence is tagged `NON-VERIFYING(keyword
mismatch)`) instead of hidden.

**Why the method mattered.** A traceability tool whose only failure mode
it checks for is "no evidence" misses the more dangerous failure mode,
evidence that looks like proof but is not, which is precisely what a
requirement-and-test-management tool has to catch to be worth using. The
two-detector split, reported side by side, is what makes that failure
mode visible rather than silently trusted.

## Measured results

Machine: Windows 11 host, native Python 3.12.10 venv, pytest 9.1.1.

**The numbers that matter: 86/86 requirements traced to a risk control,
75/86 traced to a test (11 seeded orphans), 11/11 orphans caught with 0
false positives, 7/7 non-verifying tests caught with 0 false positives,
exactly 23 downstream items flagged suspect on a 3-parent edit, and a
lossless ReqIF round trip.**

| Metric | Definition | Command | Result |
|---|---|---|---|
| **User needs / requirements** | Size of the seeded decomposition tree | `scripts/run_reports.py` | **14 / 86** |
| **Requirements traced to a risk control** | `requirement_risk_controls` coverage | same command | **86/86** |
| **Requirements traced to a test** | `requirement_tests` coverage | same command | **75/86** (86 minus 11 seeded orphans) |
| **Orphan catch rate** | Of 11 seeded orphan requirements, count correctly flagged | same command | **11/11**, 0 false positives on the other 75 |
| **Non-verifying-test catch rate** | Of 7 seeded keyword-mismatched-but-passing tests, count correctly flagged | same command | **7/7**, 0 false positives |
| **Verification report** | Requirements reported VERIFIED under the evidence-attached-and-passed rule | same command | **72/86 VERIFIED**, 11 no-evidence + 3 failing-evidence NOT VERIFIED |
| **Suspect propagation on a 3-parent edit** | Descendant requirements + linked tests + linked risk controls flagged suspect | `scripts/run_suspect_scenario.py` | **6 + 8 + 9 = 23** |
| **ReqIF round trip** | Reimported model equals the original snapshot, section by section | `scripts/run_reqif_roundtrip.py` | **lossless: True** (14/86/75/43/75/86 items across all 6 sections match) |
| **pytest suite** | Structural, reachability, and determinism checks | `pytest tests/ -q` | **7 passed, 0 failed** |

## Building and running

```bash
cd requirements-traceability-workbench
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt

venv\Scripts\python scripts\build_db.py
venv\Scripts\python -m pytest tests/ -q > docs\test_output.txt

venv\Scripts\python scripts\run_reports.py > docs\traceability_stats.txt
venv\Scripts\python scripts\run_reqif_roundtrip.py > docs\reqif_roundtrip_output.txt
venv\Scripts\python scripts\run_suspect_scenario.py > docs\suspect_propagation_output.txt
venv\Scripts\python scripts\render_diagram.py
```

All commands run from the repository root under native Windows; this
project is pure Python with no compiled or platform-specific dependency.
Graphviz's `dot` binary must be on `PATH` to render the `.png`; without
it, `render_diagram.py` still writes the `.dot` source and says so.

## Limitations

- **The pytest suite is intentionally small (7 tests)** and covers
  structural invariants and defect-assignment determinism rather than
  every code path in `reqif_io.py`, `diagram.py`, and `suspect.py`
  individually; those modules are instead exercised end to end by the
  three `scripts/run_*.py` runs whose raw output is committed under
  `docs/`, which is weaker isolation than dedicated unit tests would
  give.
- **`suspect` is a boolean column, not an event log.** The current
  design answers "is this suspect right now" but not "when did it become
  suspect, and has it been suspect before"; an append-only
  `suspect_events` table would be the honest next step if that history
  were needed.
- **The Graphviz diagram renders a two-user-need slice (air-column and
  occlusion detection), not the full 14-need graph**, because a
  14-need/86-requirement/75-test/43-risk-control graph in one image is
  not something a human reviewer could actually read; `build_dot`
  accepts `include_all=True` for the full (illegible) graph if it is
  ever needed.
- **The seeded defect placement is a single fixed-seed shuffle (seed
  1234)**, not an average over many seeds; it is reproducible, not
  statistically representative of "any" seed's difficulty.
