"""Top-level ``teardrop run`` command — execute an agent message."""

from __future__ import annotations

import asyncio
import json as _json
from pathlib import Path

import click


@click.command(name="run", help="Run an agent message (streaming by default).")
@click.argument("message", required=True)
@click.option("--thread", "thread", default=None, help="Continue an existing thread by id.")
@click.option(
    "--context",
    "context_json",
    default=None,
    help="JSON object of context fields to attach.",
)
@click.option(
    "--no-stream",
    is_flag=True,
    default=False,
    help="Disable streaming; print final reply only.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Output as JSON (implies --no-stream).",
)
@click.option("--base-url", "base_url", default=None, hidden=True)
@click.option(
    "--with-ui",
    "with_ui",
    is_flag=True,
    default=False,
    help="Include UI component generation (emit_ui=True). Adds ~60s but provides structured ui_components in output.",
)
@click.option(
    "--policy-file",
    "policy_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to a JSON file defining tool execution policy.",
)
@click.option(
    "--exclude",
    "exclude_names",
    default=None,
    multiple=True,
    help="Exclude a tool by name (may be specified multiple times).",
)
@click.option(
    "--estimate-cost",
    is_flag=True,
    default=False,
    help="Show estimated cost from current pricing/config (no run performed).",
)
def app(
    message: str,
    thread: str | None,
    context_json: str | None,
    no_stream: bool,
    as_json: bool,
    base_url: str | None,
    with_ui: bool,
    policy_file: str | None,
    exclude_names: tuple[str, ...] | None,
    estimate_cost: bool,
) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_error, print_json

    context: dict | None = None
    if context_json:
        try:
            context = _json.loads(context_json)
        except _json.JSONDecodeError as exc:
            print_error(f"Invalid --context JSON: {exc}")
            raise click.exceptions.Exit(2) from None
        if not isinstance(context, dict):
            print_error("--context must be a JSON object.")
            raise click.exceptions.Exit(2)

    # --- Resolve tool policy ---
    tool_policy = None
    if policy_file:
        try:
            raw = _json.loads(Path(policy_file).read_text(encoding="utf-8"))
        except _json.JSONDecodeError as exc:
            print_error(f"Invalid JSON in --policy-file: {exc}")
            raise click.exceptions.Exit(2) from None
        from teardrop import ToolPolicy

        tool_policy = ToolPolicy(**raw)
    elif exclude_names:
        from teardrop import ToolPolicy

        tool_policy = ToolPolicy(exclude_names=list(exclude_names))

    # --- Estimate cost (local, no inference) ---
    if estimate_cost:
        _estimate_cost(message, context=context, tool_policy=tool_policy, base_url=base_url)
        return

    def _run_once():
        client = config.get_client(base_url)

        async def _run_command_once():
            try:
                if as_json or no_stream:
                    return await _collect(
                        client,
                        message,
                        thread,
                        context,
                        emit_ui=with_ui,
                        tool_policy=tool_policy,
                    )
                await _stream(
                    client,
                    message,
                    thread,
                    context,
                    emit_ui=with_ui,
                    tool_policy=tool_policy,
                )
                return None
            finally:
                await client.close()

        return asyncio.run(_run_command_once())

    def _run_with_recovery():
        from teardrop_cli.formatting import handle_token_expiry

        try:
            return _run_once()
        except Exception as exc:
            action = asyncio.run(
                handle_token_expiry(
                    exc,
                    base_url,
                    allow_prompt_login=not (as_json or no_stream),
                )
            )

            if action == "retry":
                return _run_once()

            if action == "prompt_login":
                from teardrop_cli.commands.auth import interactive_reauthenticate

                if not interactive_reauthenticate(base_url=base_url):
                    raise click.exceptions.Exit(1) from None
                return _run_once()

            if action == "fail":
                raise click.exceptions.Exit(1) from None

            raise

    if as_json or no_stream:
        try:
            text = _run_with_recovery()
        except click.exceptions.Exit:
            raise
        except Exception as exc:  # noqa: BLE001
            _handle_run_error(exc)
            raise click.exceptions.Exit(1) from None

        if as_json:
            print_json({"text": text, "thread_id": thread})
        else:
            console.print(text)
        return

    try:
        _run_with_recovery()
    except click.exceptions.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        _handle_run_error(exc)
        raise click.exceptions.Exit(1) from None


