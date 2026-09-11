from trace_workbench import domain_data


def test_fourteen_user_needs():
    assert len(domain_data.USER_NEEDS) == 14


def test_eighty_six_requirements():
    assert domain_data.count_requirements() == 86


def test_every_node_has_a_keyword_and_unique_key():
    seen_keys = set()

    def walk(nodes):
        for key, text, keyword, children in nodes:
            assert key not in seen_keys, f"duplicate requirement key: {key}"
            seen_keys.add(key)
            assert keyword, f"{key} has no keyword"
            assert text.strip(), f"{key} has empty text"
            walk(children)

    for top_nodes in domain_data.REQ_TREE.values():
        walk(top_nodes)
    assert len(seen_keys) == 86
