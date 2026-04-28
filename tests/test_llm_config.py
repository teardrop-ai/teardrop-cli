"""Tests for org llm-config commands (no org_id positional)."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestGet:
    def test_get_renders_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["llm-config", "get"])
        assert result.exit_code == 0, result.output
        assert "Provider" in result.output

    def test_get_json(self, runner: CliRunner, patch_get_client):
        import json

        result = runner.invoke(app, ["llm-config", "get", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["provider"] == "anthropic"

    def test_no_org_id_positional(self, runner: CliRunner, patch_get_client):
        """Passing an extra positional should fail (no org_id arg anymore)."""
        result = runner.invoke(app, ["llm-config", "get", "org-1"])
        assert result.exit_code != 0


class TestSet:
    def test_set_merges_existing(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(
            app, ["llm-config", "set", "--max-tokens", "8192"]
        )
        assert result.exit_code == 0, result.output
        # Read-then-write merge: get_llm_config called first
        mock_client.get_llm_config.assert_awaited()
        mock_client.set_llm_config.assert_awaited()

    def test_set_invalid_provider(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app, ["llm-config", "set", "--provider", "bogus"]
        )
        assert result.exit_code != 0

    def test_set_clear_key(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "set", "--clear-key"])
        assert result.exit_code == 0, result.output
        # clear_llm_api_key does not exist on the SDK; --clear-key calls set_llm_config without api_key
        mock_client.set_llm_config.assert_awaited()


class TestDelete:
    def test_delete_with_yes(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "delete", "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.delete_llm_config.assert_awaited()
