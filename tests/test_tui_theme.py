import asyncio
import json
import re

import pytest

textual = pytest.importorskip("textual")  # noqa: F841
pilot_mod = pytest.importorskip("textual.pilot")
widgets = pytest.importorskip("textual.widgets")

from dupster import __version__  # noqa: E402
from dupster.domain.models import DuplicateGroup  # noqa: E402
from dupster.ui.tui.app import (  # noqa: E402
    DEFAULT_THEME,
    GITHUB_REPO,
    GITHUB_URL,
    THEME_CONFIG_ENV,
    THEME_PREVIEW_DELAY,
    BulkDeleteModal,
    ConfirmDeleteModal,
    DupsterApp,
    GithubButton,
    ShortcutHelpPanel,
    ThemeListItem,
    _rich_color,
    _SmoothProgress,
)


def test_tui_uses_modern_default_theme(monkeypatch, tmp_path):
    monkeypatch.setenv(THEME_CONFIG_ENV, str(tmp_path / "config.json"))

    app = DupsterApp()

    assert app.theme == DEFAULT_THEME


def test_tui_initializes_without_current_event_loop(monkeypatch, tmp_path):
    monkeypatch.setenv(THEME_CONFIG_ENV, str(tmp_path / "config.json"))
    previous_loop = None
    try:
        previous_loop = asyncio.get_event_loop()
    except RuntimeError:
        pass
    asyncio.set_event_loop(None)

    try:
        app = DupsterApp()

        assert app.theme == DEFAULT_THEME
        asyncio.get_event_loop()
    finally:
        try:
            new_loop = asyncio.get_event_loop()
        except RuntimeError:
            new_loop = None
        if new_loop is not None and new_loop is not previous_loop:
            new_loop.close()
        asyncio.set_event_loop(previous_loop)


def test_tui_loads_saved_theme(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"theme": "nord"}), encoding="utf-8")
    monkeypatch.setenv(THEME_CONFIG_ENV, str(config_path))

    app = DupsterApp()

    assert app.theme == "nord"


