"""schedules commands: create, list, get, update, delete, runs."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any

import typer

app = typer.Typer(
    name="schedules",
    help="Interval schedules — create, list, inspect, update, delete, and view runs.",
    no_args_is_help=True,
)


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _list_items(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("items") or []
    items = getattr(value, "items", None)
    if items is not None and not callable(items):
        return items
    return value


def _read_prompt_file(path: str) -> str:
    """Read prompt text from *path* (UTF-8), or stdin when *path* is ``-``."""
    from teardrop_cli.formatting import print_error

    try:
        if path == "-":
            return sys.stdin.read()
        text = Path(path).read_text(encoding="utf-8-sig")
        return text
    except UnicodeError as exc:
        print_error(f"Could not decode --prompt-file {path!r} as UTF-8: {exc}")
        raise typer.Exit(1) from None
    except OSError as exc:
        print_error(f"Could not read --prompt-file {path!r}: {exc}")
        raise typer.Exit(1) from None


def _to_page_dict(value: Any) -> dict[str, Any]:
    data = _to_dict(value)
    data["items"] = [_to_dict(item) for item in data.get("items") or []]
    return data


def _fmt_usdc(atomic: int | None) -> str:
    if atomic is None:
        return "—"
    return f"${int(atomic) / 1_000_000:.4f}"


def _fmt_interval(interval_seconds: int | None) -> str:
    if interval_seconds is None:
        return "—"
    return f"{int(interval_seconds)}s"


def _fmt_enabled(enabled: bool | None) -> str:
    if enabled is None:
        return "—"
    return "Yes" if enabled else "No"


def _print_schedule_detail(data: dict[str, Any]) -> None:
    from teardrop_cli.formatting import print_table

    rows = [
        ["ID", data.get("id") or "—"],
        ["Name", data.get("name") or "—"],
        ["Prompt", data.get("prompt") or "—"],
        ["Kind", data.get("schedule_kind") or "—"],
        ["Interval", _fmt_interval(data.get("interval_seconds"))],
        ["Enabled", _fmt_enabled(data.get("enabled"))],
        ["Callback URL", data.get("callback_url") or "—"],
        ["Next Run At", data.get("next_run_at") or "—"],
        ["Last Run At", data.get("last_run_at") or "—"],
        ["Consecutive Failures", data.get("consecutive_failures", 0)],
        ["Created At", data.get("created_at") or "—"],
        ["Updated At", data.get("updated_at") or "—"],
    ]
    title = f"Schedule: {data.get('name') or data.get('id') or 'Schedule'}"
    print_table([("Field", {"style": "bold cyan"}), "Value"], rows, title=title)


async def _call_and_close(
    client: Any,
    operation: Callable[[Any], Awaitable[Any]],
) -> Any:
    try:
        return await operation(client)
    finally:
        await client.close()


def _run_authenticated(
    spinner_message: str,
    base_url: str | None,
    *,
    allow_prompt_login: bool,
    operation: Callable[[Any], Awaitable[Any]],
) -> Any:
    from teardrop_cli import config
    from teardrop_cli.formatting import handle_token_expiry, spinner

    def _call_once() -> Any:
        client = config.get_client(base_url)
        return asyncio.run(_call_and_close(client, operation))

    try:
        with spinner(spinner_message):
            return _call_once()
    except Exception as exc:
        action = asyncio.run(
            handle_token_expiry(
                exc,
                base_url,
                allow_prompt_login=allow_prompt_login,
            )
        )
        if action == "retry":
            with spinner(spinner_message):
                return _call_once()
        if action == "prompt_login":
            from teardrop_cli.commands.auth import interactive_reauthenticate

            if not interactive_reauthenticate(base_url=base_url):
                raise typer.Exit(1) from None
            with spinner(spinner_message):
                return _call_once()
        if action == "fail":
            raise typer.Exit(1) from None
        raise


def _validate_callback_options(
    callback_url: str | None,
    clear_callback_url: bool,
) -> None:
    from teardrop_cli.formatting import print_error

    if callback_url is not None and clear_callback_url:
        print_error("Use either --callback-url or --clear-callback-url, not both.")
        raise typer.Exit(1) from None


@app.command()
def create(
    name: Annotated[str, typer.Option("--name", help="Schedule name.")],
    interval_seconds: Annotated[
        int,
        typer.Option("--interval-seconds", min=1, help="Run interval in seconds."),
    ],
    prompt: Annotated[
        str | None,
        typer.Option("--prompt", help="Prompt to run. Mutually exclusive with --prompt-file."),
    ] = None,
    prompt_file: Annotated[
        str | None,
        typer.Option(
            "--prompt-file",
            help="Read the prompt from a UTF-8 file. Use '-' to read from stdin. "
            "Mutually exclusive with --prompt.",
        ),
    ] = None,
    callback_url: Annotated[
        str | None,
        typer.Option("--callback-url", help="Optional callback URL invoked after each run."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Create a new interval schedule."""
    from teardrop import CreateScheduleRequest

    from teardrop_cli.formatting import print_error, print_json, print_success

    if prompt is not None and prompt_file is not None:
        print_error("Use either --prompt or --prompt-file, not both.")
        raise typer.Exit(1) from None
    if prompt is None and prompt_file is None:
        print_error("Provide either --prompt or --prompt-file.")
        raise typer.Exit(1) from None
    if prompt_file is not None:
        prompt = _read_prompt_file(prompt_file)

    request = CreateScheduleRequest(
        name=name,
        prompt=prompt,
        interval_seconds=interval_seconds,
        callback_url=callback_url,
    )
    result = _run_authenticated(
        f"Creating schedule [bold]{name}[/bold]…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.schedules.create(request),
    )

    data = _to_dict(result)
    if as_json:
        print_json(data)
        return
    print_success(f"Schedule created: {data.get('name', name)} ({data.get('id', '?')})")
    _print_schedule_detail(data)


