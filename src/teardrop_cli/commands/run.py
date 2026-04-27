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
def app(
    message: str,
    thread: str | None,
    context_json: str | None,
    no_stream: bool,
    as_json: bool,
    base_url: str | None,
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

    if as_json or no_stream:
        try:
            text = asyncio.run(_collect(client, message, thread, context))
        except Exception as exc:  # noqa: BLE001
            _handle_run_error(exc)
            raise click.exceptions.Exit(1) from None

        if as_json:
            print_json({"text": text, "thread_id": thread})
        else:
            console.print(text)
        return

    try:
        asyncio.run(_stream(client, message, thread, context))
    except Exception as exc:  # noqa: BLE001
        _handle_run_error(exc)
        raise click.exceptions.Exit(1) from None


async def _stream(client, message: str, thread: str | None, context: dict | None) -> None:
    from teardrop_cli.formatting import _render_stream

    try:
        events = client.run(message, thread_id=thread, context=context, stream=True)
        if hasattr(events, "__await__") and not hasattr(events, "__aiter__"):
            events = await events
        await _render_stream(events)
    finally:
        await client.close()


async def _collect(client, message: str, thread: str | None, context: dict | None) -> str:
    try:
        try:
            from teardrop.streaming import async_collect_text
        except ImportError:
            async_collect_text = None  # type: ignore[assignment]

        if async_collect_text is not None:
            events = client.run(message, thread_id=thread, context=context, stream=True)
            if hasattr(events, "__await__") and not hasattr(events, "__aiter__"):
                events = await events
            return await async_collect_text(events)

        result = await client.run(message, thread_id=thread, context=context, stream=False)
        if hasattr(result, "text"):
            return result.text
        if isinstance(result, dict):
            return result.get("text", "")
        return str(result)
    finally:
        await client.close()


def _handle_run_error(exc: BaseException) -> None:
    from teardrop_cli.formatting import print_error

    name = type(exc).__name__
    msg = str(exc)

    if name == "PaymentRequiredError" or "402" in msg:
        print_error(
            "Insufficient credit.",
            hint="Run: `teardrop topup stripe --amount 10.00`",
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

    print_error(f"{name}: {msg}")
