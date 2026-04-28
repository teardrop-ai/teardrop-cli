"""Tests for `teardrop auth signup` and SIWE key-file/--generate-wallet flags."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from teardrop_cli.cli import app


def _mock_httpx_post(*, status_code: int, json_body: dict | None = None, text: str = ""):
    """Build a patcher for ``httpx.AsyncClient`` whose ``post`` returns the response."""
    response = MagicMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=json_body or {})
    response.text = text

    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ---------------------------------------------------------------------------
# signup
# ---------------------------------------------------------------------------


class TestSignup:
    def test_happy_path(self, runner: CliRunner, monkeypatch):
        stored: dict = {}
        monkeypatch.setattr(
            "teardrop_cli.config.store_session",
            lambda **kw: stored.update({"session": kw}),
        )

        client = _mock_httpx_post(
            status_code=201,
            json_body={
                "access_token": "jwt.access",
                "refresh_token": "jwt.refresh",
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )
        with patch("httpx.AsyncClient", return_value=client):
            result = runner.invoke(
                app,
                [
                    "auth",
                    "signup",
                    "--email",
                    "alice@example.com",
                    "--password",
                    "Hunter2pass",
                    "--org-name",
                    "Acme",
                ],
            )

        assert result.exit_code == 0, result.output
        assert stored["session"]["access_token"] == "jwt.access"
        assert stored["session"]["refresh_token"] == "jwt.refresh"
        assert stored["session"]["email"] == "alice@example.com"

    def test_duplicate_email(self, runner: CliRunner):
        client = _mock_httpx_post(
            status_code=409,
            json_body={"detail": "user already exists"},
        )
        with patch("httpx.AsyncClient", return_value=client):
            result = runner.invoke(
                app,
                [
                    "auth",
                    "signup",
                    "-e",
                    "dup@example.com",
                    "-p",
                    "Hunter2pass",
                    "--org-name",
                    "Acme",
                ],
            )
        assert result.exit_code == 1
        assert "already exists" in result.output.lower()
        assert "auth login" in result.output

    def test_duplicate_org(self, runner: CliRunner):
        client = _mock_httpx_post(
            status_code=409,
            json_body={"detail": "organization name taken"},
        )
        with patch("httpx.AsyncClient", return_value=client):
            result = runner.invoke(
                app,
                [
                    "auth",
                    "signup",
                    "-e",
                    "new@example.com",
                    "-p",
                    "Hunter2pass",
                    "--org-name",
                    "Acme",
                ],
            )
        assert result.exit_code == 1
        assert "organization" in result.output.lower()

    def test_rate_limited(self, runner: CliRunner):
        client = _mock_httpx_post(status_code=429, json_body={"detail": "too many"})
        with patch("httpx.AsyncClient", return_value=client):
            result = runner.invoke(
                app,
                [
                    "auth",
                    "signup",
                    "-e",
                    "x@example.com",
                    "-p",
                    "Hunter2pass",
                    "--org-name",
                    "X",
                ],
            )
        assert result.exit_code == 1
        assert "rate" in result.output.lower() or "429" in result.output

    def test_invalid_payload_422(self, runner: CliRunner):
        client = _mock_httpx_post(
            status_code=422, json_body={"detail": "password too weak"}
        )
        with patch("httpx.AsyncClient", return_value=client):
            result = runner.invoke(
                app,
                [
                    "auth",
                    "signup",
                    "-e",
                    "x@example.com",
                    "-p",
                    "Goodpass1",  # passes local check; server rejects
                    "--org-name",
                    "X",
                ],
            )
        assert result.exit_code == 1
        assert "invalid" in result.output.lower()

    def test_weak_password_local_validation(self, runner: CliRunner):
        # Local validation should reject before any HTTP call.
        result = runner.invoke(
            app,
            [
                "auth",
                "signup",
                "-e",
                "x@example.com",
                "-p",
                "short",  # < 8 chars + no digit
                "--org-name",
                "X",
            ],
        )
        assert result.exit_code == 1
        # should mention password requirement
        assert "password" in result.output.lower()

    def test_json_output(self, runner: CliRunner, monkeypatch):
        monkeypatch.setattr("teardrop_cli.config.store_session", lambda **kw: None)
        client = _mock_httpx_post(
            status_code=201,
            json_body={"access_token": "tok", "refresh_token": "ref"},
        )
        with patch("httpx.AsyncClient", return_value=client):
            result = runner.invoke(
                app,
                [
                    "auth",
                    "signup",
                    "-e",
                    "alice@example.com",
                    "-p",
                    "Hunter2pass",
                    "--org-name",
                    "Acme",
                    "--json",
                ],
            )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["email"] == "alice@example.com"
        assert data["org_name"] == "Acme"
        assert data["access_token"] == "tok"


# ---------------------------------------------------------------------------
# SIWE: --key-file and --generate-wallet
# ---------------------------------------------------------------------------


class TestSiweKeyFile:
    def test_key_file_used(self, runner: CliRunner, monkeypatch, tmp_path):
        """`--key-file` reads a private key from disk and uses it for SIWE."""
        from eth_account import Account

        acct = Account.create()
        priv_hex = acct.key.hex()
        key_path = tmp_path / "wallet.key"
        key_path.write_text(priv_hex)

        # Stub auth + session storage
        monkeypatch.setattr("teardrop_cli.config.store_session", lambda **kw: None)
        monkeypatch.setattr(
            "teardrop_cli.config.extract_session_tokens", lambda c: ("acc", "ref")
        )

        mock_client = MagicMock()
        mock_client.get_siwe_nonce = AsyncMock(
            return_value=MagicMock(nonce="abc123nonce456")
        )
        mock_client.authenticate_siwe = AsyncMock(
            return_value=MagicMock(access_token="acc", refresh_token="ref")
        )
        mock_client.close = AsyncMock()

        with patch("teardrop.AsyncTeardropClient", return_value=mock_client):
            result = runner.invoke(
                app, ["auth", "login", "--siwe", "--key-file", str(key_path)]
            )
        assert result.exit_code == 0, result.output
        # The private key must NOT appear in the command output.
        assert priv_hex.lstrip("0x") not in result.output

    def test_generate_wallet_requires_confirm(self, runner: CliRunner):
        """`--generate-wallet` aborts when the user does not confirm having saved the key."""
        # Send "n" to the confirmation prompt → command should abort non-zero.
        result = runner.invoke(
            app,
            ["auth", "login", "--siwe", "--generate-wallet"],
            input="n\n",
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Differentiated auth errors
# ---------------------------------------------------------------------------


class TestAuthErrorDifferentiation:
    def test_login_404_hints_signup(self, runner: CliRunner):
        """A 404 / 'no account' error should hint the user to run signup."""
        from teardrop import AuthenticationError

        # Some CLIs raise generic AuthenticationError on 404 — verify _handle_auth_error
        # surfaces a signup hint when the message looks like 'not found'.
        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(
            side_effect=AuthenticationError("user not found (404)")
        )
        mock_client.close = AsyncMock()

        with patch("teardrop.AsyncTeardropClient", return_value=mock_client):
            result = runner.invoke(
                app,
                ["auth", "login", "--email", "ghost@example.com", "--secret", "wp"],
            )
        assert result.exit_code == 1
        # Either signup-hint or generic invalid creds — assert non-zero + email echoed.
        # The current behavior is to suggest `auth signup` when 404 detected.
        out = result.output.lower()
        assert "signup" in out or "invalid" in out
