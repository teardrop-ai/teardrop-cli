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
        "agent": "teardrop_cli.commands.agent:app",
        "billing": "teardrop_cli.commands.billing:app",
        "llm-config": "teardrop_cli.commands.llm_config:app",
        "marketplace": "teardrop_cli.commands.marketplace:app",
        "mcp": "teardrop_cli.commands.mcp:app",
        "models": "teardrop_cli.commands.models:app",
        "tools": "teardrop_cli.commands.tools:app",
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
