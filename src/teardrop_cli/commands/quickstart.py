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
    from teardrop_cli import config
    if config.has_existing_credentials():
        console.print("[dim]Existing credentials detected.[/dim]")
        if typer.confirm("Use them?", default=True):
            print_success("Using existing credentials.")
        else:
            _auth_menu(base_url)
    else:
        _auth_menu(base_url)

    # 2. What's next?
    console.print()
    console.print("[bold]What would you like to do next?[/bold]")
    console.print("  [cyan]1[/cyan]  Scaffold a tool to publish")
    console.print("  [cyan]2[/cyan]  Run a sample agent prompt")
    console.print("  [cyan]3[/cyan]  Browse marketplace tools")
    console.print("  [cyan]4[/cyan]  Exit")
    choice = typer.prompt("Choice", default="2")

    if choice == "1":
        _scaffold_branch()
    elif choice == "2":
        _sample_run_branch(base_url)
    elif choice == "3":
        _marketplace_browse_branch(base_url)
    else:
        console.print("\nAll set. Run [bold]teardrop --help[/bold] to explore commands.")


def _has_existing_credentials() -> bool:
    """True if get_client() would succeed without prompting the user.

    Mirrors the full resolution order in config.get_client() so the wizard
    never shows an auth prompt when valid credentials already exist.
    """
    import os

    from teardrop_cli import config

    # Env vars (priorities 1-3)
    if os.environ.get("TEARDROP_API_KEY") or os.environ.get("TEARDROP_TOKEN"):
        return True
    if os.environ.get("TEARDROP_EMAIL") and os.environ.get("TEARDROP_SECRET"):
        return True
    if os.environ.get("TEARDROP_CLIENT_ID") and os.environ.get("TEARDROP_CLIENT_SECRET"):
        return True

    # Config file (priority 4)
    cfg = config.load_config()
    if cfg.get("access_token") or cfg.get("auth", {}).get("token"):
        return True

    # Keyring (priority 5) — mirrors get_client() fallback
    if config._keyring_available():
        import keyring

        email = keyring.get_password(config._KEYRING_SERVICE, config._KEYRING_EMAIL_KEY)
        secret = keyring.get_password(config._KEYRING_SERVICE, config._KEYRING_SECRET_KEY)
        if email and secret:
            return True
        cid = keyring.get_password(config._KEYRING_SERVICE, config._KEYRING_CLIENT_ID_KEY)
        csecret = keyring.get_password(
            config._KEYRING_SERVICE, config._KEYRING_CLIENT_SECRET_KEY
        )
        if cid and csecret:
            return True

    return False


def _auth_menu(base_url: str | None) -> None:
    from teardrop_cli.commands.auth import _login_siwe, login, signup
    from teardrop_cli.formatting import console

    has_account = typer.confirm("Do you have a Teardrop account already?", default=False)

    if not has_account:
        console.print("\n[bold]Create your account:[/bold]")
        console.print(
            "  [cyan]1[/cyan]  Ethereum wallet — fastest, no email needed [recommended]"
        )
        console.print("  [cyan]2[/cyan]  Email + password")
        choice = typer.prompt("Choice", default="1")

        if choice == "2":
            signup(base_url=base_url)
        else:
            from teardrop_cli import config

            url = base_url or config.get_base_url()
            generate = typer.confirm("Generate a new wallet?", default=True)
            _login_siwe(url, generate_wallet=generate)
    else:
        console.print("\n[bold]Sign in:[/bold]")
        console.print("  [cyan]1[/cyan]  Ethereum wallet")
        console.print("  [cyan]2[/cyan]  Email + password")
        choice = typer.prompt("Choice", default="2")

        if choice == "1":
            from teardrop_cli import config

            url = base_url or config.get_base_url()
            generate = typer.confirm("Generate a new wallet?", default=True)
            _login_siwe(url, generate_wallet=generate)
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
    import asyncio

    from teardrop_cli import config
    from teardrop_cli.commands.run import _handle_run_error, _stream
    from teardrop_cli.formatting import console

    message = typer.prompt(
        "Prompt", default="What is the current ETH gas price?", show_default=True
    )
    console.print()
    if typer.confirm(
        "Configure a BYOK LLM key first? (skip if you have credits)", default=False
    ):
        from teardrop_cli.commands.llm_config import _byok_interactive

        _byok_interactive(base_url=base_url)
        console.print()

    client = config.get_client(base_url)
    try:
        asyncio.run(_stream(client, message, None, None))
    except Exception as exc:  # noqa: BLE001
        _handle_run_error(exc)
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
        "\n[dim]Subscribe to a tool:[/dim]\n"
        "  [bold]teardrop marketplace subscribe <name>[/bold]\n"
    )
