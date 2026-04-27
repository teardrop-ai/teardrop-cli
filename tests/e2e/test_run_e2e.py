"""Live end-to-end tests for the ``teardrop run`` command.

Covers:
- Real agent execution returns a text response (no-stream + JSON)
- Thread ID argument is forwarded correctly
- Unauthenticated run exits 1 with an auth hint
"""

from __future__ import annotations

import json
import uuid

import pytest

from teardrop_cli.cli import app

pytestmark = pytest.mark.e2e


class TestRunRealResponse:
    def test_run_returns_text(self, live_runner) -> None:
        """``run --no-stream --json`` contacts the real API and returns a text reply."""
        result = live_runner.invoke(
            app,
            ["run", "--no-stream", "--json", "Reply with only the word PONG"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data.get("text"), str), f"Missing 'text' key in: {data}"
        assert len(data["text"]) > 0

    def test_run_response_contains_expected_word(self, live_runner) -> None:
        """The agent actually answers the prompt (not just an empty or error response)."""
        result = live_runner.invoke(
            app,
            ["run", "--no-stream", "--json", "Reply with only the word PONG"],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "PONG" in data.get("text", "").upper(), (
            f"Expected 'PONG' in response, got: {data.get('text')!r}"
        )


class TestRunWithThread:
    def test_thread_id_forwarded(self, live_runner) -> None:
        """``--thread`` is accepted and the supplied ID echoed back in JSON output.

        A unique thread ID is generated per run so that repeated test runs do
        not accumulate messages in a single persistent thread row.  Note: the
        SDK has no delete_thread method, so these threads remain in the
        database but are individually isolated and labelled ``e2e-test-``.
        """
        thread_id = f"e2e-test-{uuid.uuid4().hex[:12]}"
        result = live_runner.invoke(
            app,
            [
                "run",
                "--no-stream",
                "--json",
                "--thread",
                thread_id,
                "Say hello",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data.get("thread_id") == thread_id


class TestRunAuthErrors:
    def test_unauthenticated_exits_1(self, blank_runner) -> None:
        """``run`` without credentials exits 1 and prints an auth hint."""
        result = blank_runner.invoke(app, ["run", "--no-stream", "hello"])
        assert result.exit_code == 1
        # The CLI must guide the user toward auth login
        assert "auth login" in result.output or "teardrop auth" in result.output
