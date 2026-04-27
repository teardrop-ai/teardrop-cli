"""Shared pytest fixtures for teardrop-cli tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    """Click CliRunner for invoking the CLI in tests."""
    return CliRunner()


# ---------------------------------------------------------------------------
# Temporary config directory
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def tmp_config_dir(request, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect all config I/O to a temporary directory for test isolation.

    No-op for e2e-marked tests — they manage their own config dir via live_runner.
    """
    if request.node.get_closest_marker("e2e"):
        return None
    config_dir = tmp_path / "teardrop-config"
    config_dir.mkdir()
    monkeypatch.setattr("teardrop_cli.config.get_config_dir", lambda: config_dir)
    return config_dir


# ---------------------------------------------------------------------------
# Mock keyring (avoid real keyring during tests)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_keyring(request, monkeypatch: pytest.MonkeyPatch):
    """Replace keyring with a simple in-memory dict backend.

    No-op for e2e-marked tests — they may interact with the real keyring or
    rely on env-var credential resolution instead.
    """
    if request.node.get_closest_marker("e2e"):
        yield {}
        return
    store: dict[tuple[str, str], str] = {}

    def _get(service, key):
        return store.get((service, key))

    def _set(service, key, value):
        store[(service, key)] = value

    def _delete(service, key):
        store.pop((service, key), None)

    monkeypatch.setattr("teardrop_cli.config._keyring_available", lambda: True)
    with (
        patch("keyring.get_password", side_effect=_get),
        patch("keyring.set_password", side_effect=_set),
        patch("keyring.delete_password", side_effect=_delete),
    ):
        yield store


# ---------------------------------------------------------------------------
# Mock AsyncTeardropClient
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client():
    """Return a fully-mocked AsyncTeardropClient."""
    client = MagicMock(name="AsyncTeardropClient")

    # Async close
    client.close = AsyncMock(return_value=None)

    # auth
    from teardrop_cli._fixtures import make_jwt_payload

    client.get_me = AsyncMock(return_value=make_jwt_payload())

    # billing / balance
    client.get_marketplace_balance = AsyncMock(
        return_value={"balance_usdc": 10_000_000, "pending_usdc": 0, "settlement_wallet": "0xABC"}
    )
    client.get_earnings = AsyncMock(return_value={"earnings": [], "next_cursor": None})
    client.get_withdrawals = AsyncMock(return_value={"withdrawals": [], "next_cursor": None})
    client.withdraw = AsyncMock(return_value={"status": "pending", "id": "w_123"})
    client.set_author_config = AsyncMock(
        return_value=MagicMock(model_dump=lambda: {"payout_address": "0xABC"})
    )
    client.get_balance = AsyncMock(
        return_value={
            "balance_usdc": 5_000_000,
            "spending_limit_usdc": 100_000_000,
            "daily_spend_usdc": 12_345,
            "is_paused": False,
        }
    )
    client.get_usage = AsyncMock(
        return_value={
            "total_runs": 12,
            "total_tokens_in": 1234,
            "total_tokens_out": 5678,
            "total_tool_calls": 3,
            "total_duration_ms": 1500,
        }
    )
    client.topup_stripe = AsyncMock(
        return_value={
            "session_id": "cs_test_1",
            "client_secret": "https://checkout.stripe.com/c/cs_test_1",
        }
    )
    client.get_stripe_topup_status = AsyncMock(
        return_value={"status": "complete", "new_balance_fmt": "15.00"}
    )
    client.get_usdc_topup_requirements = AsyncMock(
        return_value={"x402Version": 1, "accepts": [{"scheme": "exact", "amount": "1.00"}]}
    )

    # marketplace
    client.get_marketplace_catalog = AsyncMock(
        return_value={
            "tools": [
                {
                    "name": "acme/weather",
                    "author": "acme",
                    "cost_usdc": 5000,
                    "description": "Get the weather",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
            "next_cursor": None,
        }
    )
    client.subscribe = AsyncMock(
        return_value=MagicMock(
            model_dump=lambda: {"id": "sub_1", "qualified_tool_name": "acme/weather"}
        )
    )
    client.unsubscribe = AsyncMock(return_value=None)
    client.get_subscriptions = AsyncMock(
        return_value=[
            MagicMock(
                id="sub_1",
                qualified_tool_name="acme/weather",
                model_dump=lambda: {
                    "id": "sub_1",
                    "qualified_tool_name": "acme/weather",
                    "subscribed_at": "2025-01-01T00:00:00Z",
                },
            )
        ]
    )

    # auth
    client.logout = AsyncMock(return_value=None)

    # mcp
    client.list_mcp_servers = AsyncMock(return_value=[])
    client.create_mcp_server = AsyncMock(
        return_value=MagicMock(
            id="srv_1",
            name="my-mcp",
            model_dump=lambda: {"id": "srv_1", "name": "my-mcp", "url": "http://mcp.local"},
        )
    )
    client.discover_mcp_server_tools = AsyncMock(return_value=MagicMock(tools=[]))
    client.delete_mcp_server = AsyncMock(return_value=None)

    # tools
    client.list_tools = AsyncMock(return_value=[])
    client.create_tool = AsyncMock(
        return_value=MagicMock(
            id="tool_1",
            name="my_tool",
            model_dump=lambda: {"id": "tool_1", "name": "my_tool"},
        )
    )
    client.update_tool = AsyncMock(
        return_value=MagicMock(
            id="tool_1",
            name="my_tool",
            model_dump=lambda: {"id": "tool_1", "name": "my_tool"},
        )
    )
    client.delete_tool = AsyncMock(return_value=None)
    client.get_tool = AsyncMock(
        return_value=MagicMock(
            id="tool_1",
            name="my-tool",
            model_dump=lambda: {
                "id": "tool_1",
                "name": "my-tool",
                "description": "A test tool",
                "type": "function",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Search query"}},
                    "required": ["query"],
                },
            },
        )
    )

    # agent run — returns an async generator of SSE events
    async def _default_run(*args, **kwargs):
        from teardrop_cli._fixtures import make_sse_events

        for event in make_sse_events("Hello from the agent!"):
            yield event

    client.run = _default_run

    # llm-config
    from teardrop_cli._fixtures import make_benchmarks_response, make_llm_config

    client.get_llm_config = AsyncMock(return_value=make_llm_config())
    client.set_llm_config = AsyncMock(return_value=make_llm_config())
    client.clear_llm_api_key = AsyncMock(return_value=make_llm_config())
    client.delete_llm_config = AsyncMock(return_value={"status": "deleted"})

    # models benchmarks
    client.get_model_benchmarks = AsyncMock(return_value=make_benchmarks_response())
    client.get_org_model_benchmarks = AsyncMock(return_value=make_benchmarks_response())

    # siwe wallet sessions
    from teardrop_cli._fixtures import make_siwe_session

    client.create_siwe_session = AsyncMock(return_value=make_siwe_session())
    client.get_siwe_session = AsyncMock(return_value=make_siwe_session(status="completed"))

    return client


@pytest.fixture()
def patch_get_client(mock_client, monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch config.get_client to return mock_client."""
    monkeypatch.setattr("teardrop_cli.config.get_client", lambda *a, **kw: mock_client)
    return mock_client
