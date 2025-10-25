import asyncio

from dupster.application.scanner import find_duplicates_by_hash_async


def test_dataset_scanner_groups_and_members(dupe_dataset):
    root = dupe_dataset["root"]
    expected = dupe_dataset["expected"]
    hm = asyncio.run(find_duplicates_by_hash_async(root))
    assert set(hm.keys()) == set(expected.keys())
    for h, files in expected.items():
        assert set(hm[h]) == files

