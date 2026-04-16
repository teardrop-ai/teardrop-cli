"""auth commands: login, logout, whoami."""

from __future__ import annotations

import asyncio
from typing import Annotated, Optional

import typer

app = typer.Typer(
    name="auth",
    help="Authentication — login, logout, and identity.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


@app.command()
def login(
    email: Annotated[Optional[str], typer.Option("--email", "-e", help="Email address.")] = None,
    secret: Annotated[
        Optional[str],
        typer.Option("--secret", "-s", help="Password / secret.", hide_input=True),
    ] = None,
    client_id: Annotated[
        Optional[str], typer.Option("--client-id", help="M2M client ID.")
    ] = None,
    client_secret: Annotated[
        Optional[str],
        typer.Option("--client-secret", help="M2M client secret.", hide_input=True),
    ] = None,
    token: Annotated[
        Optional[str],
        typer.Option("--token", "-t", help="Pre-existing static JWT token.", hide_input=True),
    ] = None,
    siwe: Annotated[bool, typer.Option("--siwe", help="Sign in with Ethereum wallet.")] = False,
    base_url: Annotated[
        Optional[str], typer.Option("--base-url", help="Override the API base URL.", hidden=True)
    ] = None,
) -> None:
    """Authenticate with the Teardrop API and store credentials locally."""
    from teardrop import AsyncTeardropClient

    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_error, print_success, spinner

    url = base_url or config.get_base_url()

    # ------------------------------------------------------------------ #
    # Static token                                                         #
    # ------------------------------------------------------------------ #
    if token:
        config.store_token(token)
        print_success("Token stored. Run [bold]teardrop auth whoami[/bold] to verify.")
        return

    # ------------------------------------------------------------------ #
    # SIWE (Sign-In With Ethereum)                                         #
    # ------------------------------------------------------------------ #
    if siwe:
        _login_siwe(url)
        return

    # ------------------------------------------------------------------ #
    # Client credentials (M2M)                                             #
    # ------------------------------------------------------------------ #
    if client_id or client_secret:
        if not client_id:
            client_id = typer.prompt("Client ID")
        if not client_secret:
            client_secret = typer.prompt("Client secret", hide_input=True)

        with spinner("Authenticating…"):
            client = AsyncTeardropClient(url, client_id=client_id, client_secret=client_secret)
            try:
                me = asyncio.run(client.get_me())
            except Exception as exc:
                _handle_auth_error(exc)
                return
            finally:
                asyncio.run(client.close())

        config.store_client_credentials(client_id, client_secret)
        print_success(f"Authenticated as [bold]{me.sub}[/bold] (client credentials).")
        return

    # ------------------------------------------------------------------ #
    # Email + password (interactive)                                       #
    # ------------------------------------------------------------------ #
    if not email:
        email = typer.prompt("Email")
    if not secret:
        secret = typer.prompt("Password", hide_input=True)

    with spinner("Authenticating…"):
        client = AsyncTeardropClient(url, email=email, secret=secret)
        try:
            me = asyncio.run(client.get_me())
        except Exception as exc:
            _handle_auth_error(exc)
            return
        finally:
            asyncio.run(client.close())

    config.store_email_credentials(email, secret)
    print_success(f"Authenticated as [bold]{me.sub}[/bold].")


def _login_siwe(url: str) -> None:
    """Interactive SIWE (Sign-In With Ethereum) login flow."""
    import asyncio

    from teardrop import AsyncTeardropClient

    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_error, print_success, spinner

    private_key = typer.prompt(
        "Private key (hex, 0x-prefixed)",
        hide_input=True,
    )

    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        print_error(
            "eth-account is required for SIWE login.",
            hint="Install it with: pip install eth-account",
        )
        raise typer.Exit(1)

    account = Account.from_key(private_key)
    wallet_address = account.address
    console.print(f"[dim]Wallet:[/dim] {wallet_address}")

    async def _do_siwe() -> str:
        client = AsyncTeardropClient(url)
        try:
            nonce_resp = await client.get_siwe_nonce()
            nonce = nonce_resp.get("nonce", nonce_resp.get("value", ""))

            # Construct EIP-4361 message
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            message = (
                f"{domain} wants you to sign in with your Ethereum account:\n"
                f"{wallet_address}\n\n"
                f"Sign in to Teardrop\n\n"
                f"URI: {url}\n"
                f"Version: 1\n"
                f"Chain ID: 1\n"
                f"Nonce: {nonce}"
            )

            signable = encode_defunct(text=message)
            signed = account.sign_message(signable)
            signature = signed.signature.hex()
            if not signature.startswith("0x"):
                signature = "0x" + signature

            jwt_token = await client.authenticate_siwe(message, signature, nonce)
            return jwt_token
        finally:
            await client.close()

    with spinner("Signing in with Ethereum…"):
        try:
            jwt_token = asyncio.run(_do_siwe())
        except Exception as exc:
            _handle_auth_error(exc)
            return

    config.store_token(jwt_token)
    print_success(f"Authenticated via SIWE as [bold]{wallet_address}[/bold].")


def _handle_auth_error(exc: Exception) -> None:
    from teardrop import AuthenticationError, APIError

    from teardrop_cli.formatting import print_error

    if isinstance(exc, AuthenticationError):
        print_error("Invalid credentials.", hint="Check your email and password.")
    elif isinstance(exc, APIError):
        print_error(f"API error {exc.status_code}.", hint=str(exc))
    else:
        print_error(str(exc))
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


@app.command()
def logout() -> None:
    """Remove stored credentials."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_success

    config.clear_credentials()
    print_success("Logged out. Credentials removed.")


# ---------------------------------------------------------------------------
# whoami
# ---------------------------------------------------------------------------


@app.command()
def whoami(
    base_url: Annotated[
        Optional[str], typer.Option("--base-url", help="Override the API base URL.", hidden=True)
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show the currently authenticated user."""
    import asyncio

    from teardrop_cli import config
    from teardrop_cli.formatting import print_json, print_table, spinner

    client = config.get_client(base_url)

    with spinner("Fetching identity…"):
        try:
            me = asyncio.run(client.get_me())
        finally:
            asyncio.run(client.close())

    data = me.model_dump()
    if as_json:
        print_json(data)
        return

    rows = [[k, v] for k, v in data.items() if v is not None]
    print_table(
        [("Field", {"style": "bold cyan"}), "Value"],
        rows,
        title="Current User",
    )
