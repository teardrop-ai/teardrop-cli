"""Tests for the top-level ``run`` command."""

from __future__ import annotations

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


class TestSSEContract:
    """The backend guarantees event hygiene: TEXT_MESSAGE_CONTENT is clean prose.
    UI data is separate via SURFACE_UPDATE events.
    """

    def test_run_trusts_clean_prose(self, runner: CliRunner, patch_get_client, mock_client):
        async def _emit(*args, **kwargs):
            from teardrop_cli._fixtures import build_text_event
            yield build_text_event("Clean narrative text.")

        mock_client.run = _emit
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 0
        assert "Clean narrative text." in result.output

    def test_run_ignores_surface_update(self, runner: CliRunner, patch_get_client, mock_client):
        async def _emit(*args, **kwargs):
            from teardrop_cli._fixtures import build_text_event
            from unittest.mock import MagicMock
            
            yield build_text_event("Narrative start.")
            
            ev = MagicMock()
            ev.type = "SURFACE_UPDATE"
            ev.data = {"components": [{"type": "chart"}]}
            yield ev
            
            yield build_text_event(" Narrative end.")

        mock_client.run = _emit
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 0
        assert "Narrative start. Narrative end." in result.output
        assert "chart" not in result.output


class TestDuplicateCallHandling:
    def test_run_streaming_suppresses_duplicate_event(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop_cli._fixtures import make_duplicate_call_events

        async def _run_dup(*a, **kw):
            for ev in make_duplicate_call_events():
                yield ev

        mock_client.run = _run_dup
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 0
        # Should show text but NOT the error
        assert "I'll fetch that again." in result.output
        assert "Error" not in result.output
        assert "DUPLICATE_CALL_BLOCKED" not in result.output

    def test_run_no_stream_suppresses_duplicate_error(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        async def _fail_dup(*a, **kw):
            raise Exception("DUPLICATE_CALL_BLOCKED: Result retrieved from cache.")
            yield

        mock_client.run = _fail_dup
        result = runner.invoke(app, ["run", "--no-stream", "hello"])
        # Should exit 0 or 1 without showing Error:
        assert "Error:" not in result.output
        assert "DUPLICATE_CALL_BLOCKED" not in result.output


class TestMultiPhaseRun:
    """Verify that multi-message streams (e.g. planner phases) are handled correctly."""

    def test_run_appends_deltas_within_same_message(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop_cli._fixtures import build_done_event, build_text_event

        async def _run(*a, **kw):
            yield build_text_event("Hello ", message_id="msg_1")
            yield build_text_event("world!", message_id="msg_1")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "hi"])
        assert result.exit_code == 0
        assert "Hello world!" in result.output

    def test_run_streaming_resets_on_new_message_id(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop_cli._fixtures import build_done_event, build_text_event

        async def _run(*a, **kw):
            # Phase 1: Planner
            yield build_text_event("Now let me fetch yield rates...", message_id="msg_1")
            # Phase 2: Actual answer (replaces previous block)
            yield build_text_event("The current yield is 5%.", message_id="msg_2")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "hi"])
        assert result.exit_code == 0
        # In the final output stream, we only see the last message's text
        # (Rich Live updates are flattened in CliRunner output)
        assert "The current yield is 5%." in result.output
        assert "Now let me fetch yield rates..." not in result.output

    def test_run_no_stream_keeps_only_last_message(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop_cli._fixtures import build_done_event, build_text_event

        async def _run(*a, **kw):
            yield build_text_event("Planning...", message_id="msg_1")
            yield build_text_event("Final answer.", message_id="msg_2")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "--no-stream", "hi"])
        assert result.exit_code == 0
        assert "Final answer." in result.output
        assert "Planning..." not in result.output

    def test_run_preserves_accumulation_without_message_id(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        """Older backends without message_id should still accumulate correctly."""
        from teardrop_cli._fixtures import build_done_event, build_text_event

        async def _run(*a, **kw):
            yield build_text_event("Part 1")
            yield build_text_event(" and Part 2")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "hi"])
        assert result.exit_code == 0
        assert "Part 1 and Part 2" in result.output

    def test_run_tool_calls_do_not_reset_text(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop_cli._fixtures import (
            build_done_event,
            build_text_event,
            build_tool_event,
        )

        async def _run(*a, **kw):
            yield build_text_event("Thinking...", message_id="msg_1")
            yield build_tool_event("TOOL_CALL_START", tool_name="serpapi")
            yield build_tool_event("TOOL_CALL_END")
            yield build_text_event(" Done.", message_id="msg_1")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "hi"])
        assert result.exit_code == 0
        # Rich Live updates can be tricky to assert on exactly when multiple 
        # frames are involved. We verify the final text accumulation.
        assert "Thinking..." in result.output
        assert "Done." in result.output


