"""Top-level ``teardrop balance`` command group and ``credit-history``."""

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


# ---------------------------------------------------------------------------
# group (default → show)
# ---------------------------------------------------------------------------


@click.group(
    name="balance",
    help="Show your credit balance and history.",
    invoke_without_command=True,
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--base-url", "base_url", default=None, hidden=True)
@click.pass_context
def app(ctx: click.Context, as_json: bool, base_url: str | None) -> None:
    """Query billing and credit‑history information."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(show, as_json=as_json, base_url=base_url)


# ---------------------------------------------------------------------------
# show  (default subcommand)
# ---------------------------------------------------------------------------


@app.command(name="show", help="Show your current credit balance (default).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--base-url", "base_url", default=None, hidden=True)
def show(as_json: bool, base_url: str | None) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import (
        console,
        handle_token_expiry,
        print_json,
        print_table,
        spinner,
    )

    async def _fetch_once(client):
        try:
            return await client.get_balance()
        finally:
            await client.close()

    def _call_once():
        client = config.get_client(base_url)
        return asyncio.run(_fetch_once(client))

    try:
        with spinner("Fetching balance…"):
            data = _call_once()
    except Exception as exc:
        action = asyncio.run(
            handle_token_expiry(
                exc,
                base_url,
                allow_prompt_login=not as_json,
            )
        )

        if action == "retry":
            with spinner("Fetching balance…"):
                data = _call_once()
        elif action == "prompt_login":
            from teardrop_cli.commands.auth import interactive_reauthenticate

            if not interactive_reauthenticate(base_url=base_url):
                raise click.exceptions.Exit(1) from None
            with spinner("Fetching balance…"):
                data = _call_once()
        elif action == "fail":
            raise click.exceptions.Exit(1) from None
        else:
            raise

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


# ---------------------------------------------------------------------------
# credit-history
# ---------------------------------------------------------------------------


@app.command(name="credit-history", help="Show credit history (charges, top-ups, etc.).")
@click.option("--limit", "limit", default=20, show_default=True, help="Number of entries.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--base-url", "base_url", default=None, hidden=True)
def _credit_history(limit: int, as_json: bool, base_url: str | None) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import (
        handle_token_expiry,
        print_json,
        print_table,
        spinner,
    )

    async def _fetch_once(client):
        try:
            return await client.get_credit_history()
        finally:
            await client.close()

    def _call_once():
        client = config.get_client(base_url)
        return asyncio.run(_fetch_once(client))

    try:
        with spinner("Fetching credit history…"):
            data = _call_once()
    except Exception as exc:
        action = asyncio.run(
            handle_token_expiry(
                exc,
                base_url,
                allow_prompt_login=not as_json,
            )
        )

        if action == "retry":
            with spinner("Fetching credit history…"):
                data = _call_once()
        elif action == "prompt_login":
            from teardrop_cli.commands.auth import interactive_reauthenticate

            if not interactive_reauthenticate(base_url=base_url):
                raise click.exceptions.Exit(1) from None
            with spinner("Fetching credit history…"):
                data = _call_once()
        elif action == "fail":
            raise click.exceptions.Exit(1) from None
        else:
            raise

    # Normalise Pydantic models to plain dicts (handles both single models
    # and list-of-models from get_credit_history).
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
        data = [i.model_dump() for i in data]

    if as_json:
        print_json(data)
        return

    items = data if isinstance(data, list) else data.get("entries", data.get("items", []))

    if not items:
        from teardrop_cli.formatting import data_console
        data_console.print("[dim]No credit history found.[/dim]")
        return

    rows = []
    for item in items[:limit]:
        desc = item.get("reason") or item.get("description") or item.get("operation") or "—"
        amount = _fmt_usdc(item.get("amount_usdc", item.get("amount", 0)))
        ts = item.get("created_at") or item.get("timestamp", "—")
        rows.append([desc, amount, ts])

    print_table(
        [("Description", {"style": "bold cyan"}), "Amount", "Date"],
        rows,
        title="Credit History",
    )
