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


def make_sse_events(text: str) -> list[MagicMock]:
    """Build a minimal sequence of SSE events for a successful agent run."""
    events = []

    # text chunk
    chunk = MagicMock()
    chunk.type = "TEXT_MESSAGE_CONTENT"
    chunk.data = {"delta": [{"text": text, "type": "text", "index": 0}]}
    events.append(chunk)

    # usage summary
    usage = MagicMock()
    usage.type = "USAGE_SUMMARY"
    usage.data = {"input_tokens": 5, "output_tokens": 10, "total_cost_usd": 0.0001}
    events.append(usage)

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
                    "tokens_in_cost_per_1k": 0.08,
                    "tokens_out_cost_per_1k": 0.24,
                    "tool_call_cost": 0.0,
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
