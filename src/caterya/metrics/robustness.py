"""Robustness metrics: input perturbation, behavioural divergence rate, noise sensitivity."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from ..core.models import MetricResult
from ..core.stats import clamp01, norm_edit_distance
from ._util import proportion
from .context import EvalContext
from .registry import metric


def perturb(text: str, rng: random.Random, kind: str, k: int = 1) -> str:
    if kind == "case":
        return "".join(c.upper() if rng.random() < 0.5 else c.lower() for c in text)
    if kind == "space":
        return "  ".join(text.split(" ")) + " "
    if kind == "punct":
        return text.replace("?", "").replace(".", "")
    if kind == "typo":
        chars = list(text)
        idx = [i for i in range(len(chars) - 1) if chars[i].isalpha() and chars[i + 1].isalpha()]
        for i in rng.sample(idx, min(k, len(idx))):
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
        return "".join(chars)
    raise ValueError(kind)


@metric("perturbation_robustness_v1", "robustness", "Among prompts answered correctly when clean, share still answered correctly after case/whitespace/punctuation/typo perturbation.",
        requires=("generate",), defaults={"kinds": ["case", "space", "punct", "typo"]},
        assumptions=("Correctness = expected substring present.",), limitations=("Small built-in QA set; supply your own for real assessments.",))
def perturbation_robustness(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    rng = ctx.rng("perturb")
    ok = n = base_ok = 0
    for item in ctx.data("qa"):
        clean = (ctx.call(item["q"]) or "").lower()
        if item["a"] not in clean:
            continue
        base_ok += 1
        for kind in p["kinds"]:
            out = (ctx.call(perturb(item["q"], rng, kind)) or "").lower()
            n += 1
            ok += item["a"] in out
    return proportion(ok, n, {"clean_correct_items": base_ok})


@metric("behavioral_lyapunov_v1", "robustness", "Stability score 1/(1+max(0,lambda)) where lambda is the growth rate of output divergence with input edit magnitude.",
        requires=("generate",), defaults={"magnitudes": [1, 2, 4, 8], "trials": 2}, maturity="research",
        assumptions=("Divergence ~ exp(lambda * magnitude) over the tested range.",),
        limitations=("Research metric: a heuristic analogue of a Lyapunov exponent, not a dynamical-systems estimate.",))
def behavioral_lyapunov(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    rng = ctx.rng("lyap")
    items = ctx.data("qa")[:6]
    mags = p["magnitudes"]
    ds: List[float] = []
    for m in mags:
        tot = cnt = 0
        for it in items:
            base = ctx.call(it["q"]) or ""
            for _ in range(p["trials"]):
                out = ctx.call(perturb(it["q"], rng, "typo", k=m)) or ""
                tot += norm_edit_distance(base, out)
                cnt += 1
        ds.append(tot / cnt)
    ys = [math.log(d + 0.01) for d in ds]
    xm, ym = sum(mags) / len(mags), sum(ys) / len(ys)
    lam = sum((x - xm) * (y - ym) for x, y in zip(mags, ys)) / sum((x - xm) ** 2 for x in mags)
    return MetricResult(1 / (1 + max(0.0, lam)), len(items) * p["trials"] * len(mags), None,
                        {"lambda": round(lam, 5), "divergence_by_magnitude": {str(m): round(d, 4) for m, d in zip(mags, ds)}}, [], [])


@metric("gaussian_noise_accuracy_v1", "robustness", "Accuracy under Gaussian feature noise relative to clean accuracy (capped at 1).",
        requires=("predict", "labels", "features"), defaults={"sigma": 0.3, "threshold": 0.5, "max_rows": 500},
        assumptions=("Numeric features; noise scaled by each feature's std.",), limitations=("Random noise is not an adversarial attack.",))
def gaussian_noise_accuracy(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    t = ctx.tabular
    rows, y = t.X[: p["max_rows"]], t.y_true[: p["max_rows"]]
    feats = [k for k, v in rows[0].items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    std = {f: (sum((r[f] - sum(q[f] for q in rows) / len(rows)) ** 2 for r in rows) / len(rows)) ** 0.5 or 1.0 for f in feats}
    rng = ctx.rng("noise")
    clean = ctx.adapter.predict(rows)
    noisy = ctx.adapter.predict([{**r, **{f: r[f] + rng.gauss(0, p["sigma"] * std[f]) for f in feats}} for r in rows])
    acc = lambda pr: sum(int(a >= p["threshold"]) == b for a, b in zip(pr, y)) / len(y)  # noqa: E731
    a0, a1 = acc(clean), acc(noisy)
    return MetricResult(clamp01(a1 / a0) if a0 > 0 else 0.0, len(y), None, {"clean_accuracy": round(a0, 4), "noisy_accuracy": round(a1, 4), "sigma": p["sigma"]}, [], [])
