from dupster.application.planner import groups_from_hash_map


def test_groups_sorted_by_hash_and_indexed():
    hm = {
        "zz": ["/p/a", "/p/b"],
        "aa": ["/p/c", "/p/d"],
        "mm": ["/p/e", "/p/f"],
    }
    groups = groups_from_hash_map(hm)
    hashes = [g.hash for g in groups]
    assert hashes == sorted(hm.keys())
    assert [g.index for g in groups] == [1, 2, 3]
