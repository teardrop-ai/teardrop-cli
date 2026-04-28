"""auth commands: signup, login, login --siwe, status, logout."""

from __future__ import annotations

import asyncio
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="auth",
    help="Authentication — signup, login, status, and logout.",
    no_args_is_help=True,
)


# Backend rule: ≥8 chars, must contain a digit (mirrored client-side for
# fast feedback; server is the source of truth).
_PASSWORD_MIN_LEN = 8
_PASSWORD_DIGIT_RE = re.compile(r"\d")


# ---------------------------------------------------------------------------
# signup
# ---------------------------------------------------------------------------


def _validate_password(password: str) -> str | None:
    """Return an error message if *password* fails local validation, else None."""
    if len(password) < _PASSWORD_MIN_LEN:
        return f"Password must be at least {_PASSWORD_MIN_LEN} characters."
    if not _PASSWORD_DIGIT_RE.search(password):
        return "Password must contain at least one digit."
    return None


@app.command()
def signup(
    email: Annotated[str | None, typer.Option("--email", "-e", help="Email address.")] = None,
    password: Annotated[
        str | None,
        typer.Option("--password", "-p", help="Password (≥8 chars, ≥1 digit).", hide_input=True),
    ] = None,
    org_name: Annotated[
        str | None,
        typer.Option("--org-name", help="Organization name (1–200 chars)."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output the JWT response as JSON.")] = False,
    base_url: Annotated[
        str | None, typer.Option("--base-url", help="Override the API base URL.", hidden=True)
    ] = None,
) -> None:
    """Create a new Teardrop account and organization.

    Calls ``POST /register``. On success, the returned JWT is stored locally
    so subsequent commands work immediately — no second login step required.
    """
    import httpx

    from teardrop_cli import config
    from teardrop_cli.formatting import print_error, print_json, print_success, print_warning, spinner

    url = base_url or config.get_base_url()

    # Interactive prompts for missing fields.
    if not email:
        email = typer.prompt("Email")
    if not org_name:
        org_name = typer.prompt("Organization name")
    if not password:
        password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)

    # Local validation (fast feedback; server still authoritative).
    if not (1 <= len(org_name) <= 200):
        print_error("Organization name must be 1–200 characters.")
        raise typer.Exit(1)
    if err := _validate_password(password):
        print_error(err)
        raise typer.Exit(1)

    payload = {"email": email, "password": password, "org_name": org_name}

    async def _do_signup() -> dict:
        async with httpx.AsyncClient(base_url=url, timeout=30.0) as http:
            resp = await http.post("/register", json=payload)
            return _interpret_signup_response(resp, email=email)

    try:
        with spinner("Creating account…"):
            data = asyncio.run(_do_signup())
    finally:
        # Best-effort scrub of the password string from the local frame.
        password = "0" * len(password)  # noqa: F841
        del password
        payload.pop("password", None)

    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if not access:
        print_error("Signup succeeded but the server returned no access token.")
        raise typer.Exit(1)

    config.store_session(
        access_token=access,
        refresh_token=refresh,
        email=email,
    )

    if as_json:
        # Never echo the raw password; the response itself is safe to print.
        print_json({"email": email, "org_name": org_name, **data})
        return

    print_success(f"Account created — welcome, [bold]{email}[/bold] (org: {org_name}).")
    if data.get("email_verification_required"):
        print_warning(
            "Check your inbox to verify your email — required before next password login."
        )
    print_success("You're signed in. Try: [bold]teardrop balance[/bold]")


def _interpret_signup_response(resp, *, email: str) -> dict:
    """Translate ``POST /register`` HTTP response into either a token dict or a typer.Exit."""
    from teardrop_cli.formatting import print_error

    if resp.status_code == 201 or resp.status_code == 200:
        return resp.json()

    body: dict = {}
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"detail": resp.text[:200]}
    detail = str(body.get("detail") or body.get("message") or "").lower()

    if resp.status_code == 409:
        if "org" in detail or "name" in detail:
            print_error(
                "That organization name is taken.",
                hint="Choose a different --org-name and try again.",
            )
        else:
            print_error(
                f"An account already exists for {email}.",
                hint="Run: [bold]teardrop auth login[/bold]",
            )
    elif resp.status_code == 422:
        print_error(
            "Invalid signup details.",
            hint=str(body.get("detail") or "Check email format and password rules."),
        )
    elif resp.status_code == 429:
        print_error(
            "Rate limited (3 signups per minute per email).",
            hint="Wait a minute and try again.",
        )
    else:
        print_error(f"Signup failed (HTTP {resp.status_code}).", hint=str(body)[:200])
    raise typer.Exit(1)


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
    key_file: Annotated[
        Path | None,
        typer.Option(
            "--key-file",
            help="(SIWE) Path to a file containing the private key (read once, never stored).",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    generate_wallet: Annotated[
        bool,
        typer.Option(
            "--generate-wallet",
            help="(SIWE) Generate a new wallet, print it once, and sign in with it.",
        ),
    ] = False,
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
    if siwe or generate_wallet or key_file is not None:
        _login_siwe(url, key_file=key_file, generate_wallet=generate_wallet)
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
# SIWE — wallet sign-in (interactive prompt, --key-file, or --generate-wallet)
# ---------------------------------------------------------------------------


def _resolve_siwe_private_key(
    *,
    key_file: Path | None,
    generate_wallet: bool,
) -> tuple[str, bool]:
    """Resolve the private key to use for SIWE.

    Precedence: --generate-wallet > --key-file > TEARDROP_SIWE_PRIVATE_KEY env > prompt.
    Returns ``(private_key, is_generated)``. Caller is responsible for clearing
    the returned string from memory after use.
    """
    from teardrop_cli.formatting import console, print_error, print_success

    if generate_wallet:
        try:
            from eth_account import Account
        except ImportError:
            print_error(
                "eth-account is required.", hint="pip install 'teardrop-cli[siwe]'"
            )
            raise typer.Exit(1) from None
        acct = Account.create()
        from rich.panel import Panel

        console.print(
            Panel.fit(
                f"[bold]Address:[/bold]      {acct.address}\n"
                f"[bold]Private key:[/bold]  {acct.key.hex()}\n\n"
                "[yellow]⚠  Save this private key now. It will not be shown again.[/yellow]\n"
                "[dim]Anyone with this key controls your wallet (and your Teardrop earnings).[/dim]",
                title="New wallet",
                border_style="yellow",
            )
        )
        if not typer.confirm("I have saved my private key", default=False):
            print_error("Aborted. No account created.")
            raise typer.Exit(1)
        print_success("Wallet generated. Continuing with SIWE login…")
        return acct.key.hex(), True

    if key_file is not None:
        text = key_file.read_text(encoding="utf-8").strip()
        if not text:
            print_error(f"{key_file} is empty.")
            raise typer.Exit(1)
        return text, False

    if env_key := os.environ.get("TEARDROP_SIWE_PRIVATE_KEY"):
        return env_key, False

    return typer.prompt("Ethereum private key", hide_input=True), False


def _login_siwe(
    url: str,
    *,
    key_file: Path | None = None,
    generate_wallet: bool = False,
) -> None:
    """SIWE login. First-time signers are auto-registered by the backend."""
    from teardrop import AsyncTeardropClient

    from teardrop_cli import config
    from teardrop_cli.formatting import console, print_success, spinner

    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        from teardrop_cli.formatting import print_error

        print_error(
            "eth-account is required for SIWE login.",
            hint="Install it with: pip install eth-account",
        )
        raise typer.Exit(1) from None

    private_key, _ = _resolve_siwe_private_key(
        key_file=key_file, generate_wallet=generate_wallet
    )

    try:
        account = Account.from_key(private_key)
    except Exception as exc:
        from teardrop_cli.formatting import print_error

        # Avoid leaking the key in the error string.
        print_error(f"Invalid private key: {type(exc).__name__}")
        raise typer.Exit(1) from None

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

    try:
        with spinner("Signing in with Ethereum…"):
            jwt_token = asyncio.run(_do_siwe())
    except Exception as exc:
        _handle_auth_error(exc)
        return
    finally:
        # Best-effort scrub of the key string from the local frame.
        private_key = "0" * len(private_key)  # noqa: F841
        del private_key

    config.store_session(access_token=jwt_token)
    print_success(f"Authenticated via SIWE as [bold]{wallet_address}[/bold].")


def _handle_auth_error(exc: Exception) -> None:
    from teardrop import APIError, AuthenticationError

    from teardrop_cli.formatting import print_error

    if isinstance(exc, AuthenticationError):
        # 401 with a recognized email = wrong password.
        # 401 with no account = differentiated where possible via status/body.
        msg = str(exc).lower()
        status = getattr(exc, "status_code", None)
        if status == 404 or "not found" in msg or "no such" in msg:
            print_error(
                "No account found for that email.",
                hint="Create one with: [bold]teardrop auth signup[/bold]",
            )
        else:
            print_error(
                "Invalid email or password.",
                hint="New here? Run: [bold]teardrop auth signup[/bold]",
            )
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
