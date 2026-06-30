"""event trigger commands: create, list, get, update, delete, rotate-secret, runs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import typer

app = typer.Typer(
    name="event-triggers",
    help="Event triggers — create, inspect, rotate secrets, and view run history.",
    no_args_is_help=True,
)


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _to_page_dict(value: Any) -> dict[str, Any]:
    data = _to_dict(value)
    data["items"] = [_to_dict(item) for item in data.get("items") or []]
    return data


def _fmt_usdc(atomic: int | None) -> str:
    if atomic is None:
        return "—"
    return f"${int(atomic) / 1_000_000:.4f}"


def _fmt_enabled(enabled: bool | None) -> str:
    if enabled is None:
        return "—"
    return "Yes" if enabled else "No"


def _event_endpoint(data: dict[str, Any], base_url: str | None) -> str | None:
    from teardrop_cli import config

    path = data.get("event_path")
    root = (base_url or config.get_base_url()).rstrip("/")
    if isinstance(path, str) and path:
        if path.startswith(("http://", "https://")):
            return path
        if path.startswith("/"):
            return f"{root}{path}"
        return f"{root}/{path}"

    token = data.get("trigger_token")
    if token:
        return f"{root}/agent/events/{token}"

    return None


def _print_event_detail(data: dict[str, Any], base_url: str | None) -> None:
    from teardrop_cli.formatting import print_table

    rows = [
        ["ID", data.get("id") or "—"],
        ["Name", data.get("name") or "—"],
        ["Prompt", data.get("prompt") or "—"],
        ["Kind", data.get("schedule_kind") or "—"],
        ["Enabled", _fmt_enabled(data.get("enabled"))],
        ["Callback URL", data.get("callback_url") or "—"],
        ["Public Endpoint", _event_endpoint(data, base_url) or "—"],
        ["Consecutive Failures", data.get("consecutive_failures", 0)],
        ["Last Run At", data.get("last_run_at") or "—"],
        ["Created At", data.get("created_at") or "—"],
        ["Updated At", data.get("updated_at") or "—"],
    ]
    title = f"Event Trigger: {data.get('name') or data.get('id') or 'Trigger'}"
    print_table([("Field", {"style": "bold cyan"}), "Value"], rows, title=title)


def _print_secret_output(
    headline: str,
    data: dict[str, Any],
    secret: str,
    base_url: str | None,
) -> None:
    from teardrop_cli.formatting import console

    console.print(
        f"[bold green]✓[/bold green] {headline}: {data.get('name', '—')} ({data.get('id', '—')})"
    )
    endpoint = _event_endpoint(data, base_url)
    if endpoint:
        console.print(f"  Public endpoint: POST {endpoint}")
    console.print(f"  Secret (store securely now; only shown once): {secret}")


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


def _extract_secret(payload: dict[str, Any]) -> str:
    return (
        payload.get("secret")
        or payload.get("signing_secret")
        or payload.get("rotated_secret")
        or "—"
    )


@app.command()
def create(
    name: Annotated[str, typer.Option("--name", help="Trigger name.")],
    prompt: Annotated[str, typer.Option("--prompt", help="Prompt to run.")],
    callback_url: Annotated[
        str | None,
        typer.Option("--callback-url", help="Optional callback URL invoked after each run."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Create a new event trigger."""
    from teardrop import CreateEventTriggerRequest

    from teardrop_cli.formatting import print_json

    request = CreateEventTriggerRequest(
        name=name,
        prompt=prompt,
        callback_url=callback_url,
    )
    result = _run_authenticated(
        f"Registering event trigger [bold]{name}[/bold]…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.event_triggers.create(request),
    )

    data = _to_dict(result)
    if as_json:
        # Output EventTriggerWithSecret shape — secret field is present only here.
        print_json(data)
        return
    _print_secret_output(
        "Event trigger registered",
        data,
        _extract_secret(data),
        base_url,
    )


