import pytest

from caterya import CATERYAGuardrail, Decider, EthicsSwarm, MockModel, StandingAuthorization, new_signer
from caterya.core.errors import GovernanceError
from caterya.monitoring.continuous import ContinuousMonitor, IncidentLoop
from caterya.monitoring.drift import CUSUM, ks_statistic


def test_guardrail_recommends_and_seals_hash_not_text(engine):
    g = CATERYAGuardrail(engine.registry, "sys", deny_terms=["secret-sauce"])
    r = g.check("Contact budi.santoso@example.test please")
    assert r.decision == "FAIL" and not r.held and r.recommendations
    ev = engine.registry.get(r.evidence_id)
    assert "budi" not in str(ev.to_dict()) and ev.result["output_hash"].startswith("sha256:")
    assert g.check("a perfectly fine answer").decision == "PASS"
    assert g.check("   ").decision == "UNTESTED"  # empty is never PASS


def test_hold_only_with_valid_standing_authorization(engine):
    d = Decider("Dr. Rina", "Head of Risk", new_signer())
    engine.registry.keyring.add(d.signer)
    auth = StandingAuthorization.issue(d, "prod")
    assert CATERYAGuardrail(engine.registry, deny_terms=["x-leak"], authorization=auth, scope="prod").check("x-leak").held
    assert not CATERYAGuardrail(engine.registry, deny_terms=["x-leak"], authorization=auth, scope="other").check("x-leak").held
    assert not CATERYAGuardrail(engine.registry, deny_terms=["x-leak"]).check("x-leak").held


def test_full_mode_judge_error_is_untested_not_pass(engine):
    from caterya import CallableAdapter

    def broken(prompt, **k):
        raise TimeoutError()
    g = CATERYAGuardrail(engine.registry, mode="full", adapter=CallableAdapter(generate=broken))
    assert g.check("hello").decision == "UNTESTED"
    with pytest.raises(ValueError):
        CATERYAGuardrail(engine.registry, mode="full")


def test_wrap_does_not_alter_or_block_result(engine):
    g = CATERYAGuardrail(engine.registry)
    out = g.wrap(lambda: {"output": "hello"}, extract=lambda o: o["output"])()
    assert out["output"] == "hello" and out["caterya_guard"]["decision"] == "PASS"


def test_swarm_veto_and_evidence(engine):
    s = EthicsSwarm(engine.registry)
    assert s.vote("hello")["consensus"] == "ACCEPT"
    r = s.vote("call +62 812 5550 0199")
    assert r["consensus"] == "REJECT" and r["vetoed_by"] == ["privacy"]
    assert engine.registry.get(r["evidence_id"]).kind == "swarm"
    assert engine.registry.verify().ok


def test_swarm_voter_error_is_recorded_as_untested(engine):
    def bad(o, c):
        raise ValueError
    r = EthicsSwarm(engine.registry, {"a": bad, "b": lambda o, c: 1.0}).vote("x")
    assert r["voter_errors"] == {"a": "ValueError"}


def test_monitor_canary_requests_replay_on_regression(engine):
    m = ContinuousMonitor(engine)
    ok = m.run("canary", MockModel())
    assert not ok.needs_incident_replay and ok.report.profile == "CATERYA-MONITOR"
    bad = m.run("canary", MockModel(["policy", "pii"]))
    assert bad.needs_incident_replay and bad.delta["policy_adherence_v1"] < 0
    with pytest.raises(ValueError):
        m.run("nonsense", MockModel())


def test_incident_loop_enforces_order_actor_and_evidence(engine):
    loop = IncidentLoop(engine, "INC-1", "regression", "ops-a")
    with pytest.raises(GovernanceError):
        loop.advance("CONTAINED", "ops-a", "skipped triage")
    loop.advance("TRIAGED", "ops-a", "sev2")
    loop.advance("CONTAINED", "ops-a", "feature flag off")
    with pytest.raises(GovernanceError):
        loop.advance("REPLAYED", "ops-a", "no refs")
    with pytest.raises(GovernanceError):
        loop.advance("REPLAYED", "", "no actor", ["ev_x"])
    loop.advance("REPLAYED", "ops-a", "replayed", ["ev_x"])
    loop.advance("REMEDIATED", "ops-b", "patched")
    loop.advance("VERIFIED", "ops-c", "re-evaluated", ["ev_y"])
    loop.advance("CLOSED", "ops-c", "done")
    with pytest.raises(GovernanceError):
        loop.advance("CLOSED", "ops-c", "again")
    assert engine.registry.verify().ok


def test_drift_stats():
    a = [i / 100 for i in range(100)]
    assert ks_statistic(a, a) == 0 and ks_statistic(a, [x + 0.5 for x in a]) > 0.4
    c = CUSUM(target=0.9)
    assert not any(c.update(0.9) for _ in range(20))
    assert any(c.update(0.5) for _ in range(10))
