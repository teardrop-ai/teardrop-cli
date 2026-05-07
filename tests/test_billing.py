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

