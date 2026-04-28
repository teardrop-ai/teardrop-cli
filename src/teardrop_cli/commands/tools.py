"""tools commands: list, publish, info, update, pause, delete."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Annotated, Any

import typer

app = typer.Typer(
    name="tools",
    help="Org tools — publish, list, info, update, pause, delete.",
    no_args_is_help=True,
)


_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _fmt_usdc(atomic: int | None) -> str:
    if atomic is None:
        return "—"
    try:
        from teardrop import format_usdc

        return f"${float(format_usdc(int(atomic))):.4f}"
    except Exception:
        return f"${int(atomic) / 1_000_000:.4f}"


async def _resolve_tool_id(client, name: str) -> str | None:
    tools = await client.list_tools()
    for t in tools:
        if getattr(t, "name", None) == name or (
            isinstance(t, dict) and t.get("name") == name
        ):
            return getattr(t, "id", None) or t.get("id")
    return None


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_tools(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List your org's tools."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.list_tools()
        finally:
            await client.close()

    with spinner("Fetching tools…"):
        tools = asyncio.run(_fetch())

    items = [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in tools]

    if as_json:
        print_json(items)
        return

    if not items:
        data_console.print("[dim]No tools found.[/dim]")
        return

    rows = []
    for t in items:
        active = "✓" if t.get("is_active") else "✗"
        marketplace = "✓" if t.get("publish_as_mcp") else "✗"
        price = (
            _fmt_usdc(t.get("base_price_usdc")) if t.get("publish_as_mcp") else "—"
        )
        webhook = (t.get("webhook_url") or "")
        if len(webhook) > 50:
            webhook = webhook[:47] + "…"
        rows.append([t.get("name", "—"), active, marketplace, price, webhook])

    print_table(
        [
            "Name",
            ("Active", {"justify": "center"}),
            ("Marketplace", {"justify": "center"}),
            ("Price/Call", {"justify": "right"}),
            "Webhook",
        ],
        rows,
        title="Org Tools",
    )


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@app.command()
def info(
    name: Annotated[str, typer.Argument(help="Tool name.")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show full detail for one tool."""
    from teardrop_cli import config
    from teardrop_cli.formatting import data_console, print_error, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            tool_id = await _resolve_tool_id(client, name)
            if tool_id is None:
                return None
            return await client.get_tool(tool_id)
        finally:
            await client.close()

    with spinner(f"Fetching tool {name}…"):
        tool = asyncio.run(_fetch())

    if tool is None:
        print_error(f"Tool {name!r} not found.")
        raise typer.Exit(1)

    data = tool.model_dump() if hasattr(tool, "model_dump") else dict(tool)

    if as_json:
        print_json(data)
        return

    schema = data.pop("input_schema", None)
    rows = [[k, v] for k, v in data.items() if v is not None]
    print_table([("Field", {"style": "bold cyan"}), "Value"], rows, title=name)

    if schema:
        data_console.print("\n[bold]Input Schema:[/bold]")
        data_console.print_json(json.dumps(schema, default=str))


# ---------------------------------------------------------------------------
# init — scaffold tool.json
# ---------------------------------------------------------------------------


