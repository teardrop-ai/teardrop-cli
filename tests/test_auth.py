"""Tests for auth commands (login, status, logout)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from teardrop_cli.cli import app


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_static_token(self, runner: CliRunner, monkeypatch):
        stored = {}
        monkeypatch.setattr(
            "teardrop_cli.config.store_token",
            lambda t: stored.update({"token": t}),
        )

        result = runner.invoke(app, ["auth", "login", "--token", "my.jwt.here"])
        assert result.exit_code == 0, result.output
        assert stored["token"] == "my.jwt.here"

    def test_email_password_success(self, runner: CliRunner, monkeypatch):
        from teardrop_cli._fixtures import make_jwt_payload

        stored = {}
        monkeypatch.setattr(
            "teardrop_cli.config.store_email_credentials",
            lambda e, s: stored.update({"email": e, "secret": s}),
        )
        # Avoid touching real session state in writes
        monkeypatch.setattr(
            "teardrop_cli.config.store_session",
            lambda **kw: stored.update({"session": kw}),
        )
        monkeypatch.setattr(
            "teardrop_cli.config.extract_session_tokens",
            lambda c: ("acc-tok", "ref-tok"),
        )

        fake_me = make_jwt_payload(sub="alice@example.com")
        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=fake_me)
        mock_client.close = AsyncMock()

        with patch("teardrop.AsyncTeardropClient", return_value=mock_client):
            result = runner.invoke(
                app,
                ["auth", "login", "--email", "alice@example.com", "--secret", "pass"],
            )

        assert result.exit_code == 0, result.output
        assert stored["email"] == "alice@example.com"
        assert stored["session"]["access_token"] == "acc-tok"
        assert stored["session"]["refresh_token"] == "ref-tok"

    def test_invalid_credentials(self, runner: CliRunner):
        from teardrop import AuthenticationError

        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(side_effect=AuthenticationError("bad creds"))
        mock_client.close = AsyncMock()

        with patch("teardrop.AsyncTeardropClient", return_value=mock_client):
            result = runner.invoke(
                app,
                ["auth", "login", "--email", "x@x.com", "--secret", "wrong"],
            )

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# SIWE login
# ---------------------------------------------------------------------------


class TestSiweLogin:
    def test_siwe_success(self, runner: CliRunner, monkeypatch):
        from eth_account import Account

        stored = {}
        monkeypatch.setattr(
            "teardrop_cli.config.store_session",
            lambda **kw: stored.update(kw),
        )
        monkeypatch.setenv("TEARDROP_SIWE_PRIVATE_KEY", Account.create().key.hex())

        mock_client = MagicMock()
        mock_client.get_siwe_nonce = AsyncMock(return_value={"nonce": "abc123"})
        mock_client.authenticate_siwe = AsyncMock(return_value="jwt.siwe.ok")
        mock_client.close = AsyncMock()

        with patch("teardrop.AsyncTeardropClient", return_value=mock_client):
            result = runner.invoke(app, ["auth", "login", "--siwe"])

        assert result.exit_code == 0, result.output
        assert stored["access_token"] == "jwt.siwe.ok"
        # authenticate_siwe must be called with exactly (message, signature) — no nonce arg
        args, kwargs = mock_client.authenticate_siwe.call_args
        assert len(args) == 2, f"Expected 2 positional args, got {len(args)}"
        assert not kwargs, f"Expected no kwargs, got {kwargs}"

    def test_siwe_missing_env_prompts(self, runner: CliRunner, monkeypatch):
        """With no env key and no flags, --siwe falls back to a hidden prompt.

        Sending an empty stdin aborts the prompt, so we expect a non-zero exit
        and the prompt label in the output.
        """
        monkeypatch.delenv("TEARDROP_SIWE_PRIVATE_KEY", raising=False)
        result = runner.invoke(app, ["auth", "login", "--siwe"], input="")
        assert result.exit_code != 0
        assert "private key" in result.output.lower()


# ---------------------------------------------------------------------------
# status (replaces whoami)
# ---------------------------------------------------------------------------


class TestStatus:
    def test_status_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, result.output

    def test_status_json(self, runner: CliRunner, patch_get_client):
        import json

        result = runner.invoke(app, ["auth", "status", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "sub" in data

    def test_whoami_alias_removed(self, runner: CliRunner, patch_get_client):
        """whoami should NOT exist anymore."""
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "whoami" in result.output


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_clears_credentials(self, runner: CliRunner, monkeypatch):
        cleared = {}
        monkeypatch.setattr(
            "teardrop_cli.config.clear_credentials",
            lambda: cleared.update({"done": True}),
        )
        # No refresh token stored → no server call
        monkeypatch.setattr("teardrop_cli.config.get_refresh_token", lambda: None)

        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0
        assert cleared.get("done")

    def test_logout_calls_server_when_refresh_present(
        self, runner: CliRunner, monkeypatch
    ):
        called = {}
        monkeypatch.setattr(
            "teardrop_cli.config.clear_credentials", lambda: called.update({"clr": True})
        )
        monkeypatch.setattr(
            "teardrop_cli.config.get_refresh_token", lambda: "rt-123"
        )

        mock_client = MagicMock()
        mock_client.logout = AsyncMock(return_value=None)
        mock_client.close = AsyncMock()

        with patch("teardrop.AsyncTeardropClient", return_value=mock_client):
            result = runner.invoke(app, ["auth", "logout"])

        assert result.exit_code == 0
        mock_client.logout.assert_awaited_once_with("rt-123")
        assert called.get("clr")
