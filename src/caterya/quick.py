"""One-call convenience facade for prediction-level data.

``CATERYAEvaluator.evaluate(model_output=..., ground_truth=..., sensitive_attributes=...)`` runs the full engine
underneath, so the result is signed Evidence + a CAR, with the COS attached as a *derived* number. Untested pillars
are reported as gaps (not scored 0), groups below ``min_group_size`` are suppressed, and COS never implies an
assurance level. Use ``AssuranceEngine`` directly for the full feature set.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .assurance.engine import AssuranceEngine, AssuranceReport
from .core.models import SystemConfig
from .metrics.context import TabularData


@dataclass
class CATERYAResult:
    cos: Optional[float]
    grade: Optional[str]
    pillar_scores: Dict[str, Optional[float]]
    gaps: List[Dict[str, Any]]
    report: AssuranceReport

    def to_dict(self) -> Dict[str, Any]:
        return {"cos": self.cos, "grade": self.grade, "pillar_scores": self.pillar_scores, "gaps": self.gaps,
                "recommendation": self.report.recommendation, "evidence_ids": self.report.evidence_ids, "car_evidence": self.report.car_evidence.evidence_id}


class CATERYAEvaluator:
    def __init__(self, system_name: str = "quick-evaluator", min_group_size: int = 10, profile: str = "CATERYA-TABULAR"):
        self.engine = AssuranceEngine(SystemConfig(system_name, "0", description="evaluated through the one-call CATERYAEvaluator facade"), profile=profile)
        self.min_group_size, self.profile = min_group_size, profile

    def evaluate_sync(self, model_output: Sequence[float], ground_truth: Optional[Sequence[int]] = None,
                      sensitive_attributes: Optional[Dict[str, Sequence[str]]] = None, threshold: float = 0.5) -> CATERYAResult:
        t = TabularData(y_true=list(ground_truth) if ground_truth is not None else None, y_prob=[float(x) for x in model_output],
                        groups={k: list(v) for k, v in (sensitive_attributes or {}).items()}, threshold=threshold)
        params = {m: {"min_group_size": self.min_group_size} for m in ("demographic_parity_v1", "equalized_odds_v1", "entropy_dispersion_v1")}
        rep = self.engine.evaluate(profile=self.profile, tabular=t, params=params)
        ps = rep.cos["pillars"]
        return CATERYAResult(rep.cos["cos"], rep.cos["grade"], {k: v["score"] for k, v in ps.items()}, rep.gaps, rep)

    async def evaluate(self, *a: Any, **kw: Any) -> CATERYAResult:
        return self.evaluate_sync(*a, **kw)
