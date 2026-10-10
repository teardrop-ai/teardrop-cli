"""Tests for org llm-config commands (no org_id positional)."""

from __future__ import annotations

import json

import httpx
import pytest
from click.testing import CliRunner

from teardrop_cli._fixtures import make_llm_config
from teardrop_cli.cli import app


class TestGet:
    def test_get_renders_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["llm-config", "get"])
        assert result.exit_code == 0, result.output
        assert "Provider" in result.output
        assert "Reasoning Effort" in result.output
        assert "Model Reasoning Effort" in result.output
        assert "(none)" in result.output

    def test_get_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["llm-config", "get", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["provider"] == "anthropic"
        assert data["reasoning_effort"] is None
        assert data["model_reasoning_effort"] is None

    def test_get_displays_reasoning_values(self, runner: CliRunner, patch_get_client):
        patch_get_client.get_llm_config.return_value = make_llm_config(
            reasoning_effort="medium",
            model_reasoning_effort={"anthropic:claude-sonnet-4-6": "high"},
        )
        result = runner.invoke(app, ["llm-config", "get"])
        assert result.exit_code == 0, result.output
        assert "medium" in result.output
        assert "anthropic:claude-sonnet-4-6" in result.output
        assert "high" in result.output

    def test_no_org_id_positional(self, runner: CliRunner, patch_get_client):
        """Passing an extra positional should fail (no org_id arg anymore)."""
        result = runner.invoke(app, ["llm-config", "get", "org-1"])
        assert result.exit_code != 0


class TestSet:
    def test_set_merges_existing(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "set", "--max-tokens", "8192"])
        assert result.exit_code == 0, result.output
        # Read-then-write merge: get_llm_config called first
        mock_client.get_llm_config.assert_awaited()
        mock_client.set_llm_config.assert_awaited()
        kwargs = mock_client.set_llm_config.call_args.kwargs
        assert "reasoning_effort" not in kwargs
        assert "model_reasoning_effort" not in kwargs

    @pytest.mark.parametrize("effort", ["none", "minimal", "low", "medium", "high"])
    def test_set_reasoning_effort(
        self, runner: CliRunner, patch_get_client, mock_client, effort: str
    ):
        result = runner.invoke(app, ["llm-config", "set", "--reasoning-effort", effort])
        assert result.exit_code == 0, result.output
        assert mock_client.set_llm_config.call_args.kwargs["reasoning_effort"] == effort

    def test_set_invalid_provider(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["llm-config", "set", "--provider", "bogus"])
        assert result.exit_code != 0

    def test_set_clear_key(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "set", "--clear-key"])
        assert result.exit_code == 0, result.output
        mock_client.set_llm_config.assert_awaited()
        kwargs = mock_client.set_llm_config.call_args.kwargs
        assert "api_key" in kwargs
        assert kwargs["api_key"] is None

    def test_set_clear_key_keeps_reasoning_override(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(
            app,
            ["llm-config", "set", "--clear-key", "--reasoning-effort", "high"],
        )
        assert result.exit_code == 0, result.output
        kwargs = mock_client.set_llm_config.call_args.kwargs
        assert "api_key" in kwargs
        assert kwargs["api_key"] is None
        assert kwargs["reasoning_effort"] == "high"

    def test_set_clear_reasoning_effort_passes_null(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(app, ["llm-config", "set", "--clear-reasoning-effort"])
        assert result.exit_code == 0, result.output
        kwargs = mock_client.set_llm_config.call_args.kwargs
        assert "reasoning_effort" in kwargs
        assert kwargs["reasoning_effort"] is None

    def test_set_clear_reasoning_effort_conflicts_with_value(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "--clear-reasoning-effort",
                "--reasoning-effort",
                "none",
            ],
        )
        assert result.exit_code != 0
        mock_client.set_llm_config.assert_not_awaited()

    def test_set_invalid_reasoning_effort(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "set", "--reasoning-effort", "extreme"])
        assert result.exit_code != 0
        mock_client.set_llm_config.assert_not_awaited()

    def test_set_repeated_model_reasoning_efforts(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(
            app,
            [
                "llm-config",
                "set",
                "--model-reasoning-effort",
                "anthropic:claude-sonnet-4-6=experimental",
                "--model-reasoning-effort",
                "openai:gpt-4.1=none",
            ],
        )
        assert result.exit_code == 0, result.output
        kwargs = mock_client.set_llm_config.call_args.kwargs
        assert kwargs["model_reasoning_effort"] == {
            "anthropic:claude-sonnet-4-6": "experimental",
            "openai:gpt-4.1": "none",
        }

    def test_set_invalid_model_reasoning_effort(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        result = runner.invoke(
            app,
            ["llm-config", "set", "--model-reasoning-effort", "anthropic:sonnet"],
        )
        assert result.exit_code != 0
        mock_client.set_llm_config.assert_not_awaited()


class TestDelete:
    def test_delete_with_yes(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["llm-config", "delete", "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.delete_llm_config.assert_awaited()


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ([], {}),
        (["--clear-key"], {"api_key": None}),
        (["--byok-key", "test-byok-key"], {"api_key": "test-byok-key"}),
        (
            ["--clear-key", "--reasoning-effort", "high"],
            {"api_key": None, "reasoning_effort": "high"},
        ),
        (
            ["--clear-key", "--clear-reasoning-effort"],
            {"api_key": None, "reasoning_effort": None},
        ),
        (
            ["--model-reasoning-effort", "openai:gpt-4.1=high"],
            {"model_reasoning_effort": {"openai:gpt-4.1": "high"}},
        ),
    ],
)
def test_set_real_sdk_payload(runner, monkeypatch, sdk_http, options, expected):
    monkeypatch.setenv("TEARDROP_API_KEY", "test-token")
    state = make_llm_config(is_byok=True).model_dump()
    state.update(configured=True, has_api_key=True)
    bodies = []

    def respond(request):
        if request.method == "PUT":
            body = json.loads(request.content)
            bodies.append(body)
            state.update(body)
            if "api_key" in body:
                state["has_api_key"] = body["api_key"] is not None
                state["is_byok"] = state["has_api_key"]
        return httpx.Response(200, json=state)

    sdk_http.side_effect = respond
    result = runner.invoke(app, ["llm-config", "set", *options, "--json"])

    assert result.exit_code == 0, result.output
    assert len(bodies) == 1
    for field in ("api_key", "reasoning_effort", "model_reasoning_effort"):
        if field in expected:
            assert field in bodies[0]
            assert bodies[0][field] == expected[field]
        else:
            assert field not in bodies[0]
    assert json.loads(result.stdout)["has_api_key"] is ("--clear-key" not in options)
