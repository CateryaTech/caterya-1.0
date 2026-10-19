"""Pillar views and the derived COS index.

The four pillars group metrics for *reading*. They are
a VIEW: the source of truth is always the signed Evidence. COS is a derived index over *tested*
fairness/interpretability/robustness/accountability metrics only — it deliberately ignores safety,
security and privacy probes and can never be used as an assurance level.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

PILLARS: Dict[str, Dict[str, Any]] = {
    "fairness_symmetry": {"label": "Fairness & Symmetry", "metrics": [
        "demographic_parity_v1", "equalized_odds_v1", "counterfactual_parity_v1", "invariance_symmetry_v1", "quantum_symmetry_index_v1"]},
    "interpretability_information": {"label": "Interpretability & Information", "metrics": [
        "explanation_faithfulness_v1", "entropy_dispersion_v1", "quantum_entanglement_entropy_v1"]},
    "robustness_stability": {"label": "Robustness & Stability", "metrics": [
        "perturbation_robustness_v1", "behavioral_lyapunov_v1", "gaussian_noise_accuracy_v1", "consistency_v1", "calibration_ece_v1",
        "distribution_drift_psi_v1", "quantum_fidelity_v1", "context_retention_v1", "availability_v1"]},
    "accountability_transparency": {"label": "Accountability & Transparency", "metrics": [
        "provenance_completeness_v1", "regulatory_mapping_coverage_v1", "agent_trace_completeness_v1", "agent_human_oversight_v1",
        "agent_escalation_v1", "guardrail_recommendation_v1", "swarm_consensus_v1"]},
}
GRADES = ((0.85, "A"), (0.70, "B"), (0.55, "C"), (0.40, "D"), (0.0, "F"))


def pillar_scores(values: Mapping[str, float]) -> Dict[str, Any]:
    """``values``: {metric_id: value} for TESTED metrics. Untested pillars are reported as gaps, not zero."""
    out: Dict[str, Any] = {}
    for pid, spec in PILLARS.items():
        vs = [values[m] for m in spec["metrics"] if m in values]
        out[pid] = {"label": spec["label"], "score": (sum(vs) / len(vs)) if vs else None, "n_metrics": len(vs)}
    return out


def cos_index(values: Mapping[str, float]) -> Dict[str, Any]:
    ps = pillar_scores(values)
    tested = [v["score"] for v in ps.values() if v["score"] is not None]
    cos = sum(tested) / len(tested) if tested else None
    grade = next((g for thr, g in GRADES if cos is not None and cos >= thr), None)
    return {"cos": cos, "grade": grade, "pillars": ps, "pillars_untested": [k for k, v in ps.items() if v["score"] is None],
            "note": "Derived index. Excludes safety/security/privacy. Not an assurance level."}
