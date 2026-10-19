"""Reliability: consistency, calibration, context retention, availability, drift."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict

from ..core.models import MetricResult
from ..core.stats import clamp01, histogram, mean
from ._util import norm_text, proportion
from .context import EvalContext
from .registry import metric


@metric("consistency_v1", "reliability", "Mean share of repeated answers equal to the modal answer for the same prompt.",
        requires=("generate",), defaults={"repeats": 5, "prompts": 6}, assumptions=("Temperature/decoding settings are fixed by the adapter.",),
        limitations=("Lexical equality after normalisation.",))
def consistency(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    shares = []
    for it in ctx.data("qa")[: p["prompts"]]:
        outs = [norm_text(ctx.call(it["q"], seed=i) or "") for i in range(p["repeats"])]
        shares.append(Counter(outs).most_common(1)[0][1] / len(outs))
    return MetricResult(mean(shares), len(shares) * p["repeats"], None, {"min_share": round(min(shares), 3)}, [], [])


@metric("calibration_ece_v1", "reliability", "1 - expected calibration error of predicted probabilities.",
        requires=("tabular_labels",), defaults={"bins": 10}, assumptions=("y_prob are probabilities of the positive class.",),
        limitations=("ECE is sensitive to binning and small samples.",))
def calibration_ece(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    t, B = ctx.tabular, p["bins"]
    n = len(t.y_true)
    ece = 0.0
    for b in range(B):
        idx = [i for i, pr in enumerate(t.y_prob) if min(int(pr * B), B - 1) == b]
        if idx:
            conf = sum(t.y_prob[i] for i in idx) / len(idx)
            acc = sum(t.y_true[i] for i in idx) / len(idx)
            ece += len(idx) / n * abs(conf - acc)
    return MetricResult(clamp01(1 - ece), n, None, {"ece": round(ece, 4)}, [], [])


@metric("context_retention_v1", "reliability", "Share of multi-turn probes where a fact stated earlier is recalled later.",
        requires=("generate",), defaults={}, assumptions=("Context is passed as a flat transcript.",), limitations=("Short contexts only.",))
def context_retention(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    ok = n = 0
    for it in ctx.data("retention"):
        out = ctx.call("\n".join([it["fact"], *it["filler"], it["question"]]))
        n += 1
        ok += out is not None and it["expect"] in out.lower()
    return proportion(ok, n, {})


@metric("availability_v1", "reliability", "Share of benign calls that return a non-empty answer without error.",
        requires=("generate",), defaults={"calls": 20}, assumptions=("Measured from the evaluator's vantage point only.",),
        limitations=("A short burst is not an SLA measurement.",))
def availability(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    ok = sum(1 for _ in range(p["calls"]) if (ctx.call("What is the capital of France?") or "").strip())
    return proportion(ok, p["calls"], {"errors": p["calls"] - ok})


def psi(expected, actual, bins: int = 10) -> float:
    e = [c / len(expected) + 1e-4 for c in histogram(expected, bins)]
    a = [c / len(actual) + 1e-4 for c in histogram(actual, bins)]
    import math
    return sum((ai - ei) * math.log(ai / ei) for ei, ai in zip(e, a))


@metric("distribution_drift_psi_v1", "reliability", "max(0, 1 - PSI/0.25) between a reference and the current score distribution (PSI >= 0.25 = major shift).",
        requires=("reference",), defaults={"bins": 10}, assumptions=("Reference reflects the validated operating distribution.",),
        limitations=("PSI conventions (0.1 / 0.25) are rules of thumb.",))
def drift_psi(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    v = psi(ctx.reference, ctx.tabular.y_prob, p["bins"])
    return MetricResult(clamp01(1 - v / 0.25), len(ctx.tabular.y_prob), None, {"psi": round(v, 5)}, [], [])
