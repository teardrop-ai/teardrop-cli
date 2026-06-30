"""Tests for the event-triggers command group."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


def _trigger(**overrides):
    return {
        "id": "evt_1",
        "name": "webhook-trigger",
        "prompt": "Handle inbound webhook",
        "schedule_kind": "event",
        "enabled": True,
        "callback_url": None,
        "trigger_token": "pub_123",
        "event_path": "/agent/events/pub_123",
        "consecutive_failures": 0,
        "last_run_at": None,
        "created_at": "2026-06-29T12:00:00Z",
        "updated_at": "2026-06-29T12:00:00Z",
        **overrides,
    }


def _runs_page(*items):
    return {"items": list(items), "next_cursor": None}


class TestCreate:
    def test_create(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.create.return_value = _trigger(secret="top-secret")
        result = runner.invoke(
            app,
            [
                "event-triggers",
                "create",
                "--name",
                "webhook-trigger",
                "--prompt",
                "Handle inbound webhook",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Event trigger registered: webhook-trigger (evt_1)" in result.output
        assert (
            "Public endpoint: POST https://api.teardrop.dev/agent/events/pub_123" in result.output
        )
        assert "Secret (store securely now; only shown once): top-secret" in result.output

    def test_create_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.create.return_value = _trigger(secret="top-secret")
        result = runner.invoke(
            app,
            [
                "event-triggers",
                "create",
                "--name",
                "webhook-trigger",
                "--prompt",
                "Handle inbound webhook",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        # EventTriggerWithSecret shape — secret present in JSON output.
        assert '"id": "evt_1"' in result.output
        assert '"secret": "top-secret"' in result.output
        assert '"schedule_kind": "event"' in result.output


class TestList:
    def test_list(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.list.return_value = [_trigger(name="order-events")]
        result = runner.invoke(app, ["event-triggers", "list"])
        assert result.exit_code == 0, result.output
        assert "order-events" in result.output
        assert "event" in result.output

    def test_list_empty(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.list.return_value = []
        result = runner.invoke(app, ["event-triggers", "list"])
        assert result.exit_code == 0, result.output
        assert "No event triggers found" in result.output


class TestGet:
    def test_get_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.get.return_value = _trigger(name="order-events")
        result = runner.invoke(app, ["event-triggers", "get", "evt_1", "--json"])
        assert result.exit_code == 0, result.output
        assert '"name": "order-events"' in result.output

    def test_get_table(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.get.return_value = _trigger(name="order-events")
        result = runner.invoke(app, ["event-triggers", "get", "evt_1"])
        assert result.exit_code == 0, result.output
        assert "order-events" in result.output
        assert "Public Endpoint" in result.output


class TestUpdate:
    def test_update_clear_callback_url(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.update.return_value = _trigger(callback_url=None)
        result = runner.invoke(
            app,
            ["event-triggers", "update", "evt_1", "--clear-callback-url"],
        )
        assert result.exit_code == 0, result.output
        request = mock_client.event_triggers.update.await_args.args[1]
        assert request.model_dump(exclude_unset=True) == {"callback_url": None}

    def test_update_name(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.update.return_value = _trigger(name="renamed")
        result = runner.invoke(
            app,
            ["event-triggers", "update", "evt_1", "--name", "renamed"],
        )
        assert result.exit_code == 0, result.output
        request = mock_client.event_triggers.update.await_args.args[1]
        assert request.model_dump(exclude_unset=True) == {"name": "renamed"}

    def test_update_rejects_conflicting_callback_flags(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(
            app,
            [
                "event-triggers",
                "update",
                "evt_1",
                "--callback-url",
                "https://example.com/callback",
                "--clear-callback-url",
            ],
        )
        assert result.exit_code == 1
        assert "Use either --callback-url or --clear-callback-url" in result.output

    def test_update_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.update.return_value = _trigger(name="renamed")
        result = runner.invoke(
            app,
            ["event-triggers", "update", "evt_1", "--name", "renamed", "--json"],
        )
        assert result.exit_code == 0, result.output
        # Standard EventTrigger shape — no secret key.
        assert '"id": "evt_1"' in result.output
        assert '"name": "renamed"' in result.output
        assert '"secret"' not in result.output


class TestDelete:
    def test_delete_with_yes(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["event-triggers", "delete", "evt_1", "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.event_triggers.delete.assert_awaited_once_with("evt_1")

    def test_delete_abort(self, runner: CliRunner, patch_get_client, mock_client):
        # No --yes and no input → EOF in confirm() → returns False → Abort
        result = runner.invoke(app, ["event-triggers", "delete", "evt_1"])
        assert result.exit_code != 0
        mock_client.event_triggers.delete.assert_not_awaited()


class TestRotateSecret:
    def test_rotate_secret(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.get.return_value = _trigger(name="webhook-trigger")
        mock_client.event_triggers.rotate_secret.return_value = {"secret": "rotated-secret"}
        result = runner.invoke(app, ["event-triggers", "rotate-secret", "evt_1"])
        assert result.exit_code == 0, result.output
        assert "Event trigger secret rotated: webhook-trigger (evt_1)" in result.output
        assert "Secret (store securely now; only shown once): rotated-secret" in result.output

    def test_rotate_secret_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.get.return_value = _trigger(name="webhook-trigger")
        mock_client.event_triggers.rotate_secret.return_value = {"secret": "rotated-secret"}
        result = runner.invoke(app, ["event-triggers", "rotate-secret", "evt_1", "--json"])
        assert result.exit_code == 0, result.output
        # Rotation model shape: id + new plaintext secret only.
        assert '"id": "evt_1"' in result.output
        assert '"secret": "rotated-secret"' in result.output
        assert '"name"' not in result.output


class TestRuns:
    def test_runs_table(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.runs.return_value = _runs_page(
            {
                "id": "schedrun_1",
                "run_id": "run_1",
                "status": "failed",
                "cost_usdc": 0,
                "error": "bad signature",
                "created_at": "2026-06-29T12:00:00Z",
            }
        )
        result = runner.invoke(app, ["event-triggers", "runs", "evt_1"])
        assert result.exit_code == 0, result.output
        assert "run_1" in result.output
        assert "bad signature" in result.output

    def test_runs_empty(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.runs.return_value = {"items": [], "next_cursor": None}
        result = runner.invoke(app, ["event-triggers", "runs", "evt_1"])
        assert result.exit_code == 0, result.output
        assert "No event-trigger runs found" in result.output

    def test_runs_pagination_hint(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.runs.return_value = {
            "items": [
                {
                    "run_id": "run_1",
                    "status": "succeeded",
                    "cost_usdc": 0,
                    "error": "",
                    "created_at": "2026-06-29T12:00:00Z",
                }
            ],
            "next_cursor": "cursor_xyz",
        }
        result = runner.invoke(app, ["event-triggers", "runs", "evt_1"])
        assert result.exit_code == 0, result.output
        assert "cursor_xyz" in result.output
        assert "--cursor" in result.output

    def test_runs_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.event_triggers.runs.return_value = _runs_page(
            {
                "id": "schedrun_1",
                "run_id": "run_1",
                "status": "succeeded",
                "cost_usdc": 125_000,
                "error": "",
                "created_at": "2026-06-29T12:00:00Z",
            }
        )
        result = runner.invoke(app, ["event-triggers", "runs", "evt_1", "--json"])
        assert result.exit_code == 0, result.output
        assert '"cost_usdc": 125000' in result.output
