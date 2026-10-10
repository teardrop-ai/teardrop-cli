"""Read-only public scorecard queries."""

from __future__ import annotations

from collections.abc import Callable
from json import JSONDecodeError
from typing import TYPE_CHECKING, Annotated, Any, TypeVar

import typer

if TYPE_CHECKING:
    from teardrop.models.scorecards import ScorecardItem

_Response = TypeVar("_Response")

app = typer.Typer(
    name="scorecards",
    help="Browse public scorecards.",
    no_args_is_help=True,
)

_SCORECARD_COLUMNS = [
    "Subject",
    "Eligible",
    ("Samples", {"justify": "right"}),
    ("Coverage", {"justify": "right"}),
    ("Adjusted Brier", {"justify": "right"}),
    ("Accuracy", {"justify": "right"}),
]


def _query_scorecards(
    base_url: str | None,
    operation: str,
    query: Callable[[Any], _Response],
) -> _Response:
    from pydantic import ValidationError as PydanticValidationError
    from teardrop import TeardropClient, TeardropError

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error

    url = base_url if base_url is not None else config.get_base_url()
    try:
        # Public scorecard queries must not inherit configured credentials.
        with TeardropClient(url) as client:
            return query(client.scorecards)
    except (JSONDecodeError, PydanticValidationError, TeardropError) as exc:
        print_error(f"Unable to {operation}: {exc}")
        raise typer.Exit(1) from exc


def _format_percentage(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:.1%}"


def _format_brier(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:.4f}"


def _scorecard_row(item: ScorecardItem) -> list[str]:
    return [
        item.subject,
        "Yes" if item.eligible else "No",
        str(item.n_scored),
        _format_percentage(item.coverage),
        _format_brier(item.adjusted_brier),
        _format_percentage(item.accuracy),
    ]


def _print_scorecard_table(rows: list[list[str]], *, title: str) -> None:
    from teardrop_cli.formatting import data_console, print_table

    print_table(_SCORECARD_COLUMNS, rows, title=title)
    data_console.print("[dim]Lower adjusted Brier is better.[/dim]")


@app.command()
def tasks(
    as_json: Annotated[
        bool, typer.Option("--json", help="Output the complete response as JSON.")
    ] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List public scorecard tasks."""
    from teardrop_cli.formatting import data_console, print_json, print_table, spinner

    with spinner("Fetching public scorecard tasks..."):
        response = _query_scorecards(
            base_url,
            "fetch scorecard tasks",
            lambda scorecards: scorecards.list_tasks(),
        )

    if as_json:
        print_json(response.model_dump(mode="json"))
        return

    if not response.items:
        data_console.print("[dim]No scorecard tasks available.[/dim]")
        return

    rows = [
        [task.definition_key, task.definition_version, task.definition_sha256[:12]]
        for task in response.items
    ]
    print_table(
        ["Definition key", "Version", "SHA-256 prefix"],
        rows,
        title="Public Scorecard Tasks",
    )


@app.command()
def leaderboard(
    definition_key: Annotated[str, typer.Argument(help="Scorecard definition key.")],
    version: Annotated[int, typer.Argument(help="Integer definition version.")],
    window_days: Annotated[
        int, typer.Option("--window-days", help="Score evaluation window in days.")
    ] = 90,
    as_json: Annotated[
        bool, typer.Option("--json", help="Output the complete response as JSON.")
    ] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show the public leaderboard for a scorecard definition."""
    from teardrop_cli.formatting import data_console, print_json, spinner

    with spinner("Fetching scorecard leaderboard..."):
        response = _query_scorecards(
            base_url,
            "fetch the scorecard leaderboard",
            lambda scorecards: scorecards.get_leaderboard(
                definition_key,
                version,
                window_days=window_days,
            ),
        )

    if as_json:
        print_json(response.model_dump(mode="json"))
        return

    if not response.items:
        data_console.print("[dim]No scorecard results available for this window.[/dim]")
        return

    _print_scorecard_table(
        [_scorecard_row(item) for item in response.items],
        title=f"Leaderboard: {definition_key} v{version} ({window_days} days)",
    )


@app.command()
def show(
    definition_key: Annotated[str, typer.Argument(help="Scorecard definition key.")],
    version: Annotated[int, typer.Argument(help="Integer definition version.")],
    subject: Annotated[str, typer.Argument(help="Subject to look up.")],
    window_days: Annotated[
        int, typer.Option("--window-days", help="Score evaluation window in days.")
    ] = 90,
    as_json: Annotated[
        bool, typer.Option("--json", help="Output the complete response as JSON.")
    ] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show one public subject scorecard."""
    from teardrop_cli.formatting import print_json, spinner

    with spinner("Fetching subject scorecard..."):
        response = _query_scorecards(
            base_url,
            "fetch the subject scorecard",
            lambda scorecards: scorecards.get_scorecard(
                definition_key,
                version,
                subject,
                window_days=window_days,
            ),
        )

    if as_json:
        print_json(response.model_dump(mode="json"))
        return

    _print_scorecard_table(
        [_scorecard_row(response.item)],
        title=f"Scorecard: {definition_key} v{version}",
    )
