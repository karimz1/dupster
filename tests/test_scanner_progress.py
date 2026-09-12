import asyncio
import time

from dupster.application import scanner
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


def test_file_discovery_does_not_block_event_loop(monkeypatch, tmp_path):
    events = []

    def slow_scan_entries(root, follow_symlinks=False):
        time.sleep(0.05)
        events.append("scan_done")
        return []

    async def drive():
        monkeypatch.setattr(scanner, "scan_entries", slow_scan_entries)
        scan_task = asyncio.create_task(scanner.find_duplicates_by_hash_async(str(tmp_path)))
        await asyncio.sleep(0.01)
        events.append("tick")
        await scan_task

    asyncio.run(drive())

    assert events == ["tick", "scan_done"]
