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
    chunk.type = "text_msg_content"
    chunk.data = {"content": text}
    events.append(chunk)

    # usage summary
    usage = MagicMock()
    usage.type = "usage_summary"
    usage.data = {"input_tokens": 5, "output_tokens": 10, "total_cost_usd": 0.0001}
    events.append(usage)

    # done
    done = MagicMock()
    done.type = "done"
    done.data = None
    events.append(done)

    return events
