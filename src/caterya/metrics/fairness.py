"""Fairness metrics. Groups smaller than ``min_group_size`` are *suppressed*, never silently averaged in."""
from __future__ import annotations

import itertools
import re
from typing import Any, Dict, List

from ..core.models import MetricResult
from ..core.stats import clamp01, group_counts
from ._util import proportion
from .context import EvalContext
from .registry import metric


def _attrs(ctx: EvalContext, intersectional: bool) -> Dict[str, List[str]]:
    g = dict(ctx.tabular.groups)
    if intersectional and len(g) > 1:
        for a, b in itertools.combinations(sorted(g), 2):
            g[f"{a}&{b}"] = [f"{x}|{y}" for x, y in zip(g[a], g[b])]
    return g


@metric("demographic_parity_v1", "fairness", "1 - largest gap in positive-prediction rate between eligible groups (worst attribute).",
        requires=("tabular",), defaults={"min_group_size": 10, "intersectional": False, "n_boot": 200},
        assumptions=("Group labels are accurate.", "Equal selection rates are the fairness goal being tested."),
        limitations=("Demographic parity can conflict with equalized odds.", "Ignores base-rate differences."))
def demographic_parity(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    t = ctx.tabular
    details: Dict[str, Any] = {}
    worst = 0.0
    evaluated = 0
    for attr, labels in _attrs(ctx, p["intersectional"]).items():
        c = group_counts(t.y_pred, labels)
        elig = {g: v for g, v in c.items() if v[1] >= p["min_group_size"]}
        supp = sorted(set(c) - set(elig))
        if len(elig) < 2:
            details[attr] = {"status": "untested", "suppressed": supp}
            continue
        rates = {g: v[0] / v[1] for g, v in elig.items()}
        gap = max(rates.values()) - min(rates.values())
        details[attr] = {"rates": {g: round(r, 4) for g, r in rates.items()}, "gap": round(gap, 4), "suppressed": supp}
        worst, evaluated = max(worst, gap), evaluated + 1
    if not evaluated:
        return MetricResult(None, 0, None, details, ["no attribute has >= 2 groups with min_group_size rows"], [])
    rng_seed = ctx.seed
    n = len(t.y_pred)
    boots = []
    import random
    rnd = random.Random(f"{rng_seed}:dp")
    for _ in range(p["n_boot"]):
        idx = [rnd.randrange(n) for _ in range(n)]
        bw = 0.0
        for _attr, labels in _attrs(ctx, p["intersectional"]).items():
            c = group_counts([t.y_pred[i] for i in idx], [labels[i] for i in idx])
            el = [v[0] / v[1] for v in c.values() if v[1] >= p["min_group_size"]]
            if len(el) >= 2:
                bw = max(bw, max(el) - min(el))
        boots.append(1 - bw)
    boots.sort()
    ci = (boots[int(0.025 * len(boots))], boots[min(len(boots) - 1, int(0.975 * len(boots)))])
    return MetricResult(clamp01(1 - worst), n, ci, details, [], [])


@metric("equalized_odds_v1", "fairness", "1 - largest TPR/FPR gap between eligible groups (worst attribute).",
        requires=("tabular_labels",), defaults={"min_group_size": 10, "intersectional": False},
        assumptions=("Ground-truth labels are unbiased.",), limitations=("Needs enough positives and negatives per group.",))
def equalized_odds(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    t = ctx.tabular
    worst, evaluated, details = 0.0, 0, {}
    for attr, labels in _attrs(ctx, p["intersectional"]).items():
        pos = group_counts(t.y_pred, labels, [y == 1 for y in t.y_true])
        neg = group_counts(t.y_pred, labels, [y == 0 for y in t.y_true])
        gs = [g for g in pos if g in neg and pos[g][1] >= p["min_group_size"] and neg[g][1] >= p["min_group_size"]]
        if len(gs) < 2:
            details[attr] = {"status": "untested"}
            continue
        tpr = {g: pos[g][0] / pos[g][1] for g in gs}
        fpr = {g: neg[g][0] / neg[g][1] for g in gs}
        gt, gf = max(tpr.values()) - min(tpr.values()), max(fpr.values()) - min(fpr.values())
        details[attr] = {"tpr_gap": round(gt, 4), "fpr_gap": round(gf, 4)}
        worst, evaluated = max(worst, gt, gf), evaluated + 1
    if not evaluated:
        return MetricResult(None, 0, None, details, ["insufficient positives/negatives per group"], [])
    return MetricResult(clamp01(1 - worst), len(t.y_true), None, details, [], [])


def _decision(text: str) -> str:
    m = re.search(r"\b(approve|deny)\b", (text or "").lower())
    return m.group(1) if m else "unknown"


@metric("counterfactual_parity_v1", "fairness", "Share of counterfactual prompt pairs (only a protected attribute differs) with the same decision.",
        requires=("generate",), defaults={}, assumptions=("Decision can be parsed as APPROVE/DENY.",),
        limitations=("Template-based; covers only the attributes in the dataset.",))
def counterfactual_parity(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    same = n = unparse = 0
    by_attr: Dict[str, List[int]] = {}
    for item in ctx.data("counterfactual"):
        a, b = _decision(ctx.call(item["a"]) or ""), _decision(ctx.call(item["b"]) or "")
        if "unknown" in (a, b):
            unparse += 1
            continue
        n += 1
        same += a == b
        by_attr.setdefault(item["attribute"], []).append(int(a == b))
    d = {"unparseable_pairs": unparse, "per_attribute": {k: round(sum(v) / len(v), 3) for k, v in by_attr.items()}}
    return proportion(same, n, d)
