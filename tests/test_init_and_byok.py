"""Tests for `teardrop tools init` and `teardrop llm-config byok`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from teardrop_cli.cli import app


# ---------------------------------------------------------------------------
# tools init
# ---------------------------------------------------------------------------


class TestToolsInit:
    def test_writes_valid_json(self, runner: CliRunner, tmp_path: Path):
        out = tmp_path / "tool.json"
        result = runner.invoke(
            app, ["tools", "init", "my_scraper", "--out", str(out)]
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["name"] == "my_scraper"
        assert "webhook_url" in data
        assert "input_schema" in data
        assert data["timeout_seconds"] == 10
        assert data["publish_as_mcp"] is False
        # Next-step hint must reference publish.
        assert "publish" in result.output

    def test_refuses_overwrite(self, runner: CliRunner, tmp_path: Path):
        out = tmp_path / "tool.json"
        out.write_text("{}")
        result = runner.invoke(
            app, ["tools", "init", "thing", "--out", str(out)]
        )
        assert result.exit_code == 1
        assert "exists" in result.output.lower()

    def test_force_overwrites(self, runner: CliRunner, tmp_path: Path):
        out = tmp_path / "tool.json"
        out.write_text('{"name":"old"}')
        result = runner.invoke(
            app, ["tools", "init", "newname", "--out", str(out), "--force"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text())
        assert data["name"] == "newname"

    def test_with_marketplace(self, runner: CliRunner, tmp_path: Path):
        out = tmp_path / "tool.json"
        result = runner.invoke(
            app,
            ["tools", "init", "premium", "--out", str(out), "--with-marketplace"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(out.read_text())
        assert data["publish_as_mcp"] is True
        assert "base_price_usdc" in data
        assert "marketplace_description" in data

    def test_invalid_name_rejected(self, runner: CliRunner, tmp_path: Path):
        out = tmp_path / "tool.json"
        result = runner.invoke(
            app, ["tools", "init", "BadName", "--out", str(out)]
        )
        assert result.exit_code == 1
        assert "invalid" in result.output.lower()
        assert not out.exists()


# ---------------------------------------------------------------------------
# llm-config byok
# ---------------------------------------------------------------------------


class TestLlmConfigByok:
    def test_byok_interactive_happy_path(
        self, runner: CliRunner, patch_get_client
    ):
        """End-to-end: pick provider 1, accept default model, choose routing,
        paste key. Should call ``client.set_llm_config`` with all four args."""
        # Inputs in order:
        #   provider (1 → anthropic)
        #   model (accept default)
        #   routing (accept default 'quality')
        #   api key (hidden)
        stdin = "1\n\n\nsk-test-key\n"
        result = runner.invoke(app, ["llm-config", "byok"], input=stdin)
        assert result.exit_code == 0, result.output
        patch_get_client.set_llm_config.assert_called_once()
        kwargs = patch_get_client.set_llm_config.call_args.kwargs
        assert kwargs["provider"] == "anthropic"
        assert kwargs["routing_preference"] == "quality"
        assert kwargs["api_key"] == "sk-test-key"

    def test_byok_unknown_provider(self, runner: CliRunner, patch_get_client):
        # Pick a clearly invalid provider name as freeform input.
        stdin = "totally_fake_provider\n"
        result = runner.invoke(app, ["llm-config", "byok"], input=stdin)
        assert result.exit_code == 1
        assert "provider" in result.output.lower()
