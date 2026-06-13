"""In-package templates for ``teardrop tools init``."""

from __future__ import annotations

# Complete starter template matching CreateOrgToolRequest schema.
# All fields are explicit --- nullable fields use None so they appear as
# ``null`` in the output JSON and users discover them early.
_BASE_TEMPLATE = {
    "name": "{name}",
    "description": "Short one-line summary of what this tool does.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Example input field. Replace with your real schema.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": "Example output field. Replace with your real schema.",
            }
        },
        "required": ["result"],
        "additionalProperties": True,
    },
    "webhook_url": "https://example.com/your-webhook-endpoint",
    "webhook_method": "GET",
    "auth_header_name": None,
    "auth_header_value": None,
    "timeout_seconds": 10,
    "publish_as_mcp": False,
    "marketplace_description": None,
    "category": "",
    "base_price_usdc": 0,
}


def render_tool_template(name: str, *, with_marketplace: bool = False) -> dict:
    """Return a dict suitable for ``json.dumps`` describing a starter tool."""
    data = {**_BASE_TEMPLATE, "name": name}
    if with_marketplace:
        data["publish_as_mcp"] = True
        data["marketplace_description"] = (
            "One-line marketplace pitch (max 200 characters)."
        )
    return data
