from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from rich.markup import escape
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.coordinate import Coordinate
from textual.events import Click, Resize
from textual.message import Message
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import (
    DataTable,
    Footer,
    ListItem,
    ListView,
    ProgressBar,
    Static,
)

from dupster import __version__
from dupster.application.planner import (
    bulk_delete_plan,
    groups_from_hash_map,
    total_reclaim_bytes,
)
from dupster.application.scanner import find_duplicates_detailed_async
from dupster.domain.models import DuplicateGroup
from dupster.infrastructure.filesystem import get_size, open_file
from dupster.utils.formatting import human_size

BRAND_NAME = "Dupster"
ACTIVE_THEME_MARK = ">"
DEFAULT_THEME = "catppuccin-mocha"
GITHUB_REPO = "karimz1/dupster"
GITHUB_URL = "https://github.com/karimz1/dupster"
THEME_CONFIG_ENV = "DUPSTER_CONFIG_FILE"
PROGRESS_REDRAW_INTERVAL = 1 / 30
THEME_PREVIEW_DELAY = 0.12


def _theme_config_path() -> Path:
    override = os.environ.get(THEME_CONFIG_ENV)
    if override:
        return Path(override).expanduser()

    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / "dupster" / "config.json"

    return Path.home() / ".config" / "dupster" / "config.json"


def _rich_color(value: str | None, fallback: str) -> str:
    """Convert a Textual theme variable into a Rich-compatible color."""
    if not value:
        return fallback
    if value.startswith("#") and len(value) == 9:
        return value[:7]
    if value.startswith("#") and len(value) == 7:
        return value
    if value.startswith("ansi_") or value.startswith("auto") or " " in value:
        return fallback
    return value


