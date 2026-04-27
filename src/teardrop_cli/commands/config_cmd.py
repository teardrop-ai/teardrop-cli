"""``teardrop init`` and ``teardrop config {set,get,list}`` commands."""

from __future__ import annotations

from typing import Annotated

import click
import typer

# ---------------------------------------------------------------------------
# `teardrop init`
# ---------------------------------------------------------------------------


@click.command(name="init", help="Initialize ~/.teardrop/config.toml.")
@click.option(
    "--base-url",
    "base_url",
    default=None,
    help="Set the api_url field on creation.",
)
def init_app(base_url: str | None) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import print_success

    path = config.init_config_file()
    if base_url:
        config.set_api_url(base_url)
    print_success(f"Initialized {path}")


# ---------------------------------------------------------------------------
# `teardrop config {set,get,list}`
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="config",
    help="Inspect and modify ~/.teardrop/config.toml.",
    no_args_is_help=True,
)


_ALLOWED_KEYS = {"api_url", "email", "org_id"}


@app.command("set")
def set_cmd(
    key: Annotated[str, typer.Argument(help="Config key (api_url, email, org_id).")],
    value: Annotated[str, typer.Argument(help="Value to set.")],
) -> None:
    """Set a config field."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_success

    if key not in _ALLOWED_KEYS:
        print_error(
            f"Unknown or read-only key {key!r}.",
            hint=f"Allowed: {', '.join(sorted(_ALLOWED_KEYS))}",
        )
        raise typer.Exit(1)

    cfg = config.load_config()
    cfg[key] = value
    config.save_config(cfg)
    print_success(f"Set {key} = {value}")


@app.command("get")
def get_cmd(
    key: Annotated[str, typer.Argument(help="Config key to read.")],
) -> None:
    """Get the value of a single config field."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_error

    cfg = config.load_config()
    if key not in cfg:
        print_error(f"Key {key!r} not set.")
        raise typer.Exit(1)
    value = cfg[key]
    if key in ("access_token", "refresh_token") and isinstance(value, str):
        value = (value[:12] + "…") if len(value) > 12 else value
    data_console.print(value)


@app.command("list")
def list_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show all stored config values (tokens redacted)."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_table

    cfg = dict(config.load_config())
    for key in ("access_token", "refresh_token"):
        v = cfg.get(key)
        if isinstance(v, str) and len(v) > 12:
            cfg[key] = v[:12] + "…"

    if as_json:
        print_json(cfg)
        return

    if not cfg:
        from teardrop_cli.formatting import data_console

        data_console.print("[dim]No config saved yet.[/dim]")
        return

    rows = [[k, v] for k, v in cfg.items()]
    print_table(
        [("Key", {"style": "bold cyan"}), "Value"], rows, title="~/.teardrop/config.toml"
    )
