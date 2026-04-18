"""models commands: benchmarks."""

from __future__ import annotations

import asyncio
from typing import Annotated, Optional

import typer

app = typer.Typer(
    name="models",
    help="Model catalogue and benchmarks.",
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """Model catalogue and benchmarks."""


# ---------------------------------------------------------------------------
# benchmarks
# ---------------------------------------------------------------------------


@app.command()
def benchmarks(
    org: Annotated[
        Optional[str],
        typer.Option("--org", help="Org ID for org-scoped metrics (requires auth)."),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", "--force-refresh", help="Bypass the local 10-minute cache."),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[Optional[str], typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Display model catalogue with operational metrics.

    Without --org: public benchmarks (no auth required).
    With --org ORG_ID: org-scoped metrics (auth required).
    """
    from teardrop import AuthenticationError

    from teardrop_cli import config
    from teardrop_cli.formatting import (
        console,
        data_console,
        print_error,
        print_json,
        print_table,
        spinner,
    )

    client = config.get_client(base_url)

    try:
        async def _fetch():
            try:
                if org:
                    return await client.get_org_model_benchmarks(org_id=org)
                else:
                    return await client.get_model_benchmarks(no_cache=no_cache)
            finally:
                await client.close()

        label = "Fetching org model benchmarks…" if org else "Fetching model benchmarks…"
        with spinner(label):
            response = asyncio.run(_fetch())
    except AuthenticationError:
        print_error(
            "Not authenticated.",
            hint="Run: `teardrop auth login`",
        )
        raise typer.Exit(1)
    except Exception as exc:
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status == 401:
            print_error("Not authenticated.", hint="Run: `teardrop auth login`")
            raise typer.Exit(1)
        print_error(f"Unexpected error: {exc}")
        raise typer.Exit(1)

    data = response if isinstance(response, dict) else response.model_dump()
    models_list: list[dict] = data.get("models", [])

    if as_json:
        print_json(data)
        return

    if not models_list:
        if org:
            data_console.print(
                f"[dim]No benchmark data for {org}. Run some agent tasks first.[/dim]"
            )
        else:
            data_console.print("[dim]No benchmark data available.[/dim]")
        return

    if org:
        _print_org_benchmarks(models_list, org_id=org)
    else:
        _print_public_benchmarks(models_list)


# ---------------------------------------------------------------------------
# Internal renderers
# ---------------------------------------------------------------------------


def _print_public_benchmarks(models: list[dict]) -> None:
    """Render the global model catalogue table."""
    from teardrop_cli.formatting import print_table

    rows = []
    for m in models:
        benchmarks = m.get("benchmarks") or {}
        pricing = m.get("pricing") or {}
        p95 = benchmarks.get("p95_latency_ms")
        cost_in = pricing.get("tokens_in_cost_per_1k")
        cost_out = pricing.get("tokens_out_cost_per_1k")
        runs = benchmarks.get("total_runs_7d")

        rows.append(
            [
                m.get("provider", "—"),
                m.get("model", "—"),
                m.get("display_name", "—"),
                str(m.get("quality_tier", "—")),
                f"{int(p95)} ms" if p95 is not None else "—",
                f"${cost_in:.4f}/1k" if cost_in is not None else "—",
                f"${cost_out:.4f}/1k" if cost_out is not None else "—",
                str(runs) if runs is not None else "—",
            ]
        )

    print_table(
        [
            "Provider",
            "Model",
            "Display Name",
            ("Quality", {"justify": "right"}),
            ("Latency P95", {"justify": "right"}),
            ("Cost (in)", {"justify": "right"}),
            ("Cost (out)", {"justify": "right"}),
            ("Runs 7d", {"justify": "right"}),
        ],
        rows,
        title="Model Catalogue",
    )


def _print_org_benchmarks(models: list[dict], *, org_id: str) -> None:
    """Render the org-scoped benchmark table."""
    from teardrop_cli.formatting import data_console, print_table

    data_console.print(
        f"[bold]Your org's model usage (7-day aggregate) — {org_id}[/bold]"
    )

    rows = []
    for m in models:
        b = m.get("benchmarks") or {}
        runs = b.get("total_runs_7d")
        avg_cost = b.get("avg_cost_usdc_per_run")
        total_cost = (runs * avg_cost) if (runs is not None and avg_cost is not None) else None
        rows.append(
            [
                m.get("provider", "—"),
                m.get("model", "—"),
                str(runs) if runs is not None else "—",
                f"{b.get('avg_latency_ms', '—')} ms" if b.get("avg_latency_ms") is not None else "—",
                f"${avg_cost:.2f}" if avg_cost is not None else "—",
                f"${total_cost:.2f}" if total_cost is not None else "—",
                f"{b.get('avg_tokens_per_sec', '—'):.1f}" if b.get("avg_tokens_per_sec") is not None else "—",
            ]
        )

    print_table(
        [
            "Provider",
            "Model",
            ("Runs", {"justify": "right"}),
            ("Avg Latency", {"justify": "right"}),
            ("Avg Cost/Run", {"justify": "right"}),
            ("Total Cost", {"justify": "right"}),
            ("Tokens/sec", {"justify": "right"}),
        ],
        rows,
    )
