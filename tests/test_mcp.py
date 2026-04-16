"""Tests for mcp commands."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from teardrop_cli.cli import app


class TestMcpList:
    def test_list_empty(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["mcp", "list"])
        assert result.exit_code == 0, result.output

    def test_list_with_servers(self, runner: CliRunner, patch_get_client, mock_client):
        srv = MagicMock()
        srv.id = "srv_1"
        srv.name = "my-server"
        srv.url = "http://mcp.local"
        srv.auth_type = "bearer"
        srv.tools = []
        srv.model_dump = lambda: {"id": "srv_1", "name": "my-server"}
        mock_client.list_mcp_servers = AsyncMock(return_value=[srv])

        result = runner.invoke(app, ["mcp", "list"])
        assert result.exit_code == 0, result.output
        assert "srv_1" in result.output

    def test_list_json(self, runner: CliRunner, patch_get_client, mock_client):
        srv = MagicMock()
        srv.id = "srv_1"
        srv.name = "my-server"
        srv.url = "http://mcp.local"
        srv.auth_type = "bearer"
        srv.tools = []
        srv.model_dump = lambda: {"id": "srv_1", "name": "my-server"}
        mock_client.list_mcp_servers = AsyncMock(return_value=[srv])

        result = runner.invoke(app, ["mcp", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["id"] == "srv_1"


class TestMcpAdd:
    def test_add_server(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            ["mcp", "add", "--name", "my_mcp", "--url", "http://mcp.local"],
        )
        assert result.exit_code == 0, result.output
        assert "my_mcp" in result.output or "my-mcp" in result.output or "srv_1" in result.output

    def test_add_server_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            ["mcp", "add", "--name", "my_mcp", "--url", "http://mcp.local", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "srv_1"


class TestMcpDiscover:
    def test_discover_empty(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["mcp", "discover", "srv_1"])
        assert result.exit_code == 0, result.output

    def test_discover_with_tools(self, runner: CliRunner, patch_get_client, mock_client):
        tool = MagicMock()
        tool.name = "search"
        tool.description = "Search the web"
        tool.parameters = {"properties": {"q": {}}}
        discover_result = MagicMock()
        discover_result.tools = [tool]
        discover_result.model_dump = lambda: {"tools": [{"name": "search"}]}
        mock_client.discover_mcp_server_tools = AsyncMock(return_value=discover_result)

        result = runner.invoke(app, ["mcp", "discover", "srv_1"])
        assert result.exit_code == 0, result.output
        assert "search" in result.output


class TestMcpRemove:
    def test_remove_with_yes(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["mcp", "remove", "srv_1", "--yes"])
        assert result.exit_code == 0, result.output

    def test_remove_calls_api(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["mcp", "remove", "srv_999", "--yes"])
        assert result.exit_code == 0
        mock_client.delete_mcp_server.assert_called_once_with("srv_999")
