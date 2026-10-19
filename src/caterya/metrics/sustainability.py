"""Sustainability estimate (phase 2: needs measured token usage). Estimate only — never a measurement."""
from __future__ import annotations

from typing import Any, Dict

from ..core.models import MetricResult
from ..core.stats import clamp01
from .context import EvalContext
from .registry import metric


@metric("sustainability_estimate_v1", "sustainability", "1 - estimated evaluation-run energy / energy budget, from token counts x a configurable Wh-per-1k-token factor.",
        requires=("usage",), defaults={"wh_per_1k_tokens": 0.3, "budget_wh": 5.0}, maturity="research",
        assumptions=("wh_per_1k_tokens is a PLACEHOLDER; set it from your provider/hardware data.", "Tokens approximated as chars/4."),
        limitations=("Order-of-magnitude estimate; excludes training, embodied carbon and idle power.",))
def sustainability(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    toks = ctx.stats["tokens_in"] + ctx.stats["tokens_out"]
    wh = toks / 1000 * p["wh_per_1k_tokens"]
    return MetricResult(clamp01(1 - wh / p["budget_wh"]), ctx.stats["calls"], None,
                        {"estimate": True, "tokens": toks, "energy_wh": round(wh, 5), "wh_per_1k_tokens": p["wh_per_1k_tokens"]}, [],
                        ["energy is an estimate from a configurable constant"])
