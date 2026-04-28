"""Live end-to-end test for ``teardrop auth signup``.

Opt-in via ``TEARDROP_E2E_SIGNUP=1`` (in addition to ``TEARDROP_E2E=1``)
because this test creates a real account on the target environment and
should not run by default even when other e2e tests are enabled.

Required env vars:
    TEARDROP_E2E=1
    TEARDROP_E2E_SIGNUP=1
    TEARDROP_E2E_BASE_URL          (defaults to https://api.teardrop.dev)

Optional env vars:
    TEARDROP_E2E_SIGNUP_EMAIL      (default: signup-e2e+<random>@teardrop.test)
    TEARDROP_E2E_SIGNUP_PASSWORD   (default: a generated 16-char password)
    TEARDROP_E2E_SIGNUP_ORG        (default: teardrop-cli-e2e-<random>)
"""

from __future__ import annotations

import os
import secrets

import pytest
from click.testing import CliRunner

from teardrop_cli.cli import app


pytestmark = pytest.mark.e2e


@pytest.fixture()
def _require_signup_optin() -> None:
    if not os.environ.get("TEARDROP_E2E_SIGNUP"):
        pytest.skip(
            "Set TEARDROP_E2E_SIGNUP=1 to run the live signup test "
            "(creates a real account)."
        )


def test_signup_creates_account(_require_signup_optin):
    """Happy-path: POST /register returns 201 with a usable JWT."""
    rand = secrets.token_hex(4)
    email = os.environ.get(
        "TEARDROP_E2E_SIGNUP_EMAIL", f"signup-e2e+{rand}@teardrop.test"
    )
    password = os.environ.get(
        "TEARDROP_E2E_SIGNUP_PASSWORD", f"Pw{secrets.token_hex(8)}1"
    )
    org = os.environ.get(
        "TEARDROP_E2E_SIGNUP_ORG", f"teardrop-cli-e2e-{rand}"
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "auth",
            "signup",
            "--email",
            email,
            "--password",
            password,
            "--org-name",
            org,
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    # JSON output must include an access_token to confirm the JWT round-tripped.
    assert "access_token" in result.output

    # Smoke check: status should now succeed.
    status = runner.invoke(app, ["auth", "status"])
    assert status.exit_code == 0, status.output
