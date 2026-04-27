"""Tests for the top-level ``run`` command."""

from __future__ import annotations

from unittest.mock import AsyncMock

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestRun:
    def test_run_streams_text(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 0, result.output

    def test_run_no_stream_collects(self, runner: CliRunner, patch_get_client, mock_client):
        # Force --no-stream path. SDK's async_collect_text helper will be
        # called with the events generator from mock_client.run.
        result = runner.invoke(app, ["run", "--no-stream", "hello"])
        assert result.exit_code == 0, result.output

    def test_run_invalid_context_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["run", "hello", "--context", "not json"])
        assert result.exit_code == 2
        assert "Invalid --context" in result.output

    def test_run_payment_required_error(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop import PaymentRequiredError

        async def _fail(*a, **kw):
            raise PaymentRequiredError("402")
            yield  # pragma: no cover  (mark as async-gen)

        mock_client.run = _fail
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 1
        assert "Insufficient credit" in result.output

    def test_run_rate_limit(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop import RateLimitError

        async def _fail(*a, **kw):
            raise RateLimitError("rate limited")
            yield  # pragma: no cover

        mock_client.run = _fail
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 1
        assert "Rate limit" in result.output

    def test_run_with_thread_id(self, runner: CliRunner, patch_get_client, mock_client):
        captured = {}

        async def _capture(message, **kwargs):
            captured["thread_id"] = kwargs.get("thread_id")
            captured["context"] = kwargs.get("context")
            from teardrop_cli._fixtures import make_sse_events

            for ev in make_sse_events("ok"):
                yield ev

        mock_client.run = _capture
        result = runner.invoke(
            app, ["run", "hello", "--thread", "thr_42", "--context", '{"k":"v"}']
        )
        assert result.exit_code == 0, result.output
        assert captured["thread_id"] == "thr_42"
        assert captured["context"] == {"k": "v"}
