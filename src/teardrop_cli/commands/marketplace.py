"""marketplace commands: balance, earnings, withdraw, publish."""

from __future__ import annotations

import asyncio
from typing import Annotated, Optional

import typer

app = typer.Typer(
    name="marketplace",
    help="Marketplace — balance, earnings, withdrawals, and publishing.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# balance
# ---------------------------------------------------------------------------


@app.command()
def balance(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[Optional[str], typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show your marketplace balance."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_table, spinner

    client = config.get_client(base_url)

    with spinner("Fetching balance…"):
        try:
            data = asyncio.run(client.get_marketplace_balance())
        finally:
            asyncio.run(client.close())

    if as_json:
        print_json(data)
        return

    rows = [[k, v] for k, v in data.items()]
    print_table(
        [("Field", {"style": "bold cyan"}), "Value"],
        rows,
        title="Marketplace Balance",
    )


# ---------------------------------------------------------------------------
# earnings
# ---------------------------------------------------------------------------


@app.command()
def earnings(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max entries to return.")] = 20,
    cursor: Annotated[
        Optional[str], typer.Option("--cursor", help="Pagination cursor.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[Optional[str], typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List marketplace earnings."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_table, spinner

    client = config.get_client(base_url)

    with spinner("Fetching earnings…"):
        try:
            data = asyncio.run(client.get_earnings(limit=limit, cursor=cursor))
        finally:
            asyncio.run(client.close())

    if as_json:
        print_json(data)
        return

    items: list[dict] = data.get("items", data) if isinstance(data, dict) else data
    rows = [
        [
            e.get("id", ""),
            e.get("amount", ""),
            e.get("currency", ""),
            e.get("created_at", ""),
            e.get("description", ""),
        ]
        for e in items
    ]
    print_table(
        ["ID", ("Amount", {"justify": "right"}), "Currency", "Date", "Description"],
        rows,
        title="Earnings",
    )


# ---------------------------------------------------------------------------
# withdraw
# ---------------------------------------------------------------------------


@app.command()
def withdraw(
    amount_usdc: Annotated[int, typer.Option("--amount-usdc", "-a", help="Amount to withdraw in USDC (integer).")],
    payout_address: Annotated[
        str, typer.Option("--payout-address", help="Wallet address to send funds to.")
    ],
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[Optional[str], typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Withdraw marketplace earnings to a wallet address."""
    from teardrop import WithdrawRequest

    from teardrop_cli import config
    from teardrop_cli.formatting import confirm, print_json, print_success, print_table, spinner

    if not yes:
        if not confirm(f"Withdraw {amount_usdc} USDC to {payout_address}?"):
            raise typer.Abort()

    client = config.get_client(base_url)

    with spinner("Processing withdrawal…"):
        try:
            result = asyncio.run(
                client.withdraw(WithdrawRequest(amount_usdc=amount_usdc, payout_address=payout_address))
            )
        finally:
            asyncio.run(client.close())

    if as_json:
        print_json(result)
        return

    print_success(f"Withdrawal initiated: {amount_usdc} USDC → {payout_address}")
    if isinstance(result, dict):
        rows = [[k, v] for k, v in result.items()]
        print_table([("Field", {"style": "bold cyan"}), "Value"], rows, title="Withdrawal")


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


@app.command()
def publish(
    payout_address: Annotated[
        str,
        typer.Option(
            "--payout-address",
            "-p",
            help="Wallet address to receive marketplace earnings.",
        ),
    ],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[Optional[str], typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Set your marketplace author config (payout address)."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_success, print_table, spinner

    client = config.get_client(base_url)

    with spinner("Updating author config…"):
        try:
            result = asyncio.run(client.set_author_config(payout_address))
        finally:
            asyncio.run(client.close())

    if as_json:
        print_json(result.model_dump() if hasattr(result, "model_dump") else result)
        return

    print_success(f"Payout address set to [bold]{payout_address}[/bold].")
    if hasattr(result, "model_dump"):
        rows = [[k, v] for k, v in result.model_dump().items() if v is not None]
        print_table([("Field", {"style": "bold cyan"}), "Value"], rows, title="Author Config")
