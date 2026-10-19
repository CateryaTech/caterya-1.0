"""Indicative mapping from frameworks' *themes* to CATERYA metrics.

COVERAGE IS NOT CONFORMITY. A theme counts as "covered" when at least one mapped metric produced a
tested result; this says nothing about whether the result is sufficient to satisfy any law or
standard. Themes are paraphrased labels, not legal citations. Not legal advice.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

FRAMEWORKS: Dict[str, Dict[str, Any]] = {
    "EU_AI_ACT": {"status": "indicative", "themes": {
        "risk_management": ["policy_adherence_v1", "prompt_injection_resistance_v1", "agent_tool_misuse_v1"],
        "data_governance_and_bias": ["demographic_parity_v1", "equalized_odds_v1", "counterfactual_parity_v1", "distribution_drift_psi_v1"],
        "documentation_and_record_keeping": ["provenance_completeness_v1"],
        "transparency": ["explanation_faithfulness_v1", "entropy_dispersion_v1", "invariance_symmetry_v1"],
        "human_oversight": ["agent_human_oversight_v1", "agent_escalation_v1"],
        "accuracy_robustness_cybersecurity": ["perturbation_robustness_v1", "gaussian_noise_accuracy_v1", "calibration_ece_v1",
                                              "consistency_v1", "availability_v1", "prompt_injection_resistance_v1"]}},
    "NIST_AI_RMF": {"status": "indicative", "themes": {
        "govern": ["provenance_completeness_v1"],
        "map": ["context_retention_v1", "provenance_completeness_v1"],
        "measure": ["demographic_parity_v1", "equalized_odds_v1", "calibration_ece_v1", "perturbation_robustness_v1",
                    "policy_adherence_v1", "pii_leakage_v1", "consistency_v1"],
        "manage": ["guardrail_recommendation_v1", "swarm_consensus_v1", "agent_budget_adherence_v1", "agent_loop_detection_v1"]}},
    "ISO_IEC_42001": {"status": "indicative", "themes": {
        "ai_risk_assessment": ["policy_adherence_v1", "prompt_injection_resistance_v1"],
        "data_for_ai_systems": ["demographic_parity_v1", "pii_leakage_v1", "distribution_drift_psi_v1"],
        "performance_evaluation": ["calibration_ece_v1", "consistency_v1", "availability_v1", "agent_task_success_v1"],
        "monitoring_and_improvement": ["guardrail_recommendation_v1", "distribution_drift_psi_v1"],
        "transparency_to_interested_parties": ["provenance_completeness_v1", "explanation_faithfulness_v1"]}},
    "OECD_AI": {"status": "indicative", "themes": {
        "inclusive_and_sustainable": ["sustainability_estimate_v1"],
        "human_rights_and_fairness": ["demographic_parity_v1", "equalized_odds_v1", "counterfactual_parity_v1", "pii_leakage_v1"],
        "transparency_and_explainability": ["explanation_faithfulness_v1", "provenance_completeness_v1"],
        "robustness_security_safety": ["perturbation_robustness_v1", "prompt_injection_resistance_v1", "policy_adherence_v1"],
        "accountability": ["provenance_completeness_v1", "agent_human_oversight_v1"]}},
    "ID_AI_ETHICS_2026": {"status": "draft", "note": "Thematic draft mapping for Indonesian AI-ethics guidance; verify against the official text before relying on it.",
                          "themes": {
        "keadilan_fairness": ["demographic_parity_v1", "equalized_odds_v1", "counterfactual_parity_v1"],
        "transparansi": ["explanation_faithfulness_v1", "provenance_completeness_v1"],
        "akuntabilitas": ["provenance_completeness_v1", "agent_human_oversight_v1"],
        "keamanan_dan_privasi": ["pii_leakage_v1", "prompt_injection_resistance_v1", "policy_adherence_v1"],
        "kemanusiaan_pengawasan_manusia": ["agent_escalation_v1", "agent_human_oversight_v1"],
        "keberlanjutan": ["sustainability_estimate_v1"]}},
}
DISCLAIMER = "Indicative thematic mapping. Coverage is not conformity and is not legal advice."


def coverage(framework: str, tested_metric_ids: Iterable[str]) -> Dict[str, Any]:
    if framework not in FRAMEWORKS:
        raise KeyError(f"unknown framework {framework!r}; known: {sorted(FRAMEWORKS)}")
    tested = set(tested_metric_ids)
    themes = FRAMEWORKS[framework]["themes"]
    detail: Dict[str, Any] = {}
    for theme, mids in themes.items():
        hit = [m for m in mids if m in tested]
        detail[theme] = {"covered": bool(hit), "evidence_metrics": hit, "mapped_metrics": mids}
    covered = sum(1 for d in detail.values() if d["covered"])
    return {"framework": framework, "status": FRAMEWORKS[framework]["status"], "coverage": covered / len(themes), "themes": detail,
            "gaps": [t for t, d in detail.items() if not d["covered"]], "disclaimer": DISCLAIMER}


def all_metric_ids() -> List[str]:
    return sorted({m for f in FRAMEWORKS.values() for ms in f["themes"].values() for m in ms})
