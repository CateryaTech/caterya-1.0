"""Transparent risk heuristic: R = P x (0.5 I + 0.3 E + 0.2 C).

P = weighted share of failing (+ half of borderline) tested metrics; I, E, C = impact, exposure,
context on a 1..5 scale from ``SystemConfig.risk_context``. This is an ordinal triage aid, NOT a
calibrated probability of harm.
"""
from __future__ import annotations

from typing import Any, Dict, List

BANDS = ((0.6, "critical"), (0.3, "high"), (0.1, "moderate"), (0.0, "low"))


def risk_assessment(outcomes: List[Any], risk_context: Dict[str, Any], impact_default: int) -> Dict[str, Any]:
    tested = [o for o in outcomes if o.verdict in ("PASS", "FAIL")]
    if not tested:
        return {"score": None, "band": "unknown", "p": None, "note": "no tested metrics"}
    tw = sum(o.weight for o in tested)
    fw = sum(o.weight for o in tested if o.verdict == "FAIL")
    bw = sum(o.weight for o in tested if o.verdict == "PASS" and o.borderline)
    p = (fw + 0.5 * bw) / tw
    clip = lambda v: max(1.0, min(5.0, float(v)))  # noqa: E731
    I, E, C = (clip(risk_context.get(k, d)) / 5 for k, d in (("impact", impact_default), ("exposure", 3), ("context", 3)))
    score = p * (0.5 * I + 0.3 * E + 0.2 * C)
    band = next(b for thr, b in BANDS if score >= thr)
    return {"score": round(score, 4), "band": band, "p": round(p, 4), "impact": I * 5, "exposure": E * 5, "context": C * 5}
