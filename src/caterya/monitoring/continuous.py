"""Continuous assurance: tiered re-evaluation modes and an ordered incident loop."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..assurance.engine import AssuranceEngine, AssuranceReport
from ..core.errors import GovernanceError
from ..core.models import Evidence

# mode -> (profile or None to use the caller's, depth)
MODES = {"pre_release": (None, "full"), "canary": ("CATERYA-MONITOR", "light"), "post_release": ("CATERYA-MONITOR", "light"),
         "drift": ("CATERYA-MONITOR", "light"), "incident_replay": (None, "full")}


@dataclass
class MonitorResult:
    mode: str
    report: AssuranceReport
    needs_incident_replay: bool
    delta: Dict[str, float]
    evidence_id: str


class ContinuousMonitor:
    def __init__(self, engine: AssuranceEngine, default_profile: str = "CATERYA-LLM", canary_min_pass: float = 0.9):
        self.engine, self.default_profile, self.canary_min_pass = engine, default_profile, canary_min_pass
        self._last: Dict[str, Dict[str, float]] = {}

    def run(self, mode: str, adapter=None, **inputs: Any) -> MonitorResult:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}")
        prof, depth = MODES[mode]
        rep = self.engine.evaluate(adapter, prof or self.default_profile, depth=depth, **inputs)
        vals = {o.metric_id: o.result.value for o in rep.outcomes if o.result.tested}
        prev = self._last.get(rep.profile, {})
        delta = {k: round(v - prev[k], 6) for k, v in vals.items() if k in prev}
        self._last[rep.profile] = vals
        tested = [o for o in rep.outcomes if o.verdict in ("PASS", "FAIL")]
        pass_rate = sum(o.verdict == "PASS" for o in tested) / len(tested) if tested else 0.0
        replay = bool(rep.car["required_failed"]) or (mode in ("canary", "post_release") and pass_rate < self.canary_min_pass)
        ev = self.engine.registry.append(Evidence(
            kind="monitor", claim=f"{mode} run: pass-rate {pass_rate:.2f}; incident_replay {'REQUESTED' if replay else 'not needed'}",
            system_hash=rep.system_hash, result={"mode": mode, "profile": rep.profile, "pass_rate": round(pass_rate, 4), "needs_incident_replay": replay,
                                                 "delta": delta, "car_evidence_id": rep.car_evidence.evidence_id}))
        return MonitorResult(mode, rep, replay, delta, ev.evidence_id)


STAGES = ["DETECTED", "TRIAGED", "CONTAINED", "REPLAYED", "REMEDIATED", "VERIFIED", "CLOSED"]


class IncidentLoop:
    """Detect -> triage -> contain -> replay -> remediate -> verify -> close. Stages cannot be skipped or reordered."""

    def __init__(self, engine: AssuranceEngine, incident_id: str, title: str, actor: str):
        self.engine, self.incident_id = engine, incident_id
        self.stage_idx = -1
        self.history: List[str] = []
        self.advance("DETECTED", actor, title)

    @property
    def stage(self) -> str:
        return STAGES[self.stage_idx]

    def advance(self, stage: str, actor: str, note: str, evidence_refs: Optional[List[str]] = None) -> Evidence:
        if stage != STAGES[min(self.stage_idx + 1, len(STAGES) - 1)] or self.stage_idx + 1 >= len(STAGES):
            raise GovernanceError(f"invalid transition {self.stage if self.stage_idx >= 0 else None} -> {stage}; next must be "
                                  f"{STAGES[self.stage_idx + 1] if self.stage_idx + 1 < len(STAGES) else 'none (closed)'}")
        if not actor.strip():
            raise GovernanceError("every incident transition needs a named actor")
        if stage in ("REPLAYED", "VERIFIED") and not evidence_refs:
            raise GovernanceError(f"{stage} requires evidence_refs (the replay / re-evaluation evidence)")
        self.stage_idx += 1
        ev = self.engine.registry.append(Evidence(kind="incident", claim=f"incident {self.incident_id}: {stage}", system_hash=self.engine.system.hash(),
                                                  result={"incident_id": self.incident_id, "stage": stage, "actor": actor, "note": note,
                                                          "evidence_refs": evidence_refs or []}))
        self.history.append(ev.evidence_id)
        return ev
