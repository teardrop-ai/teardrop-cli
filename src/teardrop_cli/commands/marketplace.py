"""marketplace commands: list, search, info, subscribe, unsubscribe, subscriptions."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer

app = typer.Typer(
    name="marketplace",
    help="Marketplace — browse and subscribe to published tools.",
    no_args_is_help=True,
)


def _cost_dollars(atomic: int | None) -> str:
    """Format an atomic-USDC integer as ``$0.0050``."""
    if atomic is None:
        return "—"
    try:
        from teardrop import format_usdc

        decimal = format_usdc(int(atomic))
        return f"${float(decimal):.4f}"
    except Exception:
        # Fallback assuming 6-decimal USDC
        return f"${int(atomic) / 1_000_000:.4f}"


async def _fetch_catalog(client) -> list[dict]:
    """Fetch the full catalog and return a flat list of tool dicts."""
    from pydantic import ValidationError as PydanticValidationError

    try:
        result = await client.get_marketplace_catalog(limit=100)
    except PydanticValidationError:
        # SDK model is out of sync with the API response (e.g. a required field is
        # absent).  Fall back to the raw HTTP layer so the CLI keeps working.
        http = await client._get_http()
        resp = await http.get(
            f"{client._base_url}/marketplace/catalog", params={"limit": 100}
        )
        client._raise_for_status(resp)
        data = resp.json()
        tools = data.get("tools", data.get("items", []))
        return [dict(t) for t in tools]

    if hasattr(result, "model_dump"):
        result = result.model_dump()
    tools = result.get("tools", result.get("items", []))
    return [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in tools]


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_cmd(
    category: Annotated[
        str | None, typer.Option("--category", help="Filter by category.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Browse published tools (no auth required)."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url, require_auth=False)

    async def _fetch():
        try:
            return await _fetch_catalog(client)
        finally:
            await client.close()

    with spinner("Fetching marketplace catalog…"):
        tools = asyncio.run(_fetch())

    if category:
        tools = [
            t for t in tools if (t.get("category") or "").lower() == category.lower()
        ]

    if as_json:
        print_json(tools)
        return

    if not tools:
        data_console.print("[dim]No tools found.[/dim]")
        return

    rows = [
        [
            t.get("name", "—"),
            t.get("author") or t.get("author_slug", "—"),
            _cost_dollars(t.get("cost_usdc")),
            (t.get("description") or "")[:60],
        ]
        for t in tools
    ]
    print_table(
        ["Name", "Author", ("Price/Call", {"justify": "right"}), "Description"],
        rows,
        title="Marketplace",
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query.")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Search the catalog by keyword (client-side filter)."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url, require_auth=False)

    async def _fetch():
        try:
            return await _fetch_catalog(client)
        finally:
            await client.close()

    with spinner("Searching marketplace…"):
        tools = asyncio.run(_fetch())

    q = query.lower()
    matches = [
        t
        for t in tools
        if q in (t.get("name") or "").lower() or q in (t.get("description") or "").lower()
    ]

    if as_json:
        print_json(matches)
        return

    if not matches:
        data_console.print(f"[dim]No tools matching '{query}'.[/dim]")
        return

    rows = [
        [
            t.get("name", "—"),
            t.get("author") or t.get("author_slug", "—"),
            _cost_dollars(t.get("cost_usdc")),
            (t.get("description") or "")[:60],
        ]
        for t in matches
    ]
    print_table(
        ["Name", "Author", ("Price/Call", {"justify": "right"}), "Description"],
        rows,
        title=f"Search: {query!r}",
    )


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@app.command()
def info(
    qualified_name: Annotated[
        str, typer.Argument(metavar="ORG/TOOL", help="Qualified tool name e.g. acme/weather.")
    ],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show full detail for one marketplace tool."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_error, print_json, print_table, spinner

    client = config.get_client(base_url, require_auth=False)

    async def _fetch():
        try:
            return await _fetch_catalog(client)
        finally:
            await client.close()

    with spinner("Fetching tool…"):
        tools = asyncio.run(_fetch())

    matching = [t for t in tools if t.get("name") == qualified_name]
    if not matching:
        print_error(f"Tool {qualified_name!r} not found.")
        raise typer.Exit(1)

    tool = matching[0]
    if as_json:
        print_json(tool)
        return

    rows = [
        ["Name", tool.get("name", "—")],
        ["Author", tool.get("author") or tool.get("author_slug", "—")],
        ["Price/Call", _cost_dollars(tool.get("cost_usdc"))],
        ["Description", tool.get("description", "—")],
    ]
    print_table([("Field", {"style": "bold cyan"}), "Value"], rows, title=qualified_name)

    schema = tool.get("input_schema")
    if schema:
        data_console.print("\n[bold]Input Schema:[/bold]")
        data_console.print_json(json.dumps(schema, default=str))


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------


@app.command()
def subscribe(
    qualified_name: Annotated[
        str, typer.Argument(metavar="ORG/TOOL", help="Qualified tool name.")
    ],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Subscribe your org to a marketplace tool."""
    from teardrop import ConflictError

    from teardrop_cli import config
    from teardrop_cli.formatting import (
        confirm,
        console,
        print_error,
        print_json,
        print_success,
        spinner,
    )

    if not yes:
        # Lookup price for confirmation
        public = config.get_client(base_url, require_auth=False)
        try:
            tools = asyncio.run(_lookup_then_close(public, qualified_name))
        except Exception:
            tools = []
        match = next((t for t in tools if t.get("name") == qualified_name), None)
        cost_label = _cost_dollars(match.get("cost_usdc")) if match else "?"
        console.print(f"Subscribe to [bold]{qualified_name}[/bold]?")
        console.print(f"  Cost: {cost_label}/call")
        console.print("  This tool will be available to your agent immediately.")
        if not confirm("Confirm?"):
            raise typer.Abort()

    client = config.get_client(base_url)

    async def _do():
        try:
            return await client.subscribe(qualified_name)
        finally:
            await client.close()

    try:
        with spinner("Subscribing…"):
            sub = asyncio.run(_do())
    except ConflictError:
        print_error(f"Already subscribed to {qualified_name}.")
        raise typer.Exit(1) from None

    data = sub.model_dump() if hasattr(sub, "model_dump") else dict(sub)

    if as_json:
        print_json(data)
        return

    print_success(f"Subscribed to {qualified_name} (id: {data.get('id', '?')})")


