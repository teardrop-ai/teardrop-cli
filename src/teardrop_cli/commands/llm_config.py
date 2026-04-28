"""llm-config commands: get, set, delete."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import Annotated

import typer

app = typer.Typer(
    name="llm-config",
    help="Org LLM configuration — get, set, and delete.",
    no_args_is_help=True,
)

_SUPPORTED_PROVIDERS = ["anthropic", "openai", "google", "openrouter"]
_SUPPORTED_ROUTINGS = ["default", "cost", "speed", "quality"]


def _mask_api_key(key: str) -> str:
    """Return first 6 chars of *key* followed by ``•••••``."""
    prefix = key[:6] if len(key) >= 6 else key
    return f"{prefix}•••••"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@app.command()
def get(
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", "--force-refresh", help="Bypass the local 5-minute cache."),
    ] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Display the org's current LLM configuration."""
    from teardrop import AuthenticationError

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_json, print_table, spinner

    client = config.get_client(base_url)
    if no_cache:
        # Bypass SDK in-process cache
        with contextlib.suppress(Exception):
            client._llm_config_cache = None  # type: ignore[attr-defined]

    async def _fetch():
        try:
            return await client.get_llm_config()
        finally:
            await client.close()

    try:
        with spinner("Fetching LLM config…"):
            cfg = asyncio.run(_fetch())
    except AuthenticationError:
        print_error("Not authenticated.", hint="Run: `teardrop auth login`")
        raise typer.Exit(1) from None
    except Exception as exc:
        _handle_common_error(exc)

    data = cfg if isinstance(cfg, dict) else cfg.model_dump()

    if as_json:
        print_json(data)
        return

    print_table(
        [("Field", {"style": "bold cyan"}), "Value"],
        [
            ["Provider", data.get("provider", "—")],
            ["Model", data.get("model", "—")],
            ["API Key Set", "true" if data.get("has_api_key") else "false"],
            ["Self-Hosted URL", data.get("api_base") or "(none)"],
            ["Max Tokens", data.get("max_tokens", "—")],
            ["Temperature", data.get("temperature", "—")],
            ["Timeout", f"{data.get('timeout_seconds', '—')}s"],
            ["Routing Preference", data.get("routing_preference", "—")],
            ["BYOK", "true" if data.get("is_byok") else "false"],
            ["Updated", data.get("updated_at", "—")],
        ],
        title="LLM Config",
    )


# ---------------------------------------------------------------------------
# set
# ---------------------------------------------------------------------------


