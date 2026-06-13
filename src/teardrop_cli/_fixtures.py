"""Test fixture helpers shared across test modules."""

from __future__ import annotations

from unittest.mock import MagicMock


def make_jwt_payload(
    sub: str = "user@example.com",
    org: str = "acme",
    role: str = "admin",
) -> MagicMock:
    """Return a minimal JwtPayloadBase-like mock."""
    payload = MagicMock()
    payload.sub = sub
    payload.org = org
    payload.role = role
    payload.model_dump = lambda: {"sub": sub, "org": org, "role": role}
    return payload


def build_text_event(text: str, message_id: str | None = None) -> MagicMock:
    """Build a TEXT_MESSAGE_CONTENT event for testing."""
    chunk = MagicMock()
    chunk.type = "TEXT_MESSAGE_CONTENT"
    data = {"delta": text}
    if message_id:
        data["message_id"] = message_id
    chunk.data = data
    return chunk


def build_tool_event(
    event_type: str,
    tool_name: str | None = None,
    call_id: str | None = None,
) -> MagicMock:
    """Build a tool start/end event for testing."""
    ev = MagicMock()
    ev.type = event_type
    data = {}
    if tool_name:
        data["tool_name"] = tool_name
        data["name"] = tool_name
    if call_id:
        data["call_id"] = call_id
    ev.data = data
    return ev


def build_tool_result_event(
    tool_name: str,
    result: dict,
    call_id: str | None = None,
) -> MagicMock:
    """Build a TOOL_CALL_RESULT event for testing."""
    ev = MagicMock()
    ev.type = "TOOL_CALL_RESULT"
    data: dict = {"tool_name": tool_name, "result": result}
    if call_id:
        data["call_id"] = call_id
    ev.data = data
    return ev


def build_done_event() -> MagicMock:
    """Build a DONE event for testing."""
    ev = MagicMock()
    ev.type = "DONE"
    ev.data = None
    return ev


def make_sse_events(text: str) -> list[MagicMock]:
    """Build a minimal sequence of SSE events for a successful agent run."""
    events = []

    # text chunk
    chunk = MagicMock()
    chunk.type = "TEXT_MESSAGE_CONTENT"
    chunk.data = {"delta": [{"text": text, "type": "text", "index": 0}]}
    events.append(chunk)

    return events


def make_duplicate_call_events() -> list[MagicMock]:
    """Build a sequence of SSE events with a duplicate tool call."""
    events = []

    # text
    chunk = MagicMock()
    chunk.type = "TEXT_MESSAGE_CONTENT"
    chunk.data = {"delta": "I'll fetch that again."}
    events.append(chunk)

    # duplicate block
    dup = MagicMock()
    dup.type = "TOOL_CALL_DUPLICATE"
    dup.data = {"tool_name": "web_search", "reason": "cache_hit"}
    events.append(dup)

    # done
    done = MagicMock()
    done.type = "DONE"
    done.data = None
    events.append(done)

    return events


def make_llm_config(
    org_id: str = "org-1",
    provider: str = "anthropic",
    model: str = "claude-haiku-4-5-20251001",
    has_api_key: bool = False,
    api_base: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    timeout_seconds: int = 120,
    routing_preference: str = "default",
    is_byok: bool = False,
) -> MagicMock:
    """Return a minimal OrgLlmConfig-like mock."""
    data = {
        "org_id": org_id,
        "provider": provider,
        "model": model,
        "has_api_key": has_api_key,
        "api_base": api_base,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout_seconds": timeout_seconds,
        "routing_preference": routing_preference,
        "is_byok": is_byok,
        "created_at": "2026-04-16T10:00:00Z",
        "updated_at": "2026-04-16T10:00:00Z",
    }
    obj = MagicMock()
    obj.model_dump = lambda: dict(data)
    for k, v in data.items():
        setattr(obj, k, v)
    return obj


def make_siwe_session(
    session_id: str = "siwe_sess_1",
    status: str = "pending",
    nonce: str = "abc123nonce",
    jwt: str | None = None,
) -> MagicMock:
    """Return a minimal SiweSession-like mock."""
    data = {
        "id": session_id,
        "status": status,
        "nonce": nonce,
        "jwt": jwt,
    }
    obj = MagicMock()
    obj.model_dump = lambda: dict(data)
    for k, v in data.items():
        setattr(obj, k, v)
    return obj


def make_benchmarks_response(models: list[dict] | None = None) -> MagicMock:
    """Return a minimal ModelBenchmarksResponse-like mock."""
    if models is None:
        models = [
            {
                "provider": "anthropic",
                "model": "claude-haiku-4-5-20251001",
                "display_name": "Claude Haiku 4.5",
                "context_window": 200000,
                "supports_tools": True,
                "supports_streaming": True,
                "quality_tier": 2,
                "pricing": {
                    "tokens_in_cost_per_1k": 1_250.0,
                    "tokens_out_cost_per_1k": 6_250.0,
                    "tool_call_cost": 1_000.0,
                },
                "benchmarks": {
                    "total_runs_7d": 1250,
                    "avg_latency_ms": 485.5,
                    "p95_latency_ms": 1200.0,
                    "avg_cost_usdc_per_run": 12.5,
                    "avg_tokens_per_sec": 45.2,
                },
            }
        ]
    data = {"models": models, "updated_at": "2026-04-16T12:00:00Z"}
    obj = MagicMock()
    obj.model_dump = lambda: dict(data)
    obj.models = models
    obj.updated_at = data["updated_at"]
    return obj


def make_pricing_response(
    base_cost_usdc: int = 500,
    tools: list[dict] | None = None,
) -> MagicMock:
    """Return a minimal BillingPricingResponse-like mock."""
    if tools is None:
        tools = [
            {
                "tool_name": "acme/weather",
                "price_usdc": 5000,
                "description": "Get the weather",
            }
        ]
    data = {"tools": tools, "base_cost_usdc": base_cost_usdc, "updated_at": "2026-04-16T12:00:00Z"}
    obj = MagicMock()
    obj.model_dump = lambda: dict(data)
    obj.tools = tools
    obj.base_cost_usdc = base_cost_usdc
    obj.updated_at = data["updated_at"]
    return obj


def make_credit_history_entries(
    count: int = 3,
) -> list[MagicMock]:
    """Return a list of CreditHistoryEntry-like mocks.

    Each mock has a ``model_dump`` method so the CLI can normalise it, matching
    the real SDK's ``list[CreditHistoryEntry]`` return type.
    """
    entries = []
    samples = [
        {"reason": "Subscription fee — acme/weather", "amount_usdc": 5000, "operation": "debit"},
        {"reason": "Top-up", "amount_usdc": 50_000_000, "operation": "topup"},
        {"reason": "Agent run — code review", "amount_usdc": 1250, "operation": "debit"},
    ]
    for i in range(count):
        base = samples[i % len(samples)]
        data = {
            "id": f"ch_{i}",
            "amount_usdc": base["amount_usdc"],
            "operation": base["operation"],
            "balance_usdc_after": 100_000_000 - base["amount_usdc"] * (i + 1),
            "reason": base["reason"],
            "created_at": f"2026-06-{10 - i:02d}T12:00:00Z",
        }
        obj = MagicMock()
        obj.model_dump = lambda d=data: dict(d)
        for k, v in data.items():
            setattr(obj, k, v)
        entries.append(obj)
    return entries
