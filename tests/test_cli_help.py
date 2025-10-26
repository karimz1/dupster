import pytest

pytest.importorskip("typer")
from typer.testing import CliRunner
from dupster.ui.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Dupster" in result.stdout
    assert "Folder to scan"  in result.stdout
    assert "Install completion" not in result.stdout
    assert "Show completion" not in result.stdout
