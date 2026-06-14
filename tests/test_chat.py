"""Tests for the ``teardrop chat`` command — stateful chat with thread persistence."""

from __future__ import annotations

from unittest.mock import MagicMock

from click.testing import CliRunner

from teardrop_cli.cli import app


def _make_text_event(text: str, thread_id: str | None = None) -> MagicMock:
    """Build a TEXT_MESSAGE_CONTENT event; optionally include a thread_id."""
    ev = MagicMock()
    ev.type = "TEXT_MESSAGE_CONTENT"
    data: dict = {"delta": [{"text": text, "type": "text", "index": 0}]}
    if thread_id:
        data["thread_id"] = thread_id
    ev.data = data
    return ev


def _make_done_event() -> MagicMock:
    ev = MagicMock()
    ev.type = "DONE"
    ev.data = None
    return ev


class TestChatBasic:
    """Basic chat command smoke tests."""

    def test_chat_streams_text(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 0, result.output
        assert "Hello from the agent!" in result.output

    def test_chat_no_stream_collects(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["chat", "--no-stream", "hello"])
        assert result.exit_code == 0, result.output

    def test_chat_invalid_context_json(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["chat", "hello", "--context", "not json"])
        assert result.exit_code == 2
        assert "Invalid --context" in result.output

    def test_chat_estimate_cost_short_circuits(
        self, runner: CliRunner, patch_get_client
    ):
        result = runner.invoke(app, ["chat", "hello", "--estimate-cost"])
        assert result.exit_code == 0
        assert "Cost Estimate" in result.output or "USDC" in result.output

    def test_chat_payment_required_error(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        from teardrop import PaymentRequiredError

        async def _fail(*a, **kw):
            raise PaymentRequiredError("402")
            yield  # pragma: no cover

        mock_client.run = _fail
        result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 1
        assert "Insufficient credit" in result.output

    def test_chat_rate_limit(self, runner: CliRunner, patch_get_client, mock_client):
        from teardrop import RateLimitError

        async def _fail(*a, **kw):
            raise RateLimitError("rate limited")
            yield  # pragma: no cover

        mock_client.run = _fail
        result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 1
        assert "Rate limit" in result.output

    def test_chat_json_output(self, runner: CliRunner, patch_get_client, mock_client):
        """Chat --json should include thread_id."""
        thread_id = "thr_chat_json"
        async def _emit(*a, **kw):
            yield _make_text_event("ok", thread_id=thread_id)
            yield _make_done_event()

        mock_client.run = _emit
        result = runner.invoke(app, ["chat", "hello", "--json"])
        assert result.exit_code == 0, result.output
        assert thread_id in result.output
        assert '"text"' in result.output


class TestChatThreadPersistence:
    """Tests for automatic active-thread storage and reuse."""

    def test_first_turn_persists_thread_id(
        self, runner: CliRunner, patch_get_client, mock_client, tmp_config_dir
    ):
        """First chat with no stored thread → server provides one → stored."""
        from teardrop_cli import config

        assert config.get_active_thread_id() is None  # nothing stored yet

        server_thread_id = "thr_first"

        async def _emit(*a, **kw):
            yield _make_text_event("reply", thread_id=server_thread_id)
            yield _make_done_event()

        mock_client.run = _emit
        result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 0, result.output
        assert config.get_active_thread_id() == server_thread_id

    def test_second_turn_reuses_stored_thread(
        self, runner: CliRunner, patch_get_client, mock_client, tmp_config_dir
    ):
        """Second chat picks up the previously stored thread id."""
        from teardrop_cli import config

        config.set_active_thread_id("thr_stored")
        captured = {}

        async def _capture(message, **kwargs):
            captured["thread_id"] = kwargs.get("thread_id")
            yield _make_text_event("reply")
            yield _make_done_event()

        mock_client.run = _capture
        result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 0, result.output
        assert captured["thread_id"] == "thr_stored"

    def test_new_flag_clears_stored_thread(
        self, runner: CliRunner, patch_get_client, mock_client, tmp_config_dir
    ):
        """--new clears stored thread and starts fresh."""
        from teardrop_cli import config

        config.set_active_thread_id("thr_to_clear")
        captured = {}

        async def _capture(message, **kwargs):
            captured["thread_id"] = kwargs.get("thread_id")
            yield _make_text_event("reply")
            yield _make_done_event()

        mock_client.run = _capture
        result = runner.invoke(app, ["chat", "--new", "hello"])
        assert result.exit_code == 0, result.output
        # thread_id should be None since --new cleared it and no server returned one
        assert captured["thread_id"] is None or captured["thread_id"] == ""

    def test_explicit_thread_overrides_stored(
        self, runner: CliRunner, patch_get_client, mock_client, tmp_config_dir
    ):
        """--thread overrides any stored active thread."""
        from teardrop_cli import config

        config.set_active_thread_id("thr_stored")
        captured = {}

        async def _capture(message, **kwargs):
            captured["thread_id"] = kwargs.get("thread_id")
            yield _make_text_event("reply")
            yield _make_done_event()

        mock_client.run = _capture
        result = runner.invoke(app, ["chat", "--thread", "thr_explicit", "hello"])
        assert result.exit_code == 0, result.output
        assert captured["thread_id"] == "thr_explicit"

    def test_json_output_includes_thread_id(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        """Chat --json emits thread_id in JSON output."""
        server_thread = "thr_json_out"

        async def _emit(*a, **kw):
            yield _make_text_event("data", thread_id=server_thread)
            yield _make_done_event()

        mock_client.run = _emit
        result = runner.invoke(app, ["chat", "--json", "hello"])
        assert result.exit_code == 0, result.output
        assert f'"thread_id": "{server_thread}"' in result.output

    def test_chat_displays_thread_on_stderr(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        """Run prints 'thread: <id>' on stderr after a turn."""
        server_thread = "thr_display"

        async def _emit(*a, **kw):
            yield _make_text_event("data", thread_id=server_thread)
            yield _make_done_event()

        mock_client.run = _emit
        result = runner.invoke(app, ["chat", "hello"])
        assert result.exit_code == 0, result.output
        assert f"thread: {server_thread}" in result.output


class TestChatToolPolicy:
    """Tool policy and exclusion flags work from chat."""

    def test_chat_with_exclude(self, runner, patch_get_client, mock_client):
        captured = {}

        async def _capture(message, **kwargs):
            policy = kwargs.get("tool_policy")
            captured["exclude"] = policy.exclude_names if policy else None
            yield _make_text_event("ok")
            yield _make_done_event()

        mock_client.run = _capture
        result = runner.invoke(app, ["chat", "hello", "--exclude", "platform/web_search"])
        assert result.exit_code == 0, result.output
        assert captured["exclude"] == ["platform/web_search"]

    def test_chat_with_context(
        self, runner: CliRunner, patch_get_client, mock_client
    ):
        captured = {}

        async def _capture(message, **kwargs):
            captured["context"] = kwargs.get("context")
            yield _make_text_event("ok")
            yield _make_done_event()

        mock_client.run = _capture
        result = runner.invoke(
            app, ["chat", "hello", "--context", '{"k":"v"}']
        )
        assert result.exit_code == 0, result.output
        assert captured["context"] == {"k": "v"}