@app.command(name="list")
def list_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List schedules."""
    from teardrop_cli.formatting import data_console, print_json, print_table

    result = _run_authenticated(
        "Fetching schedules…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.schedules.list(),
    )

    # The SDK returns a ScheduledRunListResponse model with an ``items``
    # field (plus ``next_cursor``). Iterating the model directly would yield
    # its field tuples, so unwrap ``.items`` when present.
    items = [_to_dict(item) for item in _list_items(result)]
    if as_json:
        print_json(items)
        return

    if not items:
        data_console.print("[dim]No schedules found.[/dim]")
        return

    rows = [
        [
            item.get("id") or "—",
            item.get("name") or "—",
            _fmt_enabled(item.get("enabled")),
            _fmt_interval(item.get("interval_seconds")),
            item.get("consecutive_failures", 0),
            item.get("last_run_at") or "—",
        ]
        for item in items
    ]
    print_table(
        ["ID", "Name", "Enabled", "Interval", "Consecutive Failures", "Last Run At"],
        rows,
        title="Interval Schedules",
    )


@app.command()
def get(
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID.")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show one schedule."""
    from teardrop_cli.formatting import print_json

    result = _run_authenticated(
        f"Fetching schedule [bold]{schedule_id}[/bold]…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.schedules.get(schedule_id),
    )

    data = _to_dict(result)
    if as_json:
        print_json(data)
        return

    _print_schedule_detail(data)


@app.command()
def update(
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID.")],
    name: Annotated[str | None, typer.Option("--name", help="Updated schedule name.")] = None,
    prompt: Annotated[str | None, typer.Option("--prompt", help="Updated prompt.")] = None,
    interval_seconds: Annotated[
        int | None,
        typer.Option("--interval-seconds", min=1, help="Updated run interval in seconds."),
    ] = None,
    enabled: Annotated[
        bool | None,
        typer.Option("--enabled", help="Set enabled to true or false."),
    ] = None,
    callback_url: Annotated[
        str | None,
        typer.Option("--callback-url", help="Updated callback URL."),
    ] = None,
    clear_callback_url: Annotated[
        bool,
        typer.Option("--clear-callback-url", help="Clear the callback URL."),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Update one or more schedule fields."""
    from teardrop import UpdateScheduleRequest

    from teardrop_cli.formatting import print_error, print_json, print_success

    _validate_callback_options(callback_url, clear_callback_url)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if prompt is not None:
        payload["prompt"] = prompt
    if interval_seconds is not None:
        payload["interval_seconds"] = interval_seconds
    if enabled is not None:
        payload["enabled"] = enabled
    if clear_callback_url:
        payload["callback_url"] = None
    elif callback_url is not None:
        payload["callback_url"] = callback_url

    if not payload:
        print_error("No fields to update. Provide at least one --flag.")
        raise typer.Exit(1) from None

    request = UpdateScheduleRequest(**payload)
    result = _run_authenticated(
        f"Updating schedule [bold]{schedule_id}[/bold]…",
        base_url,
        allow_prompt_login=True,
        operation=lambda client: client.schedules.update(schedule_id, request),
    )

    data = _to_dict(result)
    if as_json:
        print_json(data)
        return
    print_success(
        f"Updated schedule: {data.get('name', schedule_id)} ({data.get('id', schedule_id)})"
    )
    _print_schedule_detail(data)


@app.command()
def delete(
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID to delete.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Delete a schedule."""
    from teardrop_cli.formatting import confirm, print_success

    if not yes and not confirm(f"Delete schedule [bold]{schedule_id}[/bold]?"):
        raise typer.Abort()

    _run_authenticated(
        f"Deleting schedule [bold]{schedule_id}[/bold]…",
        base_url,
        allow_prompt_login=True,
        operation=lambda client: client.schedules.delete(schedule_id),
    )
    print_success(f"Deleted schedule {schedule_id}.")


@app.command()
def runs(
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID.")],
    limit: Annotated[int, typer.Option("--limit", min=1, help="Max runs to return.")] = 20,
    cursor: Annotated[
        str | None,
        typer.Option("--cursor", help="Pagination cursor from a previous response."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show recent runs for a schedule."""
    from teardrop_cli.formatting import data_console, print_json, print_table

    result = _run_authenticated(
        f"Fetching runs for [bold]{schedule_id}[/bold]…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.schedules.runs(
            schedule_id,
            limit=limit,
            cursor=cursor,
        ),
    )

    data = _to_page_dict(result)
    if as_json:
        print_json(data)
        return

    items = data.get("items") or []
    if not items:
        data_console.print("[dim]No schedule runs found.[/dim]")
        return

    rows = [
        [
            item.get("run_id") or item.get("id") or "—",
            item.get("status") or "—",
            _fmt_usdc(item.get("cost_usdc")),
            item.get("error") or item.get("error_message") or "—",
            item.get("created_at") or item.get("executed_at") or "—",
        ]
        for item in items
    ]
    print_table(
        [
            "Run ID",
            "Status",
            ("Cost (USDC)", {"justify": "right"}),
            "Error Message",
            "Executed At",
        ],
        rows,
        title=f"Runs: {schedule_id}",
    )
    if data.get("next_cursor"):
        data_console.print(
            f"[dim]More results available. Use --cursor {data['next_cursor']!r} to fetch the next page.[/dim]"
        )
