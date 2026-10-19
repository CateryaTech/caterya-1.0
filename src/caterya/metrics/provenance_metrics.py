"""Metrics about the assurance process itself (phase 2: need the evidence gathered so far)."""
from __future__ import annotations

from typing import Any, Dict

from ..core.models import MetricResult
from ..core.stats import mean
from ..regulatory.mapping import FRAMEWORKS, coverage
from .context import EvalContext
from .registry import metric


@metric("provenance_completeness_v1", "provenance", "Mean of: system description completeness, dataset binding, chain integrity, asymmetric signatures.",
        requires=("evidence",), defaults={}, assumptions=("Evaluated over the evidence produced so far in this run.",),
        limitations=("Checks presence/integrity, not the truthfulness of the declared fields.",))
def provenance_completeness(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    s = ctx.system
    fields = [s.name, s.version, s.owner, s.intended_use, s.description, s.model_id or s.provider]
    sys_c = sum(bool(str(f).strip()) for f in fields) / len(fields)
    items = ctx.evidence["items"]
    ds_c = (sum(1 for e in items if e.dataset_hash) / len(items)) if items else 0.0
    chain_c = 1.0 if ctx.evidence["chain_ok"] else 0.0
    sig_c = 1.0 if ctx.evidence["asymmetric"] else 0.0
    comps = {"system_fields": sys_c, "dataset_binding": ds_c, "chain_integrity": chain_c, "asymmetric_signatures": sig_c}
    return MetricResult(mean(list(comps.values())), len(items), None, {k: round(v, 3) for k, v in comps.items()}, [], [])


@metric("regulatory_mapping_coverage_v1", "provenance", "Mean share of framework themes with >= 1 tested mapped metric. COVERAGE IS NOT CONFORMITY.",
        requires=("evidence",), defaults={"frameworks": sorted(FRAMEWORKS)}, assumptions=("Thematic, indicative mapping (see docs/REGULATORY.md).",),
        limitations=("Not legal advice; says nothing about sufficiency of the evidence.",))
def regulatory_coverage(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    tested = ctx.evidence["tested"]
    per = {f: coverage(f, tested) for f in p["frameworks"]}
    return MetricResult(mean([v["coverage"] for v in per.values()]), len(per),
                        None, {f: {"coverage": round(v["coverage"], 3), "gaps": v["gaps"], "status": v["status"]} for f, v in per.items()}, [],
                        ["coverage is not conformity"])
