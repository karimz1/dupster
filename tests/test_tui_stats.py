import asyncio

import pytest

textual = pytest.importorskip("textual")  # noqa: F841

from dupster.ui.tui.app import DupsterApp  # noqa: E402


def write(p, data: bytes):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_tui_reports_scan_stats(tmp_path):
    data = b"duplicate payload " * 5000
    write(tmp_path / "one" / "a.bin", data)
    write(tmp_path / "two" / "b.bin", data)
    write(tmp_path / "three" / "unique.bin", b"solo")

    app = DupsterApp(folder=str(tmp_path))

    async def drive():
        async with app.run_test() as pilot:
            for _ in range(60):
                await pilot.pause()
                if app.groups:
                    break

            assert app.groups, "expected duplicate groups"
            assert app.last_stats is not None
            assert app.last_stats.files_seen == 3
            # The lone file has a unique size, so it is never opened.
            assert app.last_stats.skipped_by_size >= 1

            # Sizes come from the scan, so savings need no extra stat calls.
            group = app.groups[0]
            assert group.size == len(data)
            assert group.potential_savings() == len(data)

            line = app._scan_line()
            assert "Scanned 3 files" in line
            assert "skipped without a full read" in line

    asyncio.run(drive())


def test_tui_accepts_scan_options(tmp_path):
    write(tmp_path / "a.bin", b"x" * 100)
    app = DupsterApp(folder=str(tmp_path), workers=2, min_size=10, verify=True)
    assert app.scan_workers == 2
    assert app.scan_min_size == 10
    assert app.scan_verify is True
    # Textual's App.workers is its worker manager and must not be shadowed.
    assert app.workers is not app.scan_workers
