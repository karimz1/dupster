import asyncio

from dupster.application.scanner import find_duplicates_by_hash_async


def test_progress_callback_invoked(tmp_path):
    for i in range(5):
        (tmp_path / f"f{i}.bin").write_bytes(b"x" * (i + 1))
    calls = []

    def progress(i, t):
        calls.append((i, t))

    asyncio.run(find_duplicates_by_hash_async(str(tmp_path), progress))
    assert len(calls) == 5
    assert calls[-1][0] == 5 and calls[-1][1] == 5
