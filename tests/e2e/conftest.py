"""Shared fixtures for live end-to-end tests.

Required env vars:
    TEARDROP_E2E=1
    TEARDROP_API_KEY (for static JWT) OR TEARDROP_EMAIL + TEARDROP_SECRET

Optional:
    TEARDROP_E2E_BASE_URL            default: https://api.teardrop.dev
    TEARDROP_E2E_TEST_TOOL           required for marketplace lifecycle test
    TEARDROP_E2E_WALLET_PRIVATE_KEY  required for live SIWE login test

All tests are skipped automatically when TEARDROP_E2E is absent, so the
default ``pytest`` run is never affected.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Guard: skip every test in this package unless TEARDROP_E2E=1
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_e2e_env() -> None:
    """Skip any test in tests/e2e/ unless TEARDROP_E2E=1 is set."""
    if not os.environ.get("TEARDROP_E2E"):
        pytest.skip("Set TEARDROP_E2E=1 to run live end-to-end tests.")


# ---------------------------------------------------------------------------
# Credential fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def live_creds() -> dict[str, str | None]:
    """Return live credentials from env; skip the test if none are present.

    Credentials are read from standard Teardrop env vars:
    - TEARDROP_API_KEY (for static JWT tokens)
    - TEARDROP_EMAIL + TEARDROP_SECRET (for email/password auth)
    """
    token = os.environ.get("TEARDROP_API_KEY")
    email = os.environ.get("TEARDROP_EMAIL")
    secret = os.environ.get("TEARDROP_SECRET")
    base_url = os.environ.get("TEARDROP_E2E_BASE_URL", "https://api.teardrop.dev")

    if not token and not (email and secret):
        pytest.skip(
            "No credentials: set TEARDROP_API_KEY "
            "or TEARDROP_EMAIL + TEARDROP_SECRET"
        )

    return {"token": token, "email": email, "secret": secret, "base_url": base_url}


# ---------------------------------------------------------------------------
# Runner fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def blank_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_creds: dict[str, str | None],
) -> CliRunner:
    """CliRunner with an isolated config dir and NO pre-stored credentials.

    Use this for auth-flow tests that need to test login itself.
    """
    config_dir = tmp_path / ".teardrop"
    config_dir.mkdir()
    monkeypatch.setattr("teardrop_cli.config.get_config_dir", lambda: config_dir)
    monkeypatch.setenv("TEARDROP_BASE_URL", live_creds["base_url"])
    # Strip any ambient credential env vars so the runner starts unauthenticated
    for key in ("TEARDROP_API_KEY", "TEARDROP_TOKEN", "TEARDROP_EMAIL", "TEARDROP_SECRET"):
        monkeypatch.delenv(key, raising=False)
    return CliRunner()


@pytest.fixture()
def live_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    live_creds: dict[str, str | None],
) -> CliRunner:
    """CliRunner with an isolated config dir and live credentials as env vars.

    Use this for tests that assume the user is already authenticated.
    Credentials are set as env vars (priority 1 in credential resolution)
    rather than stored in config files to ensure they take precedence.
    """
    config_dir = tmp_path / ".teardrop"
    config_dir.mkdir()
    monkeypatch.setattr("teardrop_cli.config.get_config_dir", lambda: config_dir)
    monkeypatch.setenv("TEARDROP_BASE_URL", live_creds["base_url"])

    # Set credentials as env vars (priority 1) so they always take precedence
    if live_creds.get("token"):
        monkeypatch.setenv("TEARDROP_API_KEY", live_creds["token"])
    elif live_creds.get("email") and live_creds.get("secret"):
        monkeypatch.setenv("TEARDROP_EMAIL", live_creds["email"])
        monkeypatch.setenv("TEARDROP_SECRET", live_creds["secret"])

    return CliRunner()
