"""Human governance: named deciders with their own signature, overrides, standing authorizations."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from ..core.canonical import canonical_json, digest, strip_algo
from ..core.errors import GovernanceError
from ..core.models import Evidence
from ..provenance.registry import EvidenceRegistry, _utc
from ..provenance.signing import Keyring, Signer

DECISIONS = ("ASSURED", "CONDITIONALLY_ASSURED", "REJECTED", "DEFERRED")
POSITIVE = ("ASSURED", "CONDITIONALLY_ASSURED")


@dataclass
class Decider:
    """A named human (or accountable body) with their own signing key."""

    name: str
    role: str
    signer: Signer


def decide(registry: EvidenceRegistry, car_evidence: Evidence, decider: Decider, decision: str, rationale: str,
           override_reason: str = "", conditions: Iterable[str] = (), valid_days: int = 90) -> Evidence:
    if decision not in DECISIONS:
        raise GovernanceError(f"decision must be one of {DECISIONS}")
    if not decider.name.strip() or not decider.role.strip():
        raise GovernanceError("a decision requires a named decider and a role")
    if not rationale.strip():
        raise GovernanceError("a decision requires a written rationale")
    car = car_evidence.result
    rec = car.get("recommendation", "")
    if decision in POSITIVE and rec in ("RECOMMEND_REJECT", "INSUFFICIENT_EVIDENCE") and not override_reason.strip():
        raise GovernanceError(f"recommendation is {rec}; a positive decision requires a written override_reason")
    now = registry.clock()
    body = {
        "car_evidence_id": car_evidence.evidence_id, "car_hash": car_evidence.record_hash, "decision": decision, "rationale": rationale,
        "conditions": list(conditions), "override_reason": override_reason, "recommendation_at_decision": rec,
        "valid_until": _utc(now + valid_days * 86400),
        "decider": {"name": decider.name, "role": decider.role, "key_id": decider.signer.key_id, "alg": decider.signer.alg},
    }
    body_hash = digest(body)
    sig = decider.signer.signature_dict(bytes.fromhex(strip_algo(body_hash)))
    ev = Evidence(kind="decision", claim=f"{decision} by {decider.name} ({decider.role})", system_hash=car_evidence.system_hash,
                  result={**body, "body_hash": body_hash, "decider_signature": sig}, actor=registry.signer.key_id)
    registry.keyring.add(decider.signer)
    return registry.append(ev)


def verify_decision(ev: Evidence, keyring: Keyring) -> bool:
    r = ev.result
    body = {k: r[k] for k in ("car_evidence_id", "car_hash", "decision", "rationale", "conditions", "override_reason",
                              "recommendation_at_decision", "valid_until", "decider")}
    h = digest(body)
    return h == r.get("body_hash") and keyring.verify(r.get("decider_signature", {}), bytes.fromhex(strip_algo(h)))


@dataclass
class StandingAuthorization:
    """A decider's pre-signed permission for *automated holds* (never for approvals)."""

    body: Dict[str, Any]
    signature: Dict[str, str]

    @classmethod
    def issue(cls, decider: Decider, scope: str, actions: Iterable[str] = ("hold",), valid_seconds: int = 86400 * 30, now: Optional[float] = None) -> "StandingAuthorization":
        acts = list(actions)
        if any(a not in ("hold", "throttle", "rollback") for a in acts):
            raise GovernanceError("standing authorizations may only grant hold/throttle/rollback")
        t = now if now is not None else time.time()
        body = {"scope": scope, "actions": acts, "issued": t, "expires": t + valid_seconds,
                "decider": {"name": decider.name, "role": decider.role, "key_id": decider.signer.key_id}}
        return cls(body, decider.signer.signature_dict(canonical_json(body)))

    def permits(self, action: str, scope: str, keyring: Keyring, now: Optional[float] = None) -> bool:
        t = now if now is not None else time.time()
        return (action in self.body["actions"] and scope == self.body["scope"] and t < self.body["expires"]
                and keyring.verify(self.signature, canonical_json(self.body)))
