"""agent commands: run."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Annotated

import typer

app = typer.Typer(
    name="agent",
    help="Run prompts against the Teardrop AI agent.",
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """Run prompts against the Teardrop AI agent."""


# SSE event type constants (must match teardrop_sdk's streaming module)
_EV_TEXT = "text_msg_content"
_EV_TOOL_START = "tool_call_start"
_EV_TOOL_END = "tool_call_end"
_EV_USAGE = "usage_summary"
_EV_BILLING = "billing_settlement"
_EV_ERROR = "error"
_EV_DONE = "done"


@app.command()
def run(
    prompt: Annotated[str, typer.Argument(help="The prompt to send to the agent.")],
    thread_id: Annotated[
        str | None, typer.Option("--thread-id", "-t", help="Continue an existing thread.")
    ] = None,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Model override.")] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit raw SSE events as JSON lines (machine-readable)."),
    ] = False,
    base_url: Annotated[
        str | None, typer.Option("--base-url", help="Override the API base URL.", hidden=True)
    ] = None,
) -> None:
    """Send a prompt to the agent and stream the response."""
    from teardrop import PaymentRequiredError, RateLimitError

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error

    client = config.get_client(base_url)

    try:
        if as_json:
            asyncio.run(_run_json(client, prompt, thread_id=thread_id, model=model))
        else:
            asyncio.run(_run_rich(client, prompt, thread_id=thread_id, model=model))
    except PaymentRequiredError:
        print_error(
            "Insufficient balance.",
            hint=f"Top up your account at {config.get_base_url()}/billing",
        )
        raise typer.Exit(2) from None
    except RateLimitError as exc:
        retry = getattr(exc, "retry_after", None)
        hint = f"Retry in {retry}s." if retry else "Please wait before retrying."
        print_error("Rate limited.", hint=hint)
        raise typer.Exit(3) from None
    except KeyboardInterrupt:
        raise typer.Exit(130) from None


# ---------------------------------------------------------------------------
# Rich streaming renderer
# ---------------------------------------------------------------------------


async def _run_rich(client, prompt: str, *, thread_id, model) -> None:
    """Stream response with Rich Live rendering."""
    from rich.live import Live
    from rich.markdown import Markdown

    from teardrop_cli.formatting import _print_billing_settlement, _print_usage_summary, console

    try:
        accumulated = ""
        tool_depth = 0

        live = Live(
            Markdown(""),
            console=console,
            refresh_per_second=15,
            auto_refresh=True,
            transient=False,
        )

        # Show a quick spinner before first token arrives
        first_token = True

        with live:
            async for event in client.run(prompt, thread_id=thread_id, model=model):
                ev_type: str = getattr(event, "type", "") or ""
                data = getattr(event, "data", None)

                if ev_type == _EV_TEXT:
                    if first_token:
                        first_token = False
                    chunk = _extract_text(data)
                    accumulated += chunk
                    live.update(Markdown(accumulated))

                elif ev_type == _EV_TOOL_START:
                    tool_depth += 1
                    tool_name = _extract_tool_name(data)
                    indicator = f"\n\n*[Tool: {tool_name}…]*"
                    live.update(Markdown(accumulated + indicator))

                elif ev_type == _EV_TOOL_END:
                    tool_depth = max(0, tool_depth - 1)
                    if tool_depth == 0:
                        live.update(Markdown(accumulated))

                elif ev_type == _EV_USAGE:
                    if isinstance(data, dict):
                        live.stop()
                        _print_usage_summary(data)

                elif ev_type == _EV_BILLING:
                    if isinstance(data, dict):
                        _print_billing_settlement(data)

                elif ev_type == _EV_ERROR:
                    msg = _extract_text(data) or "Unknown agent error"
                    live.stop()
                    from teardrop_cli.formatting import print_error

                    print_error(f"Agent error: {msg}")
                    raise typer.Exit(5)

                elif ev_type == _EV_DONE:
                    break

        console.print()  # trailing newline after stream
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# JSON streaming renderer (machine-readable)
# ---------------------------------------------------------------------------


async def _run_json(client, prompt: str, *, thread_id, model) -> None:
    """Emit each SSE event as a JSON line to stdout."""
    try:
        async for event in client.run(prompt, thread_id=thread_id, model=model):
            line = json.dumps(
                {
                    "type": getattr(event, "type", None),
                    "data": getattr(event, "data", None),
                },
                default=str,
            )
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_text(data) -> str:
    if isinstance(data, dict):
        return data.get("content", data.get("message", data.get("text", "")))
    if isinstance(data, str):
        return data
    return ""


def _extract_tool_name(data) -> str:
    if isinstance(data, dict):
        return data.get("tool_name", data.get("name", "unknown"))
    return "unknown"
