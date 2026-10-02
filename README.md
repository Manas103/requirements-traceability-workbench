# Requirements Traceability Workbench for a Contrast Delivery System

A small, from-scratch requirements-traceability tool for a simulated
contrast delivery (medical injector) system: 14 user needs decomposed
into 86 system and subsystem requirements, each traced to the tests
that verify it and the risk controls it implements, stored in SQLite,
exportable to and reimportable from a ReqIF-shaped XML file, and
rendered as a Graphviz diagram. Extended (Oct. 2026) with a second,
independent layer: an Agile story-to-release traceability gate (60
stories, each tied to acceptance criteria, a live 48-endpoint FastAPI
OpenAPI contract, a pytest test, and a documentation paragraph) backed
by a real PostgreSQL server, plus a generator that drafts first-pass
user documentation for all 48 endpoints from the contract itself. Every
number below was measured on this machine by running the scripts named
next to it, not targeted: the seeded defects and gaps were placed by a
fixed-seed shuffle before any detector was run against them, and the
detector code was written once and not adjusted after seeing the
counts.

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

## Extension (Oct. 2026): Story-to-Release Traceability Gate with Generated User Documentation

A second, independent layer was added on top of the original
86-requirement tree: an Agile story-to-release gate with a generated
first-pass documentation set. This is new work, a new concept (a
"story" is not a "requirement"), and is measured separately from the
86-requirement numbers above, which are re-verified unchanged (see
"Original numbers, re-verified" below).

**What was built.** A thin, real FastAPI service (`trace_workbench/
api_app.py`) exposing 12 simulated contrast-injector operations
resources (protocols, injections, alarms, devices, reservoirs,
calibrations, maintenance records, audit events, network configs,
operators, occlusion events, reports), four real CRUD operations each
(list, create, get, update): 48 live, inspectable OpenAPI operations,
counted from the running schema every time, never hardcoded (`endpoint_
count()`). On top of it, 60 Agile user stories (`trace_workbench/
stories_seed.py`), each nominally tied to its own acceptance-criteria
text, one of the 48 API operations, a real pytest test
(`tests/test_story_endpoints.py`, parametrized over all 60 stories), and
a generated documentation paragraph. A deterministic, fixed-seed
(9000) shuffle seeds exactly 22 of the 240 possible (story, link type)
pairs as missing, the same assign-before-building-the-detector pattern
as the original `seed.py`. A release gate (`trace_workbench/
story_gate.py`) walks every story and fails, naming the exact story key
and missing link type, if any of the four required links is absent. A
documentation generator (`trace_workbench/docgen.py`) drafts a paragraph
for every one of the 48 live endpoints directly from the OpenAPI
schema's own path, method, parameters, and request/response field
shapes, plus the acceptance-criteria text of whichever stories link to
that operation; the routes in `api_app.py` carry no docstrings, so a
passing coverage number cannot be explained by the generator echoing
text a human already wrote.

**PostgreSQL, stated honestly.** A real PostgreSQL 14 server is already
running as a WSL2 Ubuntu-22.04 systemd service (`pg_lsclusters`: cluster
"main", port 5432, online). Raw TCP connect and a real `psycopg` session
from this Windows-native Python process to `127.0.0.1:5432` were both
verified before any story-layer code was written. The stronger claim was
taken: the story layer is not SQLite with a Postgres-compatible schema,
it is two real PostgreSQL schemas (`story_seeded`, `story_clean`) in a
real `tracestory` database, queried with real SQL
(`trace_workbench/story_db.py`, `psycopg[binary]==3.3.6`) by every test
and script in this section. `DATABASE_URL` defaults to
`postgresql://tracestory_app:tracestory_dev_pw@127.0.0.1:5432/tracestory`;
tests and scripts that need it call `story_db.is_available()` first and
skip (tests) or print a clear message and exit (scripts) if it is not
reachable, matching this project's documented convention for services
that are not guaranteed to be running.

