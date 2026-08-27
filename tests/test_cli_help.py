import pytest

pytest.importorskip("typer")
from typer.testing import CliRunner

from dupster.ui.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Dupster" in result.stdout
    assert "Star me on GitHub" in result.stdout
    assert "karimz1/dupster" in result.stdout
    assert "(https://github.com/karimz1/dupster)" not in result.stdout
    assert "—" not in result.stdout
    assert "Folder to scan" in result.stdout
    assert "Install completion" not in result.stdout
    assert "Show completion" not in result.stdout


def test_cli_version_uses_plain_brand():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "Dupster" in result.stdout
    assert "https://github.com/karimz1/dupster" in result.stdout
