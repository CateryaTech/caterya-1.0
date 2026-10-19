"""Assurance *levels* describe the depth and independence of the PROCESS, never the safety of the system."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ..core.models import Evidence
from ..provenance.anchors import AnchorReceipt
from ..provenance.attestation import dsse_verify
from ..provenance.registry import EvidenceRegistry
from ..provenance.signing import Keyring
from .governance import POSITIVE, verify_decision

LABELS = {0: "L0 Unverified", 1: "L1 Self-assessed (integrity-verified)", 2: "L2 Evidence-backed (signed, reproduced)",
          3: "L3 Independently evaluated and decided", 4: "L4 Independently attested and anchored"}


def compute_level(registry: EvidenceRegistry, report: Any, *, reproduced: Optional[Dict[str, Any]] = None, decision: Optional[Evidence] = None,
                  attestation: Optional[Dict[str, Any]] = None, accredited: Optional[Keyring] = None, owner_key_ids: Iterable[str] = (),
                  anchors: Optional[List[AnchorReceipt]] = None) -> Dict[str, Any]:
    owner = set(owner_key_ids)
    reasons: List[str] = []
    blockers: List[str] = []
    ver = registry.verify()
    items = [registry.get(i) for i in report.evidence_ids]
    tested = [e for e in items if e.kind == "metric" and not e.untested]
    level = 0
    if not ver.ok:
        return {"level": 0, "label": LABELS[0], "reasons": [], "blockers": ["evidence chain failed verification"] + ver.errors[:3]}
    if tested:
        level = 1
        reasons.append("hash chain and signatures verify; >= 1 tested metric")
    else:
        return {"level": 0, "label": LABELS[0], "reasons": [], "blockers": ["no tested metrics"]}

    # L2
    l2 = True
    if not ver.asymmetric_only:
        l2 = False
        blockers.append("L2: some evidence uses a symmetric/dev signature (install caterya[crypto])")
    if report.coverage < report.min_coverage:
        l2 = False
        blockers.append(f"L2: coverage {report.coverage:.2f} < profile minimum {report.min_coverage:.2f}")
    if report.required_untested:
        l2 = False
        blockers.append("L2: required metrics untested: " + ", ".join(report.required_untested))
    if not (reproduced and reproduced.get("ok")):
        l2 = False
        blockers.append("L2: results not reproduced (run engine.reproduce(report))")
    if not l2:
        return {"level": level, "label": LABELS[level], "reasons": reasons, "blockers": blockers}
    level = 2
    reasons.append("asymmetric signatures, coverage met, required metrics tested, reproduction succeeded")

    # L3
    eval_keys = {e.signature.get("key_id") for e in items}
    l3 = True
    if not decision or not verify_decision(decision, registry.keyring):
        l3 = False
        blockers.append("L3: no verifiable named decision")
    else:
        d = decision.result
        if d["decision"] not in POSITIVE:
            l3 = False
            blockers.append(f"L3: decision is {d['decision']}")
        dk = d["decider"]["key_id"]
        if not registry.keyring.is_asymmetric(dk):
            l3 = False
            blockers.append("L3: decider key is not asymmetric")
        if dk in eval_keys:
            l3 = False
            blockers.append("L3: decider key equals an evaluator key (no separation of duties)")
        if dk in owner or (eval_keys & owner):
            l3 = False
            blockers.append("L3: evaluator or decider key belongs to the system owner (not independent)")
    if not l3:
        return {"level": level, "label": LABELS[level], "reasons": reasons, "blockers": blockers}
    level = 3
    reasons.append("named decider with own asymmetric key, separate from evaluator and owner keys")

    # L4
    l4 = True
    stmt = None
    if not attestation or not accredited:
        l4 = False
        blockers.append("L4: missing DSSE attestation or accreditation keyring")
    else:
        try:
            stmt = dsse_verify(attestation, accredited)
            if stmt["predicate"].get("car_hash") != report.car_evidence.record_hash:
                l4 = False
                blockers.append("L4: attestation does not reference this CAR")
        except Exception as e:  # noqa: BLE001
            l4 = False
            blockers.append(f"L4: attestation invalid ({e})")
    dec_pos = registry.all().index(decision) + 1 if decision else 0
    ok_anchor = any(a.third_party and a.size >= dec_pos and a.root == registry.root_at(a.size) for a in (anchors or []))
    if not ok_anchor:
        l4 = False
        blockers.append("L4: no third-party-verifiable anchor covering the decision")
    if not l4:
        return {"level": level, "label": LABELS[level], "reasons": reasons, "blockers": blockers}
    reasons.append("accredited DSSE attestation and third-party anchor")
    return {"level": 4, "label": LABELS[4], "reasons": reasons, "blockers": []}
