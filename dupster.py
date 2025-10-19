#!/usr/bin/env python3
# Dupster - Modern Duplicate Finder CLI
# Copyright (c) 2025 Karim Zouine
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Requires Python 3.9.6 or newer

import os
import sys
import hashlib
import zipfile
import subprocess
from collections import defaultdict
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import track
from rich import box

console = Console()
app = typer.Typer(help="dupster - A modern CLI tool to find and manage duplicate files 🧹")


def compute_hash(file_path: str, block_size: int = 65536) -> Optional[str]:
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(block_size), b""):
                hasher.update(chunk)
    except Exception as e:
        console.print(f"[red]Error reading {file_path}: {e}[/red]")
        return None
    return hasher.hexdigest()


def compute_zip_content_hash(zip_path: str) -> Optional[str]:
    hasher = hashlib.sha256()
    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            file_list = sorted([f for f in zipf.namelist() if not f.endswith("/")])
            for name in file_list:
                with zipf.open(name) as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
    except Exception as e:
        console.print(f"[red]Error reading zip content from {zip_path}: {e}[/red]")
        return None
    return hasher.hexdigest()


def find_duplicates(folder_path: str) -> Dict[str, List[str]]:
    file_list = []
    for root, _, files in os.walk(folder_path):
        for name in files:
            full_path = os.path.join(root, name)
            file_list.append(full_path)

    file_list.sort(key=lambda path: os.path.basename(path).lower())
    hash_map = defaultdict(list)

    for file_path in track(file_list, description="[cyan]Scanning files...[/cyan]"):
        ext = os.path.splitext(file_path)[1].lower()
        file_hash = (
            compute_zip_content_hash(file_path)
            if ext == ".zip"
            else compute_hash(file_path)
        )
        if file_hash:
            hash_map[file_hash].append(file_path)

    duplicates = {h: files for h, files in hash_map.items() if len(files) > 1}
    return duplicates


def open_file(file_path: str):
    try:
        if sys.platform.startswith("darwin"):
            subprocess.call(["open", file_path])
        elif os.name == "nt":
            os.startfile(file_path)  # type: ignore
        elif os.name == "posix":
            subprocess.call(["xdg-open", file_path])
    except Exception as e:
        console.print(f"[red]Failed to open {file_path}: {e}[/red]")


@app.command()
def scan(folder: str):
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        console.print(f"[red]Invalid folder: {folder}[/red]")
        raise typer.Exit()

    console.print(f"\n[bold cyan]📁 Scanning folder:[/bold cyan] {folder}\n")

    duplicates = find_duplicates(folder)
    if not duplicates:
        console.print("[green]✅ No duplicates found![/green]")
        raise typer.Exit()

    console.print("[bold yellow]⚠️ Found duplicate file groups:[/bold yellow]\n")

    # Build a table with spacing between groups
    table = Table(
        title="Duplicate Groups",
        box=box.ROUNDED,
        header_style="bold magenta",
        show_lines=False,
    )
    table.add_column("Group #", justify="center", style="cyan", width=8)
    table.add_column("Hash (short)", style="green", width=15)
    table.add_column("Files", style="white")

    for i, (file_hash, files) in enumerate(duplicates.items(), start=1):
        short_hash = file_hash[:10] + "..."
        first_row = True
        for f in files:
            table.add_row(str(i) if first_row else "", short_hash if first_row else "", f)
            first_row = False
        table.add_row("", "", "")  # spacer row

    console.print(table)

    while True:
        action = Prompt.ask(
            "\nChoose action",
            choices=["preview", "delete", "exit"],
            default="exit"
        )

        # --- PREVIEW MODE ---
        if action == "preview":
            while True:
                group_num_str = Prompt.ask("\nEnter group number to preview ('back' to exit preview mode)")
                if group_num_str.lower() == "back":
                    console.print("[blue]↩ Returning to main menu...[/blue]")
                    break

                try:
                    group_num = int(group_num_str)
                except ValueError:
                    console.print("[red]Invalid input. Enter a number or 'back'.[/red]")
                    continue

                if group_num not in range(1, len(duplicates) + 1):
                    console.print("[red]Invalid group number[/red]")
                    continue

                group_hash, files = list(duplicates.items())[group_num - 1]
                console.print(f"\n[bold cyan]🔍 Preview Mode — Group {group_num}[/bold cyan]")
                console.print(f"[green]Hash:[/green] {group_hash}\n")

                for idx, f in enumerate(files, start=1):
                    console.print(f"[cyan]{idx}.[/cyan] {f}")

                console.print(
                    "\nType [bold]number[/bold] to open a file, [bold]all[/bold] to open all, or [bold]back[/bold] to go back.\n"
                )

                while True:
                    choice = Prompt.ask("preview>")
                    if choice.lower() == "back":
                        break
                    elif choice.lower() == "all":
                        for f in files:
                            open_file(f)
                        console.print("[green]Opened all files in this group.[/green]")
                    else:
                        try:
                            idx = int(choice)
                            if 1 <= idx <= len(files):
                                open_file(files[idx - 1])
                                console.print(f"[green]Opened:[/green] {files[idx - 1]}")
                            else:
                                console.print("[red]Invalid file number[/red]")
                        except ValueError:
                            console.print("[red]Invalid input[/red]")

        # --- DELETE MODE ---
        elif action == "delete":
            while True:
                del_choice = Prompt.ask(
                    "\nType [bold]group[/bold], [bold]all[/bold], or [bold]back[/bold] to return",
                    choices=["group", "all", "back"]
                )

                if del_choice == "back":
                    console.print("[blue]↩ Returning to main menu...[/blue]")
                    break

                if del_choice == "group":
                    group_num_str = Prompt.ask("Enter group number to delete")
                    try:
                        group_num = int(group_num_str)
                    except ValueError:
                        console.print("[red]Invalid group number[/red]")
                        continue

                    if group_num not in range(1, len(duplicates) + 1):
                        console.print("[red]Invalid group number[/red]")
                        continue

                    _, files = list(duplicates.items())[group_num - 1]
                    keep = Prompt.ask("Enter file to KEEP (full path or filename)")
                    to_delete = [f for f in files if keep not in f]
                    for f in to_delete:
                        try:
                            os.remove(f)
                            console.print(f"[red]🗑 Deleted:[/red] {f}")
                        except Exception as e:
                            console.print(f"[red]Failed to delete {f}: {e}[/red]")
                    console.print("[green]Group deletion complete.[/green]")

                elif del_choice == "all":
                    confirm = Confirm.ask("Are you sure you want to delete ALL duplicates?")
                    if confirm:
                        for _, files in duplicates.items():
                            for f in files[1:]:
                                try:
                                    os.remove(f)
                                    console.print(f"[red]🗑 Deleted:[/red] {f}")
                                except Exception as e:
                                    console.print(f"[red]Error deleting {f}: {e}[/red]")
                        console.print("[green]All duplicates deleted.[/green]")

        elif action == "exit":
            console.print("[blue]👋 Exiting...[/blue]")
            break


if __name__ == "__main__":
    app()