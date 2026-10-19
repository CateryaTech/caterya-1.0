"""Golden-Triangle measures (Entropy x Symmetry x Information) re-expressed as ordinary, testable metrics."""
from __future__ import annotations

import itertools
from typing import Any, Dict

from ..core.models import MetricResult
from ..core.stats import clamp01, histogram, js_divergence, normalise
from ._util import norm_text, proportion
from .context import EvalContext
from .registry import metric


@metric("entropy_dispersion_v1", "golden_triangle", "1 - largest Jensen-Shannon divergence (bits) between groups' score distributions.",
        requires=("tabular",), defaults={"bins": 10, "min_group_size": 10},
        assumptions=("y_prob are comparable scores in [0,1].",), limitations=("Histogram-based; sensitive to bin count on small groups.",))
def entropy_dispersion(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    t = ctx.tabular
    worst, ev, details = 0.0, 0, {}
    for attr, labels in t.groups.items():
        buckets: Dict[str, list] = {}
        for pr, g in zip(t.y_prob, labels):
            buckets.setdefault(g, []).append(pr)
        buckets = {g: v for g, v in buckets.items() if len(v) >= p["min_group_size"]}
        if len(buckets) < 2:
            continue
        hists = {g: normalise([c + 1e-9 for c in histogram(v, p["bins"])]) for g, v in buckets.items()}
        js = max(js_divergence(hists[a], hists[b]) for a, b in itertools.combinations(sorted(hists), 2))
        details[attr] = {"max_js_bits": round(js, 4)}
        worst, ev = max(worst, js), ev + 1
    if not ev:
        return MetricResult(None, 0, None, details, ["no attribute with >= 2 eligible groups"], [])
    return MetricResult(clamp01(1 - worst), len(t.y_prob), None, details, [], [])


@metric("invariance_symmetry_v1", "golden_triangle", "Share of question groups whose answers are identical across paraphrases (output symmetry).",
        requires=("generate",), defaults={}, assumptions=("Paraphrases are meaning-preserving.",),
        limitations=("Measures consistency, not correctness.",))
def invariance_symmetry(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    ok = n = 0
    for grp in ctx.data("paraphrases"):
        outs = [norm_text(ctx.call(q) or "") for q in grp["qs"]]
        n += 1
        ok += len(set(outs)) == 1 and outs[0] != ""
    return proportion(ok, n, {})


@metric("explanation_faithfulness_v1", "golden_triangle", "Share of rows where deleting the top-attributed feature moves the prediction at least as much as the average other feature.",
        requires=("predict", "explain", "features"), defaults={"max_rows": 50},
        assumptions=("Features are numeric; deletion = replace by the column mean.",), limitations=("Deletion tests are a proxy, not proof of causal faithfulness.",))
def explanation_faithfulness(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    X = ctx.tabular.X[: p["max_rows"]]
    feats = [k for k in X[0] if isinstance(X[0][k], (int, float)) and k in ctx.adapter.explain(X[0])]
    if len(feats) < 2:
        return MetricResult(None, 0, None, {}, ["need >= 2 explained numeric features"], [])
    means = {f: sum(float(r[f]) for r in ctx.tabular.X) / len(ctx.tabular.X) for f in feats}
    ok = n = 0
    for row in X:
        attr = ctx.adapter.explain(row)
        top = max(feats, key=lambda f: abs(attr[f]))
        base = ctx.adapter.predict([row])[0]
        eff = {}
        for f in feats:
            r2 = dict(row)
            r2[f] = means[f]
            eff[f] = abs(base - ctx.adapter.predict([r2])[0])
        others = [eff[f] for f in feats if f != top]
        n += 1
        ok += eff[top] >= sum(others) / len(others)
    return proportion(ok, n, {})
