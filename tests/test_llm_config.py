"""Tests for llm-config commands."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from typer.testing import CliRunner

from teardrop_cli.cli import app


class TestLlmConfigGet:
    def test_get_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["llm-config", "get", "org-1"])
        assert result.exit_code == 0, result.output
        assert "anthropic" in result.output

    def test_get_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["llm-config", "get", "org-1", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-haiku-4-5-20251001"

    def test_get_no_cache_flag(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "get", "org-1", "--no-cache"])
        assert result.exit_code == 0, result.output
        mock_client.get_llm_config.assert_called_once()
        _, kwargs = mock_client.get_llm_config.call_args
        assert kwargs.get("no_cache") is True

    def test_get_unauthenticated(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop import AuthenticationError

        mock_client.get_llm_config = AsyncMock(side_effect=AuthenticationError("no auth"))
        result = runner.invoke(app, ["llm-config", "get", "org-1"])
        assert result.exit_code == 1
        assert "teardrop auth login" in result.output

    def test_get_org_id_passed_to_sdk(self, runner: CliRunner, patch_get_client, mock_client):
        runner.invoke(app, ["llm-config", "get", "org-123"])
        mock_client.get_llm_config.assert_called_once()
        _, kwargs = mock_client.get_llm_config.call_args
        assert kwargs["org_id"] == "org-123"


class TestLlmConfigSet:
    def test_set_provider_and_model(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "anthropic",
                "--model",
                "claude-haiku-4-5-20251001",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Updated LLM configuration" in result.output

    def test_set_routing(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "anthropic",
                "--model",
                "claude-haiku-4-5-20251001",
                "--routing",
                "cost",
            ],
        )
        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.set_llm_config.call_args
        assert kwargs["routing_preference"] == "cost"

    def test_set_json_output(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "openai",
                "--model",
                "gpt-4o",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "provider" in data
        # Raw api_key must never appear in output
        assert "api_key" not in data

    def test_set_invalid_provider(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            ["llm-config", "set", "org-1", "--provider", "fakeai", "--model", "x"],
        )
        assert result.exit_code == 1
        assert "Unsupported provider" in result.output

    def test_set_invalid_routing(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "anthropic",
                "--model",
                "claude-haiku-4-5-20251001",
                "--routing",
                "turbo",
            ],
        )
        assert result.exit_code == 1
        assert "routing preference" in result.output.lower()

    def test_set_temperature_out_of_range(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "anthropic",
                "--model",
                "claude-haiku-4-5-20251001",
                "--temperature",
                "3.0",
            ],
        )
        assert result.exit_code == 1
        assert "Temperature" in result.output

    def test_set_max_tokens_out_of_range(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "anthropic",
                "--model",
                "claude-haiku-4-5-20251001",
                "--max-tokens",
                "300000",
            ],
        )
        assert result.exit_code == 1
        assert "Max tokens" in result.output

    def test_set_byok_key_warns(self, runner: CliRunner, patch_get_client):
        """Passing --byok-key as an argument triggers a security warning."""
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "openai",
                "--model",
                "gpt-4o",
                "--byok-key",
                "sk-supersecret",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "security" in result.output.lower() or "stdin" in result.output.lower()

    def test_set_byok_key_from_stdin(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "openai",
                "--model",
                "gpt-4o",
                "--byok-key",
                "-",
            ],
            input="sk-from-stdin\n",
        )
        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.set_llm_config.call_args
        assert kwargs.get("api_key") == "sk-from-stdin"

    def test_set_unauthenticated(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop import AuthenticationError

        mock_client.set_llm_config = AsyncMock(side_effect=AuthenticationError("no auth"))
        result = runner.invoke(
            app,
            ["llm-config", "set", "org-1", "--provider", "anthropic", "--model", "x"],
        )
        assert result.exit_code == 1
        assert "teardrop auth login" in result.output

    def test_set_400_ssrf(self, runner: CliRunner, patch_get_client, mock_client):
        exc = Exception("SSRF violation: private IP detected")
        exc.status_code = 400
        mock_client.set_llm_config = AsyncMock(side_effect=exc)
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "openai",
                "--model",
                "llama2",
                "--api-base",
                "http://192.168.1.1:8000",
            ],
        )
        assert result.exit_code == 1
        assert "public URL" in result.output

    def test_set_429_rate_limit(self, runner: CliRunner, patch_get_client, mock_client):
        exc = Exception("Too many updates")
        exc.status_code = 429
        mock_client.set_llm_config = AsyncMock(side_effect=exc)
        result = runner.invoke(
            app,
            ["llm-config", "set", "org-1", "--provider", "anthropic", "--model", "x"],
        )
        assert result.exit_code == 1
        assert "Too many" in result.output

    def test_set_rotate_key(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "anthropic",
                "--model",
                "claude-haiku-4-5-20251001",
                "--rotate-key",
            ],
        )
        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.set_llm_config.call_args
        assert kwargs.get("rotate_key") is True


class TestLlmConfigDelete:
    def test_delete_with_yes_flag(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "delete", "org-1", "--yes"])
        assert result.exit_code == 0, result.output
        assert "Deleted" in result.output
        mock_client.delete_llm_config.assert_called_once()

    def test_delete_prompt_confirmed(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "delete", "org-1"], input="y\n")
        assert result.exit_code == 0, result.output
        assert "Deleted" in result.output

    def test_delete_prompt_denied(self, runner: CliRunner, patch_get_client, mock_client):
        runner.invoke(app, ["llm-config", "delete", "org-1"], input="n\n")
        # Aborted — should not call SDK
        mock_client.delete_llm_config.assert_not_called()

    def test_delete_unauthenticated(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop import AuthenticationError

        mock_client.delete_llm_config = AsyncMock(side_effect=AuthenticationError("no auth"))
        result = runner.invoke(app, ["llm-config", "delete", "org-1", "--yes"])
        assert result.exit_code == 1
        assert "teardrop auth login" in result.output

    def test_delete_404_treated_as_success(self, runner: CliRunner, patch_get_client, mock_client):
        exc = Exception("not found")
        exc.status_code = 404
        mock_client.delete_llm_config = AsyncMock(side_effect=exc)
        result = runner.invoke(app, ["llm-config", "delete", "org-1", "--yes"])
        assert result.exit_code == 0, result.output
        assert "defaults" in result.output.lower()

    def test_delete_org_id_passed_to_sdk(self, runner: CliRunner, patch_get_client, mock_client):
        runner.invoke(app, ["llm-config", "delete", "org-99", "--yes"])
        _, kwargs = mock_client.delete_llm_config.call_args
        assert kwargs["org_id"] == "org-99"


class TestLlmConfigSetExtended:
    """Additional set-command tests for correctness and edge cases."""

    def test_set_openrouter_valid_provider(self, runner: CliRunner, patch_get_client, mock_client):
        """openrouter is a supported provider and should not raise an error."""
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "openrouter",
                "--model",
                "mistralai/mixtral-8x7b",
            ],
        )
        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.set_llm_config.call_args
        assert kwargs["provider"] == "openrouter"

    def test_set_routing_only(self, runner: CliRunner, patch_get_client, mock_client):
        """Routing preference can be updated without specifying provider or model."""
        result = runner.invoke(
            app,
            ["llm-config", "set", "org-1", "--routing", "cost"],
        )
        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.set_llm_config.call_args
        assert kwargs["routing_preference"] == "cost"
        assert "provider" not in kwargs
        assert "model" not in kwargs

    def test_set_timeout_zero_invalid(self, runner: CliRunner, patch_get_client):
        """--timeout-seconds 0 must be rejected (must be ≥ 1)."""
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "anthropic",
                "--model",
                "claude-haiku-4-5-20251001",
                "--timeout-seconds",
                "0",
            ],
        )
        assert result.exit_code == 1
        assert "timeout" in result.output.lower()

    def test_set_byok_key_masked_in_output(self, runner: CliRunner, patch_get_client, mock_client):
        """When a BYOK key is set, success output should show masked key, not raw value."""
        from unittest.mock import AsyncMock

        from teardrop_cli._fixtures import make_llm_config

        mock_client.set_llm_config = AsyncMock(
            return_value=make_llm_config(has_api_key=True, is_byok=True)
        )
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "org-1",
                "--provider",
                "openai",
                "--model",
                "gpt-4o",
                "--byok-key",
                "sk-supersecret123",
            ],
        )
        assert result.exit_code == 0, result.output
        # Raw key must not appear in output
        assert "sk-supersecret123" not in result.output
        # Masked prefix (first 5 chars) should appear
        assert "sk-su" in result.output
        # Mask bullets should appear
        assert "••••" in result.output
