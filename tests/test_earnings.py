"""Tests for the earnings command group."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestBalance:
    def test_balance(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["earnings", "balance"])
        assert result.exit_code == 0, result.output
        assert "Available balance" in result.output


class TestHistory:
    def test_history_empty(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["earnings", "history"])
        assert result.exit_code == 0, result.output


class TestWithdraw:
    def test_withdraw_with_yes(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(app, ["earnings", "withdraw", "1.50", "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.withdraw.assert_awaited()

    def test_withdraw_invalid_amount(
        self, runner: CliRunner, patch_get_client
    ):
        result = runner.invoke(app, ["earnings", "withdraw", "abc", "--yes"])
        assert result.exit_code == 1


class TestWithdrawals:
    def test_withdrawals(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["earnings", "withdrawals"])
        assert result.exit_code == 0, result.output
