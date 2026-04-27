"""Tests for billing-related top-level commands: balance, usage, topup."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestBalance:
    def test_balance_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["balance"])
        assert result.exit_code == 0, result.output
        assert "Credit balance" in result.output

    def test_balance_json(self, runner: CliRunner, patch_get_client):
        import json

        result = runner.invoke(app, ["balance", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["balance_usdc"] == 5_000_000


class TestUsage:
    def test_usage_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["usage"])
        assert result.exit_code == 0, result.output
        assert "Total runs" in result.output

    def test_usage_with_dates(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(
            app, ["usage", "--start", "2025-01-01", "--end", "2025-01-31"]
        )
        assert result.exit_code == 0, result.output
        mock_client.get_usage.assert_awaited()


class TestTopupUsdc:
    def test_topup_usdc(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["topup", "usdc", "--amount", "10.00"])
        assert result.exit_code == 0, result.output
        mock_client.get_usdc_topup_requirements.assert_awaited()

    def test_topup_usdc_invalid_amount(
        self, runner: CliRunner, patch_get_client
    ):
        result = runner.invoke(app, ["topup", "usdc", "--amount", "not-a-number"])
        assert result.exit_code == 1


class TestTopupStripe:
    def test_topup_stripe_no_browser(
        self, runner: CliRunner, patch_get_client, mock_client, monkeypatch
    ):
        # Mock get_stripe_topup_status to return complete on first poll
        result = runner.invoke(
            app,
            [
                "topup",
                "stripe",
                "--amount",
                "5.00",
                "--no-browser",
                "--poll-timeout",
                "5",
            ],
        )
        assert result.exit_code == 0, result.output
        mock_client.topup_stripe.assert_awaited()
