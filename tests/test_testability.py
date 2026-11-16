from trace_workbench import testability


def test_seeded_keys_match_selection_by_fixed_seed():
    assert testability.select_seeded_keys() == sorted(
        testability.SEEDED_UNTESTABLE_VARIANTS.keys()
    )


def test_ten_seeded_variants():
    assert len(testability.SEEDED_UNTESTABLE_VARIANTS) == 10


def test_no_false_positives_on_the_real_tree():
    flagged = testability.find_untestable_phrasing(testability.real_tree_items())
    assert flagged == []


def test_catches_all_ten_seeded_untestable_requirements_with_no_false_positives():
    flagged = testability.find_untestable_phrasing(testability.seeded_corpus_items())
    flagged_keys = {k for k, _p in flagged}
    seeded_keys = set(testability.SEEDED_UNTESTABLE_VARIANTS.keys())
    assert flagged_keys == seeded_keys  # exactly the 10, nothing else


def test_detector_is_deterministic():
    a = testability.find_untestable_phrasing(testability.seeded_corpus_items())
    b = testability.find_untestable_phrasing(testability.seeded_corpus_items())
    assert a == b
