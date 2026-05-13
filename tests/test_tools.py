"""Tests for org tools commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from click.testing import CliRunner

from teardrop_cli.cli import app


def _tool_obj(name="my_tool", tool_id="tool_1", **extra):
    data = {
        "id": tool_id,
        "name": name,
        "description": "desc",
        "is_active": True,
        "publish_as_mcp": False,
        "webhook_url": "https://hook.example.com/run",
        **extra,
    }
    obj = MagicMock(spec=[])
    obj.id = tool_id
    obj.name = name  # explicit set since `name` is reserved on MagicMock ctor
    obj.model_dump = lambda: dict(data)
    return obj


class TestList:
    def test_list_empty(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0, result.output

    def test_list_with_tools(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.list_tools.return_value = [_tool_obj()]
        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0, result.output
        assert "my_tool" in result.output


class TestInfo:
    def test_info_not_found(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["tools", "info", "missing"])
        assert result.exit_code == 1

    def test_info_found(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.list_tools.return_value = [_tool_obj()]
        result = runner.invoke(app, ["tools", "info", "my_tool"])
        assert result.exit_code == 0, result.output


class TestPublish:
    def test_publish_from_file(
        self, runner: CliRunner, patch_get_client, mock_client, tmp_path
    ):
        import json

        spec = {
            "name": "my_tool",
            "description": "A tool",
            "webhook_url": "https://hook.example.com/run",
            "input_schema": {"type": "object", "properties": {}},
            "timeout_seconds": 10,
            "publish_as_mcp": False,
        }
        path = tmp_path / "tool.json"
        path.write_text(json.dumps(spec), encoding="utf-8")

        result = runner.invoke(app, ["tools", "publish", "--from-file", str(path)])
        assert result.exit_code == 0, result.output
        mock_client.create_tool.assert_awaited()

    def test_publish_invalid_name(
        self, runner: CliRunner, patch_get_client, tmp_path
    ):
        import json

        spec = {
            "name": "Bad-Name",  # invalid: uppercase + hyphen
            "description": "A tool",
            "webhook_url": "https://hook.example.com/run",
            "input_schema": {"type": "object"},
        }
        path = tmp_path / "tool.json"
        path.write_text(json.dumps(spec), encoding="utf-8")

        result = runner.invoke(app, ["tools", "publish", "--from-file", str(path)])
        assert result.exit_code == 1


class TestUpdate:
    def test_update_no_flags(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.list_tools.return_value = [_tool_obj()]
        result = runner.invoke(app, ["tools", "update", "my_tool"])
        assert result.exit_code == 1

    def test_update_description(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        mock_client.list_tools.return_value = [_tool_obj()]
        result = runner.invoke(
            app, ["tools", "update", "my_tool", "--description", "new"]
        )
        assert result.exit_code == 0, result.output
        mock_client.update_tool.assert_awaited()


class TestPause:
    def test_pause(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.list_tools.return_value = [_tool_obj()]
        result = runner.invoke(app, ["tools", "pause", "my_tool"])
        assert result.exit_code == 0, result.output
        mock_client.update_tool.assert_awaited()


class TestProbe:
    def test_probe_success(
        self, runner: CliRunner, patch_get_client, mock_client, monkeypatch
    ):
        mock_client.list_tools.return_value = [_tool_obj()]
        mock_client.get_tool = AsyncMock(return_value=_tool_obj())

        class _Response:
            status_code = 200

        class _AsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, *args, **kwargs):
                return _Response()

        monkeypatch.setattr("teardrop_cli.commands.tools.httpx.AsyncClient", _AsyncClient)

        result = runner.invoke(app, ["tools", "probe", "my_tool"])
        assert result.exit_code == 0, result.output
        assert "Webhook healthy" in result.output

    def test_probe_with_auth_header_and_payload(
        self, runner: CliRunner, patch_get_client, mock_client, monkeypatch
    ):
        captured = {}
        mock_client.list_tools.return_value = [_tool_obj()]
        mock_client.get_tool = AsyncMock(return_value=_tool_obj())

        class _Response:
            status_code = 200

        class _AsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, method, url, **kwargs):
                captured["method"] = method
                captured["url"] = url
                captured["headers"] = kwargs.get("headers")
                captured["json"] = kwargs.get("json")
                return _Response()

        monkeypatch.setattr("teardrop_cli.commands.tools.httpx.AsyncClient", _AsyncClient)

        result = runner.invoke(
            app,
            [
                "tools",
                "probe",
                "my_tool",
                "--method",
                "POST",
                "--payload",
                '{"ping": "pong"}',
                "--auth-header-name",
                "X-Webhook-Secret",
                "--auth-header-value",
                "s3cr3t",
            ],
        )
        assert result.exit_code == 0, result.output
        assert captured["method"] == "POST"
        assert captured["json"] == {"ping": "pong"}
        assert captured["headers"]["X-Webhook-Secret"] == "s3cr3t"

    def test_probe_auth_header_pair_required(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        mock_client.list_tools.return_value = [_tool_obj()]
        mock_client.get_tool = AsyncMock(return_value=_tool_obj())
        result = runner.invoke(
            app,
            [
                "tools",
                "probe",
                "my_tool",
                "--auth-header-name",
                "X-Webhook-Secret",
            ],
        )
        assert result.exit_code == 1
        assert "required together" in result.output

    def test_probe_invalid_payload(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        mock_client.list_tools.return_value = [_tool_obj()]
        mock_client.get_tool = AsyncMock(return_value=_tool_obj())
        result = runner.invoke(app, ["tools", "probe", "my_tool", "--payload", "not-json"])
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_probe_timeout(
        self, runner: CliRunner, patch_get_client, mock_client, monkeypatch
    ):
        import httpx

        mock_client.list_tools.return_value = [_tool_obj()]
        mock_client.get_tool = AsyncMock(return_value=_tool_obj())

        class _AsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, *args, **kwargs):
                raise httpx.ReadTimeout("timed out")

        monkeypatch.setattr("teardrop_cli.commands.tools.httpx.AsyncClient", _AsyncClient)

        result = runner.invoke(app, ["tools", "probe", "my_tool"])
        assert result.exit_code == 1
        assert "Timed out" in result.output

    def test_probe_server_error(
        self, runner: CliRunner, patch_get_client, mock_client, monkeypatch
    ):
        mock_client.list_tools.return_value = [_tool_obj()]
        mock_client.get_tool = AsyncMock(return_value=_tool_obj())

        class _Response:
            status_code = 500

        class _AsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def request(self, *args, **kwargs):
                return _Response()

        monkeypatch.setattr("teardrop_cli.commands.tools.httpx.AsyncClient", _AsyncClient)

        result = runner.invoke(app, ["tools", "probe", "my_tool"])
        assert result.exit_code == 1
        assert "returned 500" in result.output

    def test_probe_tool_not_found(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["tools", "probe", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestDelete:
    def test_delete_with_yes(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.list_tools.return_value = [_tool_obj()]
        result = runner.invoke(app, ["tools", "delete", "my_tool", "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.delete_tool.assert_awaited()
