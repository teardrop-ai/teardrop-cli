"""``teardrop quickstart`` — guided onboarding for new developers.

Single command that takes a fresh install from zero to first agent run or
first published tool, branching on what the user wants to do. Pure
orchestration: each step delegates to an existing command implementation.
"""

from __future__ import annotations

import click
import typer


@click.command(
    name="quickstart",
    help="Interactive onboarding wizard — sign up or log in, configure LLM, run or publish.",
)
@click.option("--base-url", "base_url", default=None, hidden=True)
def app(base_url: str | None) -> None:
    _run_quickstart(base_url)


def _run_quickstart(base_url: str | None) -> None:
    from teardrop_cli.formatting import console, print_success

    console.print(
        "\n[bold cyan]Welcome to Teardrop.[/bold cyan]  "
        "[dim]This wizard will get you running in under a minute.[/dim]\n"
    )

    # 1. Auth — skip if creds already present.
    if _has_existing_credentials():
        console.print("[dim]Existing credentials detected.[/dim]")
        if typer.confirm("Use them?", default=True):
            print_success("Using existing credentials.")
        else:
            _auth_menu(base_url)
    else:
        _auth_menu(base_url)

    # 2. BYOK LLM (optional).
    console.print()
    if typer.confirm("Set a bring-your-own-key (BYOK) LLM provider?", default=False):
        from teardrop_cli.commands.llm_config import _byok_interactive

        _byok_interactive(base_url=base_url)

    # 3. What's next?
    console.print()
    console.print("[bold]What would you like to do next?[/bold]")
    console.print("  [cyan]1[/cyan]  Scaffold a tool to publish")
    console.print("  [cyan]2[/cyan]  Run a sample agent prompt")
    console.print("  [cyan]3[/cyan]  Exit")
    choice = typer.prompt("Choice", default="3")

    if choice == "1":
        _scaffold_branch()
    elif choice == "2":
        _sample_run_branch(base_url)
    else:
        console.print("\nAll set. Run [bold]teardrop --help[/bold] to explore commands.")


def _has_existing_credentials() -> bool:
    """True if any credential source can authenticate the next request."""
    import os

    from teardrop_cli import config

    if os.environ.get("TEARDROP_API_KEY") or os.environ.get("TEARDROP_TOKEN"):
        return True
    if os.environ.get("TEARDROP_EMAIL") and os.environ.get("TEARDROP_SECRET"):
        return True
    if os.environ.get("TEARDROP_CLIENT_ID") and os.environ.get("TEARDROP_CLIENT_SECRET"):
        return True
    cfg = config.load_config()
    return bool(cfg.get("access_token"))


def _auth_menu(base_url: str | None) -> None:
    from teardrop_cli.commands.auth import _login_siwe, login, signup
    from teardrop_cli.formatting import console

    console.print("[bold]How would you like to sign in?[/bold]")
    console.print("  [cyan]1[/cyan]  Sign in with Ethereum (recommended for tool authors)")
    console.print("  [cyan]2[/cyan]  Create a new account (email + password)")
    console.print("  [cyan]3[/cyan]  Log in to an existing account")
    choice = typer.prompt("Choice", default="1")

    if choice == "1":
        from teardrop_cli import config

        url = base_url or config.get_base_url()
        # Ask whether to generate a wallet for users who don't have one yet.
        generate = typer.confirm(
            "Generate a new wallet? (Choose 'no' if you already have one)",
            default=False,
        )
        _login_siwe(url, generate_wallet=generate)
    elif choice == "2":
        signup(base_url=base_url)
    else:
        login(base_url=base_url)


def _scaffold_branch() -> None:
    from teardrop_cli.commands.tools import init as tools_init
    from teardrop_cli.formatting import console

    name = typer.prompt("Tool name (lowercase, a-z0-9_)")
    tools_init(name=name, out=None, with_marketplace=False, force=False)
    console.print(
        "\n[dim]Edit [bold]tool.json[/bold], then publish with:[/dim]\n"
        "  [bold]teardrop tools publish --from-file tool.json[/bold]"
    )


def _sample_run_branch(base_url: str | None) -> None:
    from teardrop_cli.formatting import console

    prompt = typer.prompt(
        "Prompt", default="What is the current ETH gas price?", show_default=True
    )
    console.print(
        f"\n[dim]Run it with:[/dim]\n"
        f"  [bold]teardrop run {prompt!r}[/bold]"
    )
