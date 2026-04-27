"""Top-level ``teardrop balance`` command."""

from __future__ import annotations

import asyncio

import click


def _fmt_usdc(atomic: int | None) -> str:
    if atomic is None:
        return "—"
    try:
        from teardrop import format_usdc

        return f"${format_usdc(int(atomic))} USDC"
    except Exception:
        return f"${int(atomic) / 1_000_000:.6f} USDC"


@click.command(name="balance", help="Show your credit balance.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--base-url", "base_url", default=None, hidden=True)
def app(as_json: bool, base_url: str | None) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_balance()
        finally:
            await client.close()

    with spinner("Fetching balance…"):
        data = asyncio.run(_fetch())

    if hasattr(data, "model_dump"):
        data = data.model_dump()

    if as_json:
        print_json(data)
        return

    rows = [
        ["Credit balance", _fmt_usdc(data.get("balance_usdc"))],
        ["Spending limit", _fmt_usdc(data.get("spending_limit_usdc"))],
        ["Daily spend", _fmt_usdc(data.get("daily_spend_usdc"))],
        ["Account status", "paused" if data.get("is_paused") else "active"],
    ]
    print_table(
        [("Field", {"style": "bold cyan"}), "Value"], rows, title="Account Balance"
    )

    if data.get("is_paused"):
        console.print(
            "[bold yellow]⚠[/bold yellow]  Account is paused. Contact support or add funds."
        )
