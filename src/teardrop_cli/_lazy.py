"""Lazy subcommand loading for Typer/Click apps.

Defers module imports until a subcommand is actually invoked, keeping
``teardrop --help`` fast by avoiding top-level imports of heavy
dependencies (httpx, teardrop_sdk, etc.).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    pass


class LazyGroup(click.Group):
    """A Click Group that imports subcommand modules on demand."""

    def __init__(
        self,
        *args,
        lazy_subcommands: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        # Maps command name -> "module.path:attr_name"
        self._lazy: dict[str, str] = lazy_subcommands or {}

    # ------------------------------------------------------------------
    # Click Group overrides
    # ------------------------------------------------------------------

    def list_commands(self, ctx: click.Context) -> list[str]:
        base = super().list_commands(ctx)
        return sorted(set(base) | set(self._lazy.keys()))

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        if cmd_name in self._lazy:
            return self._load(cmd_name)
        return super().get_command(ctx, cmd_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, cmd_name: str) -> click.Command:
        import_path = self._lazy[cmd_name]
        if ":" in import_path:
            modname, attr = import_path.rsplit(":", 1)
        else:
            # Legacy dot-separated (last segment is attribute)
            modname, attr = import_path.rsplit(".", 1)

        mod = importlib.import_module(modname)
        cmd = getattr(mod, attr)

        # Typer apps must be converted to Click commands before use
        # Import here to avoid top-level dependency on typer
        import typer

        if isinstance(cmd, typer.Typer):
            cmd = typer.main.get_command(cmd)

        return cmd
