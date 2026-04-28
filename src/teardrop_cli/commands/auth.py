"""auth commands: login, login --siwe, status, logout."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Annotated

import typer

app = typer.Typer(
    name="auth",
    help="Authentication — login, status, and logout.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


@app.command()
def login(
    email: Annotated[str | None, typer.Option("--email", "-e", help="Email address.")] = None,
    password: Annotated[
        str | None,
        typer.Option("--password", "-p", help="Password.", hide_input=True),
    ] = None,
    secret: Annotated[
        str | None,
        typer.Option("--secret", "-s", help="(Alias of --password.)", hide_input=True),
    ] = None,
    client_id: Annotated[str | None, typer.Option("--client-id", help="M2M client ID.")] = None,
    client_secret: Annotated[
        str | None,
        typer.Option("--client-secret", help="M2M client secret.", hide_input=True),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="Pre-existing static JWT token.", hide_input=True),
    ] = None,
    siwe: Annotated[bool, typer.Option("--siwe", help="Sign in with Ethereum wallet.")] = False,
    base_url: Annotated[
        str | None,
        typer.Option("--base-url", help="Override the API base URL.", hidden=True),
    ] = None,
) -> None:
    """Authenticate with the Teardrop API and store credentials locally."""
    from teardrop import AsyncTeardropClient

    from teardrop_cli import config
    from teardrop_cli.formatting import print_success, spinner

    url = base_url or config.get_base_url()
    password = password or secret  # accept either flag name

    # Static token
    if token:
        config.store_token(token)
        print_success("Token stored. Run [bold]teardrop auth status[/bold] to verify.")
        return

    # SIWE
    if siwe:
        _login_siwe(url)
        return

    # Client credentials (M2M)
    if client_id or client_secret:
        if not client_id:
            client_id = typer.prompt("Client ID")
        if not client_secret:
            client_secret = typer.prompt("Client secret", hide_input=True)

        client = AsyncTeardropClient(url, client_id=client_id, client_secret=client_secret)

        async def _fetch():
            try:
                return await client.get_me()
            finally:
                await client.close()

        with spinner("Authenticating…"):
            try:
                me = asyncio.run(_fetch())
            except Exception as exc:
                _handle_auth_error(exc)
                return

        config.store_client_credentials(client_id, client_secret)
        access, refresh = config.extract_session_tokens(client)
        config.store_session(
            access_token=access,
            refresh_token=refresh,
            email=getattr(me, "email", None) or getattr(me, "sub", None),
            org_id=getattr(me, "org_id", None) or getattr(me, "org", None),
        )
        print_success(
            f"Authenticated as [bold]{getattr(me, 'sub', client_id)}[/bold] (client credentials)."
        )
        return

    # Email + password (interactive)
    if not email:
        email = typer.prompt("Email")
    if not password:
        password = typer.prompt("Password", hide_input=True)

    client = AsyncTeardropClient(url, email=email, secret=password)

    async def _fetch():
        try:
            return await client.get_me()
        finally:
            await client.close()

    with spinner("Authenticating…"):
        try:
            me = asyncio.run(_fetch())
        except Exception as exc:
            _handle_auth_error(exc)
            return

    config.store_email_credentials(email, password)
    access, refresh = config.extract_session_tokens(client)
    org_id = getattr(me, "org_id", None) or getattr(me, "org", None)
    config.store_session(
        access_token=access,
        refresh_token=refresh,
        email=email,
        org_id=org_id,
    )
    org_label = (
        f" (org: {getattr(me, 'org_name', None) or org_id}, role: {getattr(me, 'role', '?')})"
        if org_id
        else ""
    )
    print_success(f"Logged in as [bold]{email}[/bold]{org_label}")


# ---------------------------------------------------------------------------
# SIWE — private key (env var)
# ---------------------------------------------------------------------------


def _login_siwe(url: str) -> None:
    """SIWE login using a private key supplied via TEARDROP_SIWE_PRIVATE_KEY."""
    from teardrop import AsyncTeardropClient

    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_error, print_success, spinner

    private_key = os.environ.get("TEARDROP_SIWE_PRIVATE_KEY")
    if not private_key:
        print_error(
            "TEARDROP_SIWE_PRIVATE_KEY environment variable is not set.",
            hint="Export your Ethereum private key: export TEARDROP_SIWE_PRIVATE_KEY=0x<key>",
        )
        raise typer.Exit(1)

    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        print_error(
            "eth-account is required for SIWE login.",
            hint="Install it with: pip install eth-account",
        )
        raise typer.Exit(1) from None

    account = Account.from_key(private_key)
    wallet_address = account.address
    console.print(f"[dim]Wallet:[/dim] {wallet_address}")

    async def _do_siwe() -> str:
        client = AsyncTeardropClient(url)
        try:
            nonce_resp = await client.get_siwe_nonce()
            nonce = nonce_resp.get("nonce", nonce_resp.get("value", ""))

            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            issued_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            message = (
                f"{domain} wants you to sign in with your Ethereum account:\n"
                f"{wallet_address}\n\n"
                f"Sign in to Teardrop\n\n"
                f"URI: {url}\n"
                f"Version: 1\n"
                f"Chain ID: 1\n"
                f"Nonce: {nonce}\n"
                f"Issued At: {issued_at}"
            )

            signable = encode_defunct(text=message)
            signed = account.sign_message(signable)
            signature = signed.signature.hex()
            if not signature.startswith("0x"):
                signature = "0x" + signature

            return await client.authenticate_siwe(message, signature)
        finally:
            await client.close()

    with spinner("Signing in with Ethereum…"):
        try:
            jwt_token = asyncio.run(_do_siwe())
        except Exception as exc:
            _handle_auth_error(exc)
            return

    config.store_session(access_token=jwt_token)
    print_success(f"Authenticated via SIWE as [bold]{wallet_address}[/bold].")


def _handle_auth_error(exc: Exception) -> None:
    from teardrop import APIError, AuthenticationError

    from teardrop_cli.formatting import print_error

    if isinstance(exc, AuthenticationError):
        print_error("Invalid email or password.")
    elif isinstance(exc, APIError):
        print_error(f"API error {exc.status_code}.", hint=str(exc))
    else:
        print_error(str(exc))
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command()
def status(
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show the currently authenticated user."""
    from teardrop import AuthenticationError

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_json, print_table, spinner

    client = config.get_client(base_url)

    async def _fetch():
        try:
            return await client.get_me()
        finally:
            await client.close()

    try:
        with spinner("Fetching identity…"):
            me = asyncio.run(_fetch())
    except AuthenticationError:
        print_error("Not authenticated.", hint="Run: `teardrop auth login`")
        raise typer.Exit(1) from None

    data = me.model_dump() if hasattr(me, "model_dump") else dict(me)
    if as_json:
        print_json(data)
        return

    rows = [[k, v] for k, v in data.items() if v is not None]
    print_table(
        [("Field", {"style": "bold cyan"}), "Value"],
        rows,
        title="Identity",
    )


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


@app.command()
def logout(
    base_url: Annotated[str | None, typer.Option("--base-url", hidden=True)] = None,
) -> None:
    """Revoke refresh token and clear stored credentials."""
    from teardrop_cli import config
    from teardrop_cli.formatting import print_success, print_warning

    refresh = config.get_refresh_token()
    if refresh:
        try:
            from teardrop import AsyncTeardropClient

            url = base_url or config.get_base_url()
            client = AsyncTeardropClient(url)

            async def _revoke():
                try:
                    await client.logout(refresh)
                finally:
                    await client.close()

            asyncio.run(_revoke())
        except Exception as exc:  # noqa: BLE001
            print_warning(f"Server-side logout failed ({exc}); clearing local credentials anyway.")

    config.clear_credentials()
    print_success("Logged out. Credentials cleared from ~/.teardrop/config.toml")
