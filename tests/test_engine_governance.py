import pytest

from caterya import AssuranceEngine, Decider, MockModel, StandingAuthorization, new_signer
from caterya.assurance.governance import verify_decision
from caterya.core.errors import GovernanceError
from caterya.provenance.signing import HAS_ED25519, Keyring

needs_ed = pytest.mark.skipif(not HAS_ED25519, reason="L2+ requires Ed25519 (cryptography)")


def test_healthy_system_is_recommended_flawed_is_rejected(system):
    good = AssuranceEngine(system).evaluate(MockModel())
    bad = AssuranceEngine(system).evaluate(MockModel(["policy", "injection", "pii", "bias"]))
    assert bad.recommendation == "RECOMMEND_REJECT" and good.risk["score"] < bad.risk["score"]
    if HAS_ED25519:
        assert good.recommendation == "RECOMMEND_ASSURE"
    else:  # without `cryptography` evidence is signed with the dev-only HMAC signer, so provenance is deliberately NOT satisfied
        prov = {o.metric_id: o for o in good.outcomes}["provenance_completeness_v1"]
        assert prov.verdict == "FAIL" and prov.result.details["asymmetric_signatures"] == 0.0
        assert good.recommendation == "RECOMMEND_CONDITIONAL"


def test_every_metric_is_sealed_with_spec_dataset_system_binding(engine):
    rep = engine.evaluate(MockModel())
    assert engine.registry.verify().ok
    for o in rep.outcomes:
        ev = engine.registry.get(o.evidence_id)
        assert ev.spec_hash and ev.system_hash == rep.system_hash and ev.limitations
    sealed = [engine.registry.get(o.evidence_id) for o in rep.outcomes if o.metric_id == "policy_adherence_v1"][0]
    assert sealed.dataset_hash.startswith("sha256:")


def test_parameter_change_changes_spec_hash_and_dataset_change_changes_dataset_hash(system):
    e1, e2, e3 = (AssuranceEngine(system) for _ in range(3))
    r1 = e1.evaluate(MockModel(), profile="CATERYA-LLM")
    r2 = e2.evaluate(MockModel(), params={"consistency_v1": {"repeats": 3}})
    r3 = e3.evaluate(MockModel(), datasets={"qa": [{"q": "What is the capital of France?", "a": "paris"}]})
    h = lambda e, r, m: e.registry.get(next(o.evidence_id for o in r.outcomes if o.metric_id == m))  # noqa: E731
    assert h(e1, r1, "consistency_v1").spec_hash != h(e2, r2, "consistency_v1").spec_hash
    assert h(e1, r1, "consistency_v1").dataset_hash != h(e3, r3, "consistency_v1").dataset_hash


def test_missing_inputs_are_gaps_not_passes(engine, tab_fair):
    rep = engine.evaluate(profile="CATERYA-LLM")  # no adapter at all
    assert all(o.verdict in ("UNTESTED", "INFO", "PASS", "FAIL") for o in rep.outcomes)
    assert rep.recommendation == "INSUFFICIENT_EVIDENCE" and rep.coverage < 0.3
    assert any("missing inputs" in g["reason"] for g in rep.gaps)


def test_crashing_metric_becomes_visible_gap_not_a_pass(system):
    from caterya import CallableAdapter

    def boom(prompt, **kw):
        raise RuntimeError("model down")
    rep = AssuranceEngine(system).evaluate(CallableAdapter(generate=boom))
    o = {x.metric_id: x for x in rep.outcomes}
    assert o["availability_v1"].verdict == "FAIL"  # unavailability is measured, not hidden
    assert rep.recommendation != "RECOMMEND_ASSURE"


def test_informational_metrics_do_not_move_verdict_or_risk(system):
    rep = AssuranceEngine(system).evaluate(MockModel())
    info = [o for o in rep.outcomes if o.verdict == "INFO"]
    assert {o.metric_id for o in info} == {"sustainability_estimate_v1", "regulatory_mapping_coverage_v1"}


def test_reproduction_ok_for_deterministic_and_flags_nondeterministic(system):
    eng = AssuranceEngine(system)
    assert eng.reproduce(eng.evaluate(MockModel()))["ok"]
    eng2 = AssuranceEngine(system)
    r = eng2.reproduce(eng2.evaluate(MockModel(["unstable"])))
    assert not r["ok"] and r["mismatches"]


def test_cos_is_derived_and_gaps_not_zero(system, tab_fair):
    rep = AssuranceEngine(system).evaluate(profile="CATERYA-TABULAR", tabular=tab_fair)
    assert rep.cos["cos"] is not None and "Not an assurance level" in rep.cos["note"]
    assert "safety" not in str(rep.cos["pillars"]).lower()


def _decided(system, flaws=(), decider_name="Dr. Rina"):
    eng = AssuranceEngine(system)
    rep = eng.evaluate(MockModel(list(flaws)))
    dec = Decider(decider_name, "Head of Risk", new_signer())
    return eng, rep, dec


def test_decision_requires_named_decider_rationale_and_override(system):
    eng, rep, dec = _decided(system, ["policy", "injection", "pii", "bias"])
    with pytest.raises(GovernanceError):
        eng.decide(rep, Decider("", "x", new_signer()), "REJECTED", "r")
    with pytest.raises(GovernanceError):
        eng.decide(rep, dec, "REJECTED", "  ")
    with pytest.raises(GovernanceError):
        eng.decide(rep, dec, "ASSURED", "looks fine")  # contradicts RECOMMEND_REJECT without override
    ev = eng.decide(rep, dec, "ASSURED", "accepted risk", override_reason="Compensating controls documented in RISK-42.")
    assert verify_decision(ev, eng.registry.keyring) and ev.result["override_reason"]


