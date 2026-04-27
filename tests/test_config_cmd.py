"""Tests for ``teardrop init`` and ``teardrop config`` commands."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestInit:
    def test_init_creates_file(self, runner: CliRunner, tmp_config_dir):
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0, result.output
        assert (tmp_config_dir / "config.toml").exists()

    def test_init_with_base_url(self, runner: CliRunner, tmp_config_dir):
        result = runner.invoke(app, ["init", "--base-url", "https://test.example/"])
        assert result.exit_code == 0, result.output
        text = (tmp_config_dir / "config.toml").read_text(encoding="utf-8")
        assert "test.example" in text


class TestConfigSet:
    def test_set_api_url(self, runner: CliRunner, tmp_config_dir):
        result = runner.invoke(app, ["config", "set", "api_url", "https://api.x"])
        assert result.exit_code == 0, result.output

    def test_set_disallowed_key(self, runner: CliRunner, tmp_config_dir):
        result = runner.invoke(app, ["config", "set", "access_token", "bad"])
        assert result.exit_code == 1


class TestConfigGet:
    def test_get_missing_key(self, runner: CliRunner, tmp_config_dir):
        result = runner.invoke(app, ["config", "get", "api_url"])
        assert result.exit_code == 1

    def test_get_after_set(self, runner: CliRunner, tmp_config_dir):
        runner.invoke(app, ["config", "set", "api_url", "https://api.x"])
        result = runner.invoke(app, ["config", "get", "api_url"])
        assert result.exit_code == 0
        assert "https://api.x" in result.output


class TestConfigList:
    def test_list_empty(self, runner: CliRunner, tmp_config_dir):
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0

    def test_list_redacts_tokens(self, runner: CliRunner, tmp_config_dir):
        from teardrop_cli import config

        config.save_config({"access_token": "abcdefghijklmnopqrstuvwxyz", "api_url": "https://x"})
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        # Token should be truncated; full value should NOT appear
        assert "abcdefghijklmnopqrstuvwxyz" not in result.output
        assert "abcdefghijkl" in result.output  # first 12 chars present
