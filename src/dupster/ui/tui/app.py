from __future__ import annotations

import asyncio
import os

from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Static,
)

from dupster.application.planner import (
    bulk_delete_plan,
    groups_from_hash_map,
    total_reclaim_bytes,
)
from dupster.application.scanner import find_duplicates_by_hash_async
from dupster.domain.models import DuplicateGroup
from dupster.infrastructure.filesystem import get_size, open_file
from dupster.utils.formatting import human_size


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
        Binding("y", "confirm", "Confirm"),
        Binding("enter", "confirm", "Confirm"),
        Binding("q", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
    ]

    def __init__(self, keep_file: str, files: list[str]):
        super().__init__()
        self.keep_file = keep_file
        self.files = files
        try:
            self.delete_bytes = sum(get_size(p) for p in self.files)
        except Exception:
            self.delete_bytes = 0

    def compose(self) -> ComposeResult:  # type: ignore[override]
        header_text = Text.assemble(
            ("⚠ Confirm deletion", "bold bright_yellow"),
            (" — ", "dim"),
            ("Keep one, remove the rest", "italic dim"),
            ("\n"),
            ("Keep: ", "italic"),
            (self.keep_file, ""),
            ("\n"),
            ("Will delete: ", "italic"),
            (f"{len(self.files)} file(s)", "bold"),
            ("   •   Reclaim ≈ ", "dim"),
            (human_size(self.delete_bytes), "bold"),
            ("\n"),
            ("Use ↑/↓ to navigate.", "dim"),
            ("\n"),
            ("This action is permanent.", "bold red"),
        )
        with Vertical(id="confirm-wrap"):
            with Vertical(id="confirm", classes="modal-card"):
                yield Static(
                    Panel(header_text, border_style="magenta", expand=True), id="confirm-text"
                )
                with Vertical(id="confirm-body"):
                    table = DataTable(id="confirm-table", cursor_type="row")
                    table.add_columns("Action", "Size", "Path")
                    yield table
        yield Footer()

    def on_mount(self) -> None:
        dt = self.query_one("#confirm-table", DataTable)
        dt.add_row("Keep", human_size(get_size(self.keep_file)), self.keep_file)
        for p in self.files:
            dt.add_row("Delete", human_size(get_size(p)), p)
        dt.focus()
        try:
            dt.cursor_coordinate = (0, 0)
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

    def action_confirm(self) -> None:
        self.app.post_message(ConfirmDelete(True, self.keep_file, self.files))
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.app.post_message(ConfirmDelete(False, self.keep_file, self.files))
        self.dismiss(False)


class BulkDeleteModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "confirm", "Confirm"),
        Binding("enter", "confirm", "Confirm"),
        Binding("q", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
        Binding("up", "cursor_up", "Up"),
        Binding("down", "cursor_down", "Down"),
    ]

    def __init__(self, plan: list[dict]):
        super().__init__()
        self.plan = plan
        self.total_bytes = total_reclaim_bytes(plan)

    def compose(self) -> ComposeResult:  # type: ignore[override]
        total_groups = len(self.plan)
        total_deletes = sum(len(entry["delete"]) for entry in self.plan)
        header_text = Text.assemble(
            ("△ Delete ALL duplicates (preview)", "bold bright_yellow"),
            ("\n"),
            ("Groups: ", "italic"),
            (str(total_groups), "bold"),
            ("  •  Files to delete: ", "italic"),
            (str(total_deletes), "bold"),
            ("  •  Reclaim ≈ ", "italic"),
            (human_size(self.total_bytes), "bold"),
            ("\n"),
            ("Policy: keep the ", "dim"),
            ("first file per group", "italic"),
            (" (alphabetical by name).", "dim"),
            ("\n"),
            ("Use ↑/↓ to navigate. Select a group to view files.", "dim"),
            ("\n"),
            ("This action is permanent.", "bold red"),
        )
        with Vertical(id="bulk-wrap"):
            with Vertical(id="bulk", classes="modal-card"):
                yield Static(
                    Panel(header_text, border_style="magenta", expand=True), id="bulk-text"
                )
                with Vertical(id="bulk-body"):
                    summary = DataTable(id="bulk-summary", cursor_type="row")
                    summary.add_columns("Group #", "Hash (short)", "Keep (path)", "Delete count")
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
        files_dt.add_row("Keep", human_size(get_size(keep)), keep)
        for p in dels:
            files_dt.add_row("Delete", human_size(get_size(p)), p)
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

    def action_confirm(self) -> None:
        self.app.post_message(ConfirmBulkDelete(True, self.plan))
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.app.post_message(ConfirmBulkDelete(False, self.plan))
        self.dismiss(False)


