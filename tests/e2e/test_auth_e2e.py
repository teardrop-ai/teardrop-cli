"""Live end-to-end tests for authentication flows.

Covers:
- login → status → logout round-trip (email/secret or token)
- token refresh: corrupt access_token, verify an authed command still works
- credential resolution priority: TEARDROP_API_KEY env overrides config file
"""

from __future__ import annotations

import json

import pytest

from teardrop_cli.cli import app

pytestmark = pytest.mark.e2e


class TestLoginStatusLogout:
    def test_roundtrip(self, blank_runner, live_creds) -> None:
        """login → status → logout completes without errors."""
        # --- Login ---
        if live_creds.get("token"):
            login_result = blank_runner.invoke(
                app, ["auth", "login", "--token", live_creds["token"]]
            )
        else:
            login_result = blank_runner.invoke(
                app,
                [
                    "auth",
                    "login",
                    "--email",
                    live_creds["email"],
                    "--secret",
                    live_creds["secret"],
                ],
            )
        assert login_result.exit_code == 0, login_result.output

        # --- Status ---
        status_result = blank_runner.invoke(app, ["auth", "status", "--json"])
        assert status_result.exit_code == 0, status_result.output
        data = json.loads(status_result.output)
        assert "sub" in data

        # --- Logout ---
        logout_result = blank_runner.invoke(app, ["auth", "logout"])
        assert logout_result.exit_code == 0, logout_result.output

    def test_status_after_logout_fails(self, blank_runner, live_creds) -> None:
        """After logout, auth status must exit non-zero."""
        # Login then logout
        if live_creds.get("token"):
            blank_runner.invoke(app, ["auth", "login", "--token", live_creds["token"]])
        else:
            blank_runner.invoke(
                app,
                [
                    "auth",
                    "login",
                    "--email",
                    live_creds["email"],
                    "--secret",
                    live_creds["secret"],
                ],
            )
        blank_runner.invoke(app, ["auth", "logout"])

        status_result = blank_runner.invoke(app, ["auth", "status"])
        assert status_result.exit_code != 0


class TestTokenRefresh:
    def test_refresh_restores_access(
        self,
        blank_runner,
        live_creds,
        monkeypatch,
        tmp_path,
    ) -> None:
        """After corrupting the stored access_token, an authed command still succeeds.

        Proves the SDK's token-manager refresh path is wired correctly through
        the CLI.  Requires email+secret login (not static-token) so a real
        refresh token is issued.
        """
        if not live_creds.get("email"):
            pytest.skip("Token refresh requires email+secret credentials")

        # Login to obtain a real refresh token
        blank_runner.invoke(
            app,
            [
                "auth",
                "login",
                "--email",
                live_creds["email"],
                "--secret",
                live_creds["secret"],
            ],
        )

        # Corrupt the access token (simulates expiry; server will 401)
        from teardrop_cli import config

        cfg = config.load_config()
        cfg["access_token"] = (
            "eyJhbGciOiJIUzI1NiJ9"
            ".eyJleHAiOjEwMDAwMDAwMH0"
            ".stale_signature"
        )
        config.save_config(cfg)

        # Any authed command should still succeed via the refresh token
        result = blank_runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, (
            f"Expected refresh to succeed; got exit {result.exit_code}:\n{result.output}"
        )


class TestCredentialResolutionPriority:
    def test_api_key_env_overrides_config(
        self, blank_runner, live_creds, monkeypatch
    ) -> None:
        """TEARDROP_API_KEY env var (priority 1) takes precedence over config file."""
        if not live_creds.get("token"):
            pytest.skip("Requires TEARDROP_E2E_TOKEN to test env-var override")

        # Write a deliberately stale token to the config file
        from teardrop_cli import config

        config.store_token("stale.jwt.will.401")

        # Set the real token as TEARDROP_API_KEY
        monkeypatch.setenv("TEARDROP_API_KEY", live_creds["token"])

        result = blank_runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, (
            f"TEARDROP_API_KEY should override stale config token:\n{result.output}"
        )