@app.command(name="set")
def set_config(
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider (anthropic, openai, google, openrouter)."),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Model ID.")] = None,
    routing: Annotated[
        str | None,
        typer.Option("--routing", help="Routing preference (default, cost, speed, quality)."),
    ] = None,
    api_base: Annotated[
        str | None, typer.Option("--api-base", help="Self-hosted model base URL.")
    ] = None,
    max_tokens: Annotated[
        int | None, typer.Option("--max-tokens", help="Max tokens (1–200,000).")
    ] = None,
    temperature: Annotated[
        float | None, typer.Option("--temperature", help="Temperature (0.0–2.0).")
    ] = None,
    timeout_seconds: Annotated[
        int | None, typer.Option("--timeout-seconds", help="Timeout in seconds (≥1).")
    ] = None,
    byok_key: Annotated[
        str | None,
        typer.Option("--byok-key", help="Bring-your-own API key. Pass '-' to read from stdin."),
    ] = None,
    clear_key: Annotated[
        bool,
        typer.Option("--clear-key", help="Clear BYOK key (revert to platform shared key)."),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Create or update the org's LLM configuration.

    Performs a read-then-write merge: any field not supplied is taken from
    the current configuration. ``provider`` and ``model`` are always
    required by the backend, so they are merged from the existing config.
    """
    from teardrop import AuthenticationError

    from teardrop_cli import config
    from teardrop_cli.formatting import (
        print_error,
        print_json,
        print_success,
        print_table,
        print_warning,
        spinner,
    )

    # Client-side validation
    if provider is not None and provider not in _SUPPORTED_PROVIDERS:
        print_error(
            f"Unsupported provider: {provider!r}.",
            hint=f"Supported: {', '.join(_SUPPORTED_PROVIDERS)}",
        )
        raise typer.Exit(1)
    if routing is not None and routing not in _SUPPORTED_ROUTINGS:
        print_error(
            f"Invalid routing preference: {routing!r}.",
            hint=f"Supported: {', '.join(_SUPPORTED_ROUTINGS)}",
        )
        raise typer.Exit(1)
    if temperature is not None and not (0.0 <= temperature <= 2.0):
        print_error("Temperature must be 0.0–2.0.")
        raise typer.Exit(1)
    if max_tokens is not None and not (1 <= max_tokens <= 200_000):
        print_error("Max tokens must be 1–200,000.")
        raise typer.Exit(1)
    if timeout_seconds is not None and timeout_seconds < 1:
        print_error("timeout-seconds must be ≥ 1.")
        raise typer.Exit(1)

    # BYOK key resolution
    resolved_key: str | None = None
    if byok_key == "-":
        resolved_key = sys.stdin.read().strip()
    elif byok_key is not None:
        print_warning(
            "API key visible in shell history. Prefer: --byok-key - (read from stdin)"
        )
        resolved_key = byok_key

    if resolved_key and api_base and not api_base.startswith("https://"):
        print_warning("api-base is not HTTPS. API keys must only be sent over TLS.")

    if clear_key and resolved_key:
        print_error("--clear-key cannot be combined with --byok-key.")
        raise typer.Exit(1)

    client = config.get_client(base_url)

    # Read current config for merging
    try:
        current = asyncio.run(_get_current(client))
    except AuthenticationError:
        print_error("Not authenticated.", hint="Run: `teardrop auth login`")
        raise typer.Exit(1) from None

    cur = current if isinstance(current, dict) else current.model_dump()

    merged = {
        "provider": provider or cur.get("provider"),
        "model": model or cur.get("model"),
        "routing_preference": routing or cur.get("routing_preference") or "default",
        "api_base": api_base if api_base is not None else cur.get("api_base"),
        "max_tokens": max_tokens or cur.get("max_tokens") or 4096,
        "temperature": (
            temperature if temperature is not None else (cur.get("temperature") or 0.0)
        ),
        "timeout_seconds": timeout_seconds or cur.get("timeout_seconds") or 120,
    }

    if not merged["provider"] or not merged["model"]:
        print_error(
            "provider and model are required (no current config to merge from).",
            hint="Specify --provider and --model.",
        )
        raise typer.Exit(1)

    async def _apply():
        try:
            if clear_key:
                return await client.set_llm_config(**merged)
            kwargs = dict(merged)
            if resolved_key is not None:
                kwargs["api_key"] = resolved_key
            return await client.set_llm_config(**kwargs)
        finally:
            await client.close()

    try:
        with spinner("Updating LLM config…"):
            cfg = asyncio.run(_apply())
    except AuthenticationError:
        print_error("Not authenticated.", hint="Run: `teardrop auth login`")
        raise typer.Exit(1) from None
    except Exception as exc:
        _handle_common_error(exc)

    data = cfg if isinstance(cfg, dict) else cfg.model_dump()

    if as_json:
        data.pop("api_key", None)
        print_json(data)
        return

    print_success("Updated LLM configuration")
    summary_rows: list[list] = [
        ["Provider", data.get("provider", "—")],
        ["Model", data.get("model", "—")],
        ["Routing", data.get("routing_preference", "—")],
    ]
    if data.get("api_base"):
        summary_rows.append(["Self-Hosted URL", data["api_base"]])
    if data.get("has_api_key"):
        key_display = (
            f"true ({_mask_api_key(resolved_key)})" if resolved_key else "true"
        )
        summary_rows.append(["API Key Set", key_display])
    if data.get("is_byok"):
        summary_rows.append(["BYOK", "true"])

    print_table([("Field", {"style": "bold cyan"}), "Value"], summary_rows)


async def _get_current(client):
    return await client.get_llm_config()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@app.command()
def delete(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")] = False,
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Remove org's custom LLM config and revert to global defaults."""
    from teardrop import AuthenticationError

    from teardrop_cli import config
    from teardrop_cli.formatting import confirm, print_error, print_success, spinner

    if not yes:
        confirmed = confirm(
            "Delete custom LLM config? This will revert to global defaults."
        )
        if not confirmed:
            raise typer.Abort()

    client = config.get_client(base_url)

    async def _fetch():
        try:
            await client.delete_llm_config()
        finally:
            await client.close()

    try:
        with spinner("Deleting LLM config…"):
            asyncio.run(_fetch())
    except AuthenticationError:
        print_error("Not authenticated.", hint="Run: `teardrop auth login`")
        raise typer.Exit(1) from None
    except Exception as exc:
        _handle_common_error(exc, not_found_ok=True)

    print_success("Deleted. Using global defaults.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _handle_common_error(exc: Exception, *, not_found_ok: bool = False) -> None:
    """Translate SDK/HTTP exceptions to user-friendly messages."""
    from teardrop_cli.formatting import print_error, print_success

    exc_str = str(exc)
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)

    if not_found_ok and status == 404:
        print_success("No custom config found. Already using global defaults.")
        raise typer.Exit(0)

    if status == 401:
        print_error("Not authenticated.", hint="Run: `teardrop auth login`")
        raise typer.Exit(1)

    if status == 400:
        if "ssrf" in exc_str.lower() or "private" in exc_str.lower():
            print_error(
                "api_base must be a public URL (e.g., https://api.provider.com).",
                hint="Contact support for private endpoint allowlisting.",
            )
        elif "provider" in exc_str.lower():
            print_error(
                "Unsupported provider.",
                hint=f"Supported: {', '.join(_SUPPORTED_PROVIDERS)}",
            )
        elif "routing" in exc_str.lower():
            print_error(
                "Invalid routing preference.",
                hint=f"Supported: {', '.join(_SUPPORTED_ROUTINGS)}",
            )
        else:
            print_error(f"Bad request: {exc_str}")
        raise typer.Exit(1)

    if status == 422:
        print_error(f"Validation error: {exc_str}")
        raise typer.Exit(1)

    if status == 429:
        retry = getattr(exc, "retry_after", None)
        hint = (
            f"Maximum 10 updates per hour per org. Retry in {retry}s."
            if retry
            else "Maximum 10 updates per hour per org."
        )
        print_error("Too many config updates.", hint=hint)
        raise typer.Exit(1)

    print_error(f"Unexpected error: {exc_str}")
    raise typer.Exit(1)
