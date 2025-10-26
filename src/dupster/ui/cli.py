from typing import Optional
import sys
import typer

from dupster.ui.tui.app import DupsterApp


cli = typer.Typer(
    help="Dupster 🧹 — Interactive TUI to find and manage duplicate files.",
    add_completion=False,
)


@cli.callback(invoke_without_command=True)
def main(ctx: typer.Context, folder: Optional[str] = typer.Argument(None, help="Folder to scan", metavar="FOLDER")):
    app = DupsterApp(folder=folder)
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n^C", file=sys.stderr)
        raise typer.Exit(code=130)
