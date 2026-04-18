"""Tests for marketplace commands."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from typer.testing import CliRunner

from teardrop_cli.cli import app


class TestBalance:
    def test_balance_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "balance"])
        assert result.exit_code == 0, result.output

    def test_balance_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "balance", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "available" in data


class TestEarnings:
    def test_earnings_empty(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "earnings"])
        assert result.exit_code == 0, result.output

    def test_earnings_with_items(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.get_earnings = AsyncMock(
            return_value={
                "items": [
                    {
                        "id": "e_1",
                        "amount": "5.00",
                        "currency": "USDC",
                        "created_at": "2026-01-01",
                        "description": "Tool run",
                    }
                ],
                "next_cursor": None,
            }
        )
        result = runner.invoke(app, ["marketplace", "earnings"])
        assert result.exit_code == 0, result.output
        assert "e_1" in result.output

    def test_earnings_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "earnings", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "items" in data


class TestWithdraw:
    def test_withdraw_with_yes_flag(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            [
                "marketplace",
                "withdraw",
                "--amount-usdc",
                "100",
                "--payout-address",
                "0xABC",
                "--yes",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_withdraw_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            [
                "marketplace",
                "withdraw",
                "--amount-usdc",
                "100",
                "--payout-address",
                "0xABC",
                "--yes",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "status" in data


class TestPublish:
    def test_publish_sets_payout(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "publish", "--payout-address", "0xDEAD"])
        assert result.exit_code == 0, result.output

    def test_publish_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app, ["marketplace", "publish", "--payout-address", "0xDEAD", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "payout_address" in data
