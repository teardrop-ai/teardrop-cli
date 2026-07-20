"""``teardrop quickstart`` — guided onboarding for new developers.

Single command that takes a fresh install from zero to first agent run or
first published tool, branching on what the user wants to do. Pure
orchestration: each step delegates to an existing command implementation.
"""

from __future__ import annotations

import asyncio

import click
import typer


@click.command(
    name="quickstart",
    help="Interactive onboarding wizard — sign up or log in, configure LLM, run or publish.",
)
@click.option("--base-url", "base_url", default=None, hidden=True)
def app(base_url: str | None) -> None:
    _run_quickstart(base_url)


def _is_authentication_failure(exc: BaseException) -> bool:
    from teardrop import AuthenticationError

    return isinstance(exc, AuthenticationError) or getattr(exc, "status_code", None) == 401


def _verify_saved_session(
    base_url: str | None,
    source: str,
    *,
    allow_recovery: bool = True,
) -> bool:
    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, spinner

    try:
        client = config.get_client(base_url)

        async def _fetch_identity():
            try:
                return await client.get_me()
            finally:
                await client.close()

        with spinner("Verifying saved credentials…"):
            identity = asyncio.run(_fetch_identity())
    except (click.exceptions.Exit, SystemExit):
        return False
    except Exception as exc:  # noqa: BLE001
        if _is_authentication_failure(exc):
            if not allow_recovery:
                print_error(
                    "Sign-in failed.",
                    hint="Run [bold]teardrop auth login[/bold] to try again.",
                )
                return False
            if source.startswith("env:"):
                print_error(
                    "Saved environment credentials were rejected.",
                    hint=(
                        "Update or unset TEARDROP_API_KEY, TEARDROP_EMAIL, or "
                        "TEARDROP_CLIENT_ID, then run [bold]teardrop auth login[/bold]."
                    ),
                )
                return False

            from teardrop_cli.commands.auth import interactive_reauthenticate

            try:
                if not interactive_reauthenticate(
                    base_url=base_url,
                    warning_message="Your saved session is no longer valid. Sign in again to continue.",
                ):
                    return False
            except (click.exceptions.Exit, SystemExit):
                return False

            refreshed_source = config.detect_credential_source()
            if refreshed_source is None:
                print_error("Sign-in did not produce a saved session.")
                return False
            return _verify_saved_session(
                base_url,
                refreshed_source,
                allow_recovery=False,
            )

        print_error(
            "Could not verify your saved session.",
            hint="Check your network connection and API URL, then try again.",
        )
        return False

    label = None
    if isinstance(identity, dict):
        label = identity.get("email") or identity.get("sub")
    else:
        label = getattr(identity, "email", None) or getattr(identity, "sub", None)
    suffix = f" for [bold]{label}[/bold]" if label else ""
    from teardrop_cli.formatting import console

    console.print(f"[bold green]✓[/bold green] Session verified{suffix}.")
    return True


def _ensure_authenticated(base_url: str | None) -> bool:
    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_error

    source = config.detect_credential_source()
    if source is None:
        console.print("\n[bold]Sign-in is required to run an agent.[/bold]")
        try:
            _auth_menu(base_url)
        except (click.exceptions.Exit, SystemExit):
            return False
        source = config.detect_credential_source()
        if source is None:
            print_error("Sign-in did not produce a saved session.")
            return False

    return _verify_saved_session(base_url, source)


def _run_quickstart(base_url: str | None) -> None:
    from teardrop_cli import config
    from teardrop_cli.formatting import console

    is_repeat = config.has_existing_credentials()

    if not is_repeat:
        console.print(
            "\n[bold cyan]Welcome to Teardrop.[/bold cyan]  "
            "[dim]This wizard will get you running in under a minute.[/dim]\n"
        )
        console.print(
            "[dim]You can explore locally now; sign-in is requested only for "
            "account actions and agent runs.[/dim]"
        )
    else:
        console.print("[dim]Saved session found locally.[/dim]")
        console.print(f"[dim](source: {config.detect_credential_source()})[/dim]")
        console.print("[dim]It will be checked when you choose an authenticated action.[/dim]")

    console.print()
    console.print("[bold]What would you like to do next?[/bold]")
    console.print("  [cyan]0[/cyan]  Nothing, just exploring [dim](exit)[/dim]")
    console.print("  [cyan]1[/cyan]  Scaffold a tool to publish")
    console.print("  [cyan]2[/cyan]  Run a sample agent prompt")
    console.print("  [cyan]3[/cyan]  Browse marketplace tools")
    choice = typer.prompt("Choice")

    if choice == "1":
        _scaffold_branch()
    elif choice == "2":
        _sample_run_branch(base_url)
    elif choice == "3":
        _marketplace_browse_branch(base_url)
    else:
        console.print("\nAll set. Run [bold]teardrop --help[/bold] to explore commands.")