async def _fetch_subscriptions(client) -> list[dict]:
    """Fetch active subscriptions, working around SDK response-shape mismatches."""
    from pydantic import ValidationError as PydanticValidationError

    try:
        subs = await client.get_subscriptions()
        return [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in subs]
    except (PydanticValidationError, TypeError, AttributeError):
        # API returns {"subscriptions": [...]} but SDK iterates the dict keys.
        http = await client._get_http()
        resp = await http.get(
            f"{client._base_url}/marketplace/subscriptions",
            headers=await client._headers(),
        )
        client._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("subscriptions", data.get("items", []))


async def _lookup_then_close(client, qualified_name: str) -> list[dict]:
    try:
        return await _fetch_catalog(client)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# unsubscribe
# ---------------------------------------------------------------------------


@app.command()
def unsubscribe(
    qualified_name: Annotated[
        str, typer.Argument(metavar="ORG/TOOL", help="Qualified tool name.")
    ],
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Cancel a subscription."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_success, spinner

    client = config.get_client(base_url)

    async def _do():
        try:
            subs = await _fetch_subscriptions(client)
            target = next(
                (s for s in subs if s.get("qualified_tool_name") == qualified_name),
                None,
            )
            if target is None:
                return None
            sub_id = target.get("id")
            await client.unsubscribe(sub_id)
            return sub_id
        finally:
            await client.close()

    with spinner("Unsubscribing…"):
        sub_id = asyncio.run(_do())

    if sub_id is None:
        print_error(f"No active subscription found for {qualified_name}.")
        raise typer.Exit(1)

    print_success(f"Unsubscribed from {qualified_name}.")


# ---------------------------------------------------------------------------
# subscriptions
# ---------------------------------------------------------------------------


@app.command()
def subscriptions(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List your org's active subscriptions."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await _fetch_subscriptions(client)
        finally:
            await client.close()

    with spinner("Fetching subscriptions…"):
        items = asyncio.run(_fetch())

    if as_json:
        print_json(items)
        return

    if not items:
        data_console.print("[dim]No active subscriptions.[/dim]")
        return

    rows = [
        [s.get("qualified_tool_name", "—"), s.get("subscribed_at", "—")] for s in items
    ]
    print_table(["Tool", "Subscribed At"], rows, title="Subscriptions")
