"""Tests for agent commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from teardrop_cli.cli import app


class TestAgentRun:
    def test_run_streams_text(self, runner: CliRunner, patch_get_client):
        """agent run returns exit 0 and displays streamed text."""
        result = runner.invoke(app, ["agent", "run", "hello"])
        assert result.exit_code == 0, result.output

    def test_run_json_output(self, runner: CliRunner, patch_get_client):
        """--json flag emits SSE events as JSON lines on stdout."""
        result = runner.invoke(app, ["agent", "run", "--json", "hello"])
        assert result.exit_code == 0, result.output
        lines = [line for line in result.output.strip().splitlines() if line]
        assert len(lines) >= 1
        for line in lines:
            event = json.loads(line)
            assert "type" in event

    def test_run_payment_required(self, runner: CliRunner, patch_get_client, mock_client):
        """PaymentRequiredError maps to exit code 2."""
        from teardrop import PaymentRequiredError

        async def _fail(*a, **kw):
            raise PaymentRequiredError("No funds")
            # Need a generator — raise before any yield
            if False:
                yield

        mock_client.run = _fail
        result = runner.invoke(app, ["agent", "run", "hello"])
        assert result.exit_code == 2

    def test_run_rate_limit(self, runner: CliRunner, patch_get_client, mock_client):
        """RateLimitError maps to exit code 3."""
        from teardrop import RateLimitError

        async def _fail(*a, **kw):
            raise RateLimitError("rate limited")
            if False:
                yield

        mock_client.run = _fail
        result = runner.invoke(app, ["agent", "run", "hello"])
        assert result.exit_code == 3

    def test_run_with_thread_id(self, runner: CliRunner, patch_get_client, mock_client):
        """--thread-id option is passed to client.run."""
        calls = []
        original_run = mock_client.run

        async def _tracked(prompt, *, thread_id=None, model=None, **kw):
            calls.append({"thread_id": thread_id})
            async for ev in original_run(prompt, thread_id=thread_id, model=model):
                yield ev

        mock_client.run = _tracked
        result = runner.invoke(app, ["agent", "run", "--thread-id", "t123", "hello"])
        assert result.exit_code == 0, result.output
        assert calls[0]["thread_id"] == "t123"