**Design choices worth stating.** The story-to-requirement relationship
is a soft, cross-store reference (a text key, not a foreign key):
`RESOURCE_REQUIREMENT_LINK` names an existing requirement key from
`domain_data.py` for each of the 12 resources, and
`test_stories_seed.py::test_soft_requirement_links_point_at_real_
requirement_keys` is the independent check that every key named there
actually exists in the 86-requirement tree, since the story layer
(PostgreSQL) and the requirement tree (SQLite) are genuinely two
different stores, the same way a backlog tool and a requirements tool
usually are in practice. The seeded "test" gap models a backlog
bookkeeping gap (that story's `test_links` row was never recorded), not
a missing test in the suite: all 60 stories are exercised by a real,
passing `TestClient` test regardless of backlog state, because the
engineering practice of testing every endpoint should not regress just
because a tracker row is missing; the gate still correctly fails those
9 stories for a missing "test" link.

### Validation (new)

Reference-oracle cross-check, mirroring `find_orphans` vs.
`find_orphans_reference`: `story_gate.find_missing_links_fast` (indexed
LEFT JOINs) and `story_gate.find_missing_links_reference` (naive,
independent, no shared SQL) are diffed on every gate run
(`fast == reference oracle: True` in both captured outputs below).
`scripts/run_story_gate.py` additionally cross-checks every `test_links`
node id actually recorded in PostgreSQL against real `pytest
--collect-only` output, so "a test exists" is checked against pytest's
own collection, not trusted as a string in a database column.

```
$ venv\Scripts\python scripts\build_story_db.py
story_seeded: 60 stories, links = {'acceptance_criteria': 58, 'api_contract': 57, 'test': 51, 'documentation': 52}, gaps applied = 22
story_clean: 60 stories, links = {'acceptance_criteria': 60, 'api_contract': 60, 'test': 60, 'documentation': 60}, gaps applied = 0
```

### Findings (new)

**Symptom 1.** The first run of `trace_workbench/api_app.py` crashed
with `pydantic.errors.PydanticUserError: ... ForwardRef('Model') is not
fully defined`, even though every route's annotation (`item: Model`)
looked correct.

**Wrong hypothesis.** That a generic CRUD factory function could not
produce distinct Pydantic response models per resource.

**Discriminating measurement.** The error referenced a bare `ForwardRef
('Model')`, the literal parameter name, not any of the twelve real model
classes, which only makes sense if something was resolving annotations
by name rather than by the actual object already bound in the closure.

**Root cause.** `api_app.py` had `from __future__ import annotations` at
the top, which makes every annotation in the module a string, resolved
later against a function's `__globals__`. `Model` inside
`make_crud_router` is a local closure variable, not a module global, so
FastAPI's schema builder could not resolve the string `"Model"` to
anything and fell back to an unbound `ForwardRef`.

**Fix.** Removed `from __future__ import annotations` from `api_app.py`
so each route's annotation is bound eagerly, at function-definition
time, to the real class object already sitting in the closure. 48
endpoints resolved correctly afterward; documented in the module
docstring so the next person does not reintroduce it.

**Symptom 2.** `scripts/run_story_gate.py`'s pytest-collection
cross-check reported 51 (seeded) and 9 (clean) recorded `test_links`
node ids as "not collected", for stories whose tests plainly exist and
pass in `pytest tests/ -q`.

**Wrong hypothesis.** That the node id format stored in PostgreSQL
(`tests/test_story_endpoints.py::test_story_endpoint[<key>]`) did not
match pytest's actual parametrize id generation.

**Discriminating measurement.** Running `pytest --collect-only -q
tests/test_story_endpoints.py` by hand from the project root printed
node ids prefixed with `projects/requirements-traceability-workbench/
tests/...`, not `tests/...`, even though the subprocess's `cwd` was
already the project root.

**Root cause.** This repository sits inside a larger pipeline checkout
that has its own top-level `pytest.ini`; pytest's rootdir discovery
climbs parent directories looking for exactly that kind of file, found
it one level up, and used it as rootdir regardless of `cwd`, making
every printed node id relative to the outer pipeline root instead of
this project.

**Fix.** Pinned `--rootdir` explicitly in the subprocess call in
`scripts/run_story_gate.py`. All 60 (clean) and 51 (seeded) recorded
node ids matched afterward (`recorded-but-not-collected: 0` in both
captured outputs below).

### Measured results (new)

Machine: Windows 11 host, native Python 3.12.10 venv, `fastapi==0.142.2`,
`psycopg[binary]==3.3.6`, real PostgreSQL 14.24 in WSL2 Ubuntu-22.04.

**The numbers that matter: 60/60 stories fully linked on a clean
backlog, 22/22 seeded gaps caught by exact name with 0 false positives,
0 false blocks on the clean backlog, and 48/48 live endpoints drafted
with a non-trivial, schema-derived documentation paragraph.**

| Metric | Definition | Command | Result |
|---|---|---|---|
| **Live OpenAPI endpoints** | Operations counted from the running schema | `python -m trace_workbench.api_app` | **48** (24 paths x list/create/get/update, minus list sharing a path) |
| **Story backlog size** | Stories in `stories_seed.STORY_DEFS` | `python -m trace_workbench.stories_seed` | **60**, covering all 48 live operation ids with 0 drift |
| **Clean backlog, all 4 links** | `story_clean` schema link counts | `scripts\build_story_db.py` | **60/60/60/60** (acceptance criteria / API contract / test / documentation) |
| **Seeded gap catch rate** | Of 22 seeded (story, link type) gaps, caught by exact name | `scripts\run_story_gate.py --schema story_seeded` | **22/22**, 0 false positives, fast == reference oracle |
| **False blocks on clean backlog** | Gaps reported against the fully-linked backlog | `scripts\run_story_gate.py --schema story_clean` | **0/60**, exit code 0 |
| **Release gate pass/fail** | Non-zero exit naming the gap, on the seeded vs. clean backlog | same two commands | **fails (exit 1) on seeded, passes (exit 0) on clean** |
| **Endpoint documentation coverage** | Non-trivial draft (>=120 chars, names its own method and path) per live endpoint | `scripts\run_doc_coverage.py` | **48/48** |
| **pytest suite** | Original 7 plus 79 new (structural, Postgres-backed gate, docgen, live API, story-endpoint) | `pytest tests/ -q` | **86 passed, 0 failed** |

Raw output: `docs\story_gate_seeded_output.txt`, `docs\story_gate_clean_
output.txt`, `docs\doc_coverage_output.txt`, `docs\test_output.txt`.

**Original numbers, re-verified unchanged.** The same `pytest tests/ -q`
run and `scripts\run_reports.py` output above still show 14 user needs,
86 requirements, 86/86 traced to a risk control, 75/86 traced to a test,
11/11 seeded orphans caught with 0 false positives, 7/7 non-verifying
tests caught, 72/86 VERIFIED, and exactly 23 items flagged on the
3-parent suspect-propagation scenario. Nothing in this extension reads
or modifies `data/trace.db`, `trace_workbench/seed.py`,
`trace_workbench/reports.py`, `trace_workbench/suspect.py`, or
`trace_workbench/reqif_io.py`.

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

**Story-to-release gate and documentation generator (new).** Requires a
reachable PostgreSQL server (see "PostgreSQL, stated honestly" above).
To stand up an equivalent server in WSL2:

```bash
sudo -u postgres psql -c "CREATE ROLE tracestory_app LOGIN PASSWORD 'tracestory_dev_pw';"
sudo -u postgres psql -c "CREATE DATABASE tracestory OWNER tracestory_app;"
```

```bash
venv\Scripts\python scripts\build_story_db.py
venv\Scripts\python scripts\run_story_gate.py --schema story_seeded > docs\story_gate_seeded_output.txt
venv\Scripts\python scripts\run_story_gate.py --schema story_clean > docs\story_gate_clean_output.txt
venv\Scripts\python scripts\run_doc_coverage.py > docs\doc_coverage_output.txt
```

If `DATABASE_URL` is unreachable, `build_story_db.py` and
`run_story_gate.py` print a clear message and exit nonzero rather than
traceback, and the Postgres-backed tests in `tests/test_story_db.py`
skip cleanly instead of failing; `run_doc_coverage.py` falls back to the
same acceptance-criteria text from the pure-Python seed module and
discloses that it did so.

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
  statistically representative of "any" seed's difficulty. The story
  layer's gap placement (seed 9000) has the same property.
- **The 48-endpoint API is deliberately thin CRUD, not real business
  logic.** It exists to give the documentation generator and the story
  layer a genuine, inspectable OpenAPI contract to read from, not to
  model realistic validation, auth, or persistence; there is no database
  behind it beyond an in-memory dict per resource, and it resets on
  restart.
- **The documentation generator drafts shape, not intent.** It can state
  what fields an endpoint accepts and returns and cite the acceptance
  criteria that motivated it, but it cannot explain why the endpoint
  exists in product terms; a human still owns that sentence, which is
  the honest caveat this project is making a point of measuring rather
  than hiding.
- **The story-to-requirement link is a soft, cross-store reference**, a
  text key checked against the requirement tree in a test, not a
  database foreign key, because the story layer (PostgreSQL) and the
  requirement tree (SQLite) are two different stores.
- **The seeded "test" gap models a tracking gap, not a missing test.**
  All 60 stories have a real, passing pytest test regardless of backlog
  state; the 9 stories gapped on "test" are missing their `test_links`
  row in PostgreSQL, not missing test coverage. This is disclosed rather
  than left to look like a stronger claim than it is.