def _copy_to_system_clipboard(text: str) -> bool:
    commands: list[list[str]]
    if sys.platform == "darwin":
        commands = [["pbcopy"]]
    elif sys.platform == "win32":
        commands = [["clip"]]
    else:
        commands = [
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ]

    for command in commands:
        if not shutil.which(command[0]):
            continue
        try:
            subprocess.run(
                command,
                input=text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


class _SmoothProgress:
    def __init__(
        self,
        progress: ProgressBar,
        *,
        min_interval: float = PROGRESS_REDRAW_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._progress = progress
        self._min_interval = min_interval
        self._clock = clock
        self._last_percent: int | None = None
        self._last_refresh = 0.0

    def __call__(self, done: int, total: int) -> None:
        percent = min(max(int((done / max(total, 1)) * 100), 0), 100)
        now = self._clock()
        should_update = (
            self._last_percent is None
            or percent == 100
            or (percent != self._last_percent and now - self._last_refresh >= self._min_interval)
        )
        if not should_update:
            return
        self._progress.progress = percent
        self._last_percent = percent
        self._last_refresh = now


class GithubButton(Static):
    def __init__(self, content: Text, *, id: str | None = None):
        super().__init__(content, id=id)
        self.url = GITHUB_URL
        self.tooltip = f"Open and copy {GITHUB_URL}"

    def on_click(self, event: Click) -> None:
        event.stop()
        self.app.action_star_on_github()


class ShortcutHelpPanel(Vertical):
    BINDINGS = [
        Binding("?", "close", "Hide Help"),
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]
    can_focus = True

    def __init__(self):
        super().__init__(id="shortcut-help")

    def _section_text(self, title: str, rows: list[tuple[str, str]]) -> Text:
        title_style = _rich_color(self.app.theme_variables.get("primary"), "#38bdf8")
        key_style = f"bold {title_style}"
        parts: list[tuple[str, str] | str] = [(title, key_style), ("\n", "")]
        for key, description in rows:
            parts.extend(
                [
                    (key.ljust(14), key_style),
                    (description, "dim"),
                    ("\n", ""),
                ]
            )
        return Text.assemble(*parts)

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static(
            Text.assemble(
                ("Help and Keys", "bold"),
                ("\n"),
                ("Press ? or Esc to hide", "dim"),
            ),
            id="shortcut-title",
        )
        with VerticalScroll(id="shortcut-body"):
            yield Static(
                self._section_text(
                    "Move",
                    [
                        ("up/down", "Move through rows"),
                        ("h/l", "Switch panes"),
                        ("left/right", "Switch panes"),
                        ("g", "Jump to top"),
                        ("G", "Jump to bottom"),
                    ],
                ),
                classes="shortcut-section",
            )
            yield Static(
                self._section_text(
                    "Act",
                    [
                        ("c", "Copy full path"),
                        ("o", "Open selected file"),
                        ("i", "Delete duplicates in group"),
                        ("d", "Delete duplicates in all groups"),
                    ],
                ),
                classes="shortcut-section",
            )
            yield Static(
                self._section_text(
                    "App",
                    [
                        ("ctrl+p", "Search commands"),
                        ("s", "Scan again"),
                        ("t", "Change theme"),
                        ("v", "Toggle compact view"),
                        ("q", "Quit"),
                    ],
                ),
                classes="shortcut-section",
            )
            yield Static(
                self._section_text(
                    "Mouse",
                    [
                        ("click row", "Select a group or file"),
                        ("GitHub", "Open and copy repo link"),
                    ],
                ),
                classes="shortcut-section",
            )

    def on_mount(self) -> None:
        app = self.app
        if isinstance(app, DupsterApp):
            app._shortcut_help_open = True
            app._refresh_footer()
        self.focus()

    def on_unmount(self) -> None:
        app = self.app
        if isinstance(app, DupsterApp):
            app._shortcut_help_open = False
            app._refresh_footer()

    def action_close(self) -> None:
        self.remove()


class ThemeListItem(ListItem):
    def __init__(self, theme_name: str, active_theme: str):
        self.theme_name = theme_name
        marker = ACTIVE_THEME_MARK if theme_name == active_theme else " "
        current_label = " current" if theme_name == active_theme else ""
        label = Text.assemble(
            (marker, "bold"),
            ("  ", ""),
            (theme_name, "bold"),
            (current_label, "dim"),
        )
        super().__init__(Static(label, classes="theme-card"))


class ThemePicker(Vertical):
    BINDINGS = [
        Binding("enter", "select", "Apply"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel"),
        Binding("g", "cursor_top", "Jump to Top"),
        Binding("G", "cursor_bottom", "Jump to Bottom", key_display="G"),
    ]

    def __init__(self, current_theme: str, theme_names: list[str]):
        super().__init__(id="theme-picker")
        self.original_theme = current_theme
        self.theme_names = theme_names
        self._preview_timer: Timer | None = None
        self._pending_theme: str | None = None

    @property
    def current_index(self) -> int:
        try:
            return self.theme_names.index(self.original_theme)
        except ValueError:
            return 0

    def compose(self) -> ComposeResult:  # type: ignore[override]
        items = [ThemeListItem(theme_name, self.original_theme) for theme_name in self.theme_names]
        yield Static("Themes", id="theme-title")
        yield ListView(*items, id="theme-list", initial_index=self.current_index)

    def on_mount(self) -> None:
        self.query_one("#theme-list", ListView).focus()

    def _flush_preview(self) -> None:
        theme_name = self._pending_theme
        self._preview_timer = None
        if theme_name is None:
            return
        app = self.app
        if isinstance(app, DupsterApp):
            app._theme_previewing = True
            app.theme = theme_name

    def _cancel_pending_preview(self) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
            self._preview_timer = None
        self._pending_theme = None

    def _preview_theme(self, theme_name: str) -> None:
        self._pending_theme = theme_name
        if self._preview_timer is not None:
            self._preview_timer.stop()
        self._preview_timer = self.set_timer(
            THEME_PREVIEW_DELAY,
            self._flush_preview,
            name="theme-preview",
        )

    def _apply_theme(self, theme_name: str) -> None:
        self._cancel_pending_preview()
        app = self.app
        if isinstance(app, DupsterApp):
            app._theme_previewing = False
            app.theme = theme_name
            app._save_theme_name(theme_name)
            app._refresh_theme_renderables(rebuild_lists=True)
            app.notify(f"Theme saved: {theme_name}")
        self.remove()

    def action_select(self) -> None:
        item = self.query_one("#theme-list", ListView).highlighted_child
        if isinstance(item, ThemeListItem):
            self._apply_theme(item.theme_name)

    def action_cancel(self) -> None:
        self._cancel_pending_preview()
        app = self.app
        if isinstance(app, DupsterApp):
            app._theme_previewing = False
            app.theme = self.original_theme
            app._save_theme_name(self.original_theme)
            app._refresh_theme_renderables(rebuild_lists=True)
        self.remove()

    def action_cursor_top(self) -> None:
        try:
            self.query_one("#theme-list", ListView).index = 0
        except Exception:
            pass

    def action_cursor_bottom(self) -> None:
        try:
            theme_list = self.query_one("#theme-list", ListView)
            theme_list.index = max(len(theme_list.children) - 1, 0)
        except Exception:
            pass

    def on_unmount(self) -> None:
        self._cancel_pending_preview()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:  # type: ignore[override]
        event.stop()
        item = event.item
        if isinstance(item, ThemeListItem):
            self._preview_theme(item.theme_name)

    def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        event.stop()
        if isinstance(event.item, ThemeListItem):
            self._apply_theme(event.item.theme_name)


class ConfirmDelete(Message):
    def __init__(self, confirmed: bool, keep_file: str, files: list[str]):
        super().__init__()
        self.confirmed = confirmed
        self.keep_file = keep_file
        self.files = files


class ConfirmBulkDelete(Message):
    def __init__(self, confirmed: bool, plan: list[dict]):
        super().__init__()
        self.confirmed = confirmed
        self.plan = plan


class ConfirmDeleteModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "confirm", "Delete"),
        Binding("q", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
        Binding("g", "cursor_top", "Jump to Top"),
        Binding("G", "cursor_bottom", "Jump to Bottom", key_display="G"),
    ]

    def __init__(self, files: list[str], initial_keep_index: int = 0):
        super().__init__()
        self.files = files
        self.keep_index = min(max(initial_keep_index, 0), max(len(files) - 1, 0))

    @property
    def keep_file(self) -> str:
        return self.files[self.keep_index]

    @property
    def delete_files(self) -> list[str]:
        return [path for index, path in enumerate(self.files) if index != self.keep_index]

    @property
    def delete_bytes(self) -> int:
        try:
            return sum(get_size(p) for p in self.delete_files)
        except Exception:
            return 0

    def _header_text(self) -> Text:
        warning_style = _rich_color(self.app.theme_variables.get("warning"), "#fbbf24")
        error_style = _rich_color(self.app.theme_variables.get("error"), "#ef4444")
        return Text.assemble(
            ("Delete Duplicates in Group", f"bold {warning_style}"),
            ("  /  ", "dim"),
            ("Choose the file to keep", "italic dim"),
            ("\n"),
            ("Keep this file: ", "italic"),
            (self.keep_file, ""),
            ("\n"),
            ("Will delete the other ", "italic"),
            (f"{len(self.delete_files)} file(s)", "bold"),
            (" in this group   Reclaim ", "dim"),
            (human_size(self.delete_bytes), "bold"),
            ("\n"),
            ("Move to the file you want to keep, then press y to delete the others.", "dim"),
            ("\n"),
            ("This action is permanent.", f"bold {error_style}"),
        )

    def _refresh_header(self) -> None:
        warning_style = _rich_color(self.app.theme_variables.get("warning"), "#fbbf24")
        try:
            self.query_one("#confirm-text", Static).update(
                Panel(self._header_text(), border_style=warning_style, expand=True)
            )
        except Exception:
            pass

    def _refresh_table_actions(self, previous_keep_index: int | None = None) -> None:
        dt = self.query_one("#confirm-table", DataTable)
        indexes = [self.keep_index]
        if previous_keep_index is not None:
            indexes.append(previous_keep_index)
        for index in indexes:
            if index < 0 or index >= len(self.files):
                continue
            label = "Keep this" if index == self.keep_index else "Delete duplicate"
            try:
                dt.update_cell_at(Coordinate(index, 0), label)
            except Exception:
                pass

    def compose(self) -> ComposeResult:  # type: ignore[override]
        warning_style = _rich_color(self.app.theme_variables.get("warning"), "#fbbf24")
        with Vertical(id="confirm-wrap"):
            with Vertical(id="confirm", classes="modal-card"):
                yield Static(
                    Panel(self._header_text(), border_style=warning_style, expand=True),
                    id="confirm-text",
                )
                with Vertical(id="confirm-body"):
                    table = DataTable(id="confirm-table", cursor_type="row")
                    table.add_columns("Action", "Size", "Path")
                    yield table
        yield Footer()

    def on_mount(self) -> None:
        dt = self.query_one("#confirm-table", DataTable)
        for index, p in enumerate(self.files):
            action = "Keep this" if index == self.keep_index else "Delete duplicate"
            dt.add_row(action, human_size(get_size(p)), p, key=str(index))
        dt.focus()
        try:
            dt.cursor_coordinate = (self.keep_index, 0)
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        try:
            self.query_one("#confirm-table", DataTable).action_cursor_up()
        except Exception:
            pass

    def action_cursor_down(self) -> None:
        try:
            self.query_one("#confirm-table", DataTable).action_cursor_down()
        except Exception:
            pass

    def action_cursor_top(self) -> None:
        try:
            self.query_one("#confirm-table", DataTable).move_cursor(row=0)
        except Exception:
            pass

    def action_cursor_bottom(self) -> None:
        try:
            table = self.query_one("#confirm-table", DataTable)
            table.move_cursor(row=max(table.row_count - 1, 0))
        except Exception:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:  # type: ignore[override]
        event.stop()
        if event.data_table.id != "confirm-table":
            return
        if event.cursor_row < 0 or event.cursor_row >= len(self.files):
            return
        previous_keep_index = self.keep_index
        if event.cursor_row == previous_keep_index:
            return
        self.keep_index = event.cursor_row
        self._refresh_table_actions(previous_keep_index)
        self._refresh_header()

    def action_confirm(self) -> None:
        self.app.post_message(ConfirmDelete(True, self.keep_file, self.delete_files))
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.app.post_message(ConfirmDelete(False, self.keep_file, self.delete_files))
        self.dismiss(False)


class BulkDeleteModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "confirm", "Delete"),
        Binding("q", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
        Binding("g", "cursor_top", "Jump to Top"),
        Binding("G", "cursor_bottom", "Jump to Bottom", key_display="G"),
    ]

    def __init__(self, plan: list[dict]):
        super().__init__()
        self.plan = plan
        self.total_bytes = total_reclaim_bytes(plan)

    def compose(self) -> ComposeResult:  # type: ignore[override]
        total_groups = len(self.plan)
        total_deletes = sum(len(entry["delete"]) for entry in self.plan)
        warning_style = _rich_color(self.app.theme_variables.get("warning"), "#fbbf24")
        error_style = _rich_color(self.app.theme_variables.get("error"), "#ef4444")
        header_text = Text.assemble(
            ("Delete All Duplicates", f"bold {warning_style}"),
            ("\n"),
            ("Groups: ", "italic"),
            (str(total_groups), "bold"),
            ("  •  Files to delete across all groups: ", "italic"),
            (str(total_deletes), "bold"),
            ("  •  Reclaim ≈ ", "italic"),
            (human_size(self.total_bytes), "bold"),
            ("\n"),
            ("Policy: keep one file per group", "dim"),
            (" (first alphabetical path).", "dim"),
            ("\n"),
            ("Use ↑/↓ to navigate. Select a group to view files.", "dim"),
            ("\n"),
            ("Press y to delete these duplicates.", "dim"),
            ("\n"),
            ("This action is permanent.", f"bold {error_style}"),
        )
        with Vertical(id="bulk-wrap"):
            with Vertical(id="bulk", classes="modal-card"):
                yield Static(
                    Panel(header_text, border_style=warning_style, expand=True), id="bulk-text"
                )
                with Vertical(id="bulk-body"):
                    summary = DataTable(id="bulk-summary", cursor_type="row")
                    summary.add_columns("Group #", "Hash (short)", "Kept path", "Delete count")
                    yield summary
                    files = DataTable(id="bulk-files", cursor_type="row")
                    files.add_columns("Action", "Size", "Path")
                    yield files
        yield Footer()

    def on_mount(self) -> None:
        sm = self.query_one("#bulk-summary", DataTable)
        for entry in self.plan:
            gno = entry["group"]
            keep = entry["keep"]
            dels = entry["delete"]
            h = entry.get("hash", "")
            short = (h[:12] + "…") if h else ""
            sm.add_row(str(gno), short, keep, str(len(dels)))
        sm.focus()
        try:
            sm.cursor_coordinate = (0, 0)
        except Exception:
            pass
        self._load_files_for_row(0)

    def _load_files_for_row(self, row_index: int) -> None:
        files_dt = self.query_one("#bulk-files", DataTable)
        files_dt.clear()
        if row_index < 0 or row_index >= len(self.plan):
            return
        entry = self.plan[row_index]
        keep = entry["keep"]
        dels = entry["delete"]
        files_dt.add_row("Keep one", human_size(get_size(keep)), keep)
        for p in dels:
            files_dt.add_row("Delete duplicate", human_size(get_size(p)), p)
        try:
            files_dt.cursor_coordinate = (0, 0)
        except Exception:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:  # type: ignore[override]
        if event.data_table.id == "bulk-summary":
            try:
                idx = int(event.row_key)
            except Exception:
                try:
                    idx = event.data_table.cursor_row or 0
                except Exception:
                    idx = 0
            self._load_files_for_row(idx)

    def action_cursor_up(self) -> None:
        try:
            self.query_one("#bulk-summary", DataTable).action_cursor_up()
        except Exception:
            pass

    def action_cursor_down(self) -> None:
        try:
            self.query_one("#bulk-summary", DataTable).action_cursor_down()
        except Exception:
            pass

    def action_cursor_top(self) -> None:
        try:
            self.query_one("#bulk-summary", DataTable).move_cursor(row=0)
        except Exception:
            pass

    def action_cursor_bottom(self) -> None:
        try:
            table = self.query_one("#bulk-summary", DataTable)
            table.move_cursor(row=max(table.row_count - 1, 0))
        except Exception:
            pass

    def action_confirm(self) -> None:
        self.app.post_message(ConfirmBulkDelete(True, self.plan))
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.app.post_message(ConfirmBulkDelete(False, self.plan))
        self.dismiss(False)


class DupsterApp(App):
    TITLE = f"{BRAND_NAME} - Duplicate File Finder"

    CSS = r"""
    Screen {
        layers: default overlay;
        background: $background;
        color: $text;
    }

    #dashboard {
        height: 1;
        margin: 0;
        padding: 0 1;
        background: $panel;
        color: $text;
    }

    Horizontal#root {
        height: 1fr;
        padding: 0 1 1 1;
    }

    Vertical.pane {
        border: round $border-blurred;
        background: $surface;
    }

    Vertical.pane.active {
        border: round $primary;
        background: $panel;
    }

    Vertical.pane.inactive {
        border: round $border-blurred;
        background: $background;
    }

    #left {
        width: 44%;
        margin-right: 1;
    }

    #right {
        width: 1fr;
    }

    #grouplabel, #filelabel {
        height: 3;
        padding: 1 2;
        background: $panel;
        color: $text;
        text-style: bold;
    }

    #summary {
        min-height: 7;
        padding: 1 2;
        background: $surface;
        color: $text;
        border-bottom: solid $border-blurred;
    }

    #pathinfo {
        min-height: 4;
        padding: 1 2;
        background: $surface;
        border-top: solid $border-blurred;
        color: $text-muted;
    }

    ProgressBar {
        height: 1;
        margin: 0 2;
    }

    ListView {
        height: 1fr;
        background: $surface;
    }

    ListView:focus {
        border: round $accent;
        background: $panel;
    }

    ListView > ListItem {
        padding: 0 1;
    }

    ListView > ListItem.-hovered {
        background: $primary 10%;
        color: $foreground;
    }

    ListView > ListItem.-highlight {
        background: $primary 18%;
        color: $foreground;
        text-style: bold;
    }

    ListView:focus > ListItem.-highlight {
        background: $primary 28%;
        color: $foreground;
        text-style: bold;
    }

    .group-card, .file-card {
        padding: 1 0;
        margin: 0;
    }

    .compact-card {
        padding: 0;
    }

    #confirm-wrap, #bulk-wrap {
        height: 1fr;
        background: $background;
    }

    .modal-card {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
        border: round $warning;
        background: $surface;
    }

    #confirm-text, #bulk-text {
        margin-bottom: 1;
    }

    #confirm-table {
        height: 1fr;
        min-height: 12;
    }

    #bulk-summary  {
        height: 1fr;
        min-height: 10;
    }

    #bulk-files {
        height: 1fr;
        min-height: 10;
        margin-top: 1;
    }

    DataTable {
        border: round $border-blurred;
        background: $surface;
        color: $text;
        height: auto;
    }

    DataTable:focus {
        border: round $primary;
    }

    DataTable > .datatable--hover {
        background: $primary 10%;
        color: $foreground;
    }

    DataTable > .datatable--cursor,
    DataTable > .datatable--fixed-cursor,
    DataTable > .datatable--header-cursor {
        background: $primary 18%;
        color: $foreground;
        text-style: bold;
    }

    DataTable:focus > .datatable--cursor,
    DataTable:focus > .datatable--fixed-cursor,
    DataTable:focus > .datatable--header-cursor {
        background: $primary 28%;
        color: $foreground;
        text-style: bold;
    }

    DataTable > .datatable--header-hover {
        background: $primary 12%;
        color: $foreground;
    }

    OptionList > .option-list--option,
    CommandList > .option-list--option {
        color: $foreground;
    }

    OptionList > .option-list--option-hover,
    CommandList > .option-list--option-hover {
        background: $primary 10%;
        color: $foreground;
    }

    OptionList > .option-list--option-highlighted,
    CommandList > .option-list--option-highlighted,
    OptionList:focus > .option-list--option-highlighted,
    CommandList:focus > .option-list--option-highlighted {
        background: $primary 24%;
        color: $foreground;
        text-style: bold;
    }

    CommandPalette {
        background: $background 80%;
        color: $foreground;
    }

    CommandPalette > Vertical {
        background: $surface;
        border: round $border-blurred;
    }

    CommandPalette #--input {
        border: hkey $primary 50%;
        background: $panel;
    }

    CommandPalette > .command-palette--highlight {
        color: $primary;
        text-style: bold underline;
    }

    CommandPalette > .command-palette--help-text {
        color: $text-muted;
    }

    #confirm-body {
        height: 1fr;
    }

    #bulk-body {
        height: 1fr;
    }

    #bottombar {
        dock: bottom;
        height: 2;
        width: 100%;
        background: $panel;
        border-top: solid $border-blurred;
    }

    #keybar {
        width: 1fr;
        min-width: 0;
        content-align: left middle;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }

    #versionbar {
        width: auto;
        min-width: 0;
        content-align: right middle;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }

    #githubbar {
        width: auto;
        min-width: 0;
        content-align: center middle;
        padding: 0 1;
        margin: 0;
        background: $primary 18%;
        color: $foreground;
        text-style: bold;
    }

    .footer-collapsed {
        display: none;
    }

    #githubbar:hover {
        background: $primary 32%;
        color: $foreground;
    }

    #theme-picker {
        layer: overlay;
        dock: right;
        width: 46;
        height: 100%;
        border: round $primary;
        background: $surface;
    }

    #theme-title {
        height: 3;
        padding: 1 2;
        background: $panel;
        color: $foreground;
        text-style: bold;
    }

    #theme-list {
        height: 1fr;
        background: $surface;
    }

    .theme-card {
        padding: 1 1;
    }

    #shortcut-help {
        layer: overlay;
        dock: right;
        width: 42;
        height: 100%;
        border: round $primary;
        background: $surface;
    }

    #shortcut-title {
        height: 3;
        padding: 1 2;
        background: $panel;
        color: $foreground;
        text-style: bold;
    }

    #shortcut-body {
        height: 1fr;
        background: $surface;
    }

    .shortcut-section {
        padding: 1 2;
        color: $text-primary;
    }

    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Search", key_display="ctrl+p"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Force Quit"),
        Binding("s", "scan", "Scan"),
        Binding("o", "open_selected", "Open"),
        Binding("c", "copy_selected_path", "Copy Path"),
        Binding("i", "delete_duplicates_in_group", "Delete Duplicates in Group"),
        Binding("d", "bulk_delete_preview", "Delete All Duplicates"),
        Binding("g", "jump_top", "Jump to Top"),
        Binding("G", "jump_bottom", "Jump to Bottom", key_display="G"),
        Binding("v", "toggle_compact_view", "Compact View"),
        Binding("?", "toggle_shortcuts", "Help"),
        Binding("h", "focus_left", "Left Pane"),
        Binding("l", "focus_right", "Right Pane"),
        Binding("left", "focus_left", "Left Pane"),
        Binding("right", "focus_right", "Right Pane"),
        Binding("t", "change_theme", "Theme"),
    ]

    def __init__(
        self,
        folder: str | None = None,
        workers: int | None = None,
        min_size: int = 0,
        verify: bool = False,
        follow_symlinks: bool = False,
    ) -> None:
        super().__init__()
        self.folder = folder or os.path.expanduser("~")
        self._theme_config_path = _theme_config_path()
        self.theme = self._load_theme_name()
        self.stylesheet.set_variables(self.get_css_variables())
        self.scan_workers = workers
        self.scan_min_size = min_size
        self.scan_verify = verify
        self.scan_follow_symlinks = follow_symlinks
        self.last_stats = None
        self.groups: list[DuplicateGroup] = []
        self.current_group_idx: int | None = None
        self.current_file_idx: int | None = None
        self._theme_previewing = False
        self._compact_groups = True
        self._shortcut_help_open = False

    def _load_theme_name(self) -> str:
        try:
            data = json.loads(self._theme_config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

        saved = data.get("theme")
        if isinstance(saved, str) and saved in self.available_themes:
            return saved
        if DEFAULT_THEME in self.available_themes:
            return DEFAULT_THEME
        return "textual-dark"

    def _save_theme_name(self, theme_name: str | None = None) -> None:
        if self.is_headless and THEME_CONFIG_ENV not in os.environ:
            return
        theme_name = theme_name or self.theme
        if theme_name not in self.available_themes:
            return
        try:
            self._theme_config_path.parent.mkdir(parents=True, exist_ok=True)
            self._theme_config_path.write_text(
                json.dumps({"theme": theme_name}, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def _theme_color(self, name: str, fallback: str) -> str:
        return _rich_color(self.theme_variables.get(name), fallback)

    def _style(self, color_name: str, fallback: str, modifier: str = "") -> str:
        color = self._theme_color(color_name, fallback)
        return f"{modifier} {color}".strip()

    def _display_path(self, path: str, max_chars: int = 90) -> str:
        pretty = os.path.expanduser(path)
        home = os.path.expanduser("~")
        if pretty == home:
            pretty = "~"
        elif pretty.startswith(home + os.sep):
            pretty = "~" + pretty[len(home) :]
        if len(pretty) <= max_chars:
            return pretty
        return "..." + pretty[-(max_chars - 3) :]

    def _scan_root_path(self) -> str:
        try:
            return str(Path(self.folder).expanduser().resolve())
        except (OSError, RuntimeError):
            return os.path.abspath(os.path.expanduser(self.folder))

    def _dashboard_text(self, scanning: bool = False) -> Text:
        st = self.last_stats
        folder = self._scan_root_path()
        if scanning:
            return Text.assemble(
                ("Scanning", self._style("primary", "#38bdf8", "bold")),
                ("  root ", "dim"),
                (folder, self._style("text-primary", "#dbeafe")),
            )
        if st is None:
            return Text.assemble(
                ("Ready", self._style("success", "#2dd4bf", "bold")),
                ("  root ", "dim"),
                (folder, self._style("text-primary", "#dbeafe")),
            )

        duplicate_files = sum(len(g.files) for g in self.groups)
        savings = sum(g.potential_savings() for g in self.groups)
        status = "Duplicates found" if self.groups else "All clear"
        status_style = (
            self._style("warning", "#fbbf24", "bold")
            if self.groups
            else self._style("success", "#34d399", "bold")
        )
        return Text.assemble(
            (status, status_style),
            (" | groups ", "dim"),
            (f"{len(self.groups):,}", self._style("foreground", "#f8fafc", "bold")),
            (" | files ", "dim"),
            (f"{duplicate_files:,}", self._style("foreground", "#f8fafc", "bold")),
            (" | reclaim ", "dim"),
            (human_size(savings), self._style("success", "#34d399", "bold")),
            (" | scanned ", "dim"),
            (f"{st.files_seen:,}", self._style("text-primary", "#dbeafe")),
            (" in ", "dim"),
            (f"{st.elapsed:.2f}s", self._style("text-primary", "#dbeafe")),
            (" | read ", "dim"),
            (human_size(st.bytes_read), self._style("text-primary", "#dbeafe")),
            (" | root ", "dim"),
            (folder, self._style("text-primary", "#dbeafe")),
        )

    def _update_dashboard(self, scanning: bool = False) -> None:
        try:
            self.query_one("#dashboard", Static).update(self._dashboard_text(scanning))
        except Exception:
            pass

    def _footer_width(self, width: int | None = None) -> int:
        if width is not None:
            return max(width, 0)
        try:
            current_width = int(self.size.width)
        except Exception:
            return 200
        return current_width if current_width > 0 else 200

    def _footer_mode(self, width: int | None = None) -> str:
        current_width = self._footer_width(width)
        if current_width < 80:
            return "tiny"
        if current_width < 112:
            return "compact"
        if current_width < 150:
            return "medium"
        if current_width < 200:
            return "roomy"
        return "full"

    def _shortcut_text(self, segments: list[tuple[str, str]]) -> Text:
        key_style = self._style("primary", "#38bdf8", "bold")
        parts: list[tuple[str, str]] = []
        for index, (key, label) in enumerate(segments):
            if index:
                parts.append(("  ", ""))
            parts.append((key, key_style))
            if label:
                parts.append((f" {label}", "dim"))
        return Text.assemble(*parts)

    def _github_bar_text(self, width: int | None = None) -> Text:
        mode = self._footer_mode(width)
        if mode == "tiny":
            return Text("")
        label = "GH" if mode == "compact" else "GitHub"
        if mode in {"roomy", "full"}:
            label = GITHUB_REPO
        link_style = Style(
            color=self._theme_color("foreground", "#f8fafc"),
            bold=True,
            link=GITHUB_URL,
        )
        return Text(label, link_style)

    def _version_bar_text(self, width: int | None = None) -> Text:
        mode = self._footer_mode(width)
        if mode in {"tiny", "compact"}:
            return Text("")
        return Text.assemble(
            ("v", "dim"),
            (__version__, self._style("foreground", "#f8fafc", "bold")),
        )

    def _group_label_text(self) -> Text:
        mode = "Compact" if self._compact_groups else "Detailed"
        return Text.assemble(
            ("Duplicate Groups", self._style("foreground", "#f8fafc", "bold")),
            ("  ", ""),
            (mode, "dim"),
        )

    def _key_bar_text(self, width: int | None = None) -> Text:
        mode = self._footer_mode(width)
        help_label = "Hide Help" if self._shortcut_help_open else "Help"
        if mode == "tiny":
            segments = [
                ("?", help_label),
                ("q", "Quit"),
            ]
        elif mode == "compact":
            segments = [
                ("?", help_label),
                ("ctrl+p", "Search"),
                ("q", "Quit"),
            ]
        elif mode == "medium":
            segments = [
                ("?", help_label),
                ("c", "Path"),
                ("ctrl+p", "Search"),
                ("i/d", "Delete"),
                ("q", "Quit"),
            ]
        else:
            segments = [
                ("?", help_label),
                ("c", "Copy Path"),
                ("ctrl+p", "Search"),
                ("i/d", "Delete"),
                ("g/G", "Jump"),
                ("h/l/arrows", "Pane"),
                ("q", "Quit"),
            ]
        return self._shortcut_text(segments)

    def _update_footer_widget(self, selector: str, text: Text) -> None:
        try:
            widget = self.query_one(selector, Static)
        except Exception:
            return
        widget.update(text)
        widget.set_class(not bool(text.plain), "footer-collapsed")

    def _refresh_footer(self, width: int | None = None) -> None:
        current_width = self._footer_width(width)
        self._update_footer_widget("#keybar", self._key_bar_text(current_width))
        self._update_footer_widget("#versionbar", self._version_bar_text(current_width))
        self._update_footer_widget("#githubbar", self._github_bar_text(current_width))

    def _group_panel(self, g: DuplicateGroup):
        files_count = len(g.files)
        reclaim = human_size(g.potential_savings())
        hash_short = f"{g.hash[:10]}...{g.hash[-6:]}" if len(g.hash) > 18 else g.hash
        if self._compact_groups:
            return Text.assemble(
                (f"{g.index:02d}", self._style("primary", "#38bdf8", "bold")),
                ("  ", ""),
                (f"{files_count} files", self._style("foreground", "#f8fafc", "bold")),
                ("  ", ""),
                (reclaim, self._style("success", "#34d399")),
                ("  ", ""),
                ("sha ", "dim"),
                (hash_short, self._style("text-primary", "#bfdbfe")),
            )
        return Text.assemble(
            (f"Group {g.index:02d}", self._style("foreground", "#f8fafc", "bold")),
            (" | files ", "dim"),
            (str(files_count), self._style("text-primary", "#bfdbfe", "bold")),
            (" | reclaim ", "dim"),
            (reclaim, self._style("success", "#34d399", "bold")),
            ("\n"),
            ("fingerprint ", "dim"),
            (hash_short, self._style("primary", "#93c5fd")),
        )

    def _file_panel(self, index: int, path: str) -> Text:
        base = os.path.basename(path)
        size = human_size(get_size(path))
        if self._compact_groups:
            return Text.assemble(
                (f"{index + 1:02d}", self._style("primary", "#38bdf8", "bold")),
                ("  ", ""),
                (base, self._style("foreground", "#f8fafc", "bold")),
                ("  ", ""),
                (size, self._style("success", "#34d399")),
                ("  ", ""),
                (self._display_path(path, 72), "dim"),
            )
        return Text.assemble(
            (f"{index + 1:02d}", self._style("primary", "#38bdf8", "bold")),
            ("  ", ""),
            (base, self._style("foreground", "#f8fafc", "bold")),
            ("     ", ""),
            (size, self._style("success", "#34d399")),
            ("\n"),
            (self._display_path(path), "dim"),
        )

    def on_mount(self) -> None:
        self.watch(self, "theme", self._on_theme_changed, init=False)
        self._refresh_footer()
        asyncio.create_task(self.action_scan())

    def on_resize(self, event: Resize) -> None:
        self._refresh_footer(event.size.width)

    def on_unmount(self) -> None:
        if self._theme_previewing:
            picker_query = self.query(ThemePicker)
            if picker_query.nodes:
                self._save_theme_name(picker_query.nodes[0].original_theme)
            return
        self._save_theme_name()

    def _on_theme_changed(self, old_theme: str, new_theme: str) -> None:
        self.stylesheet.set_variables(self.get_css_variables())
        if not self._theme_previewing:
            self._save_theme_name(new_theme)
        self._refresh_theme_renderables(rebuild_lists=not self._theme_previewing)

    def action_change_theme(self) -> None:
        existing_query = self.query(ThemePicker)
        existing = existing_query.nodes[0] if existing_query.nodes else None
        if existing is not None:
            try:
                existing.query_one("#theme-list", ListView).focus()
            except Exception:
                pass
            return
        theme_names = sorted(name for name in self.available_themes if name != "textual-ansi")
        self.screen.mount(ThemePicker(self.theme, theme_names))

    def _refresh_theme_renderables(self, *, rebuild_lists: bool = True) -> None:
        self._update_dashboard()
        self._refresh_footer()
        try:
            self.query_one("#grouplabel", Static).update(self._group_label_text())
        except Exception:
            pass
        if self.last_stats is not None:
            try:
                self._update_summary()
            except Exception:
                pass
        if not rebuild_lists:
            return
        if self.groups:
            group_idx = self.current_group_idx
            file_idx = self.current_file_idx
            try:
                self._refresh_groups_list()
            except Exception:
                return
            try:
                if group_idx is not None:
                    self.query_one("#groups", ListView).index = group_idx
            except Exception:
                pass
            try:
                self._refresh_files_list()
            except Exception:
                return
            try:
                if file_idx is not None:
                    self.query_one("#files", ListView).index = file_idx
            except Exception:
                pass

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static(self._dashboard_text(), id="dashboard")
        with Horizontal(id="root"):
            with Vertical(id="left", classes="pane active"):
                yield Static(self._group_label_text(), id="grouplabel")
                yield ListView(id="groups")
                yield Static(
                    f"Root: [b]{escape(self._scan_root_path())}[/b]\nReady to scan.",
                    id="pathinfo",
                )
            with Vertical(id="right", classes="pane inactive"):
                yield Static("Select a group to inspect duplicate files.", id="summary")
                yield ProgressBar(total=100, id="progress")
                yield Static("Files in Group", id="filelabel")
                yield ListView(id="files")
        with Horizontal(id="bottombar"):
            yield Static(self._key_bar_text(), id="keybar")
            yield Static(self._version_bar_text(), id="versionbar")
            yield GithubButton(self._github_bar_text(), id="githubbar")

    def get_system_commands(self, screen):  # type: ignore[override]
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Copy Full Path",
            "Copy the selected duplicate file path",
            self.action_copy_selected_path,
        )
        yield SystemCommand(
            "Delete Duplicates in Group",
            "Choose one file to keep, then preview deleting the other files in this group",
            self.action_delete_duplicates_in_group,
        )
        yield SystemCommand(
            "Delete Duplicates in All Groups",
            "Preview deleting duplicate files across all groups while keeping one file per group",
            self.action_bulk_delete_preview,
        )
        yield SystemCommand(
            "Toggle Compact View",
            "Switch duplicate groups and files between detailed and compact rows",
            self.action_toggle_compact_view,
        )
        yield SystemCommand(
            "Toggle Help Panel",
            "Show or hide the help and keys panel",
            self.action_toggle_shortcuts,
        )
        yield SystemCommand(
            "Jump to Top",
            "Move to the first row in the active list",
            self.action_jump_top,
        )
        yield SystemCommand(
            "Jump to Bottom",
            "Move to the last row in the active list",
            self.action_jump_bottom,
        )
        yield SystemCommand(
            "Star on GitHub",
            "Open the repository and copy its URL",
            self.action_star_on_github,
        )

    def _scan_line(self) -> str:
        st = self.last_stats
        if st is None:
            return ""
        avoided = st.files_seen - st.fully_hashed
        devices = ", ".join(sorted({d["type"] for d in st.devices.values()})) or "unknown"
        return (
            f"\n[dim]Scanned {st.files_seen:,} files in {st.elapsed:.2f}s  •  "
            f"read {human_size(st.bytes_read)}  •  "
            f"{avoided:,} skipped without a full read  •  {devices}[/dim]"
        )

    def _update_summary(self) -> None:
        summary_widget = self.query_one("#summary", Static)
        self._update_dashboard()
        if not self.groups:
            summary_widget.update(
                Text.assemble(
                    ("All clear.", self._style("success", "#34d399", "bold")),
                    ("\nNo duplicate groups were found."),
                    (self._scan_line(), "dim"),
                )
            )
            return
        total_groups = len(self.groups)
        files_involved = sum(len(g.files) for g in self.groups)
        savings = sum(g.potential_savings() for g in self.groups)
        summary_widget.update(
            Text.assemble(
                (
                    f"{total_groups:,} duplicate groups",
                    self._style("warning", "#fbbf24", "bold"),
                ),
                (" | files ", "dim"),
                (f"{files_involved:,}", self._style("foreground", "#f8fafc", "bold")),
                (" | reclaim ", "dim"),
                (human_size(savings), self._style("success", "#34d399", "bold")),
                (self._scan_line(), "dim"),
            )
        )

    async def action_scan(self) -> None:
        progress = self.query_one("#progress", ProgressBar)
        progress.update(total=100, progress=0)
        self.query_one("#summary", Static).update(
            Text.assemble(
                ("Scanning...", self._style("primary", "#38bdf8", "bold")),
                ("\n"),
                (self._scan_root_path(), "dim"),
            )
        )
        self._update_dashboard(scanning=True)

        progress_driver = _SmoothProgress(progress)

        def _progress(i: int, t: int) -> None:
            try:
                progress_driver(i, t)
            except Exception:
                pass

        hm, stats, sizes = await find_duplicates_detailed_async(
            self.folder,
            _progress,
            workers=self.scan_workers,
            min_size=self.scan_min_size,
            verify=self.scan_verify,
            follow_symlinks=self.scan_follow_symlinks,
        )
        self.last_stats = stats
        self.groups = groups_from_hash_map(hm, sizes)
        self._refresh_groups_list()
        self._update_summary()
        if self.groups:
            self.current_group_idx = 0
            try:
                self.query_one("#groups", ListView).index = 0
            except Exception:
                pass
            self._refresh_files_list()
        else:
            self.current_group_idx = None
            self.current_file_idx = None
            self.query_one("#files", ListView).clear()
            self.query_one("#filelabel", Static).update("Files in Group")
            progress.progress = 100

    def _refresh_groups_list(self) -> None:
        lv = self.query_one("#groups", ListView)
        lv.clear()
        self.query_one("#grouplabel", Static).update(self._group_label_text())
        card_classes = "group-card compact-card" if self._compact_groups else "group-card"
        if not self.groups:
            lv.append(ListItem(Static("No duplicate groups.", classes=card_classes)))
            return
        for g in self.groups:
            lv.append(ListItem(Static(self._group_panel(g), classes=card_classes)))

    def _refresh_files_list(self) -> None:
        files_lv = self.query_one("#files", ListView)
        files_lv.clear()
        g = self._selected_group()
        if not g:
            return
        try:
            self.query_one("#filelabel", Static).update(
                f"Files in Group  [dim]SHA256 {escape(g.hash[:16])}...[/dim]"
            )
        except Exception:
            pass
        card_classes = "file-card compact-card" if self._compact_groups else "file-card"
        for i, p in enumerate(g.files):
            files_lv.append(
                ListItem(
                    Static(
                        self._file_panel(i, p),
                        classes=card_classes,
                    )
                )
            )
        self._update_summary()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:  # type: ignore[override]
        if event.list_view.id == "groups":
            try:
                self.current_group_idx = event.list_view.index
            except Exception:
                self.current_group_idx = 0
            self.current_file_idx = None
            self._refresh_files_list()
        elif event.list_view.id == "files":
            try:
                self.current_file_idx = event.list_view.index
            except Exception:
                self.current_file_idx = 0

    def action_open_selected(self) -> None:
        path = self._selected_file()
        if path:
            open_file(path)

    def action_copy_selected_path(self) -> None:
        path = self._selected_file()
        if not path:
            self.notify("Select a file to copy its path.", severity="warning")
            return

        full_path = str(Path(path).expanduser().resolve())
        self.copy_to_clipboard(full_path)
        copied_to_system = self.is_headless or _copy_to_system_clipboard(full_path)
        if copied_to_system:
            self.notify(f"Copied full path: {self._display_path(full_path, 72)}")
        else:
            self.notify(
                "Copied path inside Dupster. System clipboard was not available.",
                severity="warning",
            )

    def action_star_on_github(self) -> None:
        self.copy_to_clipboard(GITHUB_URL)
        copied_to_system = self.is_headless or _copy_to_system_clipboard(GITHUB_URL)
        self.open_url(GITHUB_URL)
        if copied_to_system:
            self.notify("Opening GitHub. Repo URL copied to clipboard.")
        else:
            self.notify(
                "Opening GitHub. Repo URL copied inside Dupster only.",
                severity="warning",
            )

    def action_delete_duplicates_in_group(self) -> None:
        g = self._selected_group()
        if not g:
            self.notify("Select a duplicate group first.", severity="warning")
            return
        if len(g.files) < 2:
            self.notify("No other duplicates to delete in this group.")
            return
        keep_index = self.current_file_idx if self.current_file_idx is not None else 0
        self.push_screen(ConfirmDeleteModal(g.files, keep_index))

    def on_confirm_delete(self, event: ConfirmDelete) -> None:
        g = self._selected_group()
        if not g:
            return
        if not event.confirmed:
            self.notify("Deletion cancelled.")
            return
        deleted = 0
        errors: list[str] = []
        for f in event.files:
            try:
                os.remove(f)
                deleted += 1
            except Exception as e:
                errors.append(f"{f}: {e}")
        if errors:
            self.notify("Some files could not be deleted.", severity="error")
        self.notify(f"Deleted {deleted} duplicate file(s) from the selected group.")
        asyncio.create_task(self.action_scan())

    def _build_bulk_plan(self) -> list[dict]:
        return bulk_delete_plan(self.groups)

    def action_bulk_delete_preview(self) -> None:
        plan = self._build_bulk_plan()
        if not plan:
            self.notify("No duplicate files to delete.")
            return
        self.push_screen(BulkDeleteModal(plan))

    def action_toggle_compact_view(self) -> None:
        self._compact_groups = not self._compact_groups
        group_idx = self.current_group_idx
        file_idx = self.current_file_idx
        try:
            self._refresh_groups_list()
            if group_idx is not None:
                self.query_one("#groups", ListView).index = group_idx
            self._refresh_files_list()
            if file_idx is not None:
                self.query_one("#files", ListView).index = file_idx
            self._refresh_footer()
        except Exception:
            pass
        mode = "compact" if self._compact_groups else "detailed"
        self.notify(f"List view: {mode}")

    def action_toggle_shortcuts(self) -> None:
        existing_query = self.query(ShortcutHelpPanel)
        existing = existing_query.nodes[0] if existing_query.nodes else None
        if existing is not None:
            self._shortcut_help_open = False
            existing.remove()
            self._refresh_footer()
            self.notify("Help hidden.")
            return
        self._shortcut_help_open = True
        self.screen.mount(ShortcutHelpPanel())
        self._refresh_footer()
        self.notify("Help shown.")

    def _active_jump_widget(self) -> ListView | DataTable | None:
        focused = self.focused
        if focused is not None:
            for widget in (focused, *focused.ancestors):
                if isinstance(widget, (ListView, DataTable)):
                    return widget
        try:
            return self.query_one("#groups", ListView)
        except Exception:
            return None

    def _jump_active_widget(self, *, bottom: bool) -> None:
        widget = self._active_jump_widget()
        if isinstance(widget, ListView):
            if widget.children:
                widget.index = len(widget.children) - 1 if bottom else 0
            return
        if isinstance(widget, DataTable):
            if widget.row_count:
                widget.move_cursor(row=widget.row_count - 1 if bottom else 0)

    def action_jump_top(self) -> None:
        self._jump_active_widget(bottom=False)

    def action_jump_bottom(self) -> None:
        self._jump_active_widget(bottom=True)

    def on_confirm_bulk_delete(self, event: ConfirmBulkDelete) -> None:
        if not event.confirmed:
            self.notify("Deletion cancelled.")
            return
        deleted = 0
        errors: list[str] = []
        for entry in event.plan:
            for f in entry["delete"]:
                try:
                    os.remove(f)
                    deleted += 1
                except Exception as e:
                    errors.append(f"{f}: {e}")
        if errors:
            self.notify("Some files could not be deleted.", severity="error")
        self.notify(f"Deleted {deleted} duplicate file(s) across {len(event.plan)} group(s).")
        asyncio.create_task(self.action_scan())

    def action_focus_left(self) -> None:
        try:
            groups_lv = self.query_one("#groups", ListView)
            left = self.query_one("#left")
            right = self.query_one("#right")
            if self.groups and (
                self.current_group_idx is None
                or self.current_group_idx < 0
                or self.current_group_idx >= len(self.groups)
            ):
                self.current_group_idx = 0
                try:
                    groups_lv.index = 0
                except Exception:
                    pass
                self._refresh_files_list()
            groups_lv.focus()
            left.add_class("active")
            left.remove_class("inactive")
            right.add_class("inactive")
            right.remove_class("active")
        except Exception:
            pass

    def action_focus_right(self) -> None:
        try:
            files_lv = self.query_one("#files", ListView)
            left = self.query_one("#left")
            right = self.query_one("#right")
            if not self._selected_group() and self.groups:
                self.current_group_idx = 0
                self._refresh_files_list()
            g = self._selected_group()
            if (
                g
                and g.files
                and (
                    self.current_file_idx is None
                    or self.current_file_idx < 0
                    or self.current_file_idx >= len(g.files)
                )
            ):
                self.current_file_idx = 0
                try:
                    files_lv.index = 0
                except Exception:
                    pass
            files_lv.focus()
            right.add_class("active")
            right.remove_class("inactive")
            left.add_class("inactive")
            left.remove_class("active")
        except Exception:
            pass

    def _selected_group(self) -> DuplicateGroup | None:
        gi = self.current_group_idx
        if gi is None:
            return None
        if gi < 0 or gi >= len(self.groups):
            return None
        return self.groups[gi]

    def _selected_file(self) -> str | None:
        g = self._selected_group()
        if not g:
            return None
        fi = self.current_file_idx
        if fi is None:
            return None
        if fi < 0 or fi >= len(g.files):
            return None
        return g.files[fi]
