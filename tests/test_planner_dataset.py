from dupster.application.planner import bulk_delete_plan, groups_from_hash_map


def test_planner_on_dataset(dupe_dataset):
    expected = dupe_dataset["expected"]
    hm = {h: sorted(files) for h, files in expected.items()}
    groups = groups_from_hash_map(hm)
    assert len(groups) == 2
    all_files = sorted([p for g in groups for p in g.files])
    assert set(all_files) == set().union(*expected.values())

    plan = bulk_delete_plan(groups)
    assert len(plan) == 2
    for entry in plan:
        files = set(expected[entry["hash"]])
        assert entry["keep"] in files
        assert set(entry["delete"]).issubset(files - {entry["keep"]})
