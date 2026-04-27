"""Live end-to-end test for SIWE (Sign-In-With-Ethereum) login.

Requires:
    TEARDROP_E2E_WALLET_PRIVATE_KEY — hex private key of a pre-registered
    test wallet (or any wallet if the staging environment accepts new signups).

If the env var is absent the test is skipped cleanly.
"""

from __future__ import annotations

import os

import pytest

from teardrop_cli.cli import app

pytestmark = pytest.mark.e2e


class TestSiweLogin:
    def test_siwe_login_stores_jwt(self, blank_runner, monkeypatch) -> None:
        """``auth login --siwe`` with a valid private key stores a JWT and exits 0."""
        private_key = os.environ.get("TEARDROP_E2E_WALLET_PRIVATE_KEY")
        if not private_key:
            pytest.skip(
                "Set TEARDROP_E2E_WALLET_PRIVATE_KEY=0x<key> to run the live SIWE test"
            )

        monkeypatch.setenv("TEARDROP_SIWE_PRIVATE_KEY", private_key)

        result = blank_runner.invoke(app, ["auth", "login", "--siwe"])
        assert result.exit_code == 0, result.output

        # The JWT must now be stored in the config file
        from teardrop_cli import config

        cfg = config.load_config()
        token = cfg.get("access_token")
        assert token, "Expected access_token in config after SIWE login"
        # JWT format: three base64url segments separated by dots
        assert token.count(".") >= 2, (
            f"Stored token does not look like a JWT: {token!r}"
        )

    def test_siwe_status_after_login(self, blank_runner, monkeypatch) -> None:
        """After SIWE login, ``auth status`` succeeds and returns the wallet address."""
        private_key = os.environ.get("TEARDROP_E2E_WALLET_PRIVATE_KEY")
        if not private_key:
            pytest.skip(
                "Set TEARDROP_E2E_WALLET_PRIVATE_KEY=0x<key> to run the live SIWE test"
            )

        monkeypatch.setenv("TEARDROP_SIWE_PRIVATE_KEY", private_key)

        login_result = blank_runner.invoke(app, ["auth", "login", "--siwe"])
        assert login_result.exit_code == 0, login_result.output

        status_result = blank_runner.invoke(app, ["auth", "status", "--json"])
        assert status_result.exit_code == 0, status_result.output

        import json

        data = json.loads(status_result.output)
        assert "sub" in data
