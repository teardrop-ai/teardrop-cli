"""earnings commands: balance, history, withdraw, withdrawals."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

app = typer.Typer(
    name="earnings",
    help="Marketplace earnings — balance, history, withdrawals.",
    no_args_is_help=True,
)


def _fmt_usdc(atomic: int | None) -> str:
    if atomic is None:
        return "—"
    try:
        from teardrop import format_usdc

        return f"${format_usdc(int(atomic))}"
    except Exception:
        return f"${int(atomic) / 1_000_000:.6f}"


# ---------------------------------------------------------------------------
# balance
# ---------------------------------------------------------------------------


@app.command()
def balance(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show your marketplace earnings balance."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_marketplace_balance()
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
        ["Available balance", _fmt_usdc(data.get("balance_usdc"))],
        ["Pending", _fmt_usdc(data.get("pending_usdc"))],
    ]
    if data.get("settlement_wallet"):
        rows.append(["Settlement wallet", data["settlement_wallet"]])
    print_table(
        [("Field", {"style": "bold cyan"}), "Value"], rows, title="Earnings Balance"
    )


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


@app.command()
def history(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max entries to return.")] = 20,
    tool: Annotated[
        str | None,
        typer.Option("--tool", help="Filter by tool name."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List earnings entries."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_earnings(limit=limit, tool_name=tool)
        finally:
            await client.close()

    with spinner("Fetching earnings…"):
        data = asyncio.run(_fetch())

    if hasattr(data, "model_dump"):
        data = data.model_dump()
    items_raw = data.get("earnings") or data.get("items") or []
    items = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in items_raw]

    if as_json:
        print_json({"earnings": items, "next_cursor": data.get("next_cursor")})
        return

    if not items:
        data_console.print("[dim]No earnings yet.[/dim]")
        return

    rows = [
        [
            e.get("tool_name", "—"),
            e.get("caller_org_id", "—"),
            _fmt_usdc(e.get("author_share_usdc")),
            e.get("status", "—"),
            (e.get("created_at") or "")[:10],
        ]
        for e in items
    ]
    print_table(
        [
            "Tool",
            "Caller Org",
            ("Author Share", {"justify": "right"}),
            "Status",
            "Date",
        ],
        rows,
        title="Earnings",
    )


# ---------------------------------------------------------------------------
# withdraw
# ---------------------------------------------------------------------------


@app.command()
def withdraw(
    amount: Annotated[
        str,
        typer.Argument(help="Amount in USDC (decimal dollars), e.g. 4.50."),
    ],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Withdraw earnings to your settlement wallet."""
    from teardrop import WithdrawRequest, parse_usdc

    from teardrop_cli import config
    from teardrop_cli.formatting import (
        confirm,
        print_error,
        print_json,
        print_success,
        spinner,
    )

    try:
        atomic = parse_usdc(amount)
    except Exception as exc:
        print_error(f"Invalid amount: {exc}")
        raise typer.Exit(1) from None

    client = config.get_client(base_url)

    if not yes:
        # Try to fetch settlement wallet for confirmation; non-fatal if unavailable
        wallet = "your settlement wallet"
        try:
            bal = asyncio.run(_quick_balance(client))
            if bal:
                wallet = bal.get("settlement_wallet") or wallet
        except Exception:
            pass
        if not confirm(f"Withdraw ${amount} USDC to {wallet}?"):
            raise typer.Abort()
        # Re-acquire client (the previous call closed it)
        client = config.get_client(base_url)

    async def _do():
        try:
            return await client.withdraw(WithdrawRequest(amount_usdc=atomic))
        finally:
            await client.close()

    with spinner("Processing withdrawal…"):
        result = asyncio.run(_do())

    if hasattr(result, "model_dump"):
        result = result.model_dump()

    if as_json:
        print_json(result)
        return

    print_success(
        f"Withdrawal initiated. Transaction may take 1–5 minutes on-chain."
    )


async def _quick_balance(client) -> dict | None:
    try:
        bal = await client.get_marketplace_balance()
        return bal.model_dump() if hasattr(bal, "model_dump") else dict(bal)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# withdrawals
# ---------------------------------------------------------------------------


@app.command()
def withdrawals(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max entries to return.")] = 20,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show withdrawal history."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_withdrawals(limit=limit)
        finally:
            await client.close()

    with spinner("Fetching withdrawals…"):
        data = asyncio.run(_fetch())

    if hasattr(data, "model_dump"):
        data = data.model_dump()
    items = data.get("withdrawals") or data.get("items") or []
    items = [w.model_dump() if hasattr(w, "model_dump") else dict(w) for w in items]

    if as_json:
        print_json({"withdrawals": items, "next_cursor": data.get("next_cursor")})
        return

    if not items:
        data_console.print("[dim]No withdrawals yet.[/dim]")
        return

    rows = [
        [
            (w.get("created_at") or "")[:10],
            _fmt_usdc(w.get("amount_usdc")),
            w.get("status", "—"),
            w.get("tx_hash", "—"),
        ]
        for w in items
    ]
    print_table(
        ["Date", ("Amount", {"justify": "right"}), "Status", "Tx Hash"],
        rows,
        title="Withdrawals",
    )
