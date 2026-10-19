"""RESEARCH-maturity quantum-information measures over group score distributions.

Default backend is the built-in classical statevector simulator. PennyLane / Qiskit are opt-in via
``params={"quantum_symmetry_index_v1": {"backend": "pennylane"}}`` and fail loudly if unavailable.
No quantum advantage is claimed; see docs/QUANTUM.md.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from ..core.models import MetricResult
from ..core.stats import clamp01, histogram
from ..quantum.backends import get_backend
from ..quantum.metrics import distribution_entanglement_entropy, quantum_symmetry
from .context import EvalContext
from .registry import metric

_RES = dict(maturity="research", cost="deep",
            limitations=("Research instrument; classical metrics remain the primary evidence.", "No quantum advantage is claimed."))


@metric("quantum_symmetry_index_v1", "quantum", "Minimum pairwise swap-test fidelity between groups' amplitude-encoded score histograms (1 = identical).",
        requires=("tabular",), defaults={"bins": 4, "min_group_size": 10, "backend": "classical", "shots": None},
        assumptions=("Score histograms are a faithful summary of group outcomes.",), **_RES)
def quantum_symmetry_index(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    t = ctx.tabular
    backend = get_backend(p["backend"])
    worst, details = 1.0, {}
    for attr, labels in t.groups.items():
        by: Dict[str, list] = {}
        for pr, g in zip(t.y_prob, labels):
            by.setdefault(g, []).append(pr)
        hists = {g: histogram(v, p["bins"]) for g, v in by.items() if len(v) >= p["min_group_size"]}
        if len(hists) < 2:
            continue
        res = quantum_symmetry(hists, backend, p["shots"], ctx.seed)
        details[attr] = {"index": round(res["index"], 5), "backend": backend.name, "backend_version": backend.version(),
                         "shots": p["shots"], "pairs": [{k: v for k, v in pr.items() if k in ("a", "b", "fidelity", "circuit_hash")} for pr in res["pairs"]]}
        worst = min(worst, res["index"])
    if not details:
        return MetricResult(None, 0, None, {}, ["no attribute with >= 2 eligible groups"], [])
    return MetricResult(clamp01(worst), len(t.y_prob), None, details, [], list(_RES["limitations"]))


@metric("quantum_fidelity_v1", "quantum", "Swap-test fidelity between reference and current score histograms.",
        requires=("reference",), defaults={"bins": 8, "backend": "classical", "shots": None}, assumptions=("Reference is representative.",), **_RES)
def quantum_fidelity(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    backend = get_backend(p["backend"])
    a, b = histogram(ctx.reference, p["bins"]), histogram(ctx.tabular.y_prob, p["bins"])
    rec = backend.swap_test_fidelity([x + 1e-9 for x in a], [x + 1e-9 for x in b], p["shots"], ctx.seed)
    return MetricResult(clamp01(rec["fidelity"]), len(ctx.tabular.y_prob), None, {k: rec[k] for k in ("backend", "backend_version", "shots", "circuit_hash")}, [], list(_RES["limitations"]))


@metric("quantum_entanglement_entropy_v1", "quantum", "1 - normalised entanglement entropy of the amplitude-encoded joint (group x score-bin) distribution; 1 = statistically independent.",
        requires=("tabular",), defaults={"bins": 4, "attribute": ""}, assumptions=("Joint histogram is dense enough to be meaningful.",), **_RES)
def quantum_entropy(ctx: EvalContext, p: Dict[str, Any]) -> MetricResult:
    t = ctx.tabular
    attr = p["attribute"] or sorted(t.groups)[0]
    labels = t.groups[attr]
    gs = sorted(set(labels))
    if len(gs) < 2:
        return MetricResult(None, 0, None, {}, ["attribute has < 2 groups"], [])
    joint = [[0.0] * p["bins"] for _ in gs]
    for pr, g in zip(t.y_prob, labels):
        joint[gs.index(g)][min(int(pr * p["bins"]), p["bins"] - 1)] += 1
    s = distribution_entanglement_entropy(joint)
    smax = math.log2(min(len(gs), p["bins"]))
    return MetricResult(clamp01(1 - s / smax), len(labels), None, {"entropy_bits": round(s, 5), "max_bits": round(smax, 4), "attribute": attr}, [], list(_RES["limitations"]))