def _auth_menu(base_url: str | None) -> None:
    from teardrop_cli.commands.auth import _login_siwe, login, signup
    from teardrop_cli.formatting import console

    has_account = typer.confirm("Do you have a Teardrop account already?", default=False)

    if not has_account:
        console.print("\n[bold]Create your account:[/bold]")
        console.print("  [cyan]1[/cyan]  Email + password [recommended]")
        console.print("  [cyan]2[/cyan]  Ethereum wallet — no email needed")
        choice = typer.prompt("Choice", default="1")

        if choice == "2":
            from teardrop_cli import config

            url = base_url or config.get_base_url()
            generate = typer.confirm("Generate a new wallet?", default=True)
            save_key = typer.confirm(
                "Save the private key in your OS keyring for future re-authentication?",
                default=False,
            )
            _login_siwe(url, generate_wallet=generate, save_key=save_key)
        else:
            signup(base_url=base_url)
    else:
        console.print("\n[bold]Sign in:[/bold]")
        console.print("  [cyan]1[/cyan]  Ethereum wallet")
        console.print("  [cyan]2[/cyan]  Email + password [recommended]")
        choice = typer.prompt("Choice")

        if choice == "1":
            from teardrop_cli import config

            url = base_url or config.get_base_url()
            generate = typer.confirm("Generate a new wallet?", default=True)
            save_key = typer.confirm(
                "Save the private key in your OS keyring for future re-authentication?",
                default=False,
            )
            _login_siwe(url, generate_wallet=generate, save_key=save_key)
        else:
            login(base_url=base_url)


def _scaffold_branch() -> None:
    from teardrop_cli.commands.tools import init as tools_init
    from teardrop_cli.formatting import console

    name = typer.prompt("Tool name (lowercase, a-z0-9_)")
    tools_init(name=name, out=None, with_marketplace=False, force=False)
    console.print(
        "\n[bold]What's next:[/bold]\n"
        "  1. Edit [bold]tool.json[/bold] — set webhook_url, schema, price\n"
        "  2. Publish:  [bold]teardrop tools publish --from-file tool.json[/bold]\n"
        "  3. Earnings: [bold]teardrop earnings balance[/bold]\n"
    )


def _sample_run_branch(base_url: str | None) -> None:
    from teardrop_cli.commands.run import _estimate_cost, _execute_run
    from teardrop_cli.formatting import console

    if not _ensure_authenticated(base_url):
        return

    message = typer.prompt(
        "Prompt", default="What is the current ETH gas price?", show_default=True
    )
    console.print()
    console.print(
        "[dim]Billing note: platform credits or x402 cover non-BYOK model usage and platform costs. "
        "BYOK pays your provider directly but still needs Teardrop payment capacity for orchestration.[/dim]"
    )
    if typer.confirm("Configure a BYOK LLM key first?", default=False):
        from teardrop_cli.commands.llm_config import _byok_interactive

        _byok_interactive(base_url=base_url)
        console.print()

    if typer.confirm(
        "Show an estimated cost before running?", default=True
    ) and not _estimate_cost(message, base_url=base_url):
        console.print("\nNo run started. Resolve the issue and run quickstart again.")
        return

    if not typer.confirm("Run this prompt now? It may use credits or x402.", default=True):
        console.print("\nRun cancelled. No agent request was sent.")
        return

    try:
        _execute_run(message, base_url=base_url)
    except click.exceptions.Exit:
        return  # error already printed; skip next-steps

    console.print(
        "\n[dim]Continue exploring:[/dim]\n"
        "  [bold]teardrop marketplace list[/bold]   — browse tools\n"
        "  [bold]teardrop run '...'[/bold]           — run another prompt\n"
        "  [bold]teardrop llm-config byok[/bold]     — use your own LLM key\n"
    )


def _marketplace_browse_branch(base_url: str | None) -> None:
    from teardrop_cli.commands.marketplace import list_cmd
    from teardrop_cli.formatting import console

    list_cmd(base_url=base_url)
    console.print(
        "\n[dim]Subscribe to a tool:[/dim]\n  [bold]teardrop marketplace subscribe <name>[/bold]\n"
    )