def test_decision_tamper_is_detected(system):
    eng, rep, dec = _decided(system)
    ev = eng.decide(rep, dec, "ASSURED", "ok")
    ev.result["decision"] = "REJECTED"
    assert not verify_decision(ev, eng.registry.keyring)


def test_standing_authorization(system):
    d = Decider("Dr. Rina", "Head of Risk", new_signer())
    ring = Keyring().add(d.signer)
    auth = StandingAuthorization.issue(d, "prod-chat", ("hold",), valid_seconds=100, now=1000)
    assert auth.permits("hold", "prod-chat", ring, now=1050)
    assert not auth.permits("hold", "other-scope", ring, now=1050) and not auth.permits("hold", "prod-chat", ring, now=2000)
    assert not auth.permits("hold", "prod-chat", Keyring(), now=1050)  # unknown signer
    with pytest.raises(GovernanceError):
        StandingAuthorization.issue(d, "x", ("approve",))  # approvals can never be pre-authorised


def full_chain(system, independent=True, third_party=True, flaws=()):
    eng, rep, dec = _decided(system, flaws)
    rr = eng.reproduce(rep)
    de = eng.decide(rep, dec, "ASSURED" if not flaws else "CONDITIONALLY_ASSURED", "ok")
    attester = new_signer()
    eng.registry.keyring.add(attester)
    att = eng.attest(rep, de, attester)
    rc = eng.registry.anchor(eng.registry.__class__ and __import__("caterya.provenance.anchors", fromlist=["DryRunAnchor"]).DryRunAnchor())
    if third_party:
        rc.third_party = True
    return eng, rep, dec, rr, de, att, attester


@needs_ed
def test_level_progression_l0_to_l4(system):
    eng, rep, dec, rr, de, att, attester = full_chain(system)
    acc = Keyring().add(attester)
    assert eng.level(rep)["level"] == 1
    assert eng.level(rep, reproduced=rr)["level"] == 2
    assert eng.level(rep, reproduced=rr, decision=de)["level"] == 3
    l4 = eng.level(rep, reproduced=rr, decision=de, attestation=att, accredited=acc, anchors=eng.registry.anchors)
    assert l4["level"] == 4 and not l4["blockers"]


@needs_ed
def test_l4_needs_third_party_anchor_and_matching_attestation(system):
    eng, rep, dec, rr, de, att, attester = full_chain(system, third_party=False)
    acc = Keyring().add(attester)
    r = eng.level(rep, reproduced=rr, decision=de, attestation=att, accredited=acc, anchors=eng.registry.anchors)
    assert r["level"] == 3 and any("third-party" in b for b in r["blockers"])
    r2 = eng.level(rep, reproduced=rr, decision=de, attestation=att, accredited=Keyring(), anchors=eng.registry.anchors)
    assert r2["level"] == 3


@needs_ed
def test_l3_blocked_without_separation_of_duties(system):
    eng = AssuranceEngine(system)
    rep = eng.evaluate(MockModel())
    rr = eng.reproduce(rep)
    same_key = Decider("Dr. Rina", "Head", eng.signer)  # decider reuses the evaluator key
    de = eng.decide(rep, same_key, "ASSURED", "ok")
    r = eng.level(rep, reproduced=rr, decision=de)
    assert r["level"] == 2 and any("separation of duties" in b for b in r["blockers"])


@needs_ed
def test_l3_blocked_when_keys_belong_to_owner(system):
    eng, rep, dec, rr, de, *_ = full_chain(system)
    r = eng.level(rep, reproduced=rr, decision=de, owner_key_ids=[dec.signer.key_id])
    assert r["level"] == 2 and any("owner" in b for b in r["blockers"])


@needs_ed
def test_rejected_decision_never_reaches_l3(system):
    eng, rep, dec = _decided(system, ["policy", "injection", "pii", "bias"])
    rr = eng.reproduce(rep)
    de = eng.decide(rep, dec, "REJECTED", "unsafe")
    assert eng.level(rep, reproduced=rr, decision=de)["level"] <= 2


def test_dev_hmac_signer_caps_level_at_1(system):
    from caterya.provenance.signing import HmacDevSigner
    eng = AssuranceEngine(system, signer=HmacDevSigner())
    rep = eng.evaluate(MockModel())
    r = eng.level(rep, reproduced=eng.reproduce(rep))
    assert r["level"] == 1 and any("symmetric" in b for b in r["blockers"])


def test_tamper_drops_level_to_zero(system):
    eng, rep, *_ = _decided(system)
    eng.registry._items[0].claim = "edited after the fact"
    assert eng.level(rep)["level"] == 0


def test_engine_uses_a_passed_empty_registry(system):
    """Regression: an empty EvidenceRegistry is falsy (defines __len__); it must still be used, not replaced."""
    from caterya import EvidenceRegistry
    reg = EvidenceRegistry(new_signer())
    assert len(reg) == 0
    eng = AssuranceEngine(system, registry=reg)
    assert eng.registry is reg and eng.signer is reg.signer
    eng.evaluate(MockModel())
    assert len(reg) > 0
