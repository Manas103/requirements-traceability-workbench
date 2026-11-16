"""Untestable-phrasing detector (Nov. 2026 extension).

A requirement can have full traceability (a verifying test, an
implemented control, no orphan, no keyword mismatch) and still be
unverifiable in practice, because its acceptance criterion is written
in language with no measurable threshold: "the system shall be
user-friendly" cannot be shown false by any test. This module is a
from-scratch lexical linter: UNTESTABLE_PHRASES is a fixed list of
vague qualifiers with no attached number or enumerable condition,
checked against requirement text as a case-insensitive substring scan.

The 86 real requirement texts in domain_data.py were written before
this list and contain zero matches (confirmed by
test_no_false_positives_on_the_real_tree), which is the honest
zero-false-positive baseline, not an assumption. To measure a catch
rate, SEEDED_UNTESTABLE_VARIANTS replaces 10 of those 86 texts with a
hand-authored vague rewrite of that same requirement's own criterion
(its measurable clause removed, a phrase from UNTESTABLE_PHRASES put in
its place). Which 10 of the 86 keys receive a variant was chosen by a
fixed seed (2468) shuffling the same 86 keys seed.py uses, before the
variant text or the phrase list were finalized; the seed decides WHICH
keys are vague, a human decided WHAT the vague rewrite says, the same
split `seed.py` uses for its own non-verifying-test defect (seed picks
the key, a formula picks the mismatched keyword).

This corpus is a derived test fixture, kept in this module. It never
writes to data/trace.db and never edits domain_data.REQ_TREE, so the
original 86-requirement tree, its orphan/non-verifying counts, and the
ReqIF round trip are untouched by this extension, the same scoping
discipline the Oct. 2026 story-layer extension used.
"""
from __future__ import annotations

import random

from . import domain_data
from .seed import flatten_tree

UNTESTABLE_PHRASES = [
    "appropriate", "adequate", "sufficient", "robust", "reasonable",
    "user-friendly", "intuitive", "efficient", "promptly", "quickly",
    "where possible", "etc.", "and so on", "state of the art",
    "best effort", "as needed", "timely",
]

SEED = 2468
N_UNTESTABLE = 10

SEEDED_UNTESTABLE_VARIANTS = {
    "alarm_log_export": (
        "The system shall support exporting the alarm log in a "
        "user-friendly format for service review."
    ),
    "dual_syringe_sync": (
        "For dual-syringe (contrast/saline) configurations, the system "
        "shall synchronize switchover promptly after the programmed "
        "transition point."
    ),
    "emc_immunity": (
        "The system shall provide adequate electromagnetic immunity for "
        "use adjacent to CT and angiography equipment."
    ),
    "flow_rate_closed_loop": (
        "The pump control loop shall sample the flow sensor efficiently "
        "and adjust motor drive in a timely manner."
    ),
    "luer_lock_torque": (
        "The syringe-to-catheter connector shall be a standard luer-lock "
        "fitting rated to withstand reasonable injection pressures without "
        "disconnection."
    ),
    "needle_compat_labeling": (
        "The system shall display the compatible needle gauge range on the "
        "injector head housing in a clear, user-friendly way."
    ),
    "protocol_library": (
        "The system shall provide a sufficient library of preconfigured "
        "injection protocols selectable by exam type."
    ),
    "reprocessing_cycle_count_display": (
        "The system shall display the remaining validated reprocessing "
        "cycle count for a reusable component where possible."
    ),
    "reservoir_barcode_mismatch": (
        "A barcode scan that does not match the previously loaded lot "
        "shall require operator re-confirmation in a timely manner."
    ),
    "volume_accuracy": (
        "The injector shall deliver the programmed total volume within a "
        "reasonable tolerance for volumes between 5 and 200 mL."
    ),
}


def select_seeded_keys(seed: int = SEED, n: int = N_UNTESTABLE):
    """Which of the 86 real requirement keys get a vague rewrite,
    decided the same way seed.py decides its own defect placement: a
    fixed-seed shuffle of the 86 keys in tree-walk order, not a
    hand-picked convenient set."""
    keys = [row[0] for row in flatten_tree()]
    rng = random.Random(seed)
    shuffled = list(keys)
    rng.shuffle(shuffled)
    return sorted(shuffled[:n])


def find_untestable_phrasing(items):
    """items: iterable of (key, text). Returns a sorted list of
    (key, matched_phrase) for every item whose text contains at least
    one phrase from UNTESTABLE_PHRASES (case-insensitive substring),
    the first such phrase found, in UNTESTABLE_PHRASES order."""
    flagged = []
    for key, text in items:
        low = text.lower()
        for phrase in UNTESTABLE_PHRASES:
            if phrase in low:
                flagged.append((key, phrase))
                break
    flagged.sort(key=lambda t: t[0])
    return flagged


def real_tree_items():
    """The 86 real requirement texts, unmodified, as (key, text) pairs."""
    return [(row[0], row[1]) for row in flatten_tree()]


def seeded_corpus_items():
    """The 86 real requirement texts with the 10 seeded keys' text
    replaced by their vague variant from SEEDED_UNTESTABLE_VARIANTS."""
    items = []
    for key, text in real_tree_items():
        items.append((key, SEEDED_UNTESTABLE_VARIANTS.get(key, text)))
    return items


def main():
    real_flagged = find_untestable_phrasing(real_tree_items())
    corpus_flagged = find_untestable_phrasing(seeded_corpus_items())
    seeded_keys = set(SEEDED_UNTESTABLE_VARIANTS.keys())
    caught = {k for k, _p in corpus_flagged if k in seeded_keys}
    false_positives = [k for k, _p in corpus_flagged if k not in seeded_keys]

    print(f"real tree (86 unmodified texts): {len(real_flagged)} flagged "
          f"(expected 0)")
    print(f"seeded corpus (10 vague rewrites among 86): "
          f"{len(corpus_flagged)} flagged")
    print(f"caught: {len(caught)}/{len(seeded_keys)} seeded untestable "
          f"requirements")
    print(f"false positives: {len(false_positives)} (clean requirements "
          f"flagged): {false_positives}")
    for key, phrase in corpus_flagged:
        tag = "SEEDED-UNTESTABLE" if key in seeded_keys else "FALSE-POSITIVE"
        print(f"  [{tag}] {key}: matched phrase {phrase!r}")


if __name__ == "__main__":
    main()
