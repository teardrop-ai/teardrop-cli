"""Tests for the schedules command group."""

from __future__ import annotations

from click.testing import CliRunner

from teardrop_cli.cli import app


def _schedule(**overrides):
    return {
        "id": "sch_1",
        "name": "daily-report",
        "prompt": "Generate a report",
        "schedule_kind": "interval",
        "interval_seconds": 60,
        "enabled": True,
        "callback_url": None,
        "next_run_at": "2026-06-29T12:05:00Z",
        "last_run_at": "2026-06-29T12:00:00Z",
        "consecutive_failures": 0,
        "created_at": "2026-06-29T12:00:00Z",
        "updated_at": "2026-06-29T12:00:00Z",
        **overrides,
    }


def _runs_page(*items):
    return {"items": list(items), "next_cursor": None}


class TestCreate:
    def test_create(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.create.return_value = _schedule(name="hourly-sync")
        result = runner.invoke(
            app,
            [
                "schedules",
                "create",
                "--name",
                "hourly-sync",
                "--prompt",
                "Sync warehouse status",
                "--interval-seconds",
                "60",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Schedule created: hourly-sync" in result.output
        mock_client.schedules.create.assert_awaited()

    def test_create_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.create.return_value = _schedule(name="hourly-sync")
        result = runner.invoke(
            app,
            [
                "schedules",
                "create",
                "--name",
                "hourly-sync",
                "--prompt",
                "Sync warehouse status",
                "--interval-seconds",
                "60",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert '"id": "sch_1"' in result.output
        assert '"name": "hourly-sync"' in result.output
        assert '"schedule_kind": "interval"' in result.output


class TestList:
    def test_list(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.list.return_value = [_schedule(name="nightly")]
        result = runner.invoke(app, ["schedules", "list"])
        assert result.exit_code == 0, result.output
        assert "nightly" in result.output
        assert "60s" in result.output

    def test_list_empty(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.list.return_value = []
        result = runner.invoke(app, ["schedules", "list"])
        assert result.exit_code == 0, result.output
        assert "No schedules found" in result.output

    def test_list_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.list.return_value = [_schedule(name="nightly-report")]
        result = runner.invoke(app, ["schedules", "list", "--json"])
        assert result.exit_code == 0, result.output
        assert '"name": "nightly-report"' in result.output


class TestGet:
    def test_get_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.get.return_value = _schedule(name="nightly-report")
        result = runner.invoke(app, ["schedules", "get", "sch_1", "--json"])
        assert result.exit_code == 0, result.output
        assert '"id": "sch_1"' in result.output

    def test_get_table(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.get.return_value = _schedule(
            name="daily-report", interval_seconds=3600
        )
        result = runner.invoke(app, ["schedules", "get", "sch_1"])
        assert result.exit_code == 0, result.output
        assert "daily-report" in result.output
        assert "3600s" in result.output
        assert "Interval" in result.output


class TestUpdate:
    def test_update_clear_callback_url(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.update.return_value = _schedule(callback_url=None)
        result = runner.invoke(
            app,
            ["schedules", "update", "sch_1", "--clear-callback-url"],
        )
        assert result.exit_code == 0, result.output
        request = mock_client.schedules.update.await_args.args[1]
        assert request.model_dump(exclude_unset=True) == {"callback_url": None}

    def test_update_name(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.update.return_value = _schedule(name="renamed")
        result = runner.invoke(
            app,
            ["schedules", "update", "sch_1", "--name", "renamed"],
        )
        assert result.exit_code == 0, result.output
        request = mock_client.schedules.update.await_args.args[1]
        assert request.model_dump(exclude_unset=True) == {"name": "renamed"}

    def test_update_rejects_missing_fields(self, runner: CliRunner, patch_get_client):
        result = runner.invoke(app, ["schedules", "update", "sch_1"])
        assert result.exit_code == 1
        assert "No fields to update" in result.output

    def test_update_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.update.return_value = _schedule(name="renamed")
        result = runner.invoke(
            app,
            ["schedules", "update", "sch_1", "--name", "renamed", "--json"],
        )
        assert result.exit_code == 0, result.output
        assert '"id": "sch_1"' in result.output
        assert '"name": "renamed"' in result.output


class TestDelete:
    def test_delete_with_yes(self, runner: CliRunner, patch_get_client, mock_client):
        result = runner.invoke(app, ["schedules", "delete", "sch_1", "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.schedules.delete.assert_awaited_once_with("sch_1")

    def test_delete_abort(self, runner: CliRunner, patch_get_client, mock_client):
        # No --yes and no input → EOF in confirm() → returns False → Abort
        result = runner.invoke(app, ["schedules", "delete", "sch_1"])
        assert result.exit_code != 0
        mock_client.schedules.delete.assert_not_awaited()


class TestRuns:
    def test_runs_table(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.runs.return_value = _runs_page(
            {
                "id": "schedrun_1",
                "run_id": "run_1",
                "status": "succeeded",
                "cost_usdc": 125_000,
                "error": "",
                "created_at": "2026-06-29T12:00:00Z",
            }
        )
        result = runner.invoke(app, ["schedules", "runs", "sch_1"])
        assert result.exit_code == 0, result.output
        assert "run_1" in result.output
        assert "$0.1250" in result.output

    def test_runs_empty(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.runs.return_value = {"items": [], "next_cursor": None}
        result = runner.invoke(app, ["schedules", "runs", "sch_1"])
        assert result.exit_code == 0, result.output
        assert "No schedule runs found" in result.output

    def test_runs_pagination_hint(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.runs.return_value = {
            "items": [
                {
                    "run_id": "run_1",
                    "status": "succeeded",
                    "cost_usdc": 0,
                    "error": "",
                    "created_at": "2026-06-29T12:00:00Z",
                }
            ],
            "next_cursor": "cursor_abc",
        }
        result = runner.invoke(app, ["schedules", "runs", "sch_1"])
        assert result.exit_code == 0, result.output
        assert "cursor_abc" in result.output
        assert "--cursor" in result.output

    def test_runs_json(self, runner: CliRunner, patch_get_client, mock_client):
        mock_client.schedules.runs.return_value = _runs_page(
            {
                "id": "schedrun_1",
                "run_id": "run_1",
                "status": "failed",
                "cost_usdc": 0,
                "error": "boom",
                "created_at": "2026-06-29T12:00:00Z",
            }
        )
        result = runner.invoke(app, ["schedules", "runs", "sch_1", "--json"])
        assert result.exit_code == 0, result.output
        assert '"error": "boom"' in result.output
