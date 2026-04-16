"""Tests for auth commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from teardrop_cli.cli import app


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_static_token(self, runner: CliRunner, monkeypatch):
        """--token flag stores the token without hitting the API."""
        stored = {}

        monkeypatch.setattr(
            "teardrop_cli.config.store_token",
            lambda t: stored.update({"token": t}),
        )

        result = runner.invoke(app, ["auth", "login", "--token", "my.jwt.here"])
        assert result.exit_code == 0, result.output
        assert stored["token"] == "my.jwt.here"

    def test_email_password_success(self, runner: CliRunner, monkeypatch):
        """Interactive email+password login succeeds and stores credentials."""
        from teardrop_cli._fixtures import make_jwt_payload

        stored = {}
        monkeypatch.setattr(
            "teardrop_cli.config.store_email_credentials",
            lambda e, s: stored.update({"email": e, "secret": s}),
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

    def test_invalid_credentials(self, runner: CliRunner, monkeypatch):
        """Authentication error is surfaced as exit code 1."""
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

    def test_client_credentials(self, runner: CliRunner, monkeypatch):
        """M2M client credentials login succeeds."""
        from teardrop_cli._fixtures import make_jwt_payload

        stored = {}
        monkeypatch.setattr(
            "teardrop_cli.config.store_client_credentials",
            lambda cid, cs: stored.update({"client_id": cid}),
        )

        fake_me = make_jwt_payload(sub="svc@example.com")
        mock_client = MagicMock()
        mock_client.get_me = AsyncMock(return_value=fake_me)
        mock_client.close = AsyncMock()

        with patch("teardrop.AsyncTeardropClient", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "auth",
                    "login",
                    "--client-id",
                    "cid_123",
                    "--client-secret",
                    "csec_abc",
                ],
            )

        assert result.exit_code == 0, result.output
        assert stored["client_id"] == "cid_123"


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
        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0
        assert cleared.get("done")


# ---------------------------------------------------------------------------
# whoami
# ---------------------------------------------------------------------------


class TestWhoami:
    def test_whoami_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code == 0, result.output

    def test_whoami_json(self, runner: CliRunner, patch_get_client):
        import json

        result = runner.invoke(app, ["auth", "whoami", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "sub" in data

    def test_whoami_no_credentials(self, runner: CliRunner, monkeypatch):
        """Calling whoami without credentials exits with code 1."""
        monkeypatch.setattr(
            "teardrop_cli.config.get_client",
            lambda *a, **kw: (_ for _ in ()).throw(SystemExit(1)),
        )
        result = runner.invoke(app, ["auth", "whoami"])
        assert result.exit_code != 0
