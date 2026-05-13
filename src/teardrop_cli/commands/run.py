"""Top-level ``teardrop run`` command — execute an agent message."""

from __future__ import annotations

import asyncio
import json as _json

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
def app(
    message: str,
    thread: str | None,
    context_json: str | None,
    no_stream: bool,
    as_json: bool,
    base_url: str | None,
    with_ui: bool,
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

    client = config.get_client(base_url)

    async def _run_command():
        from teardrop_cli.formatting import handle_token_expiry
        
        nonlocal client
        try:
            if as_json or no_stream:
                return await _collect(client, message, thread, context, emit_ui=with_ui)
            else:
                await _stream(client, message, thread, context, emit_ui=with_ui)
                return None
        except Exception as exc:
            if await handle_token_expiry(exc, base_url):
                # Re-fetch client and retry
                client = config.get_client(base_url)
                if as_json or no_stream:
                    return await _collect(client, message, thread, context, emit_ui=with_ui)
                else:
                    await _stream(client, message, thread, context, emit_ui=with_ui)
                    return None
            raise

    if as_json or no_stream:
        try:
            text = asyncio.run(_run_command())
        except Exception as exc:  # noqa: BLE001
            _handle_run_error(exc)
            raise click.exceptions.Exit(1) from None

        if as_json:
            print_json({"text": text, "thread_id": thread})
        else:
            console.print(text)
        return

    try:
        asyncio.run(_run_command())
    except Exception as exc:  # noqa: BLE001
        _handle_run_error(exc)
        raise click.exceptions.Exit(1) from None


async def _stream(client, message: str, thread: str | None, context: dict | None, *, emit_ui: bool = False) -> None:
    from contextlib import aclosing

    from teardrop_cli.formatting import _render_stream

    try:
        events = client.run(message, thread_id=thread, context=context, emit_ui=emit_ui)
        if hasattr(events, "__await__") and not hasattr(events, "__aiter__"):
            events = await events
        
        async with aclosing(events):
            await _render_stream(events)
    finally:
        await client.close()


async def _collect(client, message: str, thread: str | None, context: dict | None, *, emit_ui: bool = False) -> str:
    from teardrop_cli.formatting import (
        _EV_TEXT,
        _extract_text_and_id,
    )

    try:
        events = client.run(message, thread_id=thread, context=context, emit_ui=emit_ui)
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
