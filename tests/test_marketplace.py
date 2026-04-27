"""Tests for marketplace commands."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestList:
    def test_list_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "list"])
        assert result.exit_code == 0, result.output
        assert "acme/weather" in result.output

    def test_list_json(self, runner: CliRunner, patch_get_client):
        import json

        result = runner.invoke(app, ["marketplace", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestSearch:
    def test_search_match(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "search", "weather"])
        assert result.exit_code == 0, result.output
        assert "acme/weather" in result.output

    def test_search_no_match(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "search", "nonexistent_xyz"])
        assert result.exit_code == 0, result.output


class TestInfo:
    def test_info_found(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "info", "acme/weather"])
        assert result.exit_code == 0, result.output
        assert "acme/weather" in result.output

    def test_info_missing(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "info", "nope/none"])
        assert result.exit_code == 1


class TestSubscribe:
    def test_subscribe_with_yes(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(
            app, ["marketplace", "subscribe", "acme/weather", "--yes"]
        )
        assert result.exit_code == 0, result.output
        mock_client.subscribe.assert_awaited_with("acme/weather")

    def test_subscribe_conflict(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop import ConflictError

        mock_client.subscribe.side_effect = ConflictError("already subscribed")
        result = runner.invoke(
            app, ["marketplace", "subscribe", "acme/weather", "--yes"]
        )
        assert result.exit_code == 1


class TestUnsubscribe:
    def test_unsubscribe(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["marketplace", "unsubscribe", "acme/weather"])
        assert result.exit_code == 0, result.output
        mock_client.unsubscribe.assert_awaited()


class TestSubscriptions:
    def test_list_subs(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "subscriptions"])
        assert result.exit_code == 0, result.output
        assert "acme/weather" in result.output