@app.command(name="list")
def list_cmd(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """List event triggers."""
    from teardrop_cli.formatting import data_console, print_json, print_table

    result = _run_authenticated(
        "Fetching event triggers…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.event_triggers.list(),
    )

    items = [_to_dict(item) for item in result]
    if as_json:
        print_json(items)
        return

    if not items:
        data_console.print("[dim]No event triggers found.[/dim]")
        return

    rows = [
        [
            item.get("id") or "—",
            item.get("name") or "—",
            _fmt_enabled(item.get("enabled")),
            item.get("schedule_kind") or "—",
            item.get("consecutive_failures", 0),
            item.get("last_run_at") or "—",
        ]
        for item in items
    ]
    print_table(
        ["ID", "Name", "Enabled", "Kind", "Consecutive Failures", "Last Run At"],
        rows,
        title="Event Triggers",
    )


@app.command()
def get(
    trigger_id: Annotated[str, typer.Argument(help="Event trigger ID.")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show one event trigger."""
    from teardrop_cli.formatting import print_json

    result = _run_authenticated(
        f"Fetching event trigger [bold]{trigger_id}[/bold]…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.event_triggers.get(trigger_id),
    )

    data = _to_dict(result)
    if as_json:
        print_json(data)
        return

    _print_event_detail(data, base_url)


@app.command()
def update(
    trigger_id: Annotated[str, typer.Argument(help="Event trigger ID.")],
    name: Annotated[str | None, typer.Option("--name", help="Updated trigger name.")] = None,
    prompt: Annotated[str | None, typer.Option("--prompt", help="Updated prompt.")] = None,
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
    """Update one or more event trigger fields."""
    from teardrop import UpdateEventTriggerRequest

    from teardrop_cli.formatting import print_error, print_json, print_success

    _validate_callback_options(callback_url, clear_callback_url)

    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if prompt is not None:
        payload["prompt"] = prompt
    if enabled is not None:
        payload["enabled"] = enabled
    if clear_callback_url:
        payload["callback_url"] = None
    elif callback_url is not None:
        payload["callback_url"] = callback_url

    if not payload:
        print_error("No fields to update. Provide at least one --flag.")
        raise typer.Exit(1) from None

    request = UpdateEventTriggerRequest(**payload)
    result = _run_authenticated(
        f"Updating event trigger [bold]{trigger_id}[/bold]…",
        base_url,
        allow_prompt_login=True,
        operation=lambda client: client.event_triggers.update(trigger_id, request),
    )

    data = _to_dict(result)
    if as_json:
        # Standard EventTrigger shape — no secret field.
        print_json(data)
        return
    print_success(
        f"Updated event trigger: {data.get('name', trigger_id)} ({data.get('id', trigger_id)})"
    )
    _print_event_detail(data, base_url)


@app.command()
def delete(
    trigger_id: Annotated[str, typer.Argument(help="Event trigger ID to delete.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Delete an event trigger."""
    from teardrop_cli.formatting import confirm, print_success

    if not yes and not confirm(f"Delete event trigger [bold]{trigger_id}[/bold]?"):
        raise typer.Abort()

    _run_authenticated(
        f"Deleting event trigger [bold]{trigger_id}[/bold]…",
        base_url,
        allow_prompt_login=True,
        operation=lambda client: client.event_triggers.delete(trigger_id),
    )
    print_success(f"Deleted event trigger {trigger_id}.")


@app.command(name="rotate-secret")
def rotate_secret(
    trigger_id: Annotated[str, typer.Argument(help="Event trigger ID.")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Rotate an event trigger signing secret."""
    from teardrop_cli.formatting import print_json

    async def _rotate(client: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        trigger = await client.event_triggers.get(trigger_id)
        payload = await client.event_triggers.rotate_secret(trigger_id)
        return _to_dict(trigger), _to_dict(payload)

    trigger_data, secret_data = _run_authenticated(
        f"Rotating secret for [bold]{trigger_id}[/bold]…",
        base_url,
        allow_prompt_login=not as_json,
        operation=_rotate,
    )

    if as_json:
        # Rotation model: id + new plaintext secret only.
        print_json(
            {"id": trigger_data.get("id", trigger_id), "secret": _extract_secret(secret_data)}
        )
        return

    merged = dict(trigger_data)
    merged.update(secret_data)
    _print_secret_output(
        "Event trigger secret rotated",
        merged,
        _extract_secret(secret_data),
        base_url,
    )


@app.command()
def runs(
    trigger_id: Annotated[str, typer.Argument(help="Event trigger ID.")],
    limit: Annotated[int, typer.Option("--limit", min=1, help="Max runs to return.")] = 20,
    cursor: Annotated[
        str | None,
        typer.Option("--cursor", help="Pagination cursor from a previous response."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Show recent runs for an event trigger."""
    from teardrop_cli.formatting import data_console, print_json, print_table

    result = _run_authenticated(
        f"Fetching runs for [bold]{trigger_id}[/bold]…",
        base_url,
        allow_prompt_login=not as_json,
        operation=lambda client: client.event_triggers.runs(
            trigger_id,
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
        data_console.print("[dim]No event-trigger runs found.[/dim]")
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
        title=f"Runs: {trigger_id}",
    )
    if data.get("next_cursor"):
        data_console.print(
            f"[dim]More results available. Use --cursor {data['next_cursor']!r} to fetch the next page.[/dim]"
        )
