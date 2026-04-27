"""Live end-to-end tests for billing commands: balance, usage, topup.

Covers:
- balance --json returns a dict with numeric balance_usdc
- usage --json returns expected schema fields
- topup stripe creates a real Stripe session (URL is printed before polling)
  [gated behind TEARDROP_E2E_STRIPE=1 — creates an abandoned session with no
   server-side cancel API, so opt-in only]
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import pytest

from teardrop_cli.cli import app

pytestmark = pytest.mark.e2e


class TestBalance:
    def test_balance_returns_numeric_usdc(self, live_runner) -> None:
        """``balance --json`` returns a parseable dict with a numeric balance field."""
        result = live_runner.invoke(app, ["balance", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "balance_usdc" in data, f"Missing balance_usdc in: {data}"
        assert isinstance(data["balance_usdc"], int), (
            f"balance_usdc must be int (atomic USDC), got {type(data['balance_usdc'])}"
        )

    def test_balance_table_renders(self, live_runner) -> None:
        """``balance`` (table output) exits 0 and mentions 'Credit balance'."""
        result = live_runner.invoke(app, ["balance"])
        assert result.exit_code == 0, result.output
        assert "Credit balance" in result.output


class TestUsage:
    def test_usage_json_schema(self, live_runner) -> None:
        """``usage --json`` returns all expected schema fields."""
        start = (date.today() - timedelta(days=30)).isoformat()
        result = live_runner.invoke(app, ["usage", "--json", "--start", start])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        for field in ("total_runs", "total_tokens_in", "total_tokens_out"):
            assert field in data, f"Missing field '{field}' in usage response: {data}"

    def test_usage_table_renders(self, live_runner) -> None:
        """``usage`` (table output) exits 0 and mentions 'Total runs'."""
        result = live_runner.invoke(app, ["usage"])
        assert result.exit_code == 0, result.output
        assert "Total runs" in result.output


class TestTopupStripe:
    def test_stripe_session_url_printed(self, live_runner) -> None:
        """``topup stripe --no-browser`` creates a Stripe session and prints the URL.

        Uses ``--poll-timeout 1`` so the test exits quickly (with code 2 for
        timeout) rather than waiting for a human to complete checkout.  We only
        assert that a checkout URL was printed — proving the Stripe session was
        successfully created on the live API.

        Gated behind ``TEARDROP_E2E_STRIPE=1``: the SDK has no session-cancel
        method, so each run creates an abandoned Stripe checkout session that
        expires after ~24 h.  Opt-in explicitly when you want to test this path.
        """
        if not os.environ.get("TEARDROP_E2E_STRIPE"):
            pytest.skip(
                "Set TEARDROP_E2E_STRIPE=1 to run the Stripe session creation test "
                "(creates an abandoned session; expires ~24 h, cannot be cancelled via API)"
            )
        result = live_runner.invoke(
            app,
            [
                "topup",
                "stripe",
                "--amount",
                "1.00",
                "--no-browser",
                "--poll-timeout",
                "1",
            ],
        )
        # Exit code is 2 (poll timeout) or 0 (completed instantly on staging)
        assert result.exit_code in (0, 2), result.output
        # The checkout URL must have been printed before polling started
        assert "checkout.stripe.com" in result.output or "https://" in result.output, (
            f"Expected a Stripe checkout URL in output:\n{result.output}"
        )
