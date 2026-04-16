"""Tests for tools commands."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from teardrop_cli.cli import app


class TestToolsList:
    def test_list_empty(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0, result.output

    def test_list_with_tools(self, runner: CliRunner, patch_get_client, mock_client):
        t = MagicMock()
        t.id = "tool_1"
        t.name = "my-tool"
        t.description = "Does stuff"
        t.type = "function"
        t.model_dump = lambda: {"id": "tool_1", "name": "my-tool"}
        mock_client.list_tools = AsyncMock(return_value=[t])

        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0, result.output
        assert "tool_1" in result.output

    def test_list_json(self, runner: CliRunner, patch_get_client, mock_client):
        t = MagicMock()
        t.id = "tool_1"
        t.name = "my-tool"
        t.description = "Does stuff"
        t.type = "function"
        t.model_dump = lambda: {"id": "tool_1", "name": "my-tool"}
        mock_client.list_tools = AsyncMock(return_value=[t])

        result = runner.invoke(app, ["tools", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["id"] == "tool_1"


class TestToolsTest:
    def test_test_tool_table(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["tools", "test", "tool_1"])
        assert result.exit_code == 0, result.output
        assert "tool_1" in result.output

    def test_test_tool_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["tools", "test", "tool_1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "tool_1"

    def test_test_tool_valid_input(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            ["tools", "test", "tool_1", "--input", '{"query": "hello"}'],
        )
        assert result.exit_code == 0, result.output

    def test_test_tool_missing_required(self, runner: CliRunner, patch_get_client):
        """Missing required field should exit non-zero."""
        result = runner.invoke(
            app,
            ["tools", "test", "tool_1", "--input", "{}"],
        )
        assert result.exit_code == 1

    def test_test_tool_invalid_json(self, runner: CliRunner, patch_get_client):
        """Malformed JSON input exits with code 1."""
        result = runner.invoke(
            app,
            ["tools", "test", "tool_1", "--input", "{not-json}"],
        )
        assert result.exit_code == 1

    def test_test_tool_wrong_type(self, runner: CliRunner, patch_get_client):
        """Wrong field type should exit with code 1."""
        result = runner.invoke(
            app,
            ["tools", "test", "tool_1", "--input", '{"query": 123}'],
        )
        assert result.exit_code == 1
