"""AssuranceEngine: evaluate a system, seal evidence, produce a CAR, support decisions/attestation/reproduction."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from ..adapters.base import ModelAdapter
from ..core.canonical import digest
from ..core.models import Evidence, MetricResult, SystemConfig
from ..metrics import registry as mreg
from ..metrics._util import untested
from ..metrics.context import EvalContext, TabularData
from ..pillars import cos_index
from ..provenance.attestation import dsse_sign, in_toto_statement
from ..provenance.registry import EvidenceRegistry
from ..provenance.signing import Signer, new_signer
from . import governance
from .levels import compute_level
from .profiles import Profile, get_profile
from .risk import risk_assessment

CAR_VERSION = "caterya.car/v1"
DISCLAIMER = ("This record states what was measured and what was not. It is not a certification, a safety guarantee, "
              "or a legal conformity assessment.")


@dataclass
class MetricOutcome:
    metric_id: str
    domain: str
    maturity: str
    result: MetricResult
    verdict: str  # PASS | FAIL | INFO | UNTESTED
    threshold: float
    weight: float
    required: bool
    borderline: bool
    evidence_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {"metric": self.metric_id, "domain": self.domain, "maturity": self.maturity, "verdict": self.verdict, "threshold": self.threshold,
                "borderline": self.borderline, "required": self.required, "evidence_id": self.evidence_id, **self.result.to_dict()}


@dataclass
class AssuranceReport:
    system: SystemConfig
    system_hash: str
    profile: str
    min_coverage: float
    outcomes: List[MetricOutcome]
    coverage: float
    required_untested: List[str]
    risk: Dict[str, Any]
    recommendation: str
    cos: Dict[str, Any]
    car: Dict[str, Any]
    car_evidence: Evidence
    evidence_ids: List[str]
    _inputs: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def gaps(self) -> List[Dict[str, Any]]:
        return [{"metric": o.metric_id, "reason": "; ".join(o.result.untested)} for o in self.outcomes if o.verdict == "UNTESTED"]

    def to_dict(self) -> Dict[str, Any]:
        return {"car": self.car, "outcomes": [o.to_dict() for o in self.outcomes]}

    def summary(self, lang: str = "en") -> str:
        from ..i18n import t
        L = [f"{t('title', lang)}: {self.system.name} {self.system.version}  [{self.profile}]",
             f"{t('recommendation', lang)}: {t(self.recommendation, lang)}   {t('risk', lang)}: {self.risk['band']} ({self.risk['score']})   "
             f"{t('coverage', lang)}: {self.coverage:.0%}"]
        for o in self.outcomes:
            v = "  -  " if o.result.value is None else f"{o.result.value:6.3f}"
            flag = "~" if o.borderline else " "
            L.append(f"  {o.verdict:<8}{flag} {o.metric_id:<38} {v}  (>= {o.threshold})")
        if self.gaps:
            L.append(f"{t('gaps', lang)}:")
            L += [f"  - {g['metric']}: {g['reason']}" for g in self.gaps]
        c = self.cos
        cos_txt = "n/a" if c["cos"] is None else "{:.3f} ({})".format(c["cos"], c["grade"])
        L.append("COS (derived, not a level): " + cos_txt)
        L.append(DISCLAIMER)
        return "\n".join(L)


def _verdict(res: MetricResult, thr: float, higher: bool):
    if not res.tested:
        return "UNTESTED", False
    ok = res.value >= thr if higher else res.value <= thr
    border = bool(res.ci and (res.ci[0] < thr <= res.ci[1] if higher else res.ci[0] <= thr < res.ci[1]))
    return ("PASS" if ok else "FAIL"), border


class AssuranceEngine:
    def __init__(self, system: SystemConfig, signer: Optional[Signer] = None, registry: Optional[EvidenceRegistry] = None,
                 profile: str = "CATERYA-LLM", seed: int = 0, clock: Callable[[], float] = time.time):
        self.system = system
        self.signer = signer if signer is not None else (registry.signer if registry is not None else new_signer())
        self.registry = registry if registry is not None else EvidenceRegistry(self.signer, clock=clock)
        self.profile_name, self.seed = profile, seed
        mreg.load_all()

    # ------------------------------------------------------------------------------------
    def evaluate(self, adapter: Optional[ModelAdapter] = None, profile: Optional[str] = None, *, tabular: Optional[TabularData] = None,
                 traces: Optional[List[Dict[str, Any]]] = None, events: Optional[List[Dict[str, Any]]] = None,
                 reference: Optional[Sequence[float]] = None, datasets: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Dict[str, Any]]] = None, seed: Optional[int] = None, depth: str = "full") -> AssuranceReport:
        inputs = dict(adapter=adapter, profile=profile, tabular=tabular, traces=traces, events=events, reference=reference,
                      datasets=datasets, params=params, seed=seed, depth=depth)
        return self._run(self.registry, inputs)

    def _run(self, registry: EvidenceRegistry, inputs: Dict[str, Any]) -> AssuranceReport:
        prof: Profile = get_profile(inputs["profile"] or self.profile_name)
        seed = self.seed if inputs["seed"] is None else inputs["seed"]
        ctx = EvalContext(self.system, inputs["adapter"], seed, inputs["tabular"], inputs["traces"], inputs["events"],
                          inputs["datasets"], inputs["params"], inputs["reference"])
        sys_hash = self.system.hash()
        reg = mreg.REGISTRY
        order = sorted(prof.metrics, key=lambda m: reg[m].phase)
        outcomes: List[MetricOutcome] = []
        run_evidence: List[Evidence] = []
        for mid in order:
            rm, pol = reg[mid], prof.metrics[mid]
            if rm.phase == 2 and ctx.evidence is None:
                rep = registry.verify()
                ctx.evidence = {"items": [e for e in run_evidence if not e.untested], "tested": {e.metric_id for e in run_evidence if not e.untested},
                                "chain_ok": rep.ok, "asymmetric": rep.asymmetric_only}
            params = ctx.p(mid, rm.defaults)
            spec = rm.spec(params)
            ctx.begin_metric()
            if inputs["depth"] == "light" and rm.cost == "deep":
                res = untested("skipped: depth=light")
            elif ctx.missing(rm.requires):
                res = untested("missing inputs: " + ", ".join(ctx.missing(rm.requires)))
            else:
                try:
                    res = rm.fn(ctx, params)
                except Exception as e:  # noqa: BLE001 - a failing metric must become a visible gap, never a crash or a pass
                    res = untested(f"error: {type(e).__name__}: {e}")
            ds_hash = self._dataset_hash(ctx, rm.requires)
            verdict, border = _verdict(res, pol.threshold, rm.higher_is_better)
            if pol.informational and res.tested:
                verdict, border = "INFO", False
            claim = (f"{mid} = {res.value:.4f} (n={res.n}) for {self.system.name} {self.system.version}" if res.tested
                     else f"{mid} UNTESTED for {self.system.name} {self.system.version}: {'; '.join(res.untested)}")
            ev = registry.append(Evidence(kind="metric", claim=claim, metric_id=mid, spec_hash=spec.spec_hash(), system_hash=sys_hash,
                                          dataset_hash=ds_hash, seed=seed, result=res.to_dict(), ci=list(res.ci) if res.ci else None,
                                          limitations=list(spec.limitations) + list(res.limitations), untested=list(res.untested)))
            run_evidence.append(ev)
            outcomes.append(MetricOutcome(mid, rm.domain, rm.maturity, res, verdict, pol.threshold, pol.weight, pol.required, border, ev.evidence_id))

        scored = [o for o in outcomes if not prof.metrics[o.metric_id].informational]
        tw = sum(o.weight for o in scored)
        coverage = sum(o.weight for o in scored if o.verdict != "UNTESTED") / tw if tw else 0.0
        req_un = [o.metric_id for o in outcomes if o.required and o.verdict == "UNTESTED"]
        risk = risk_assessment(outcomes, self.system.risk_context, prof.impact_default)
        fails_req = [o.metric_id for o in outcomes if o.required and o.verdict == "FAIL"]
        any_fail = any(o.verdict == "FAIL" for o in outcomes)
        if req_un or coverage < prof.min_coverage:
            rec = "INSUFFICIENT_EVIDENCE"
        elif fails_req or risk["band"] == "critical":
            rec = "RECOMMEND_REJECT"
        elif any_fail or risk["band"] == "high":
            rec = "RECOMMEND_CONDITIONAL"
        else:
            rec = "RECOMMEND_ASSURE"
        cos = cos_index({o.metric_id: o.result.value for o in outcomes if o.result.tested})
        car = {
            "version": CAR_VERSION, "system": {"name": self.system.name, "version": self.system.version, "hash": sys_hash}, "profile": prof.name,
            "evidence_ids": [e.evidence_id for e in run_evidence], "evidence_root": registry.root(), "evidence_count": len(run_evidence),
            "coverage": round(coverage, 4), "min_coverage": prof.min_coverage, "required_untested": req_un, "required_failed": fails_req,
            "gaps": [{"metric": o.metric_id, "reason": "; ".join(o.result.untested)} for o in outcomes if o.verdict == "UNTESTED"],
            "verdicts": {o.metric_id: {"value": None if o.result.value is None else round(o.result.value, 6), "verdict": o.verdict,
                                       "threshold": o.threshold, "borderline": o.borderline} for o in outcomes},
            "risk": risk, "recommendation": rec, "cos": {k: cos[k] for k in ("cos", "grade", "pillars_untested", "note")}, "disclaimer": DISCLAIMER}
        car_ev = registry.append(Evidence(kind="car", claim=f"Assurance record ({prof.name}) for {self.system.name} {self.system.version}: {rec}",
                                          system_hash=sys_hash, seed=seed, result=car))
        return AssuranceReport(self.system, sys_hash, prof.name, prof.min_coverage, outcomes, coverage, req_un, risk, rec, cos, car, car_ev,
                               [e.evidence_id for e in run_evidence], _inputs=inputs)

    @staticmethod
    def _dataset_hash(ctx: EvalContext, requires: Sequence[str]) -> str:
        parts: Dict[str, Any] = {k: ctx.current[k] for k in sorted(ctx.current)}
        if ctx.tabular is not None and any(r in requires for r in ("tabular", "tabular_labels", "probs", "labels", "features", "reference")):
            parts["tabular"] = digest(ctx.tabular.hash_payload())
        if ctx.reference is not None and "reference" in requires:
            parts["reference"] = digest(ctx.reference)
        if ctx.traces and "agent" in requires:
            parts["traces"] = digest(ctx.traces)
        if ctx.events and "events" in requires:
            parts["events"] = digest(ctx.events)
        return digest(parts) if parts else ""

    # ------------------------------------------------------------------------------------
    def decide(self, report: AssuranceReport, decider: governance.Decider, decision: str, rationale: str, override_reason: str = "",
               conditions: Iterable[str] = (), valid_days: int = 90) -> Evidence:
        return governance.decide(self.registry, report.car_evidence, decider, decision, rationale, override_reason, conditions, valid_days)

    def reproduce(self, report: AssuranceReport, tolerance: float = 1e-6) -> Dict[str, Any]:
        """Re-run the whole evaluation from the same inputs/seed into a scratch registry and compare values."""
        scratch = EvidenceRegistry(new_signer(self.signer.alg), clock=self.registry.clock)
        again = self._run(scratch, report._inputs)
        mism = []
        for a, b in zip(report.outcomes, again.outcomes):
            va, vb = a.result.value, b.result.value
            if (va is None) != (vb is None) or (va is not None and abs(va - vb) > tolerance):
                mism.append({"metric": a.metric_id, "original": va, "reproduced": vb})
        return {"ok": not mism, "checked": len(report.outcomes), "mismatches": mism}

    def attest(self, report: AssuranceReport, decision: Evidence, attester: Signer) -> Dict[str, Any]:
        """DSSE-wrapped in-toto statement signed by an (ideally accredited, third-party) attester key."""
        d = decision.result
        pred = {"level_basis": "process-depth", "decision": d["decision"], "valid_until": d["valid_until"], "car_hash": report.car_evidence.record_hash,
                "decision_evidence": decision.evidence_id, "profile": report.profile, "recommendation": report.recommendation,
                "coverage": report.car["coverage"], "disclaimer": DISCLAIMER}
        st = in_toto_statement(f"caterya:system:{report.system.name}@{report.system.version}", report.system_hash.split(":")[1], pred)
        return dsse_sign(st, attester)

    def level(self, report: AssuranceReport, **kw: Any) -> Dict[str, Any]:
        return compute_level(self.registry, report, **kw)