@app.command()
def init(
    name: Annotated[
        str | None,
        typer.Argument(help="Tool name (lowercase, a-z0-9_). Prompted if omitted."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", "-o", help="Output path (default: ./tool.json)."),
    ] = None,
    with_marketplace: Annotated[
        bool,
        typer.Option(
            "--with-marketplace",
            help="Include marketplace fields (publish_as_mcp, base_price_usdc, etc.).",
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing file.")
    ] = False,
) -> None:
    """Scaffold a starter ``tool.json`` ready for ``teardrop tools publish``."""
    from teardrop_cli._templates import render_tool_template
    from teardrop_cli.formatting import print_error, print_success

    if not name:
        name = typer.prompt("Tool name (lowercase, a-z0-9_)")
    if not _NAME_RE.match(name) or len(name) > 64:
        print_error(
            f"Invalid tool name {name!r}.",
            hint="Must match ^[a-z][a-z0-9_]*$ and be ≤ 64 chars.",
        )
        raise typer.Exit(1)

    target = out or Path("tool.json")
    if target.exists() and not force:
        print_error(f"{target} already exists.", hint="Pass --force to overwrite.")
        raise typer.Exit(1)

    data = render_tool_template(name, with_marketplace=with_marketplace)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print_success(f"Wrote {target}")
    print_success(
        f"Edit it, then publish with: [bold]teardrop tools publish --from-file {target}[/bold]"
    )


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


@app.command()
def publish(
    from_file: Annotated[
        Path | None,
        typer.Option(
            "--from-file",
            help="Path to a JSON file with tool definition (skips wizard).",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    settlement_wallet: Annotated[
        str | None,
        typer.Option(
            "--settlement-wallet",
            help="EIP-55 checksum address for marketplace payouts (first publish).",
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Publish a new tool — interactive wizard or ``--from-file``."""
    from teardrop import ConflictError, CreateOrgToolRequest

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_json, print_success, spinner

    if from_file:
        try:
            data: dict[str, Any] = json.loads(Path(from_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print_error(f"Invalid JSON in {from_file}: {exc}")
            raise typer.Exit(1) from None
    else:
        data = _publish_wizard()

    name = data.get("name", "")
    if not _NAME_RE.match(name) or len(name) > 64:
        print_error(
            f"Invalid tool name {name!r}.",
            hint="Must match ^[a-z][a-z0-9_]*$ and be ≤ 64 chars.",
        )
        raise typer.Exit(1)

    try:
        request = CreateOrgToolRequest(**data)
    except Exception as exc:
        print_error(f"Validation error: {exc}")
        raise typer.Exit(1) from None

    client = config.get_client(base_url)

    async def _do():
        try:
            if settlement_wallet:
                await client.set_author_config(settlement_wallet)
            return await client.create_tool(request)
        finally:
            await client.close()

    try:
        with spinner("Publishing tool…"):
            tool = asyncio.run(_do())
    except ConflictError:
        print_error(
            f"Tool name {name!r} already exists.", hint="Choose a different name."
        )
        raise typer.Exit(1) from None

    info = tool.model_dump() if hasattr(tool, "model_dump") else dict(tool)
    if as_json:
        print_json(info)
        return

    print_success(f"Tool registered: {info.get('name', name)} (id: {info.get('id', '?')})")
    if settlement_wallet:
        print_success(f"Settlement wallet configured: {settlement_wallet}")


def _publish_wizard() -> dict[str, Any]:
    """Interactive prompts; returns dict ready for ``CreateOrgToolRequest``."""
    from teardrop import parse_usdc

    name = typer.prompt("Tool name (lowercase, a-z0-9_)")
    description = typer.prompt("Description")
    webhook_url = typer.prompt("Webhook URL (HTTPS)")
    auth_header_name = typer.prompt("Webhook auth header name [optional]", default="", show_default=False)
    auth_header_value = ""
    if auth_header_name:
        auth_header_value = typer.prompt("Webhook auth header value", hide_input=True)
    timeout = typer.prompt("Timeout seconds [default 10, max 30]", default=10, type=int)
    publish_as_mcp = typer.confirm("Publish to marketplace?", default=False)
    marketplace_description = ""
    base_price_atomic = 0
    if publish_as_mcp:
        marketplace_description = typer.prompt("Marketplace description")
        price_str = typer.prompt("Price per call (e.g. 0.005)", default="0.001")
        base_price_atomic = parse_usdc(price_str)

    schema_input = typer.prompt(
        "Input schema JSON file path (or '-' for inline minimal schema)",
        default="-",
    )
    if schema_input == "-":
        input_schema: dict[str, Any] = {"type": "object", "properties": {}}
    else:
        input_schema = json.loads(Path(schema_input).read_text(encoding="utf-8"))

    data: dict[str, Any] = {
        "name": name,
        "description": description,
        "webhook_url": webhook_url,
        "input_schema": input_schema,
        "timeout_seconds": int(timeout),
        "publish_as_mcp": publish_as_mcp,
    }
    if auth_header_name:
        data["auth_header_name"] = auth_header_name
        data["auth_header_value"] = auth_header_value
    if publish_as_mcp:
        data["marketplace_description"] = marketplace_description
        data["base_price_usdc"] = base_price_atomic
    return data


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@app.command()
def update(
    name: Annotated[str, typer.Argument(help="Tool name.")],
    description: Annotated[str | None, typer.Option("--description")] = None,
    webhook_url: Annotated[str | None, typer.Option("--webhook-url")] = None,
    price: Annotated[
        float | None,
        typer.Option("--price", help="Price per call in dollars (e.g. 0.005)."),
    ] = None,
    marketplace_desc: Annotated[
        str | None, typer.Option("--marketplace-desc", help="Marketplace description.")
    ] = None,
    publish: Annotated[
        bool | None,
        typer.Option("--publish/--no-publish", help="Toggle marketplace publication."),
    ] = None,
    timeout: Annotated[int | None, typer.Option("--timeout", help="Timeout seconds.")] = None,
    active: Annotated[
        bool | None, typer.Option("--active/--no-active", help="Activate or pause the tool.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Update one or more tool fields."""
    from teardrop import UpdateOrgToolRequest, parse_usdc

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_json, print_success, spinner

    payload: dict[str, Any] = {}
    if description is not None:
        payload["description"] = description
    if webhook_url is not None:
        payload["webhook_url"] = webhook_url
    if price is not None:
        payload["base_price_usdc"] = parse_usdc(str(price))
    if marketplace_desc is not None:
        payload["marketplace_description"] = marketplace_desc
    if publish is not None:
        payload["publish_as_mcp"] = publish
    if timeout is not None:
        payload["timeout_seconds"] = timeout
    if active is not None:
        payload["is_active"] = active

    if not payload:
        print_error("No fields to update. Provide at least one --flag.")
        raise typer.Exit(1)

    client = config.get_client(base_url)

    async def _do():
        try:
            tool_id = await _resolve_tool_id(client, name)
            if tool_id is None:
                return None
            return await client.update_tool(tool_id, UpdateOrgToolRequest(**payload))
        finally:
            await client.close()

    with spinner(f"Updating {name}…"):
        result = asyncio.run(_do())

    if result is None:
        print_error(f"Tool {name!r} not found.")
        raise typer.Exit(1)

    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    if as_json:
        print_json(data)
        return

    print_success(f"Updated {name}.")


# ---------------------------------------------------------------------------
# pause
# ---------------------------------------------------------------------------


@app.command()
def pause(
    name: Annotated[str, typer.Argument(help="Tool name.")],
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Pause a tool (sets is_active=False)."""
    from teardrop import UpdateOrgToolRequest

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_success, spinner

    client = config.get_client(base_url)

    async def _do():
        try:
            tool_id = await _resolve_tool_id(client, name)
            if tool_id is None:
                return False
            await client.update_tool(tool_id, UpdateOrgToolRequest(is_active=False))
            return True
        finally:
            await client.close()

    with spinner(f"Pausing {name}…"):
        ok = asyncio.run(_do())

    if not ok:
        print_error(f"Tool {name!r} not found.")
        raise typer.Exit(1)

    print_success(
        f"{name} paused. Run `teardrop tools update {name} --active` to re-enable."
    )


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@app.command()
def delete(
    name: Annotated[str, typer.Argument(help="Tool name.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Delete a tool (soft-delete; subscribers lose access)."""
    from teardrop_cli import config
    from teardrop_cli.formatting import confirm, print_error, print_success, spinner

    if not yes and not confirm(
        f"Delete tool {name!r}? Subscribers will lose access."
    ):
        raise typer.Abort()

    client = config.get_client(base_url)

    async def _do():
        try:
            tool_id = await _resolve_tool_id(client, name)
            if tool_id is None:
                return False
            await client.delete_tool(tool_id)
            return True
        finally:
            await client.close()

    with spinner(f"Deleting {name}…"):
        ok = asyncio.run(_do())

    if not ok:
        print_error(f"Tool {name!r} not found.")
        raise typer.Exit(1)

    print_success(f"Deleted {name}.")
