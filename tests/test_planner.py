from dupster.application.planner import groups_from_hash_map, keep_one_plan, bulk_delete_plan, total_reclaim_bytes


def test_groups_and_plans(tmp_path):
    f1 = tmp_path / "a" / "x.txt"; f1.parent.mkdir(parents=True, exist_ok=True); f1.write_text("x")
    f2 = tmp_path / "b" / "x.txt"; f2.parent.mkdir(parents=True, exist_ok=True); f2.write_text("x")
    f3 = tmp_path / "b" / "y.txt"; f3.write_text("y")
    f4 = tmp_path / "c" / "y.txt"; f4.parent.mkdir(parents=True, exist_ok=True); f4.write_text("y")

    hm = {
        "h1": [str(f1), str(f2)],
        "h2": [str(f3), str(f4)],
    }

    groups = groups_from_hash_map(hm)
    assert len(groups) == 2
    assert all(g.index in (1, 2) for g in groups)

    plan = bulk_delete_plan(groups)
    assert len(plan) == 2
    assert all(len(p["delete"]) == 1 for p in plan)
    assert total_reclaim_bytes(plan) > 0

    single = keep_one_plan(groups[0], groups[0].files[0])
    assert single["keep"] == groups[0].files[0]
    assert groups[0].files[0] not in single["delete"]

