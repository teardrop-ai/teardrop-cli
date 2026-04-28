"""In-package templates for ``teardrop tools init``."""

from __future__ import annotations

# Minimal, valid CreateOrgToolRequest with placeholders flagged clearly.
_BASE_TEMPLATE = {
    "name": "{name}",
    "description": "TODO: Describe what this tool does in one sentence.",
    "webhook_url": "https://example.com/your-webhook-endpoint",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Example input field. Replace with your real schema.",
            }
        },
        "required": ["query"],
    },
    "timeout_seconds": 10,
    "publish_as_mcp": False,
}

# Marketplace-extension fields. Surfaced when --with-marketplace is passed.
_MARKETPLACE_EXTENSION = {
    "publish_as_mcp": True,
    "marketplace_description": "TODO: One-line marketplace pitch (≤ 200 chars).",
    "base_price_usdc": 1000,  # $0.001 per call (atomic units, 6 decimals)
}


def render_tool_template(name: str, *, with_marketplace: bool = False) -> dict:
    """Return a dict suitable for ``json.dumps`` describing a starter tool."""
    data = {**_BASE_TEMPLATE, "name": name}
    if with_marketplace:
        data.update(_MARKETPLACE_EXTENSION)
    return data
