"""Regression tests for the Click root's lazy Typer integration."""

from __future__ import annotations

import sys
from types import ModuleType

import click
import pytest
import typer

from teardrop_cli._lazy import LazyGroup


@pytest.mark.parametrize("exit_code", [1, 2])
def test_lazy_typer_command_preserves_exit_code(runner, monkeypatch, exit_code):
    subcommands = typer.Typer()

    @subcommands.command()
    def fail() -> None:
        typer.echo("Command failed.", err=True)
        raise typer.Exit(exit_code)

    module = ModuleType("_test_lazy_command")
    module.app = subcommands
    monkeypatch.setitem(sys.modules, module.__name__, module)
    root = LazyGroup(
        name="test",
        lazy_subcommands={"fail": f"{module.__name__}:app"},
    )

    result = runner.invoke(root, ["fail"])

    assert result.exit_code == exit_code
    assert isinstance(result.exception, SystemExit)
    assert result.exception.code == exit_code
    assert result.stdout == ""
    assert result.stderr == "Command failed.\n"
    assert isinstance(root.get_command(click.Context(root), "fail"), click.Command)
