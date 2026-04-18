"""tools commands: list, test."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer

app = typer.Typer(
    name="tools",
    help="Org tools — list and test.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command(name="list")
def list_tools(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List org tools."""
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

    if as_json:
        print_json([t.model_dump() for t in tools])
        return

    if not tools:
        data_console.print("[dim]No tools found.[/dim]")
        return

    rows = [
        [
            t.id,
            t.name,
            (getattr(t, "description", "") or "")[:60],
            getattr(t, "type", ""),
        ]
        for t in tools
    ]
    print_table(
        ["ID", "Name", "Description", "Type"],
        rows,
        title="Org Tools",
    )


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------


@app.command(name="test")
def test_tool(
    tool_id: Annotated[str, typer.Argument(help="Tool ID to inspect.")],
    input_json: Annotated[
        str | None,
        typer.Option(
            "--input",
            "-i",
            help="JSON object of input parameters for a dry-run validation.",
        ),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Fetch a tool definition and optionally validate input against its schema."""
    from teardrop_cli import config
    from teardrop_cli.formatting import (
        console,
        data_console,
        print_error,
        print_json,
        print_success,
        print_table,
        spinner,
    )

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_tool(tool_id)
        finally:
            await client.close()

    with spinner(f"Fetching tool [bold]{tool_id}[/bold]…"):
        tool = asyncio.run(_fetch())

    tool_data = tool.model_dump()

    if as_json:
        print_json(tool_data)
        return

    # Display tool metadata
    meta_rows = [
        [k, v] for k, v in tool_data.items() if k not in ("parameters", "schema") and v is not None
    ]
    print_table([("Field", {"style": "bold cyan"}), "Value"], meta_rows, title="Tool Definition")

    # Display parameter schema
    schema = tool_data.get("parameters") or tool_data.get("schema")
    if schema and isinstance(schema, dict):
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if props:
            param_rows = [
                [
                    name,
                    "✓" if name in required else "",
                    pdef.get("type", ""),
                    pdef.get("description", ""),
                ]
                for name, pdef in props.items()
            ]
            print_table(
                ["Parameter", "Required", "Type", "Description"],
                param_rows,
                title="Parameters",
            )

    # Optional input validation
    if input_json:
        try:
            input_data = json.loads(input_json)
        except json.JSONDecodeError as exc:
            print_error(f"Invalid JSON input: {exc}")
            raise typer.Exit(1) from None

        errors = _validate_input(schema, input_data) if schema else []
        if errors:
            print_error("Input validation failed:")
            for err in errors:
                console.print(f"  [red]•[/red] {err}")
            raise typer.Exit(1)

        print_success("Input is valid against the tool schema.")
        data_console.print_json(json.dumps(input_data, default=str))


def _validate_input(schema: dict, data: dict) -> list[str]:
    """Basic JSON Schema validation (required fields + type checks).

    Returns a list of error messages; empty list means valid.
    Does not require jsonschema — intentionally minimal.
    """
    errors: list[str] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    for field, value in data.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type and not _matches_json_type(value, expected_type):
                errors.append(
                    f"Field '{field}' expected type '{expected_type}', "
                    f"got '{type(value).__name__}'"
                )

    return errors


_JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _matches_json_type(value, json_type: str) -> bool:
    expected = _JSON_TYPE_MAP.get(json_type)
    if expected is None:
        return True  # Unknown type → no error
    # JSON Schema: integer is a subtype of number
    if json_type == "number" and isinstance(value, bool):
        return False
    if json_type == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, expected)
