import pytest
import asyncio
from pathlib import Path

textual = pytest.importorskip("textual")
widgets = pytest.importorskip("textual.widgets")
pilot_mod = pytest.importorskip("textual.pilot")

from dupster.ui.tui.app import DupsterApp


def _make_dupes(tmp_path: Path) -> None:
    (tmp_path / "g1" / "a.txt").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "g1" / "a.txt").write_bytes(b"same" * 100)
    (tmp_path / "g2").mkdir(parents=True, exist_ok=True)
    (tmp_path / "g2" / "b.txt").write_bytes(b"same" * 100)


def test_tui_lists_groups_and_shows_hash_in_header(dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        async with app.run_test(headless=True) as pilot:
            await pilot_mod.wait_for_idle()
            assert app.groups, "expected duplicate groups"
            groups_lv = app.query_one("#groups", widgets.ListView)
            assert groups_lv is not None
            await pilot.press("l")
            await pilot_mod.wait_for_idle()
            g = app._selected_group()
            assert g is not None and isinstance(g.hash, str) and len(g.hash) == 64
    asyncio.run(_run())


def test_tui_bulk_delete_preview_modal_open_and_close(dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        async with app.run_test(headless=True) as pilot:
            await pilot_mod.wait_for_idle()
            assert app.groups
            await pilot.press("d")
            await pilot_mod.wait_for_idle()
            app.screen.query_one("#bulk-summary", widgets.DataTable)
            await pilot.press("q")
            await pilot_mod.wait_for_idle()
            assert not list(app.screen.query("#bulk-summary"))
    asyncio.run(_run())
