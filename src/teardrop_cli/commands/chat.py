"""``teardrop chat`` — interactive, stateful chat with thread persistence.

Differs from ``teardrop run`` in that the active thread is automatically
stored in ``~/.teardrop/config.toml`` (under ``chat.active_thread_id``)
and reused on the next invocation.  Pass ``--new`` to start a fresh thread
or ``--thread <id>`` to explicitly opt into a specific conversation.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import click

from teardrop_cli.commands.run import _execute_run


@click.command(name="chat", help="Chat with an agent (auto-continues the same thread).")
@click.argument("message", required=True)
@click.option(
    "--new",
    is_flag=True,
    default=False,
    help="Start a new chat thread (discards the stored active thread).",
)
@click.option("--thread", "thread", default=None, help="Continue an explicit thread by id.")
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
    new: bool,
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
    """Chat with an agent on a persistent thread.

    The active thread id is stored in ``~/.teardrop/config.toml`` and
    automatically reused on subsequent ``teardrop chat`` calls.  Use
    ``--new`` to start a fresh conversation or ``--thread <id>`` to
    switch to a specific thread.
    """
    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_error, print_json

    # --- Parse --context ---
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

    # --- Resolve thread id ---
    if new:
        config.clear_active_thread_id()
        resolved_thread: str | None = None
    elif thread is not None:
        resolved_thread = thread
    else:
        resolved_thread = config.get_active_thread_id()

    # --- Estimate cost (local, no inference) — no side effects ---
    if estimate_cost:
        from teardrop_cli.commands.run import _estimate_cost

        _estimate_cost(message, context=context, tool_policy=tool_policy, base_url=base_url)
        return

    # --- Capture the server-returned thread id ---
    captured_thread: list[str | None] = [resolved_thread]

    def _on_thread_id(tid: str) -> None:
        if captured_thread[0] is None or tid != captured_thread[0]:
            captured_thread[0] = tid

    # --- Execute (reuses run's pipeline) ---
    text = _execute_run(
        message,
        thread=resolved_thread,
        context=context,
        no_stream=no_stream,
        as_json=as_json,
        base_url=base_url,
        with_ui=with_ui,
        tool_policy=tool_policy,
        on_thread_id=_on_thread_id,
    )

    # --- Persist the thread id (server may have minted one) ---
    final_thread = captured_thread[0]
    if final_thread is not None:
        config.set_active_thread_id(final_thread)

    # --- Output ---
    if as_json:
        print_json({"text": text, "thread_id": final_thread})
    elif text is not None:
        console.print(text)

    # Always print the thread id for discoverability (to stderr)
    if final_thread:
        console.print(f"[dim]thread: {final_thread}[/dim]")
