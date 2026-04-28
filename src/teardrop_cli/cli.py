"""Main CLI entry point for teardrop-cli.

The root command is a plain Click Group (via LazyGroup) so that unknown
kwargs like ``lazy_subcommands`` are forwarded correctly.  Subcommand
modules are imported only when the subcommand is actually invoked, keeping
``teardrop --help`` well under 100 ms.
"""

from __future__ import annotations

import click

from teardrop_cli._lazy import LazyGroup


@click.group(
    name="teardrop",
    cls=LazyGroup,
    lazy_subcommands={
        "auth": "teardrop_cli.commands.auth:app",
        "init": "teardrop_cli.commands.config_cmd:init_app",
        "quickstart": "teardrop_cli.commands.quickstart:app",
        "config": "teardrop_cli.commands.config_cmd:app",
        "run": "teardrop_cli.commands.run:app",
        "balance": "teardrop_cli.commands.balance:app",
        "topup": "teardrop_cli.commands.topup:app",
        "usage": "teardrop_cli.commands.usage:app",
        "marketplace": "teardrop_cli.commands.marketplace:app",
        "tools": "teardrop_cli.commands.tools:app",
        "earnings": "teardrop_cli.commands.earnings:app",
        "llm-config": "teardrop_cli.commands.llm_config:app",
        "models": "teardrop_cli.commands.models:app",
        "mcp": "teardrop_cli.commands.mcp:app",
    },
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(package_name="teardrop-cli", prog_name="teardrop")
@click.pass_context
def app(ctx: click.Context) -> None:
    """Teardrop AI — crypto-native agent orchestration & marketplace."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


if __name__ == "__main__":
    app()
