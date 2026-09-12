import sys
from typing import Optional

import typer

from dupster import __version__
from dupster.ui.tui.app import BRAND_NAME, GITHUB_URL, DupsterApp

CLI_HELP = f"{BRAND_NAME} - Interactive TUI to find and manage duplicate files."
CLI_EPILOG = f"Star me on GitHub: {GITHUB_URL}"

cli = typer.Typer(
    help=CLI_HELP,
    epilog=CLI_EPILOG,
    add_completion=False,
)


def version_callback(value: bool):
    """Display version and exit."""
    if value:
        typer.echo(f"{BRAND_NAME}\nVersion {__version__}\n{GITHUB_URL}")
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
    workers: Optional[int] = typer.Option(
        None,
        "--workers",
        "-w",
        help="Concurrent readers per disk. Default adapts to the drive: many on SSD, one on HDD.",
    ),
    min_size: int = typer.Option(
        0,
        "--min-size",
        "-m",
        help="Ignore files smaller than this many bytes.",
    ),
    verify: bool = typer.Option(
        False,
        "--verify",
        help="Confirm every match with a byte-for-byte comparison.",
    ),
    follow_symlinks: bool = typer.Option(
        False,
        "--follow-symlinks",
        help="Follow symlinks. Off by default so a link is never mistaken for a real copy.",
    ),
):
    app = DupsterApp(
        folder=folder,
        workers=workers,
        min_size=min_size,
        verify=verify,
        follow_symlinks=follow_symlinks,
    )
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n^C", file=sys.stderr)
        raise typer.Exit(code=130) from None
