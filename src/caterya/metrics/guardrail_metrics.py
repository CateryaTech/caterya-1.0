"""Metrics over guardrail / swarm events recorded by ``caterya.guardrails``."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict

from ..core.models import MetricResult
from ..core.stats import mean
from ._util import proportion
from .context import EvalContext
from .registry import metric


@metric("guardrail_recommendation_v1", "guardrail", "Share of guardrail events that completed (not UNTESTED) and were sealed as Evidence.",
        requires=("events",), defaults={}, assumptions=("Events come from CATERYAGuardrail.",), limitations=("Measures process completeness, not guardrail accuracy.",))
def guardrail_recommendation(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    ev = [e for e in ctx.events if e.get("kind") == "guardrail"]
    ok = sum(1 for e in ev if e.get("decision") != "UNTESTED" and e.get("evidence_id"))
    return proportion(ok, len(ev), {"decisions": dict(Counter(e.get("decision") for e in ev))})


@metric("swarm_consensus_v1", "guardrail", "Mean agreement ratio among EthicsSwarm voters.",
        requires=("events",), defaults={}, assumptions=("Voters are independent enough to be informative.",), limitations=("Agreement is not correctness.",))
def swarm_consensus(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    ev = [e for e in ctx.events if e.get("kind") == "swarm"]
    if not ev:
        return MetricResult(None, 0, None, {}, ["no swarm events"], [])
    return MetricResult(mean([e["agreement"] for e in ev]), len(ev), None, {}, [], [])
