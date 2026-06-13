"""Local cost estimation for agent runs — no network inference, no credit deduction.

Uses three existing SDK data sources to compute a forward-looking estimate:

1. ``client.get_pricing()`` — per-tool price book (``base_cost_usdc`` + tool list)
2. ``client.get_model_benchmarks()`` — per‑1k-token rates for the active model
3. ``client.get_llm_config()`` — current model, provider, ``max_tokens``

The estimate is a **heuristic** — actual cost may differ based on exact tokenization
and which tools are actually invoked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from teardrop import ToolPolicy


TOKEN_EST_CHARS_PER_TOKEN = 4
_EST_TOOL_CALLS = 1  # assume at least one tool call


@dataclass
class CostEstimate:
    """Breakdown of an estimated run cost."""

    input_tokens_est: int
    output_tokens_est: int
    tool_calls_est: int

    model_tokens_in_cost_usdc: int = 0  # atomic USDC (6 decimals)
    model_tokens_out_cost_usdc: int = 0
    tool_call_cost_usdc: int = 0
    tool_usage_cost_usdc: int = 0
    base_cost_usdc: int = 0
    total_usdc: int = 0
    currency: str = "USDC"

    model_provider: str = ""
    model_name: str = ""

    disclaimer: str = field(
        default="Estimate only — based on current pricing and config. Actual cost will differ."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_run_cost(
    message: str,
    *,
    context: dict[str, Any] | None = None,
    tool_policy: ToolPolicy | None = None,
    base_url: str | None = None,
) -> CostEstimate:
    """Compute a local, no‑network cost estimate for an agent run.

    **No inference is triggered. No credits are deducted.**  The estimate
    is assembled from pricing tables, benchmark rates, and the org's LLM
    config — all read‑only data.

    Parameters
    ----------
    message:
        The user message that would be sent to the agent.
    context:
        Optional JSON‑serialisable context dict (counted in input tokens).
    tool_policy:
        Optional tool policy (used to exclude tools from the tool‑cost estimate).
    base_url:
        Optional override for the API base URL.

    Returns
    -------
    CostEstimate
        A dataclass with a full breakdown.
    """
    import asyncio

    from teardrop_cli import config

    client = config.get_client(base_url)

    async def _fetch() -> CostEstimate:
        try:
            pricing, benchmarks, llm_cfg = await asyncio.gather(
                client.get_pricing(),
                client.get_model_benchmarks(),
                client.get_llm_config(),
            )
        finally:
            await client.close()

        return _compute(
            message=message,
            context=context,
            tool_policy=tool_policy,
            pricing=_normalise_pricing(pricing),
            benchmarks=_normalise_benchmarks(benchmarks),
            llm_cfg=_normalise_llm_cfg(llm_cfg),
        )

    return asyncio.run(_fetch())


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def _compute(
    *,
    message: str,
    context: dict[str, Any] | None,
    tool_policy: ToolPolicy | None,
    pricing: dict[str, Any],
    benchmarks: list[dict[str, Any]],
    llm_cfg: dict[str, Any],
) -> CostEstimate:
    provider = llm_cfg.get("provider", "unknown")
    model_name = llm_cfg.get("model", "unknown")
    max_tokens = llm_cfg.get("max_tokens", 256) or 256

    # --- Token estimation ---
    context_str = json.dumps(context or {}, separators=(",", ":"))
    input_chars = len(message) + len(context_str)
    input_tokens = max(1, input_chars // TOKEN_EST_CHARS_PER_TOKEN)
    output_tokens = max(1, int(max_tokens))

    # --- Tool call estimation ---
    excluded: set[str] = set()
    if tool_policy is not None and hasattr(tool_policy, "exclude_names"):
        excluded = set(tool_policy.exclude_names or [])
    pricing_tools = pricing.get("tools", [])
    usable_tools = [t for t in pricing_tools if t.get("tool_name") not in excluded]
    tool_calls = max(_EST_TOOL_CALLS, len(usable_tools))

    # --- Model per‑token rates ---
    model_rates = _find_model_rates(provider, model_name, benchmarks)

    in_rate = model_rates.get("tokens_in_cost_per_1k", 0.0)
    out_rate = model_rates.get("tokens_out_cost_per_1k", 0.0)
    tool_call_rate = model_rates.get("tool_call_cost", 0.0)

    # Benchmark rates are already in atomic USDC per 1k tokens (and per call).
    # No "convert to atomic" step is needed — the product is already atomic.
    model_in_cost = max(0, round(in_rate * input_tokens / 1000))
    model_out_cost = max(0, round(out_rate * output_tokens / 1000))
    tool_call_flat = max(0, round(tool_call_rate * tool_calls))

    # --- Per‑tool usage costs ---
    tool_usage = sum(
        t.get("price_usdc", 0) for t in usable_tools
    )
    base_cost = pricing.get("base_cost_usdc", 0)

    total = model_in_cost + model_out_cost + tool_call_flat + tool_usage + base_cost

    return CostEstimate(
        input_tokens_est=input_tokens,
        output_tokens_est=output_tokens,
        tool_calls_est=tool_calls,
        model_tokens_in_cost_usdc=model_in_cost,
        model_tokens_out_cost_usdc=model_out_cost,
        tool_call_cost_usdc=tool_call_flat,
        tool_usage_cost_usdc=tool_usage,
        base_cost_usdc=base_cost,
        total_usdc=total,
        currency="USDC",
        model_provider=provider,
        model_name=model_name,
    )


# ---------------------------------------------------------------------------
# Normalisation helpers (handles both SDK model objects and plain dicts)
# ---------------------------------------------------------------------------


def _normalise_pricing(raw: Any) -> dict[str, Any]:
    """Return a plain dict from a BillingPricingResponse-like object."""
    if hasattr(raw, "model_dump"):
        return raw.model_dump()
    if isinstance(raw, dict):
        return raw
    # Duck-type fallback
    return {
        "base_cost_usdc": getattr(raw, "base_cost_usdc", 0),
        "tools": [
            {
                "tool_name": getattr(t, "tool_name", ""),
                "price_usdc": getattr(t, "price_usdc", 0),
                "description": getattr(t, "description", ""),
            }
            for t in (getattr(raw, "tools", []) or [])
        ],
    }


def _normalise_benchmarks(raw: Any) -> list[dict[str, Any]]:
    """Return a list of plain dicts from a ModelBenchmarksResponse-like object."""
    items = raw.models if hasattr(raw, "models") else (raw if isinstance(raw, list) else [])
    result = []
    for m in items:
        if hasattr(m, "model_dump"):
            result.append(m.model_dump())
        elif isinstance(m, dict):
            result.append(m)
        else:
            result.append(
                {
                    "provider": getattr(m, "provider", ""),
                    "model": getattr(m, "model", ""),
                    "pricing": {
                        "tokens_in_cost_per_1k": getattr(
                            getattr(m, "pricing", None), "tokens_in_cost_per_1k", 0.0
                        ),
                        "tokens_out_cost_per_1k": getattr(
                            getattr(m, "pricing", None), "tokens_out_cost_per_1k", 0.0
                        ),
                        "tool_call_cost": getattr(
                            getattr(m, "pricing", None), "tool_call_cost", 0.0
                        ),
                    },
                }
            )
    return result


def _normalise_llm_cfg(raw: Any) -> dict[str, Any]:
    """Return a plain dict from an OrgLlmConfig-like object."""
    if hasattr(raw, "model_dump"):
        return raw.model_dump()
    if isinstance(raw, dict):
        return raw
    return {
        "provider": getattr(raw, "provider", "unknown"),
        "model": getattr(raw, "model", "unknown"),
        "max_tokens": getattr(raw, "max_tokens", 256),
    }


def _find_model_rates(
    provider: str,
    model: str,
    benchmarks: list[dict[str, Any]],
) -> dict[str, float]:
    """Find matching model pricing rates from the benchmarks list."""
    # Exact match first
    for m in benchmarks:
        mp = m.get("pricing", {})
        if m.get("provider") == provider and m.get("model") == model:
            return mp if isinstance(mp, dict) else {}
    # Fallback: match on provider only
    for m in benchmarks:
        mp = m.get("pricing", {})
        if m.get("provider") == provider:
            return mp if isinstance(mp, dict) else {}
    return {}