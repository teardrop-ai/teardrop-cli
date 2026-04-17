"""billing commands: account balance."""

from __future__ import annotations

import asyncio
from typing import Annotated, Optional

import typer

app = typer.Typer(
    name="billing",
    help="Billing — account balance and usage.",
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """Billing — account balance and usage."""


# ---------------------------------------------------------------------------
# balance
# ---------------------------------------------------------------------------


@app.command()
def balance(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[Optional[str], typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show your account balance."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_table, spinner

    async def _fetch():
        try:
            return await client.get_balance()
        finally:
            await client.close()

    client = config.get_client(base_url)

    with spinner("Fetching balance…"):
        data = asyncio.run(_fetch())

    data_dict = data.model_dump() if hasattr(data, "model_dump") else data

    if as_json:
        print_json(data_dict)
        return

    rows = [[k, v] for k, v in data_dict.items()]
    print_table(
        [("Field", {"style": "bold cyan"}), "Value"],
        rows,
        title="Account Balance",
    )
