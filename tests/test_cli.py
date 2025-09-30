import pytest
from click.testing import CliRunner
from portl.cli import cli


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "portl, version 0.0.2" in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Portl - A developer-first CLI tool" in result.output


def test_init_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Portl migration wizard" in result.output


def test_run_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "test.yaml"])
    assert result.exit_code == 0
    assert "Running migration job: test.yaml" in result.output


def test_run_command_dry_run():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "test.yaml", "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run mode" in result.output
