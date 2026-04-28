"""topup commands: stripe, usdc."""

from __future__ import annotations

import asyncio
import time
import webbrowser
from typing import Annotated

import typer

app = typer.Typer(
    name="topup",
    help="Top up your credit balance via Stripe or on-chain USDC.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# stripe
# ---------------------------------------------------------------------------


@app.command()
def stripe(
    amount: Annotated[
        float,
        typer.Option("--amount", help="Amount in USD dollars (e.g. 10.00)."),
    ],
    return_url: Annotated[
        str,
        typer.Option(
            "--return-url",
            help="URL to redirect to after Stripe checkout.",
        ),
    ] = "https://teardrop.dev/billing/topup/complete",
    no_browser: Annotated[
        bool,
        typer.Option("--no-browser", help="Do not auto-open browser; print URL instead."),
    ] = False,
    poll_timeout: Annotated[
        int,
        typer.Option("--poll-timeout", help="Seconds to wait for completion."),
    ] = 600,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Top up via Stripe checkout."""
    from teardrop import StripeTopupRequest

    from teardrop_cli import config
    from teardrop_cli.formatting import (
        console,
        print_error,
        print_json,
        print_success,
        spinner,
    )

    if amount <= 0:
        print_error("Amount must be positive.")
        raise typer.Exit(1)

    client = config.get_client(base_url)
    request = StripeTopupRequest(amount_cents=int(amount * 100), return_url=return_url)

    async def _create():
        return await client.topup_stripe(request)

    with spinner(f"Opening Stripe checkout for ${amount:.2f}…"):
        resp = asyncio.run(_create())

    data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
    checkout_url = data.get("client_secret") or data.get("url")
    session_id = data.get("session_id")

    if not session_id or not checkout_url:
        print_error("Unexpected response from Stripe topup endpoint.")
        raise typer.Exit(1)

    if no_browser:
        console.print(f"Open this URL to complete payment:\n  {checkout_url}")
    else:
        webbrowser.open(checkout_url)
        console.print(f"[dim]Browser opened: {checkout_url}[/dim]")

    # Poll for completion
    deadline = time.time() + poll_timeout
    final = None
    with spinner("Waiting for payment confirmation…"):
        while time.time() < deadline:
            status_resp = asyncio.run(client.get_stripe_topup_status(session_id))
            sd = (
                status_resp.model_dump()
                if hasattr(status_resp, "model_dump")
                else dict(status_resp)
            )
            if sd.get("status") in ("complete", "expired"):
                final = sd
                break
            time.sleep(2)

    asyncio.run(client.close())

    if final is None:
        print_error("Timed out waiting for payment confirmation.")
        raise typer.Exit(2)

    if as_json:
        print_json(final)
        return

    if final.get("status") == "expired":
        print_error("Checkout session expired without completing payment.")
        raise typer.Exit(2)

    new_balance = final.get("new_balance_fmt") or "?"
    print_success(f"Payment complete. New balance: ${new_balance}")


# ---------------------------------------------------------------------------
# usdc
# ---------------------------------------------------------------------------


@app.command()
def usdc(
    amount: Annotated[
        str,
        typer.Option("--amount", help="Amount in USDC dollars, e.g. 25.00."),
    ],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show on-chain USDC payment instructions (x402)."""
    from teardrop import parse_usdc

    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_error, print_json, spinner

    try:
        atomic = parse_usdc(amount)
    except Exception as exc:
        print_error(f"Invalid amount: {exc}")
        raise typer.Exit(1) from None

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_usdc_topup_requirements(amount_usdc=atomic)
        finally:
            await client.close()

    with spinner("Fetching USDC payment requirements…"):
        reqs = asyncio.run(_fetch())

    data = reqs.model_dump() if hasattr(reqs, "model_dump") else dict(reqs)

    if as_json:
        print_json(data)
        return

    console.print(f"[bold]USDC payment instructions (x402 v{data.get('x402Version', '?')})[/bold]\n")
    for accept in data.get("accepts", []):
        for k, v in accept.items():
            console.print(f"  {k}: {v}")
        console.print("")
