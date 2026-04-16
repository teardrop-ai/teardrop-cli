"""Rich formatting utilities for teardrop-cli.

All decorative output is sent to **stderr** so that stdout remains clean
for piping and ``--json`` output.  Data output (tables, JSON) is written
to stdout via a separate ``data_console``.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Consoles
# ---------------------------------------------------------------------------

# Decorative output (spinners, status, errors) → stderr
console = Console(stderr=True, highlight=False)

# Data output (tables, JSON) → stdout so it can be piped / redirected
data_console = Console(highlight=False)

# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def print_error(message: str, *, hint: str | None = None) -> None:
    """Print a styled error to stderr."""
    console.print(f"[bold red]Error:[/bold red] {message}")
    if hint:
        console.print(f"[dim]{hint}[/dim]")


def print_success(message: str) -> None:
    """Print a success message to stderr."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_warning(message: str) -> None:
    """Print a warning to stderr."""
    console.print(f"[bold yellow]⚠[/bold yellow]  {message}")


# ---------------------------------------------------------------------------
# Spinner / status context manager
# ---------------------------------------------------------------------------


@contextmanager
def spinner(message: str) -> Iterator[None]:
    """Show a spinner on stderr while the body runs."""
    with console.status(message):
        yield


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------


def print_table(
    columns: list[str | tuple[str, dict]],
    rows: list[list[Any]],
    *,
    title: str | None = None,
) -> None:
    """Render a Rich table to stdout.

    *columns* may be plain strings or ``(header, style_kwargs)`` tuples.
    """
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for col in columns:
        if isinstance(col, str):
            table.add_column(col)
        else:
            header, kwargs = col
            table.add_column(header, **kwargs)
    for row in rows:
        table.add_row(*[str(v) if v is not None else "—" for v in row])
    data_console.print(table)


def print_json(data: Any) -> None:
    """Print *data* as pretty JSON to stdout."""
    data_console.print_json(json.dumps(data, default=str))


def print_json_or_table(
    data: list[dict] | dict,
    columns: list[str | tuple[str, dict]],
    rows: list[list[Any]],
    *,
    as_json: bool,
    title: str | None = None,
) -> None:
    """Output as JSON (``--json``) or a Rich table."""
    if as_json:
        print_json(data)
    else:
        print_table(columns, rows, title=title)


# ---------------------------------------------------------------------------
# Streaming agent response renderer
# ---------------------------------------------------------------------------

# SSE event type constants (mirrors teardrop_sdk)
_EV_TEXT = "text_msg_content"
_EV_TOOL_START = "tool_call_start"
_EV_TOOL_END = "tool_call_end"
_EV_USAGE = "usage_summary"
_EV_BILLING = "billing_settlement"
_EV_ERROR = "error"
_EV_DONE = "done"


def stream_agent_response(events: AsyncIterator) -> None:  # type: ignore[type-arg]
    """Render a streaming agent run to the terminal.

    Blocks the calling thread by running the async iterator inside
    ``asyncio.run()``.  Renders token-by-token text, tool call indicators,
    and a usage summary at the end.
    """
    asyncio.run(_render_stream(events))


async def _render_stream(events: AsyncIterator) -> None:  # type: ignore[type-arg]
    """Async implementation of the streaming renderer."""
    accumulated_text = ""
    tool_depth = 0  # track nested tool calls

    # We use a Live display so we can update the rendered Markdown in-place.
    # ``auto_refresh=False`` lets us control exactly when re-renders happen.
    live = Live(
        Text(""),
        console=console,
        refresh_per_second=15,
        auto_refresh=True,
        transient=False,
    )

    with live:
        async for event in events:
            ev_type: str = getattr(event, "type", "") or ""
            data = getattr(event, "data", None)

            if ev_type == _EV_TEXT:
                chunk = ""
                if isinstance(data, dict):
                    chunk = data.get("content", "")
                elif isinstance(data, str):
                    chunk = data
                accumulated_text += chunk
                live.update(Markdown(accumulated_text))

            elif ev_type == _EV_TOOL_START:
                tool_depth += 1
                tool_name = ""
                if isinstance(data, dict):
                    tool_name = data.get("tool_name", data.get("name", ""))
                indicator = f"\n\n*[Tool: {tool_name}…]*\n"
                live.update(Markdown(accumulated_text + indicator))

            elif ev_type == _EV_TOOL_END:
                tool_depth = max(0, tool_depth - 1)
                if tool_depth == 0:
                    # Clear inline indicator; response text continues
                    live.update(Markdown(accumulated_text))

            elif ev_type == _EV_USAGE:
                # Print usage summary below the response
                if isinstance(data, dict):
                    _print_usage_summary(data)

            elif ev_type == _EV_BILLING:
                if isinstance(data, dict):
                    _print_billing_settlement(data)

            elif ev_type == _EV_ERROR:
                msg = ""
                if isinstance(data, dict):
                    msg = data.get("message", str(data))
                elif isinstance(data, str):
                    msg = data
                live.stop()
                print_error(f"Agent error: {msg}")
                return

            elif ev_type == _EV_DONE:
                break

    # Ensure a newline after streaming output
    console.print()


def _print_usage_summary(data: dict) -> None:
    parts: list[str] = []
    if "input_tokens" in data:
        parts.append(f"Input: {data['input_tokens']} tok")
    if "output_tokens" in data:
        parts.append(f"Output: {data['output_tokens']} tok")
    if "total_cost_usd" in data:
        parts.append(f"Cost: ${data['total_cost_usd']:.4f}")
    if parts:
        console.print(f"[dim]{'  ·  '.join(parts)}[/dim]")


def _print_billing_settlement(data: dict) -> None:
    amount = data.get("amount_charged")
    currency = data.get("currency", "credits")
    if amount is not None:
        console.print(f"[dim]Charged: {amount} {currency}[/dim]")


# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------


def confirm(message: str, *, default: bool = False) -> bool:
    """Prompt the user for a yes/no confirmation on stderr."""
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = console.input(f"[bold]{message}[/bold]{suffix}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")
