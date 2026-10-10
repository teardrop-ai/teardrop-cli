"""Tests for public scorecard commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from teardrop.models.scorecards import (
    LeaderboardResponse,
    ScorecardItem,
    ScorecardResponse,
    ScorecardTask,
    ScorecardTaskListResponse,
)

from teardrop_cli.cli import app


@pytest.fixture()
def scorecards_client(monkeypatch: pytest.MonkeyPatch):
    import teardrop

    client = MagicMock(name="TeardropClient")
    client.__enter__.return_value = client
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(teardrop, "TeardropClient", constructor)
    return client, constructor


def _tasks_response() -> ScorecardTaskListResponse:
    return ScorecardTaskListResponse(
        items=[
            ScorecardTask(
                definition_key="weather/forecast",
                definition_version=2,
                definition_sha256="a" * 64,
                prediction_schema={"type": "object", "properties": {"rain": {"type": "boolean"}}},
                config={"window_days": 90},
            )
        ]
    )


def _scorecard_item(
    subject: str,
    *,
    coverage: float | None,
    adjusted_brier: float | None,
    accuracy: float | None,
) -> ScorecardItem:
    return ScorecardItem(
        subject=subject,
        platform_attested=False,
        eligible=True,
        n_scored=12,
        rounds_submitted=12,
        rounds_expected=12,
        coverage=coverage,
        unresolved=0,
        mean_brier=adjusted_brier,
        adjusted_brier=adjusted_brier,
        accuracy=accuracy,
        calibration=None,
    )


def _leaderboard_response(items: list[ScorecardItem], *, window_days: int = 90):
    return LeaderboardResponse(
        definition_key="weather/forecast",
        definition_version=2,
        definition_sha256="b" * 64,
        window_days=window_days,
        min_sample=10,
        items=items,
    )


def _scorecard_response(item: ScorecardItem, *, window_days: int = 90):
    return ScorecardResponse(
        definition_key="weather/forecast",
        definition_version=2,
        definition_sha256="b" * 64,
        window_days=window_days,
        min_sample=10,
        item=item,
    )


def test_tasks_table_uses_unauthenticated_sdk_client(
    runner, scorecards_client, monkeypatch: pytest.MonkeyPatch
):
    client, constructor = scorecards_client
    monkeypatch.setattr("teardrop_cli.config.get_base_url", lambda: "https://public.example")
    client.scorecards.list_tasks.return_value = _tasks_response()

    result = runner.invoke(app, ["scorecards", "tasks"])

    assert result.exit_code == 0, result.output
    assert "weather/forecast" in result.output
    assert "Version" in result.output
    assert "aaaaaaaaaaaa" in result.output
    client.scorecards.list_tasks.assert_called_once_with()
    constructor.assert_called_once_with("https://public.example")
    client.__exit__.assert_called_once()


def test_tasks_json_includes_complete_sdk_response(runner, scorecards_client):
    client, _ = scorecards_client
    response = _tasks_response()
    client.scorecards.list_tasks.return_value = response

    result = runner.invoke(app, ["scorecards", "tasks", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == response.model_dump(mode="json")


def test_leaderboard_table_formats_metrics_and_preserves_nulls(runner, scorecards_client):
    client, _ = scorecards_client
    response = _leaderboard_response(
        [
            _scorecard_item(
                "zero-model",
                coverage=0.0,
                adjusted_brier=0.0,
                accuracy=0.0,
            ),
            _scorecard_item(
                "no-metrics",
                coverage=None,
                adjusted_brier=None,
                accuracy=None,
            ),
        ],
        window_days=30,
    )
    client.scorecards.get_leaderboard.return_value = response

    result = runner.invoke(
        app,
        ["scorecards", "leaderboard", "weather/forecast", "2", "--window-days", "30"],
    )

    assert result.exit_code == 0, result.output
    assert "Eligible" in result.output
    assert "Samples" in result.output
    assert "Coverage" in result.output
    assert "Adjusted" in result.output
    assert "Brier" in result.output
    assert "Lower adjusted Brier is better." in result.output
    assert "Accuracy" in result.output
    assert "zero-model" in result.output
    assert "0.0%" in result.output
    assert "0.0000" in result.output
    assert "no-metrics" in result.output
    assert "Unavailable" in result.output
    client.scorecards.get_leaderboard.assert_called_once_with(
        "weather/forecast",
        2,
        window_days=30,
    )


def test_leaderboard_json_preserves_sdk_response_and_default_window(runner, scorecards_client):
    client, _ = scorecards_client
    response = _leaderboard_response(
        [
            _scorecard_item(
                "weather-agent",
                coverage=0.75,
                adjusted_brier=0.12,
                accuracy=0.8,
            )
        ]
    )
    client.scorecards.get_leaderboard.return_value = response

    result = runner.invoke(
        app,
        ["scorecards", "leaderboard", "weather/forecast", "2", "--json"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == response.model_dump(mode="json")
    client.scorecards.get_leaderboard.assert_called_once_with(
        "weather/forecast",
        2,
        window_days=90,
    )


def test_show_table_uses_default_window_and_includes_required_metrics(runner, scorecards_client):
    client, _ = scorecards_client
    item = _scorecard_item(
        "weather-agent",
        coverage=0.75,
        adjusted_brier=0.12,
        accuracy=0.8,
    )
    client.scorecards.get_scorecard.return_value = _scorecard_response(item)

    result = runner.invoke(
        app,
        ["scorecards", "show", "weather/forecast", "2", "weather-agent"],
    )

    assert result.exit_code == 0, result.output
    assert "weather-agent" in result.output
    assert "75.0%" in result.output
    assert "0.1200" in result.output
    assert "80.0%" in result.output
    client.scorecards.get_scorecard.assert_called_once_with(
        "weather/forecast",
        2,
        "weather-agent",
        window_days=90,
    )


def test_show_json_preserves_null_metrics_and_calibration(runner, scorecards_client):
    client, _ = scorecards_client
    response = _scorecard_response(
        _scorecard_item(
            "weather-agent",
            coverage=None,
            adjusted_brier=None,
            accuracy=None,
        )
    )
    client.scorecards.get_scorecard.return_value = response

    result = runner.invoke(
        app,
        ["scorecards", "show", "weather/forecast", "2", "weather-agent", "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data == response.model_dump(mode="json")
    assert data["item"]["coverage"] is None
    assert data["item"]["adjusted_brier"] is None
    assert data["item"]["accuracy"] is None
    assert data["item"]["calibration"] is None


@pytest.mark.parametrize(
    "command",
    [
        ["tasks"],
        ["leaderboard", "weather/forecast", "2"],
        ["show", "weather/forecast", "2", "weather-agent"],
    ],
)
def test_scorecards_real_sdk_failures(runner, monkeypatch, sdk_http_failure, command):
    monkeypatch.setenv("TEARDROP_API_KEY", "test-token")

    result = runner.invoke(app, ["scorecards", *command, "--json"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stdout == ""
    assert "Unable to fetch" in result.stderr
    request = sdk_http_failure.call_args.args[0]
    assert request.method == "GET"
    assert "Authorization" not in request.headers