def test_tui_saves_selected_theme(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(THEME_CONFIG_ENV, str(config_path))

    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        async with app.run_test(headless=True) as pilot:
            app.theme = "dracula"
            await pilot.pause()

    asyncio.run(drive())

    assert json.loads(config_path.read_text(encoding="utf-8")) == {"theme": "dracula"}


def _alternate_theme(app: DupsterApp) -> str:
    return next(
        name for name in sorted(app.available_themes) if name not in {app.theme, "textual-ansi"}
    )


def test_theme_picker_previews_theme_and_restores_on_cancel(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(THEME_CONFIG_ENV, str(config_path))
    result: dict[str, str] = {}

    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        original_theme = app.theme
        target_theme = _alternate_theme(app)
        result["original_theme"] = original_theme
        async with app.run_test(headless=True) as pilot:
            await pilot.press("t")
            await pilot.pause()
            theme_list = app.screen.query_one("#theme-list", widgets.ListView)
            app.screen.query_one("#summary", widgets.Static)
            target_index = [
                item.theme_name for item in theme_list.children if isinstance(item, ThemeListItem)
            ].index(target_theme)

            theme_list.index = target_index
            await pilot.pause()

            assert app.theme == original_theme
            await pilot.pause(THEME_PREVIEW_DELAY + 0.05)

            assert app.theme == target_theme
            assert not config_path.exists()

            await pilot.press("escape")
            await pilot.pause()

    asyncio.run(drive())

    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "theme": result["original_theme"]
    }


def test_theme_picker_applies_previewed_theme(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(THEME_CONFIG_ENV, str(config_path))
    result: dict[str, str] = {}

    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        target_theme = _alternate_theme(app)
        result["target_theme"] = target_theme
        async with app.run_test(headless=True) as pilot:
            await pilot.press("t")
            await pilot.pause()
            theme_list = app.screen.query_one("#theme-list", widgets.ListView)
            app.screen.query_one("#summary", widgets.Static)
            target_index = [
                item.theme_name for item in theme_list.children if isinstance(item, ThemeListItem)
            ].index(target_theme)

            theme_list.index = target_index
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

    asyncio.run(drive())

    assert json.loads(config_path.read_text(encoding="utf-8")) == {"theme": result["target_theme"]}


def test_theme_preview_after_scan_keeps_main_ui_visible(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(THEME_CONFIG_ENV, str(config_path))

    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        target_theme = _alternate_theme(app)
        async with app.run_test(headless=True) as pilot:
            await pilot_mod.wait_for_idle()
            assert app.last_stats is not None

            await pilot.press("t")
            await pilot.pause()
            theme_list = app.screen.query_one("#theme-list", widgets.ListView)
            target_index = [
                item.theme_name for item in theme_list.children if isinstance(item, ThemeListItem)
            ].index(target_theme)

            theme_list.index = target_index
            await pilot.pause(THEME_PREVIEW_DELAY + 0.05)

            assert app.theme == target_theme
            app.screen.query_one("#summary", widgets.Static)
            app.screen.query_one("#groups", widgets.ListView)

    asyncio.run(drive())


def test_theme_picker_debounces_preview_while_browsing(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setenv(THEME_CONFIG_ENV, str(config_path))

    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        original_theme = app.theme
        target_themes = [
            name
            for name in sorted(app.available_themes)
            if name not in {original_theme, "textual-ansi"}
        ][:2]
        async with app.run_test(headless=True) as pilot:
            await pilot.press("t")
            await pilot.pause()
            theme_list = app.screen.query_one("#theme-list", widgets.ListView)
            indexes = [
                [
                    item.theme_name
                    for item in theme_list.children
                    if isinstance(item, ThemeListItem)
                ].index(theme_name)
                for theme_name in target_themes
            ]

            theme_list.index = indexes[0]
            await pilot.pause(THEME_PREVIEW_DELAY / 2)
            theme_list.index = indexes[1]
            await pilot.pause(THEME_PREVIEW_DELAY / 2)

            assert app.theme == original_theme

            await pilot.pause(THEME_PREVIEW_DELAY + 0.05)

            assert app.theme == target_themes[1]
            assert not config_path.exists()

    asyncio.run(drive())


def test_tui_css_uses_textual_theme_variables():
    assert "$background" in DupsterApp.CSS
    assert "$surface" in DupsterApp.CSS
    assert "$primary" in DupsterApp.CSS
    assert "#dashboard" in DupsterApp.CSS
    assert "height: 1;" in DupsterApp.CSS
    assert "HeaderIcon" not in DupsterApp.CSS
    assert "ListView:focus > ListItem.-highlight" in DupsterApp.CSS
    assert "DataTable:focus > .datatable--cursor" in DupsterApp.CSS
    assert "CommandList > .option-list--option-highlighted" in DupsterApp.CSS
    assert "CommandPalette > .command-palette--highlight" in DupsterApp.CSS
    assert "$block-cursor-background" not in DupsterApp.CSS
    assert "layers: default overlay" in DupsterApp.CSS
    assert "#versionbar" in DupsterApp.CSS
    assert "#githubbar:hover" in DupsterApp.CSS
    assert "#theme-picker" in DupsterApp.CSS
    assert "#shortcut-help" in DupsterApp.CSS
    assert "#shortcut-title" in DupsterApp.CSS
    assert "#theme-wrap" not in DupsterApp.CSS
    assert ".hidden" not in DupsterApp.CSS
    assert ".max" not in DupsterApp.CSS
    assert not re.search(r"#[0-9a-fA-F]{6}", DupsterApp.CSS)


def test_rich_theme_color_strips_alpha_for_rich():
    assert _rich_color("#CDD6F499", "#ffffff") == "#CDD6F4"


def test_smooth_progress_throttles_redundant_redraws():
    class FakeProgress:
        def __init__(self):
            self.values: list[int] = []

        @property
        def progress(self) -> int:
            return self.values[-1]

        @progress.setter
        def progress(self, value: int) -> None:
            self.values.append(value)

    now = 0.0

    def clock() -> float:
        return now

    progress = FakeProgress()
    smooth_progress = _SmoothProgress(progress, min_interval=0.03, clock=clock)

    smooth_progress(1, 100)
    now = 0.01
    smooth_progress(2, 100)
    now = 0.02
    smooth_progress(3, 100)
    now = 0.04
    smooth_progress(4, 100)
    smooth_progress(100, 100)

    assert progress.values == [1, 4, 100]


def test_command_palette_binding_is_named_search():
    search_bindings = [
        binding for binding in DupsterApp.BINDINGS if binding.action == "command_palette"
    ]

    assert len(search_bindings) == 1
    assert search_bindings[0].description == "Search"


def test_copy_path_binding_is_available():
    copy_bindings = [
        binding for binding in DupsterApp.BINDINGS if binding.action == "copy_selected_path"
    ]

    assert len(copy_bindings) == 1
    assert copy_bindings[0].key == "c"
    assert copy_bindings[0].description == "Copy Path"


def test_delete_and_compact_view_bindings_use_clear_labels():
    bindings = {binding.key: binding.description for binding in DupsterApp.BINDINGS}
    actions = {binding.action for binding in DupsterApp.BINDINGS}

    assert bindings["i"] == "Delete Duplicates in Group"
    assert bindings["d"] == "Delete All Duplicates"
    assert bindings["v"] == "Compact View"
    assert bindings["g"] == "Jump to Top"
    assert bindings["G"] == "Jump to Bottom"
    assert bindings["?"] == "Help"
    assert bindings["left"] == "Left Pane"
    assert bindings["right"] == "Right Pane"
    assert "g,g" not in bindings
    assert bindings.get("m") is None
    assert "toggle_maximize" not in actions


def test_delete_modals_confirm_with_y_not_enter():
    for modal_cls in (ConfirmDeleteModal, BulkDeleteModal):
        bindings = {binding.key: binding.description for binding in modal_cls.BINDINGS}

        assert bindings["y"] == "Delete"
        assert bindings["g"] == "Jump to Top"
        assert bindings["G"] == "Jump to Bottom"
        assert "enter" not in bindings


def test_compact_view_is_default_and_dashboard_is_single_line(tmp_path):
    app = DupsterApp(folder=str(tmp_path))

    assert app._compact_groups
    assert "\n" not in app._dashboard_text().plain


def test_dashboard_uses_full_scan_root_path(tmp_path):
    root = tmp_path / "really" / "deep" / "scan-root"
    root.mkdir(parents=True)
    app = DupsterApp(folder=str(root))
    dashboard = app._dashboard_text().plain

    assert app._scan_root_path() == str(root.resolve())
    assert str(root.resolve()) in dashboard
    assert "..." not in dashboard


def test_custom_bottom_bar_names_copy_search_and_github():
    app = DupsterApp()
    github_text = app._github_bar_text(width=220)
    key_text = app._key_bar_text(width=220).plain

    assert "? Help" in key_text
    assert "Copy Path" in key_text
    assert "Search" in key_text
    assert "g/G Jump" in key_text
    assert "h/l/arrows Pane" in key_text
    assert "Jump to Top" not in key_text
    assert "Jump to Bottom" not in key_text
    assert "Detailed" not in key_text
    assert "Delete Group Dupes" not in key_text
    assert "Delete All Dupes" not in key_text
    assert " Keep " not in key_text
    assert app._version_bar_text(width=220).plain == f"v{__version__}"
    assert github_text.plain == GITHUB_REPO
    assert GITHUB_URL not in github_text.plain
    assert getattr(github_text.style, "link", None) == GITHUB_URL


def test_bottom_bar_marks_open_help_panel():
    app = DupsterApp()
    app._shortcut_help_open = True
    key_text = app._key_bar_text(width=220).plain

    assert "? Hide Help" in key_text
    assert "Jump to Top" not in key_text
    assert "Jump to Bottom" not in key_text
    assert "Delete Group Dupes" not in key_text
    assert "Delete All Dupes" not in key_text


def test_shortcut_help_panel_has_headline_and_sections():
    bindings = {binding.key: binding.description for binding in ShortcutHelpPanel.BINDINGS}

    assert bindings["?"] == "Hide Help"
    assert bindings["escape"] == "Close"
    assert bindings["q"] == "Close"


def test_bottom_bar_uses_responsive_shortcuts():
    app = DupsterApp()

    tiny_keys = app._key_bar_text(width=54).plain
    compact_keys = app._key_bar_text(width=90).plain
    medium_keys = app._key_bar_text(width=120).plain

    assert tiny_keys == "? Help  q Quit"
    assert len(tiny_keys) <= 54
    assert compact_keys == "? Help  ctrl+p Search  q Quit"
    assert len(compact_keys) <= 90
    assert medium_keys == "? Help  c Path  ctrl+p Search  i/d Delete  q Quit"
    assert len(medium_keys) <= 120
    assert app._version_bar_text(width=54).plain == ""
    assert app._github_bar_text(width=54).plain == ""
    assert app._version_bar_text(width=120).plain == f"v{__version__}"
    assert app._github_bar_text(width=120).plain == "GitHub"


def test_github_button_opens_repo_and_copies_url_when_clicked(monkeypatch, tmp_path):
    monkeypatch.setenv(THEME_CONFIG_ENV, str(tmp_path / "config.json"))
    opened: list[tuple[str, bool]] = []
    copied: list[str] = []

    def open_url(url: str, *, new_tab: bool = True) -> None:
        opened.append((url, new_tab))

    def copy_to_clipboard(text: str) -> None:
        copied.append(text)

    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        async with app.run_test(headless=True) as pilot:
            monkeypatch.setattr(app, "open_url", open_url)
            monkeypatch.setattr(app, "copy_to_clipboard", copy_to_clipboard)
            button = app.query_one("#githubbar", GithubButton)
            assert button.url == GITHUB_URL
            await pilot.click("#githubbar", offset=(1, 0))
            await pilot.pause()

    asyncio.run(drive())

    assert opened == [(GITHUB_URL, True)]
    assert copied == [GITHUB_URL]


def test_group_panel_supports_detailed_and_compact_modes():
    app = DupsterApp()
    group = DuplicateGroup(
        hash="a" * 64,
        files=["/tmp/a.bin", "/tmp/b.bin", "/tmp/c.bin"],
        index=7,
        size=1024,
    )

    app._compact_groups = False
    detailed = app._group_panel(group).plain
    app._compact_groups = True
    compact = app._group_panel(group).plain

    assert "\n" in detailed
    assert "fingerprint" in detailed
    assert "\n" not in compact
    assert "sha " in compact
    assert "Group " not in compact


def test_file_panel_supports_detailed_and_compact_modes(tmp_path):
    path = tmp_path / "duplicate.bin"
    path.write_bytes(b"x" * 1024)
    app = DupsterApp()

    app._compact_groups = False
    detailed = app._file_panel(0, str(path)).plain
    app._compact_groups = True
    compact = app._file_panel(0, str(path)).plain

    assert "\n" in detailed
    assert "duplicate.bin" in detailed
    assert "\n" not in compact
    assert "duplicate.bin" in compact


def test_search_commands_include_copy_full_path(tmp_path):
    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        async with app.run_test(headless=True):
            titles = {command.title for command in app.get_system_commands(app.screen)}
            assert "Copy Full Path" in titles
            assert "Delete Duplicates in Group" in titles
            assert "Delete Duplicates in All Groups" in titles
            assert "Toggle Compact View" in titles
            assert "Toggle Help Panel" in titles
            assert "Jump to Top" in titles
            assert "Jump to Bottom" in titles
            assert "Maximize Focused Widget" in titles
            assert "Star on GitHub" in titles

    asyncio.run(drive())


def test_maximized_keybar_preserves_shortcuts():
    app = DupsterApp()
    app._pane_maximized = "left"
    key_text = app._key_bar_text(width=220).plain

    assert "ESC Exit Maximize" in key_text
    assert "Copy Path" in key_text
    assert "Search" in key_text
    assert "Delete" in key_text
    assert "Jump" in key_text
    assert "Quit" in key_text


def test_toggle_maximize_pane_expands_vertically_and_restores(tmp_path):
    async def drive():
        app = DupsterApp(folder=str(tmp_path))
        async with app.run_test(headless=True):
            dashboard = app.query_one("#dashboard")
            left = app.query_one("#left")
            right = app.query_one("#right")
            pathinfo = app.query_one("#pathinfo")

            # Initially normal
            assert "full-hide" not in dashboard.classes
            assert "pane-solo" not in left.classes

            # Toggle maximize on left pane
            app.action_toggle_maximize_pane()
            assert "full-hide" in dashboard.classes
            assert "full-hide" in pathinfo.classes
            assert "pane-solo" in left.classes
            assert "pane-hidden" in right.classes
            assert app._pane_maximized == "left"

            # Toggle off via exit
            app.action_exit_maximize()
            assert "full-hide" not in dashboard.classes
            assert "full-hide" not in pathinfo.classes
            assert "pane-solo" not in left.classes
            assert "pane-hidden" not in right.classes
            assert app._pane_maximized is None

    asyncio.run(drive())
