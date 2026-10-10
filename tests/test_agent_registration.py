"""Tests for marketplace agent registration commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from teardrop import (
    MarketplaceAgentRegistrationCheck,
    MarketplaceAgentRegistrationPreviewResponse,
    MarketplaceAgentRegistrationTestResponse,
)

from teardrop_cli.cli import app


@pytest.fixture()
def sync_client(monkeypatch: pytest.MonkeyPatch):
    client = MagicMock(name="TeardropClient")
    client.__enter__.return_value = client
    factory = MagicMock(return_value=client)
    monkeypatch.setattr("teardrop_cli.config.get_sync_client", factory)
    return client, factory


def test_preview_human_output_shows_false_detail_and_price(runner, sync_client):
    client, factory = sync_client
    agent_url = "https://agent.example/a2a"
    client.preview_agent_registration.return_value = MarketplaceAgentRegistrationPreviewResponse(
        registrable=False,
        agent_url=agent_url,
        price_per_task_usdc=250_000,
        detail="Agent card is missing required A2A fields.",
    )

    result = runner.invoke(
        app,
        ["marketplace", "agent-registration", "preview", "--agent-url", agent_url],
    )

    assert result.exit_code == 0, result.output
    assert "registrable" in result.output
    assert "false" in result.output
    assert "Agent card is missing required A2A fields." in result.output
    assert "price_per_task_usdc" in result.output
    assert "250000" in result.output
    request = client.preview_agent_registration.call_args.args[0]
    assert request.agent_url == agent_url
    factory.assert_called_once_with(None)
    client.__exit__.assert_called_once()


def test_preview_json_preserves_complete_typed_response(runner, sync_client):
    client, _ = sync_client
    response = MarketplaceAgentRegistrationPreviewResponse(
        registrable=True,
        agent_url="https://agent.example/a2a",
        price_per_task_usdc=None,
        detail=None,
    )
    client.preview_agent_registration.return_value = response

    result = runner.invoke(
        app,
        [
            "marketplace",
            "agent-registration",
            "preview",
            "--agent-url",
            response.agent_url,
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == response.model_dump(mode="json")
    assert json.loads(result.stdout)["detail"] is None


@pytest.mark.parametrize("agent_url", ["x", "x" * 2048])
def test_preview_accepts_agent_url_length_boundaries(runner, sync_client, agent_url):
    client, _ = sync_client
    client.preview_agent_registration.return_value = MarketplaceAgentRegistrationPreviewResponse(
        registrable=True,
        detail=None,
    )

    result = runner.invoke(
        app,
        ["marketplace", "agent-registration", "preview", "--agent-url", agent_url],
    )

    assert result.exit_code == 0, result.output
    request = client.preview_agent_registration.call_args.args[0]
    assert request.agent_url == agent_url


@pytest.mark.parametrize("agent_url", ["", "x" * 2049])
def test_preview_rejects_agent_url_outside_sdk_length_limits(runner, sync_client, agent_url):
    _, factory = sync_client

    result = runner.invoke(
        app,
        ["marketplace", "agent-registration", "preview", "--agent-url", agent_url],
    )

    assert result.exit_code == 2
    assert "--agent-url must contain between 1 and 2048 characters." in result.output
    factory.assert_not_called()


def test_test_human_output_shows_false_and_all_checks(runner, sync_client):
    client, _ = sync_client
    agent_url = "https://agent.example/a2a"
    response = MarketplaceAgentRegistrationTestResponse(
        passed=False,
        agent_url=agent_url,
        checks=[
            MarketplaceAgentRegistrationCheck(
                name="agent_card",
                status="pass",
                detail="A2A agent card loaded.",
            ),
            MarketplaceAgentRegistrationCheck(
                name="payment",
                status="warn",
                detail="HTTP 402 is expected for a priced agent.",
            ),
            MarketplaceAgentRegistrationCheck(
                name="message",
                status="fail",
                detail="Agent did not return a valid message.",
            ),
        ],
    )
    client.test_agent_registration.return_value = response

    result = runner.invoke(
        app,
        ["marketplace", "agent-registration", "test", "--agent-url", agent_url],
    )

    assert result.exit_code == 0, result.output
    assert "passed" in result.output
    assert "false" in result.output
    for check in response.checks:
        assert check.name in result.output
        assert check.status in result.output
        assert check.detail in result.output
    assert "not a charge to you" in result.output
    request = client.test_agent_registration.call_args.args[0]
    assert request.agent_url == agent_url
    client.__exit__.assert_called_once()


def test_test_json_preserves_complete_typed_response(runner, sync_client):
    client, _ = sync_client
    response = MarketplaceAgentRegistrationTestResponse(
        passed=True,
        agent_url="https://agent.example/a2a",
        checks=[
            MarketplaceAgentRegistrationCheck(
                name="message",
                status="pass",
                detail="Agent replied.",
            )
        ],
    )
    client.test_agent_registration.return_value = response

    result = runner.invoke(
        app,
        [
            "marketplace",
            "agent-registration",
            "test",
            "--agent-url",
            response.agent_url,
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == response.model_dump(mode="json")


@pytest.mark.parametrize("command", ["preview", "test"])
def test_registration_real_sdk_failures(runner, monkeypatch, sdk_http_failure, command):
    monkeypatch.setenv("TEARDROP_API_KEY", "test-token")

    result = runner.invoke(
        app,
        [
            "marketplace",
            "agent-registration",
            command,
            "--agent-url",
            "https://agent.example/a2a",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stdout == ""
    assert f"Unable to {command} agent registration:" in result.stderr
    request = sdk_http_failure.call_args.args[0]
    assert request.method == "POST"
    assert request.url.path.endswith(f"/agent-registration/{command}")
    assert request.headers["Authorization"] == "Bearer test-token"
