"""Tests for billing-related top-level commands: balance, usage, topup."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestBalance:
    def test_balance_default_invokes_show(self, runner: CliRunner, patch_get_client):
        """``teardrop balance`` (no subcommand) shows the balance table."""
        result = runner.invoke(app, ["balance"])
        assert result.exit_code == 0, result.output
        assert "Credit balance" in result.output

    def test_balance_default_with_json(self, runner: CliRunner, patch_get_client):
        """``teardrop balance --json`` returns a parseable dict."""
        import json

        result = runner.invoke(app, ["balance", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["balance_usdc"] == 5_000_000

    def test_balance_show_subcommand(self, runner: CliRunner, patch_get_client):
        """``teardrop balance show`` works explicitly."""
        result = runner.invoke(app, ["balance", "show"])
        assert result.exit_code == 0, result.output
        assert "Credit balance" in result.output

    def test_balance_show_with_json(self, runner: CliRunner, patch_get_client):
        """``teardrop balance show --json`` returns a parseable dict."""
        import json

        result = runner.invoke(app, ["balance", "show", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["balance_usdc"] == 5_000_000


class TestUsage:
    def test_usage_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["usage"])
        assert result.exit_code == 0, result.output
        assert "Total runs" in result.output

    def test_usage_with_dates(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["usage", "--start", "2025-01-01", "--end", "2025-01-31"])
        assert result.exit_code == 0, result.output
        mock_client.get_usage.assert_awaited()


class TestCreditHistory:
    def test_credit_history_table(self, runner: CliRunner, patch_get_client):
        """``teardrop balance credit-history`` renders a table with entries."""
        result = runner.invoke(app, ["balance", "credit-history"])
        assert result.exit_code == 0, result.output
        assert "Subscription fee" in result.output
        assert "Top-up" in result.output
        assert "Amount" in result.output
        assert "USDC" in result.output

    def test_credit_history_json(self, runner: CliRunner, patch_get_client):
        """``teardrop balance credit-history --json`` returns a list."""
        import json

        result = runner.invoke(app, ["balance", "credit-history", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["reason"] == "Subscription fee — acme/weather"
