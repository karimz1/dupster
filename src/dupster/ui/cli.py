import sys
from typing import Optional

import typer

from dupster import __version__
from dupster.ui.tui.app import DupsterApp

cli = typer.Typer(
    help="Dupster 🧹 — Interactive TUI to find and manage duplicate files.",
    add_completion=False,
)


def version_callback(value: bool):
    """Display version and exit."""
    if value:
        typer.echo(f"Dupster version {__version__}")
        raise typer.Exit()


@cli.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    folder: Optional[str] = typer.Argument(None, help="Folder to scan", metavar="FOLDER"),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    app = DupsterApp(folder=folder)
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n^C", file=sys.stderr)
        raise typer.Exit(code=130) from None
