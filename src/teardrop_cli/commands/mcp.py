"""mcp commands: list, add, discover, remove."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

app = typer.Typer(
    name="mcp",
    help="MCP servers — list, add, discover tools, and remove.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_servers(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List connected MCP servers."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.list_mcp_servers()
        finally:
            await client.close()

    with spinner("Fetching MCP servers…"):
        servers = asyncio.run(_fetch())

    if as_json:
        print_json([s.model_dump() for s in servers])
        return

    if not servers:
        data_console.print("[dim]No MCP servers configured.[/dim]")
        return

    rows = [
        [
            s.id,
            s.name,
            getattr(s, "url", ""),
            getattr(s, "auth_type", ""),
            str(len(getattr(s, "tools", []) or [])),
        ]
        for s in servers
    ]
    print_table(
        ["ID", "Name", "URL", "Auth Type", "Tools"],
        rows,
        title="MCP Servers",
    )


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


@app.command()
def add(
    name: Annotated[str, typer.Option("--name", "-n", help="Server name.")],
    url: Annotated[str, typer.Option("--url", "-u", help="Server URL.")],
    auth_type: Annotated[
        str | None,
        typer.Option("--auth-type", help="Auth type (e.g. none, bearer, basic)."),
    ] = None,
    auth_token: Annotated[
        str | None,
        typer.Option("--auth-token", help="Auth token / secret.", hide_input=True),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Add a new MCP server."""
    from teardrop import CreateMcpServerRequest

    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_success, print_table, spinner

    req_kwargs: dict = {"name": name, "url": url}
    if auth_type:
        req_kwargs["auth_type"] = auth_type
    if auth_token:
        req_kwargs["auth_token"] = auth_token

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.create_mcp_server(CreateMcpServerRequest(**req_kwargs))
        finally:
            await client.close()

    with spinner(f"Adding MCP server [bold]{name}[/bold]…"):
        server = asyncio.run(_fetch())

    if as_json:
        print_json(server.model_dump())
        return

    print_success(f"MCP server [bold]{server.name}[/bold] added (id: {server.id}).")
    rows = [[k, v] for k, v in server.model_dump().items() if v is not None]
    print_table([("Field", {"style": "bold cyan"}), "Value"], rows, title="New MCP Server")


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


@app.command()
def discover(
    server_id: Annotated[str, typer.Argument(help="MCP server ID.")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Discover tools exposed by an MCP server."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.discover_mcp_server_tools(server_id)
        finally:
            await client.close()

    with spinner(f"Discovering tools for [bold]{server_id}[/bold]…"):
        result = asyncio.run(_fetch())

    tools = getattr(result, "tools", []) or []

    if as_json:
        data = result.model_dump() if hasattr(result, "model_dump") else {"tools": tools}
        print_json(data)
        return

    if not tools:
        data_console.print("[dim]No tools discovered.[/dim]")
        return

    rows = [
        [
            getattr(t, "name", ""),
            getattr(t, "description", ""),
            str(len(getattr(t, "parameters", {}).get("properties", {})))
            if isinstance(getattr(t, "parameters", None), dict)
            else "—",
        ]
        for t in tools
    ]
    print_table(
        ["Name", "Description", "Params"],
        rows,
        title=f"Tools on {server_id}",
    )


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


@app.command()
def remove(
    server_id: Annotated[str, typer.Argument(help="MCP server ID to remove.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Remove an MCP server."""
    from teardrop_cli import config
    from teardrop_cli.formatting import confirm, print_success, spinner

    if not yes and not confirm(f"Remove MCP server [bold]{server_id}[/bold]?"):
        raise typer.Abort()

    client = config.get_client(base_url)

    async def _fetch():
        try:
            await client.delete_mcp_server(server_id)
        finally:
            await client.close()

    with spinner(f"Removing [bold]{server_id}[/bold]…"):
        asyncio.run(_fetch())

    print_success(f"MCP server [bold]{server_id}[/bold] removed.")
