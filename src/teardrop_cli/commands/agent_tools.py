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

    async def _fetch_once(client):
        try:
            return await client.get_agent_tools()
        finally:
            await client.close()

    def _call_once():
        client = config.get_client(base_url)
        return asyncio.run(_fetch_once(client))

    try:
        with spinner("Fetching agent tools…"):
            tools = _call_once()
    except Exception as exc:
        action = asyncio.run(
            handle_token_expiry(
                exc,
                base_url,
                allow_prompt_login=not as_json,
            )
        )

        if action == "retry":
            with spinner("Fetching agent tools…"):
                tools = _call_once()
        elif action == "prompt_login":
            from teardrop_cli.commands.auth import interactive_reauthenticate

            if not interactive_reauthenticate(base_url=base_url):
                raise click.exceptions.Exit(1) from None
            with spinner("Fetching agent tools…"):
                tools = _call_once()
        elif action == "fail":
            raise click.exceptions.Exit(1) from None
        else:
            raise

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