class DupsterApp(App):
    TITLE = "Dupster 🧹 — Duplicate File Finder"

    CSS = r"""
    Screen { background: #0f1117; color: #e5e7eb; }
    Horizontal#root { height: 1fr; }
    Vertical.pane { border: round #2b2b2f; background: #0b0e14; }
    Vertical.pane.active { border: round $accent; background: #12151d; }
    Vertical.pane.inactive { border: round #1f2937; }
    #grouplabel, #filelabel, #summary, #pathinfo { padding: 1; }
    ProgressBar { height: 1; margin: 0 1; }
    ListView { height: 1fr; }
    ListView:focus { border: round $accent; background: #111827; }
    .group-card { padding: 0; margin: 0; }
    #confirm-wrap, #bulk-wrap { height: 1fr; }
    .modal-card { width: 1fr; height: 1fr; padding: 1 2; border: round $accent; background: #0f131b; }
    #confirm-table { height: 1fr; min-height: 12; }
    #bulk-summary  { height: 1fr; min-height: 10; }
    #bulk-files    { height: 1fr; min-height: 10; margin-top: 1; }
    DataTable { border: round #334155; height: auto; }
    DataTable:focus { border: round $accent; }
    .keybar { height: 3; background: #0b0f16; color: #cbd5e1; content-align: center middle; padding: 0 1; border-top: solid #1f2937; }
    #confirm-body { height: 1fr; }
    #bulk-body { height: 1fr; }
    .kbd { background: #111827; border: round #4b5563; color: #e5e7eb; padding: 0 1; }
    .hidden { display: none; }
    .max { width: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Force Quit"),
        Binding("s", "scan", "Scan"),
        Binding("o", "open_selected", "Open"),
        Binding("i", "keep_delete", "Keep One Copy"),
        Binding("d", "bulk_delete_preview", "Delete ALL (Preview)"),
        Binding("h", "focus_left", "Left Pane"),
        Binding("l", "focus_right", "Right Pane"),
        Binding("m", "toggle_maximize", "Maximize"),
    ]

    def __init__(self, folder: str | None = None) -> None:
        super().__init__()
        self.folder = folder or os.path.expanduser("~")
        self.groups: list[DuplicateGroup] = []
        self.current_group_idx: int | None = None
        self.current_file_idx: int | None = None
        self._maximized: str | None = None

    def _group_panel(self, g: DuplicateGroup):
        files_count = len(g.files)
        reclaim = human_size(g.potential_savings())
        return Text.assemble(
            (f"Group #{g.index}", "bold"),
            ("  •  Files: ", "dim"),
            (str(files_count), "bold"),
            ("  •  Potential reclaim: ", "dim"),
            (reclaim, "bold"),
        )

    def on_mount(self) -> None:
        asyncio.create_task(self.action_scan())

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=True)
        with Horizontal(id="root"):
            with Vertical(id="left", classes="pane active"):
                yield Static("[b]Duplicate Groups[/b]", id="grouplabel")
                yield ListView(id="groups")
                yield Static(
                    f"Root: [b]{self.folder}[/b]\n[i]Press [b]s[/b] to scan.",
                    id="pathinfo",
                )
            with Vertical(id="right", classes="pane inactive"):
                yield Static("Select a folder and press Scan.", id="summary")
                yield ProgressBar(total=100, id="progress")
                yield Static("[b]Files in Group[/b]", id="filelabel")
                yield ListView(id="files")
        yield Footer()

    def _update_summary(self) -> None:
        summary_widget = self.query_one("#summary", Static)
        if not self.groups:
            summary_widget.update(
                "[green]✅ No duplicates found![/green]\n"
                "[i]Shortcuts:[/i] [b]s[/b]=Scan  [b]h/l[/b]=Focus Left/Right  "
                "[b]m[/b]=Maximize  [b]o[/b]=Open  [b]i[/b]=Keep One Copy  [b]d[/b]=Delete ALL (Preview)"
            )
            return
        total_groups = len(self.groups)
        files_involved = sum(len(g.files) for g in self.groups)
        savings = sum(g.potential_savings() for g in self.groups)
        summary_widget.update(
            f"[bold yellow]⚠️ Found {total_groups} duplicate groups[/bold yellow]\n"
            f"Files involved: [b]{files_involved}[/b] | Potential reclaim: [b]{human_size(savings)}[/b]\n"
            "[i]Tip:[/i] Use ↑/↓ in Groups, then ↑/↓ in Files. Press [b]o[/b] to open, "
            "[b]i[/b] to keep one copy, [b]d[/b] to preview delete-all."
        )

    async def action_scan(self) -> None:
        progress = self.query_one("#progress", ProgressBar)
        progress.update(total=100, progress=0)

        def _progress(i: int, t: int) -> None:
            try:
                pct = int((i / max(t, 1)) * 100)
                progress.progress = min(max(pct, 0), 100)
            except Exception:
                pass

        hm = await find_duplicates_by_hash_async(self.folder, _progress)
        self.groups = groups_from_hash_map(hm)
        self._refresh_groups_list()
        self._update_summary()
        if self.groups:
            self.current_group_idx = 0
            try:
                self.query_one("#groups", ListView).index = 0
            except Exception:
                pass
            self._refresh_files_list()

    def _refresh_groups_list(self) -> None:
        lv = self.query_one("#groups", ListView)
        lv.clear()
        if not self.groups:
            lv.append(ListItem(Label("No duplicates.")))
            return
        for g in self.groups:
            lv.append(ListItem(Static(self._group_panel(g), classes="group-card")))

    def _refresh_files_list(self) -> None:
        files_lv = self.query_one("#files", ListView)
        files_lv.clear()
        g = self._selected_group()
        if not g:
            return
        try:
            self.query_one("#filelabel", Static).update(
                f"[b]Files in Group[/b]  •  [dim]SHA256:[/dim] {g.hash}"
            )
        except Exception:
            pass
        for i, p in enumerate(g.files):
            base = os.path.basename(p)
            size = human_size(get_size(p))
            files_lv.append(ListItem(Label(f"{i+1:02d}. {base}  •  {size}\n{p}")))
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

    def action_keep_delete(self) -> None:
        g = self._selected_group()
        path = self._selected_file()
        if not g or not path:
            self.notify("Select a group and a file.")
            return
        dels = [p for p in g.files if p != path]
        if not dels:
            self.notify("Nothing to delete for this group.")
            return
        self.push_screen(ConfirmDeleteModal(path, dels))

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
        self.notify(f"Deleted {deleted} duplicate file(s).")
        asyncio.create_task(self.action_scan())

    def _build_bulk_plan(self) -> list[dict]:
        return bulk_delete_plan(self.groups)

    def action_bulk_delete_preview(self) -> None:
        plan = self._build_bulk_plan()
        if not plan:
            self.notify("No duplicate files to delete.")
            return
        self.push_screen(BulkDeleteModal(plan))

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

    def action_toggle_maximize(self) -> None:
        try:
            left = self.query_one("#left")
            right = self.query_one("#right")
            if self._maximized is None:
                focused = self.focused
                target = "right"
                if focused is not None and (left in focused.ancestors):
                    target = "left"
                if target == "left":
                    right.add_class("hidden")
                    left.add_class("max")
                else:
                    left.add_class("hidden")
                    right.add_class("max")
                self._maximized = target
            else:
                left.remove_class("hidden")
                right.remove_class("hidden")
                left.remove_class("max")
                right.remove_class("max")
                self._maximized = None
        except Exception:
            pass

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
