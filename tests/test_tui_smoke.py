import asyncio
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")
widgets = pytest.importorskip("textual.widgets")
pilot_mod = pytest.importorskip("textual.pilot")
coordinate_mod = pytest.importorskip("textual.coordinate")

from dupster.ui.tui import app as tui_app
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


def test_tui_group_delete_asks_which_file_to_keep(dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        async with app.run_test(headless=True) as pilot:
            await pilot_mod.wait_for_idle()
            assert app.groups
            app.current_file_idx = None

            await pilot.press("i")
            await pilot_mod.wait_for_idle()

            table = app.screen.query_one("#confirm-table", widgets.DataTable)
            header = app.screen.query_one("#confirm-text", widgets.Static)
            header_text = header.renderable.renderable.plain
            assert "Choose the file to keep" in header_text
            assert "press y to delete the others" in header_text
            assert "press Enter" not in header_text
            assert table.get_cell_at(coordinate_mod.Coordinate(0, 0)) == "Keep this"
            assert table.get_cell_at(coordinate_mod.Coordinate(1, 0)) == "Delete duplicate"

            await pilot.press("G")
            await pilot_mod.wait_for_idle()

            bottom_row = table.row_count - 1
            assert table.get_cell_at(coordinate_mod.Coordinate(0, 0)) == "Delete duplicate"
            assert table.get_cell_at(coordinate_mod.Coordinate(bottom_row, 0)) == "Keep this"
            await pilot.press("g")
            await pilot_mod.wait_for_idle()

            assert table.get_cell_at(coordinate_mod.Coordinate(0, 0)) == "Keep this"
            assert table.get_cell_at(coordinate_mod.Coordinate(1, 0)) == "Delete duplicate"
            await pilot.press("q")

    asyncio.run(_run())


def test_tui_copies_selected_file_path(dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        copied: list[str] = []
        async with app.run_test(headless=True) as pilot:
            app.copy_to_clipboard = copied.append  # type: ignore[method-assign]
            await pilot_mod.wait_for_idle()
            assert app.groups
            await pilot.press("l")
            await pilot_mod.wait_for_idle()

            selected = app._selected_file()
            assert selected is not None
            await pilot.press("c")
            await pilot_mod.wait_for_idle()

            assert copied == [str(Path(selected).resolve())]

    asyncio.run(_run())


def test_tui_open_selected_file_falls_back_to_copy_path(monkeypatch, dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        opened: list[str] = []
        copied: list[str] = []

        def open_file(path: str) -> bool:
            opened.append(path)
            raise ModuleNotFoundError("textual.scrollbar")

        async with app.run_test(headless=True) as pilot:
            monkeypatch.setattr(tui_app, "open_file", open_file)
            app.copy_to_clipboard = copied.append  # type: ignore[method-assign]
            await pilot_mod.wait_for_idle()
            assert app.groups
            await pilot.press("l")
            await pilot_mod.wait_for_idle()

            selected = app._selected_file()
            assert selected is not None
            await pilot.press("o")
            await pilot_mod.wait_for_idle()

            expected = str(Path(selected).resolve())
            assert opened == [expected]
            assert copied == [expected]

    asyncio.run(_run())


def test_tui_toggles_compact_group_and_file_view(dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        async with app.run_test(headless=True) as pilot:
            await pilot_mod.wait_for_idle()
            assert app.groups
            assert app._compact_groups
            assert "Compact" in app._group_label_text().plain
            group_item = app.query_one("#groups", widgets.ListView).children[0]
            group_card = group_item.query_one(widgets.Static)
            file_item = app.query_one("#files", widgets.ListView).children[0]
            file_card = file_item.query_one(widgets.Static)
            assert group_card.has_class("compact-card")
            assert file_card.has_class("compact-card")

            await pilot.press("v")
            await pilot_mod.wait_for_idle()

            assert not app._compact_groups
            assert "Detailed" in app._group_label_text().plain
            group_item = app.query_one("#groups", widgets.ListView).children[0]
            group_card = group_item.query_one(widgets.Static)
            file_item = app.query_one("#files", widgets.ListView).children[0]
            file_card = file_item.query_one(widgets.Static)
            assert not group_card.has_class("compact-card")
            assert not file_card.has_class("compact-card")

    asyncio.run(_run())


def test_tui_bottom_bar_stays_readable_in_small_terminals(tmp_path):
    async def _run():
        app = DupsterApp(folder=str(tmp_path))
        async with app.run_test(headless=True, size=(54, 18)):
            await pilot_mod.wait_for_idle()

            keybar = app.query_one("#keybar", widgets.Static)
            versionbar = app.query_one("#versionbar", widgets.Static)
            githubbar = app.query_one("#githubbar", widgets.Static)
            key_text = keybar.renderable.plain

            assert key_text == "? Help  q Quit"
            assert len(key_text) <= 54
            assert versionbar.has_class("footer-collapsed")
            assert githubbar.has_class("footer-collapsed")

    asyncio.run(_run())


def test_tui_shortcut_helper_can_be_shown_and_hidden(tmp_path):
    async def _run():
        app = DupsterApp(folder=str(tmp_path))
        async with app.run_test(headless=True, size=(120, 18)) as pilot:
            await pilot_mod.wait_for_idle()
            keybar = app.query_one("#keybar", widgets.Static)

            assert keybar.renderable.plain.startswith("? Help")
            await pilot.press("?")
            await pilot_mod.wait_for_idle()

            assert app._shortcut_help_open
            panel = app.query_one("#shortcut-help")
            title = app.query_one("#shortcut-title", widgets.Static)
            body_text = "".join(
                section.renderable.plain for section in panel.query(".shortcut-section").nodes
            )
            assert "Help and Keys" in title.renderable.plain
            assert "Move" in body_text
            assert "Act" in body_text
            assert "App" in body_text
            assert keybar.renderable.plain.startswith("? Hide Help")

            await pilot.press("?")
            await pilot_mod.wait_for_idle()

            assert not app._shortcut_help_open
            assert not list(app.query("#shortcut-help"))
            assert keybar.renderable.plain.startswith("? Help")

    asyncio.run(_run())


def test_tui_arrow_keys_switch_between_panes(dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        async with app.run_test(headless=True) as pilot:
            await pilot_mod.wait_for_idle()

            left = app.query_one("#left")
            right = app.query_one("#right")
            await pilot.press("right")
            await pilot_mod.wait_for_idle()

            assert right.has_class("active")
            assert left.has_class("inactive")

            await pilot.press("left")
            await pilot_mod.wait_for_idle()

            assert left.has_class("active")
            assert right.has_class("inactive")

    asyncio.run(_run())


def test_tui_vim_style_top_and_bottom_shortcuts(dupe_dataset):
    async def _run():
        app = DupsterApp(folder=dupe_dataset["root"])
        async with app.run_test(headless=True) as pilot:
            await pilot_mod.wait_for_idle()
            assert len(app.groups) > 1
            groups = app.query_one("#groups", widgets.ListView)
            files = app.query_one("#files", widgets.ListView)

            groups.focus()
            groups.index = len(groups.children) - 1
            await pilot.press("g")
            await pilot_mod.wait_for_idle()
            assert groups.index == 0

            await pilot.press("G")
            await pilot_mod.wait_for_idle()
            assert groups.index == len(groups.children) - 1

            await pilot.press("l")
            await pilot_mod.wait_for_idle()
            assert len(files.children) > 1
            files.index = len(files.children) - 1
            await pilot.press("g")
            await pilot_mod.wait_for_idle()
            assert files.index == 0

            await pilot.press("G")
            await pilot_mod.wait_for_idle()
            assert files.index == len(files.children) - 1

    asyncio.run(_run())
