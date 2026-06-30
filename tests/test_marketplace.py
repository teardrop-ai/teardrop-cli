"""Tests for marketplace commands."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestList:
    def test_list_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "list"])
        assert result.exit_code == 0, result.output
        assert "acme/weather" in result.output

    def test_list_hides_platform_tools_by_default(self, runner: CliRunner, patch_get_client):
        """Platform tools are filtered out unless --include-platform is passed."""
        result = runner.invoke(app, ["marketplace", "list"])
        assert result.exit_code == 0, result.output
        assert "platform/transmute" not in result.output
        assert "acme/weather" in result.output

    def test_list_include_platform_shows_all(self, runner: CliRunner, patch_get_client):
        """With --include-platform, platform tools appear."""
        result = runner.invoke(app, ["marketplace", "list", "--include-platform"])
        assert result.exit_code == 0, result.output
        assert "platform/transmute" in result.output
        assert "acme/weather" in result.output

    def test_list_json(self, runner: CliRunner, patch_get_client):
        import json

        result = runner.invoke(app, ["marketplace", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        # Platform tool filtered out by default in JSON, too
        names = [d["name"] for d in data]
        assert "acme/weather" in names
        assert "platform/transmute" not in names

    def test_list_json_with_include_platform(self, runner: CliRunner, patch_get_client):
        import json

        result = runner.invoke(app, ["marketplace", "list", "--json", "--include-platform"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        names = [d["name"] for d in data]
        assert "platform/transmute" in names
        assert "acme/weather" in names


class TestSearch:
    def test_search_match(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "search", "weather"])
        assert result.exit_code == 0, result.output
        assert "acme/weather" in result.output

    def test_search_does_not_return_platform_by_default(self, runner: CliRunner, patch_get_client):
        """Platform tools are hidden from search unless --include-platform."""
        result = runner.invoke(app, ["marketplace", "search", "transmute"])
        assert result.exit_code == 0, result.output
        assert "platform/transmute" not in result.output

    def test_search_with_include_platform(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "search", "transmute", "--include-platform"])
        assert result.exit_code == 0, result.output
        assert "platform/transmute" in result.output

    def test_search_no_match(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "search", "nonexistent_xyz"])
        assert result.exit_code == 0, result.output


class TestInfo:
    def test_info_found(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "info", "acme/weather"])
        assert result.exit_code == 0, result.output
        assert "acme/weather" in result.output

    def test_info_platform_shows_builtin_message(self, runner: CliRunner, patch_get_client):
        """Info for a platform tool shows the built-in notice."""
        result = runner.invoke(app, ["marketplace", "info", "platform/transmute"])
        assert result.exit_code == 0, result.output
        assert "platform/transmute" in result.output
        assert "built-in" in result.output.lower()
        assert "no subscription" in result.output.lower()

    def test_info_missing(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["marketplace", "info", "nope/none"])
        assert result.exit_code == 1


class TestSubscribe:
    def test_subscribe_with_yes(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["marketplace", "subscribe", "acme/weather", "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.subscribe.assert_awaited_with("acme/weather")

    def test_subscribe_platform_tool_fails_early(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        """Subscribing to a platform tool prints a friendly error."""
        result = runner.invoke(app, ["marketplace", "subscribe", "platform/transmute", "--yes"])
        assert result.exit_code == 1
        assert "built-in platform tool" in result.output.lower()
        assert "available to all agents" in result.output.lower()
        mock_client.subscribe.assert_not_awaited()

    def test_subscribe_conflict(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop import ConflictError

        mock_client.subscribe.side_effect = ConflictError("already subscribed")
        result = runner.invoke(app, ["marketplace", "subscribe", "acme/weather", "--yes"])
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
