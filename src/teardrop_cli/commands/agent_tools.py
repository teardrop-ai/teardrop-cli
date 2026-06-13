"""``teardrop agent-tools`` — list tools visible to the agent."""

from __future__ import annotations

import asyncio

import click


@click.group(name="agent-tools", help="Tools visible to your agent.")
def app() -> None:
    """Query tools available to the agent (platform + subscribed + custom)."""


@app.command(name="list", help="List all tools visible to your agent.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--base-url", "base_url", default=None, hidden=True)
def _list(as_json: bool, base_url: str | None) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import (
        data_console,
        handle_token_expiry,
        print_json,
        print_table,
        spinner,
    )

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_agent_tools()
        except Exception as exc:
            if await handle_token_expiry(exc, base_url):
                new_client = config.get_client(base_url)
                try:
                    return await new_client.get_agent_tools()
                finally:
                    await new_client.close()
            raise
        finally:
            await client.close()

    with spinner("Fetching agent tools…"):
        tools = asyncio.run(_fetch())

    items = [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in tools]

    if as_json:
        print_json(items)
        return

    if not items:
        data_console.print("[dim]No agent tools found.[/dim]")
        return

    rows = []
    for t in items:
        name = t.get("name", "—")
        source = t.get("source", "—")
        access = t.get("access_mode", "—")
        rows.append([name, source, access])

    print_table(
        [
            ("Name", {"style": "bold cyan"}),
            ("Source", {"style": "bold"}),
            ("Access", {"style": "bold"}),
        ],
        rows,
        title="Agent Tools",
    )