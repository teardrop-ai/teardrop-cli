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
    from teardrop_cli.formatting import console

    from teardrop_cli import config

    is_repeat = config.has_existing_credentials()

    if not is_repeat:
        console.print(
            "\n[bold cyan]Welcome to Teardrop.[/bold cyan]  "
            "[dim]This wizard will get you running in under a minute.[/dim]\n"
        )

    # 1. Auth — use existing creds if present, otherwise guide through auth.
    if is_repeat:
        console.print("[dim]Existing credentials detected.[/dim]")
        console.print(f"[dim](source: {config.detect_credential_source()})[/dim]")
        console.print(
            "[dim]Stored credentials found locally. "
            "They will be verified on first authenticated command.[/dim]"
        )
    else:
        _auth_menu(base_url)

    # 2. What's next?
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
            save_key = typer.confirm(
                "Save the private key in your OS keyring for future re-authentication?",
                default=False,
            )
            _login_siwe(url, generate_wallet=generate, save_key=save_key)
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
