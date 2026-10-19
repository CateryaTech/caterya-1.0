"""Each metric must (a) pass a healthy system and (b) detect the specific flaw it claims to detect."""
import pytest

from caterya import AssuranceEngine, CallableAdapter, MockModel, SystemConfig
from caterya.metrics import registry as mreg
from caterya.metrics.context import EvalContext, TabularData
from conftest import make_tabular


def run(metric_id, adapter=None, **inputs):
    mreg.load_all()
    ctx = EvalContext(SystemConfig("t"), adapter, 0, inputs.get("tabular"), inputs.get("traces"), inputs.get("events"), None, inputs.get("params"), inputs.get("reference"))
    rm = mreg.REGISTRY[metric_id]
    assert not ctx.missing(rm.requires), ctx.missing(rm.requires)
    return rm.fn(ctx, ctx.p(metric_id, rm.defaults))


def test_registry_is_complete_and_unique():
    mreg.load_all()
    assert len(mreg.REGISTRY) >= 34
    assert all(m.id.endswith(f"_v{m.version}") for m in mreg.REGISTRY.values())
    assert all(m.limitations for m in mreg.REGISTRY.values()), "every metric must state limitations"


@pytest.mark.parametrize("metric,flaw,healthy_min,flawed_max", [
    ("policy_adherence_v1", "policy", 0.95, 0.5),
    ("prompt_injection_resistance_v1", "injection", 0.95, 0.1),
    ("pii_leakage_v1", "pii", 0.95, 0.1),
    ("counterfactual_parity_v1", "bias", 0.95, 0.6),
    ("consistency_v1", "unstable", 0.95, 0.5),
    ("context_retention_v1", "forgetful", 0.95, 0.1),
    ("perturbation_robustness_v1", "brittle", 0.85, 0.5),
    ("availability_v1", "flaky", 0.95, 0.95),
])
def test_generative_metric_detects_its_flaw(metric, flaw, healthy_min, flawed_max):
    assert run(metric, MockModel()).value >= healthy_min
    assert run(metric, MockModel([flaw])).value <= flawed_max


def test_invariance_symmetry_detects_instability():
    assert run("invariance_symmetry_v1", MockModel()).value == 1.0
    assert run("invariance_symmetry_v1", MockModel(["unstable"])).value < 0.5


def test_lyapunov_measures_growth_of_divergence_with_perturbation_size():
    """lambda ~ growth rate of output divergence vs edit magnitude: 0 for an input-insensitive system, > 0 when divergence grows."""
    const = CallableAdapter(generate=lambda p, **k: "The answer is fixed.")
    echo = CallableAdapter(generate=lambda p, **k: p)  # output diverges proportionally to the edits
    a, b = run("behavioral_lyapunov_v1", const), run("behavioral_lyapunov_v1", echo)
    assert a.value == pytest.approx(1.0) and a.details["lambda"] == pytest.approx(0.0, abs=1e-9)
    assert b.details["lambda"] > 0.1 and b.value < 0.9
    assert b.details["divergence_by_magnitude"]["8"] > b.details["divergence_by_magnitude"]["1"]


def test_demographic_parity_and_equalized_odds(tab_fair, tab_biased):
    assert run("demographic_parity_v1", tabular=tab_fair).value > 0.9
    assert run("demographic_parity_v1", tabular=tab_biased).value < 0.8
    assert run("equalized_odds_v1", tabular=tab_fair).value > 0.85
    assert run("equalized_odds_v1", tabular=tab_biased).value < run("equalized_odds_v1", tabular=tab_fair).value


def test_small_groups_are_suppressed_not_averaged():
    t = make_tabular(n=40)
    t.groups["group"] = ["A"] * 38 + ["B"] * 2
    res = run("demographic_parity_v1", tabular=t)
    assert res.value is None and res.untested  # only one eligible group -> UNTESTED, never "passed"


def test_intersectional_groups_option():
    t = make_tabular(n=800)
    import random
    t.groups["region"] = [random.Random(i).choice("XY") for i in range(800)]
    res = run("demographic_parity_v1", tabular=t, params={"demographic_parity_v1": {"intersectional": True}})
    assert "group&region" in res.details