class TestEmitUi:
    """Verify emit_ui is forwarded correctly to client.run()."""

    def test_default_omits_emit_ui_false(self, runner: CliRunner, patch_get_client, mock_client):
        """Default invocation passes emit_ui=False."""
        captured: dict = {}

        async def _capture(message, **kwargs):
            captured.update(kwargs)
            from teardrop_cli._fixtures import make_sse_events

            for ev in make_sse_events("ok"):
                yield ev

        mock_client.run = _capture
        result = runner.invoke(app, ["run", "hello"])
        assert result.exit_code == 0, result.output
        assert captured.get("emit_ui") is False

    def test_with_ui_flag_passes_emit_ui_true(self, runner: CliRunner, patch_get_client, mock_client):
        """--with-ui flag passes emit_ui=True."""
        captured: dict = {}

        async def _capture(message, **kwargs):
            captured.update(kwargs)
            from teardrop_cli._fixtures import make_sse_events

            for ev in make_sse_events("ok"):
                yield ev

        mock_client.run = _capture
        result = runner.invoke(app, ["run", "--with-ui", "hello"])
        assert result.exit_code == 0, result.output
        assert captured.get("emit_ui") is True

    def test_no_stream_default_emit_ui_false(self, runner: CliRunner, patch_get_client, mock_client):
        """--no-stream default also passes emit_ui=False."""
        captured: dict = {}

        async def _capture(message, **kwargs):
            captured.update(kwargs)
            from teardrop_cli._fixtures import make_sse_events

            for ev in make_sse_events("ok"):
                yield ev

        mock_client.run = _capture
        result = runner.invoke(app, ["run", "--no-stream", "hello"])
        assert result.exit_code == 0, result.output
        assert captured.get("emit_ui") is False

    def test_no_stream_with_ui_flag(self, runner: CliRunner, patch_get_client, mock_client):
        """--no-stream --with-ui passes emit_ui=True."""
        captured: dict = {}

        async def _capture(message, **kwargs):
            captured.update(kwargs)
            from teardrop_cli._fixtures import make_sse_events

            for ev in make_sse_events("ok"):
                yield ev

        mock_client.run = _capture
        result = runner.invoke(app, ["run", "--no-stream", "--with-ui", "hello"])
        assert result.exit_code == 0, result.output
        assert captured.get("emit_ui") is True


class TestApprovalErrorSurfacing:
    """Verify get_token_approvals batch RPC failure surfaces a warning."""

    def test_approval_error_surfaces_warning(self, runner: CliRunner, patch_get_client, mock_client):
        """TOOL_CALL_RESULT with error from get_token_approvals prints a warning."""
        from teardrop_cli._fixtures import (
            build_done_event,
            build_text_event,
            build_tool_result_event,
        )

        async def _run(*a, **kw):
            yield build_text_event("Auditing approvals…", message_id="msg_1")
            yield build_tool_result_event(
                "get_token_approvals",
                {"approvals": [], "error": "Batch RPC call failed: timeout after 30s"},
            )
            yield build_text_event(" Audit complete.", message_id="msg_1")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "audit my wallet"])
        assert result.exit_code == 0, result.output
        assert "Approval audit incomplete" in result.output
        assert "Batch RPC call failed" in result.output

    def test_approval_success_no_warning(self, runner: CliRunner, patch_get_client, mock_client):
        """Successful get_token_approvals result (no error) does not emit a warning."""
        from teardrop_cli._fixtures import (
            build_done_event,
            build_text_event,
            build_tool_result_event,
        )

        async def _run(*a, **kw):
            yield build_tool_result_event(
                "get_token_approvals",
                {"approvals": [{"token": "USDC", "spender": "0xDEF"}], "error": None},
            )
            yield build_text_event("No risky approvals found.", message_id="msg_1")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "audit my wallet"])
        assert result.exit_code == 0, result.output
        assert "Approval audit incomplete" not in result.output
        assert "warning" not in result.output.lower()

    def test_other_tool_error_not_surfaced(self, runner: CliRunner, patch_get_client, mock_client):
        """TOOL_CALL_RESULT error from a different tool does not trigger the approval warning."""
        from teardrop_cli._fixtures import (
            build_done_event,
            build_text_event,
            build_tool_result_event,
        )

        async def _run(*a, **kw):
            yield build_tool_result_event(
                "get_portfolio_value",
                {"positions": [], "error": "RPC failure"},
            )
            yield build_text_event("Done.", message_id="msg_1")
            yield build_done_event()

        mock_client.run = _run
        result = runner.invoke(app, ["run", "check portfolio"])
        assert result.exit_code == 0, result.output
        assert "Approval audit incomplete" not in result.output
