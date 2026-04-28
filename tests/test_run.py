"""Tests for the top-level ``run`` command."""

from __future__ import annotations

from unittest.mock import AsyncMock

from click.testing import CliRunner

from teardrop_cli.cli import app


class TestRun:
    def test_run_streams_text(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 0, result.output
        assert "Hello from the agent!" in result.output

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


class TestSurfacePayloadStripping:
    """Agent occasionally emits a fenced JSON UI payload after narrative text.
    The CLI is text-only — these blocks should be hidden.
    """

    def test_strips_completed_fenced_json(self):
        from teardrop_cli.formatting import _strip_surface_payload

        text = 'Here is your answer.\n\n```json\n{"components": [1, 2]}\n```\n'
        assert _strip_surface_payload(text) == "Here is your answer."

    def test_strips_unclosed_trailing_fence(self):
        from teardrop_cli.formatting import _strip_surface_payload

        text = 'Here is your answer.\n\n```json\n{"components": [1,'
        assert _strip_surface_payload(text) == "Here is your answer."

    def test_preserves_non_json_code_blocks(self):
        from teardrop_cli.formatting import _strip_surface_payload

        text = "Run this:\n\n```python\nprint('hi')\n```\n"
        assert _strip_surface_payload(text) == text

    def test_run_no_stream_strips_surface_json(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        async def _emit(*args, **kwargs):
            from teardrop_cli._fixtures import make_sse_events

            payload = (
                'Here is the answer.\n\n```json\n{"components": [{"x": 1}]}\n```\n'
            )
            for ev in make_sse_events(payload):
                yield ev

        mock_client.run = _emit
        result = runner.invoke(app, ["run", "--no-stream", "hello"])
        assert result.exit_code == 0, result.output
        assert "Here is the answer." in result.output
        assert "components" not in result.output
        assert "```" not in result.output
