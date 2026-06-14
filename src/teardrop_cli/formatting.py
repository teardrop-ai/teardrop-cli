"""Rich formatting utilities for teardrop-cli.

All decorative output is sent to **stderr** so that stdout remains clean
for piping and ``--json`` output.  Data output (tables, JSON) is written
to stdout via a separate ``data_console``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal

from rich.console import Console
from rich.table import Table

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


TokenExpiryAction = Literal["none", "retry", "prompt_login", "fail"]


async def handle_token_expiry(
    exc: Exception,
    base_url: str | None = None,
    *,
    allow_prompt_login: bool = False,
) -> TokenExpiryAction:
    """Handle AuthenticationError by checking for fallback credentials.

    Checks, in order:

    1. Refresh-capable credential sources (email/client creds).
    2. SIWE private key in keyring (silent re-auth via ``_siwe_auth_async``)
       when the active source is config-token based.
    3. Optional caller-controlled interactive login prompt (for human-driven
       commands only; disabled for machine-readable ``--json`` paths).

    Returns one of:
      - ``"retry"`` when the caller should retry the command.
      - ``"prompt_login"`` when the caller may run an interactive login flow.
      - ``"fail"`` when the command should exit after this helper printed
        a user-facing auth error.
      - ``"none"`` when the error is unrelated to token expiry.
    """
    from teardrop import AuthenticationError

    if not isinstance(exc, AuthenticationError):
        return "none"

    # Check if the error is specifically about expiration
    msg = str(exc).lower()
    if "expire" not in msg:
        return "none"

    from teardrop_cli import config

    source = config.detect_credential_source()

    # 1. Refresh-capable sources can recover on the next client creation.
    if source in {"env:email", "env:client", "keyring:email", "keyring:client"}:
        print_warning("Session expired. Attempting auto-refresh...")
        return "retry"

    # 2. SIWE private key in keyring — silent re-auth.
    # Only attempt this when config-file token auth is active. If an env token
    # is active, retry would still pick env first and SIWE refresh would be moot.
    if source in {"config:token", "config:legacy_token", None}:
        siwe_key = config.get_siwe_key()
        if siwe_key is not None:
            private_key, address = siwe_key
            from teardrop_cli.commands.auth import _siwe_auth_async

            print_warning("Session expired. Re-authenticating via SIWE...")
            url = base_url or config.get_base_url()
            try:
                jwt_token = await _siwe_auth_async(url, private_key, address)
            except Exception:
                print_warning("Automatic SIWE re-authentication failed.")
            else:
                config.store_session(access_token=jwt_token)
                # Scrub the key string now that we're done with it.
                private_key = "0" * len(private_key)  # noqa: F841
                del private_key
                print_warning("Re-authenticated via SIWE. Retrying command...")
                return "retry"

    if allow_prompt_login and source in {"config:token", "config:legacy_token", None}:
        print_warning("Stored session has expired. Please sign in to continue.")
        return "prompt_login"

    hint = "Run [bold]teardrop auth login[/bold] to sign in again."
    if source == "env:api_key":
        hint = (
            "TEARDROP_API_KEY/TEARDROP_TOKEN appears expired. "
            "Update or unset it, then run [bold]teardrop auth login[/bold]."
        )

    print_error(
        "Your session has expired.",
        hint=hint,
    )
    return "fail"


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

# SSE event type constants — prefer values exported by the SDK so the CLI
# stays in sync with backend wire format. Fall back to UPPERCASE strings used
# by the spec when the SDK does not yet expose constants.
try:  # pragma: no cover - import shape varies across SDK versions
    from teardrop.streaming import (  # type: ignore
        EVENT_BILLING_SETTLEMENT as _EV_BILLING,
    )
    from teardrop.streaming import (
        EVENT_DONE as _EV_DONE,
    )
    from teardrop.streaming import (
        EVENT_ERROR as _EV_ERROR,
    )
    from teardrop.streaming import (
        EVENT_TEXT_MSG_CONTENT as _EV_TEXT,
    )
    from teardrop.streaming import (
        EVENT_TEXT_MSG_END as _EV_TEXT_END,
    )
    from teardrop.streaming import (
        EVENT_TEXT_MSG_START as _EV_TEXT_START,
    )
    from teardrop.streaming import (
        EVENT_TOOL_CALL_DUPLICATE as _EV_TOOL_DUPLICATE,
    )
    from teardrop.streaming import (
        EVENT_TOOL_CALL_END as _EV_TOOL_END,
    )
    from teardrop.streaming import (
        EVENT_TOOL_CALL_RESULT as _EV_TOOL_RESULT,
    )
    from teardrop.streaming import (
        EVENT_TOOL_CALL_START as _EV_TOOL_START,
    )
    from teardrop.streaming import (
        EVENT_USAGE_SUMMARY as _EV_USAGE,
    )
except ImportError:  # pragma: no cover
    _EV_TEXT = "TEXT_MESSAGE_CONTENT"
    _EV_TEXT_START = "TEXT_MESSAGE_START"
    _EV_TEXT_END = "TEXT_MESSAGE_END"
    _EV_TOOL_START = "TOOL_CALL_START"
    _EV_TOOL_DUPLICATE = "TOOL_CALL_DUPLICATE"
    _EV_TOOL_END = "TOOL_CALL_END"
    _EV_USAGE = "USAGE_SUMMARY"
    _EV_BILLING = "BILLING_SETTLEMENT"
    _EV_ERROR = "ERROR"
    _EV_DONE = "DONE"
    _EV_TOOL_RESULT = "TOOL_CALL_RESULT"

_EV_SURFACE = "SURFACE_UPDATE"


def _extract_text_and_id(data: Any) -> tuple[str, str | None]:
    """Extract a text string and optional message_id from a TEXT_MESSAGE_CONTENT event payload.

    The backend's ``delta`` field may be a plain string OR a list of
    Anthropic-style content blocks like ``[{"text": "...", "type": "text"}]``.
    Older payloads used a ``content`` key. Handle all shapes.

    The backend guarantees that TEXT_MESSAGE_CONTENT contains only prose
    (fences pre-removed); any structured UI data is delivered separately
    via SURFACE_UPDATE events.
    """
    if isinstance(data, str):
        return data, None
    if not isinstance(data, dict):
        return "", None

    # Extraction order: message_id, then text
    message_id = data.get("message_id")
    if not message_id:
        # Fallback for nested message objects if the backend wraps it
        msg = data.get("message")
        if isinstance(msg, dict):
            message_id = msg.get("id")

    value: Any = data.get("delta")
    if value is None:
        value = data.get("content", "")

    text = ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        parts: list[str] = []
        for block in value:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                inner_text = block.get("text")
                if isinstance(inner_text, str):
                    parts.append(inner_text)
        text = "".join(parts)

    return text, str(message_id) if message_id else None


def _extract_text_chunk(data: Any) -> str:
    """Extract a text string from a TEXT_MESSAGE_CONTENT event payload.

    Deprecated: Use _extract_text_and_id instead.
    """
    text, _ = _extract_text_and_id(data)
    return text


def stream_agent_response(events: AsyncIterator) -> None:  # type: ignore[type-arg]
    """Render a streaming agent run to the terminal.

    Blocks the calling thread by running the async iterator inside
    ``asyncio.run()``.  Renders token-by-token text, tool call indicators,
    and a usage summary at the end.
    """
    asyncio.run(_render_stream(events))


async def _render_stream(events: AsyncIterator) -> None:  # type: ignore[type-arg]
    """Async implementation of the streaming renderer.
    
    Streams response text and tool calls directly to scrollback (no in-place
    updates) to ensure:
    1. Full scrollback visibility during streaming
    2. No duplicate content on terminal resize
    """
    accumulated_text = ""
    current_message_id = None
    tool_depth = 0
    last_flush_len = 0  # Track printed content to avoid re-printing
    chunk_size = 100  # Flush every ~100 chars to scrollback for responsiveness

    async for event in events:
        ev_type: str = getattr(event, "type", "") or ""
        data = getattr(event, "data", None)

        if ev_type == _EV_TEXT:
            chunk, message_id = _extract_text_and_id(data)

            # Reset on new message_id (if IDs are provided)
            if message_id and message_id != current_message_id:
                accumulated_text = ""
                last_flush_len = 0
                current_message_id = message_id

            accumulated_text += chunk

            # Periodically flush new content to scrollback for visibility
            # The backend guarantees that TEXT_MESSAGE_CONTENT contains ONLY
            # prose; any structured UI data is sent via SURFACE_UPDATE.
            if len(accumulated_text) - last_flush_len >= chunk_size:
                new_content = accumulated_text[last_flush_len:]
                console.print(new_content, end="", soft_wrap=True)
                last_flush_len = len(accumulated_text)

        elif ev_type == _EV_TEXT_START:
            # Flush accumulated text before a new segment starts.
            if last_flush_len < len(accumulated_text):
                console.print(accumulated_text[last_flush_len:], end="", soft_wrap=True)
                last_flush_len = len(accumulated_text)

        elif ev_type == _EV_TEXT_END:
            # Flush accumulated text at the end of a segment.
            if last_flush_len < len(accumulated_text):
                console.print(accumulated_text[last_flush_len:], end="", soft_wrap=True)
                last_flush_len = len(accumulated_text)

        elif ev_type == _EV_SURFACE:
            # SURFACE_UPDATE events contain parsed UI components. Render
            # them as structured Markdown blocks so the user can see the
            # component type and key fields.
            if isinstance(data, dict):
                component_type = data.get("type", data.get("component", "unknown"))
                title = data.get("title", data.get("label", ""))
                from rich.markdown import Markdown
                md_lines = [f"**UI — {component_type}**"]
                if title:
                    md_lines[0] += f": {title}"
                # Include key fields but omit large payloads
                for k, v in data.items():
                    if k in ("type", "component", "title", "label"):
                        continue
                    if isinstance(v, (str, int, float, bool)):
                        md_lines.append(f"- **{k}:** {v}")
                    elif isinstance(v, dict):
                        md_lines.append(f"- **{k}:**")
                        md_lines.append("  ```json")
                        preview = json.dumps(v, default=str)[:500]
                        md_lines.append(f"  {preview}")
                        md_lines.append("  ```")
                console.print(Markdown("\n".join(md_lines)))

        elif ev_type == _EV_TOOL_START:
            tool_depth += 1
            tool_name = ""
            if isinstance(data, dict):
                tool_name = data.get("tool_name", data.get("name", ""))
            console.print(f"\n*[Tool: {tool_name}…]*")

        elif ev_type == _EV_TOOL_RESULT:
            if isinstance(data, dict):
                tool_name = data.get("tool_name", data.get("name", ""))
                result = data.get("result")
                if tool_name == "get_token_approvals" and isinstance(result, dict):
                    err = result.get("error")
                    if err:
                        print_warning(f"Approval audit incomplete: {err}")

        elif ev_type == _EV_TOOL_DUPLICATE:
            # Suppress entirely in normal mode.
            pass

        elif ev_type == _EV_TOOL_END:
            tool_depth = max(0, tool_depth - 1)

        elif ev_type == _EV_USAGE:
            # Flush any remaining text before usage summary
            if last_flush_len < len(accumulated_text):
                console.print(
                    accumulated_text[last_flush_len:],
                    soft_wrap=True,
                )
                last_flush_len = len(accumulated_text)
            console.print()  # Blank line before summary
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
            print_error(f"Agent error: {msg}")
            return

        elif ev_type == _EV_DONE:
            # Flush any remaining text on completion
            if last_flush_len < len(accumulated_text):
                console.print(accumulated_text[last_flush_len:], soft_wrap=True)
                last_flush_len = len(accumulated_text)
            break

    # Flush any remaining accumulated text (only if we didn't see DONE/USAGE)
    if last_flush_len < len(accumulated_text):
        console.print(accumulated_text[last_flush_len:], soft_wrap=True)

    # Ensure a newline after streaming output
    console.print()


def _print_usage_summary(data: dict) -> None:
    parts: list[str] = []

    run_id = data.get("run_id")
    if run_id:
        parts.insert(0, f"Run ID: {run_id}")

    tokens_in = data.get("tokens_in") or data.get("input_tokens", 0)
    tokens_out = data.get("tokens_out") or data.get("output_tokens", 0)
    cache_read = data.get("cache_read_tokens", 0)
    cache_create = data.get("cache_creation_tokens", 0)

    tok_parts = [f"{tokens_in} in"]
    if cache_read:
        tok_parts[-1] += f" ({cache_read} cached)"
    if cache_create:
        tok_parts.append(f"{cache_create} cache")
    tok_parts.append(f"{tokens_out} out")
    parts.append(f"Tokens: {' / '.join(tok_parts)}")

    cost_usdc = data.get("cost_usdc", 0)
    total_cost = data.get("total_cost_usd", 0)
    if cost_usdc:
        from teardrop import format_usdc
        parts.append(f"Cost: ${format_usdc(int(cost_usdc))}")
    elif total_cost:
        parts.append(f"Cost: ${total_cost:.4f}")

    duration = data.get("duration_ms", 0)
    if duration:
        parts.append(f"Duration: {duration / 1000:.1f}s")

    if parts:
        console.print(f"[dim]{' | '.join(parts)}[/dim]")


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
    suffix = " ([bold green]Y[/bold green]/n) " if default else " ([bold green]y[/bold green]/N) "
    try:
        answer = console.input(f"[bold]{message}[/bold]{suffix}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")
