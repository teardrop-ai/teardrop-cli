"""Tests for models commands."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from typer.testing import CliRunner

from teardrop_cli.cli import app


class TestModelsBenchmarks:
    def test_public_benchmarks_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["models", "benchmarks"])
        assert result.exit_code == 0, result.output
        # Rich truncates long values in narrow terminals; check for visible prefix
        assert "anthro" in result.output
        assert "claude" in result.output

    def test_public_benchmarks_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["models", "benchmarks", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "models" in data
        assert len(data["models"]) > 0

    def test_public_benchmarks_no_cache_flag(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        # --no-cache is a CLI flag that previously passed no_cache= to the SDK method,
        # but get_model_benchmarks() accepts no arguments; flag is still accepted by CLI
        result = runner.invoke(app, ["models", "benchmarks", "--no-cache"])
        assert result.exit_code == 0, result.output
        mock_client.get_model_benchmarks.assert_called_once()
        _, kwargs = mock_client.get_model_benchmarks.call_args
        assert "no_cache" not in kwargs

    def test_public_benchmarks_empty_list(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop_cli._fixtures import make_benchmarks_response

        mock_client.get_model_benchmarks = AsyncMock(
            return_value=make_benchmarks_response(models=[])
        )
        result = runner.invoke(app, ["models", "benchmarks"])
        assert result.exit_code == 0, result.output
        assert "No benchmark data" in result.output

    def test_org_benchmarks_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["models", "benchmarks", "--org", "org-1"])
        assert result.exit_code == 0, result.output
        assert "org-1" in result.output

    def test_org_benchmarks_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["models", "benchmarks", "--org", "org-1", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "models" in data

    def test_org_benchmarks_calls_org_endpoint(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        runner.invoke(app, ["models", "benchmarks", "--org", "org-42"])
        mock_client.get_org_model_benchmarks.assert_called_once()
        mock_client.get_model_benchmarks.assert_not_called()

    def test_public_benchmarks_calls_public_endpoint(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        runner.invoke(app, ["models", "benchmarks"])
        mock_client.get_model_benchmarks.assert_called_once()
        mock_client.get_org_model_benchmarks.assert_not_called()

    def test_org_benchmarks_unauthenticated(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop import AuthenticationError

        mock_client.get_org_model_benchmarks = AsyncMock(
            side_effect=AuthenticationError("no auth")
        )
        result = runner.invoke(app, ["models", "benchmarks", "--org", "org-1"])
        assert result.exit_code == 1
        assert "teardrop auth login" in result.output

    def test_org_benchmarks_empty_list(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop_cli._fixtures import make_benchmarks_response

        mock_client.get_org_model_benchmarks = AsyncMock(
            return_value=make_benchmarks_response(models=[])
        )
        result = runner.invoke(app, ["models", "benchmarks", "--org", "org-empty"])
        assert result.exit_code == 0, result.output
        assert "No benchmark data" in result.output
        assert "org-empty" in result.output

    def test_benchmarks_null_benchmarks_field(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        """Models with < 10 runs have benchmarks=null; table should render with dashes."""
        from teardrop_cli._fixtures import make_benchmarks_response

        mock_client.get_model_benchmarks = AsyncMock(
            return_value=make_benchmarks_response(
                models=[
                    {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "display_name": "GPT-4o",
                        "quality_tier": 3,
                        "pricing": {
                            "tokens_in_cost_per_1k": 0.30,
                            "tokens_out_cost_per_1k": 1.20,
                        },
                        "benchmarks": None,
                    }
                ]
            )
        )
        result = runner.invoke(app, ["models", "benchmarks"])
        assert result.exit_code == 0, result.output
        assert "openai" in result.output


class TestModelsBenchmarksOrgExtended:
    """Extended tests for org-scoped benchmark table."""

    def test_org_benchmarks_total_cost_column(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        """Total Cost column = Runs × Avg Cost/Run, rendered in org benchmarks table."""
        from unittest.mock import AsyncMock

        from teardrop_cli._fixtures import make_benchmarks_response

        mock_client.get_org_model_benchmarks = AsyncMock(
            return_value=make_benchmarks_response(
                models=[
                    {
                        "provider": "anthropic",
                        "model": "claude-haiku-4-5-20251001",
                        "display_name": "Claude Haiku 4.5",
                        "quality_tier": 2,
                        "pricing": {
                            "tokens_in_cost_per_1k": 0.08,
                            "tokens_out_cost_per_1k": 0.24,
                        },
                        "benchmarks": {
                            "total_runs_7d": 45,
                            "avg_latency_ms": 512.0,
                            "p95_latency_ms": 900.0,
                            "avg_cost_usdc_per_run": 8.50,
                            "avg_tokens_per_sec": 47.3,
                        },
                    }
                ]
            )
        )
        result = runner.invoke(app, ["models", "benchmarks", "--org", "org-1"])
        assert result.exit_code == 0, result.output
        # Total cost: 45 × $8.50 = $382.50
        assert "382.50" in result.output

    def test_org_benchmarks_total_cost_null_benchmarks(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        """Models with null benchmarks render Total Cost as dash, not an error."""
        from unittest.mock import AsyncMock

        from teardrop_cli._fixtures import make_benchmarks_response

        mock_client.get_org_model_benchmarks = AsyncMock(
            return_value=make_benchmarks_response(
                models=[
                    {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "display_name": "GPT-4o",
                        "quality_tier": 3,
                        "pricing": {},
                        "benchmarks": None,
                    }
                ]
            )
        )
        result = runner.invoke(app, ["models", "benchmarks", "--org", "org-1"])
        assert result.exit_code == 0, result.output
        assert "openai" in result.output
