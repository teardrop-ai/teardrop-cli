"""Top-level ``teardrop usage`` command."""

from __future__ import annotations

import asyncio

import click


@click.command(name="usage", help="Show usage summary for a date range.")
@click.option("--start", default=None, help="Start date (ISO 8601, e.g. 2025-01-01).")
@click.option("--end", default=None, help="End date (ISO 8601, e.g. 2025-01-31).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--base-url", "base_url", default=None, hidden=True)
def app(start: str | None, end: str | None, as_json: bool, base_url: str | None) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_usage(start=start, end=end)
        finally:
            await client.close()

    with spinner("Fetching usage…"):
        data = asyncio.run(_fetch())

    if hasattr(data, "model_dump"):
        data = data.model_dump()

    if as_json:
        print_json(data)
        return

    rows = [
        ["Total runs", data.get("total_runs", 0)],
        ["Tokens in", data.get("total_tokens_in", 0)],
        ["Tokens out", data.get("total_tokens_out", 0)],
        ["Tool calls", data.get("total_tool_calls", 0)],
        ["Total duration (ms)", data.get("total_duration_ms", 0)],
    ]
    title = "Usage"
    if start or end:
        title = f"Usage ({start or '…'} → {end or '…'})"
    print_table(
        [("Field", {"style": "bold cyan"}), ("Value", {"justify": "right"})],
        rows,
        title=title,
    )