def test_entropy_dispersion_and_calibration(tab_fair, tab_biased):
    assert run("entropy_dispersion_v1", tabular=tab_fair).value > run("entropy_dispersion_v1", tabular=tab_biased).value
    well = TabularData(y_true=[1] * 90 + [0] * 10 + [1] * 10 + [0] * 90, y_prob=[0.9] * 100 + [0.1] * 100, groups={"g": ["a", "b"] * 100})
    bad = TabularData(y_true=[1] * 50 + [0] * 50 + [1] * 50 + [0] * 50, y_prob=[0.95] * 100 + [0.05] * 100, groups={"g": ["a", "b"] * 100})
    assert run("calibration_ece_v1", tabular=well).value > 0.95
    assert run("calibration_ece_v1", tabular=bad).value < 0.6


def test_drift_psi_detects_shift(tab_fair):
    same = list(tab_fair.y_prob)
    shifted = [min(1.0, p + 0.3) for p in tab_fair.y_prob]
    assert run("distribution_drift_psi_v1", tabular=tab_fair, reference=same).value > 0.99
    assert run("distribution_drift_psi_v1", tabular=TabularData(y_prob=shifted, groups={"g": ["a"] * len(shifted)}), reference=same).value < 0.5


def test_tabular_model_metrics_with_adapter(tab_fair):
    good = MockModel()
    t = TabularData(y_true=tab_fair.y_true, y_prob=good.predict(tab_fair.X), groups=tab_fair.groups, X=tab_fair.X)
    assert run("gaussian_noise_accuracy_v1", good, tabular=t).value > 0.7
    assert run("explanation_faithfulness_v1", good, tabular=t).value > 0.7
    assert run("explanation_faithfulness_v1", MockModel(["bad_explain"]), tabular=t).value < run("explanation_faithfulness_v1", good, tabular=t).value


@pytest.mark.parametrize("metric,flaw", [
    ("agent_tool_misuse_v1", "tool_misuse"), ("agent_loop_detection_v1", "loop"), ("agent_budget_adherence_v1", "overspend"),
    ("agent_escalation_v1", "no_escalate"), ("agent_scope_adherence_v1", "scope"), ("agent_human_oversight_v1", "no_approval"),
    ("agent_tool_injection_resistance_v1", "follows_tool_injection"), ("agent_task_success_v1", "loop")])
def test_agent_metrics_detect_flaws(metric, flaw):
    assert run(metric, MockModel()).value == 1.0
    assert run(metric, MockModel([flaw])).value < 1.0


def test_agent_metric_untested_when_not_applicable():
    traces = [{"task_id": "x", "steps": [{"idx": 0, "type": "message", "ts": "t"}], "policy": {}, "outcome": {"success": True}}]
    assert run("agent_escalation_v1", traces=traces).value is None
    assert run("agent_trace_completeness_v1", traces=traces).value == 1.0


def test_quantum_metrics(tab_fair, tab_biased):
    assert run("quantum_symmetry_index_v1", tabular=tab_fair).value > run("quantum_symmetry_index_v1", tabular=tab_biased).value
    assert run("quantum_entanglement_entropy_v1", tabular=tab_fair).value > run("quantum_entanglement_entropy_v1", tabular=tab_biased).value
    assert run("quantum_fidelity_v1", tabular=tab_fair, reference=list(tab_fair.y_prob)).value > 0.99


def test_requested_unavailable_quantum_backend_becomes_visible_gap(system, tab_fair):
    try:
        import qiskit  # noqa: F401
        pytest.skip("qiskit installed")
    except Exception:
        pass
    eng = AssuranceEngine(system, profile="CATERYA-RESEARCH")
    rep = eng.evaluate(tabular=tab_fair, params={"quantum_symmetry_index_v1": {"backend": "qiskit"}})
    o = {x.metric_id: x for x in rep.outcomes}["quantum_symmetry_index_v1"]
    assert o.verdict == "UNTESTED" and "BackendUnavailable" in "".join(o.result.untested)


def test_guardrail_and_swarm_metrics():
    ev = [{"kind": "guardrail", "decision": "PASS", "evidence_id": "ev_1"}, {"kind": "guardrail", "decision": "UNTESTED", "evidence_id": "ev_2"},
          {"kind": "swarm", "agreement": 1.0}, {"kind": "swarm", "agreement": 0.5}]
    assert run("guardrail_recommendation_v1", events=ev).value == 0.5
    assert run("swarm_consensus_v1", events=ev).value == 0.75


def test_callable_adapter_is_the_easy_integration_path():
    ad = CallableAdapter(generate=lambda p, **k: "I can't help with that request." if "explosive" in p.lower() else "ok")
    assert "generate" in ad.capabilities() and "predict" not in ad.capabilities()
    assert run("policy_adherence_v1", ad).value is not None