def _estimate_cost(
    message: str,
    *,
    context: dict | None = None,
    tool_policy=None,
    base_url: str | None = None,
) -> None:
    """Show an estimated cost based on current pricing and config — no inference."""
    from teardrop_cli.formatting import console, print_table
    from teardrop_cli.pricing import estimate_run_cost

    try:
        est = estimate_run_cost(
            message, context=context, tool_policy=tool_policy, base_url=base_url
        )
    except Exception as exc:  # noqa: BLE001
        _handle_run_error(exc)
        return

    from teardrop import format_usdc

    rows = [
        ["Model", f"{est.model_provider} / {est.model_name}"],
        ["Input tokens (est.)", str(est.input_tokens_est)],
        ["Output tokens (est.)", str(est.output_tokens_est)],
        ["Tool calls (est.)", str(est.tool_calls_est)],
        [],
        ["Token input cost", f"${format_usdc(est.model_tokens_in_cost_usdc)} USDC"],
        ["Token output cost", f"${format_usdc(est.model_tokens_out_cost_usdc)} USDC"],
        ["Tool call flat cost", f"${format_usdc(est.tool_call_cost_usdc)} USDC"],
        ["Tool usage cost", f"${format_usdc(est.tool_usage_cost_usdc)} USDC"],
        ["Base fee", f"${format_usdc(est.base_cost_usdc)} USDC"],
        [],
        ["Estimated total", f"[bold]${format_usdc(est.total_usdc)} USDC[/bold]"],
    ]
    print_table(
        [("Item", {"style": "bold cyan"}), "Value"], rows, title="Cost Estimate"
    )
    console.print(f"[dim]{est.disclaimer}[/dim]")


async def _stream(
    client,
    message: str,
    thread: str | None,
    context: dict | None,
    *,
    emit_ui: bool = False,
    tool_policy=None,
) -> None:
    from contextlib import aclosing

    from teardrop_cli.formatting import _render_stream

    try:
        events = client.run(
            message,
            thread_id=thread,
            context=context,
            emit_ui=emit_ui,
            tool_policy=tool_policy,
        )
        if hasattr(events, "__await__") and not hasattr(events, "__aiter__"):
            events = await events

        async with aclosing(events):
            await _render_stream(events)
    finally:
        await client.close()


async def _collect(
    client,
    message: str,
    thread: str | None,
    context: dict | None,
    *,
    emit_ui: bool = False,
    tool_policy=None,
) -> str:
    from teardrop_cli.formatting import (
        _EV_TEXT,
        _extract_text_and_id,
    )

    try:
        events = client.run(
            message,
            thread_id=thread,
            context=context,
            emit_ui=emit_ui,
            tool_policy=tool_policy,
        )
        if hasattr(events, "__await__") and not hasattr(events, "__aiter__"):
            events = await events

        if hasattr(events, "__aiter__"):
            parts: list[str] = []
            current_message_id: str | None = None
            async for event in events:
                if getattr(event, "type", "") == _EV_TEXT:
                    data = getattr(event, "data", None)
                    chunk, message_id = _extract_text_and_id(data)

                    # For --no-stream, only keep the last message's text
                    if message_id and message_id != current_message_id:
                        parts = []
                        current_message_id = message_id

                    parts.append(chunk)

            return "".join(parts)

        # Non-streaming fallback (older SDKs that returned a result object).
        if hasattr(events, "text"):
            return events.text
        if isinstance(events, dict):
            return events.get("text", "")
        return str(events)
    finally:
        await client.close()


def _handle_run_error(exc: BaseException) -> None:
    from teardrop_cli.formatting import print_error

    name = type(exc).__name__
    msg = str(exc)

    if name == "PaymentRequiredError" or "402" in msg:
        print_error(
            "Insufficient credit.",
            hint="Topup at: https://teardrop.dev/billing",
        )
        return
    if name == "RateLimitError" or "429" in msg:
        retry = getattr(exc, "retry_after", None)
        suffix = f" (retry after {retry}s)" if retry else ""
        print_error(f"Rate limit exceeded{suffix}.")
        return
    if name == "AuthenticationError" or "401" in msg:
        print_error(
            "Not authenticated.",
            hint="Run `teardrop auth login` to sign in.",
        )
        return

    if "DUPLICATE_CALL_BLOCKED" in msg:
        # Suppress in normal mode; treat as informative if exposing later.
        return

    print_error(f"{name}: {msg}")
