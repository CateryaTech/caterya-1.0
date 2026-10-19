"""Guardrails recommend; they never block silently.

A ``held`` outcome exists only when a human decider has pre-signed a ``StandingAuthorization`` that
permits that automated action in that scope. Every check is sealed as Evidence (output is stored as a
hash, never as raw text).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from ..adapters.base import ModelAdapter
from ..assurance.governance import StandingAuthorization
from ..core.canonical import digest
from ..core.models import Evidence
from ..metrics.safety import find_pii
from ..provenance.registry import EvidenceRegistry

INJECTION_PATTERNS = [re.compile(p, re.I) for p in (r"ignore (all )?(previous|prior) instructions", r"reveal (your )?system prompt", r"disregard the above")]


@dataclass
class GuardResult:
    decision: str  # PASS | REMEDIATE | FAIL | UNTESTED
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    evidence_id: str = ""
    held: bool = False
    mode: str = "heuristic"


class CATERYAGuardrail:
    def __init__(self, registry: EvidenceRegistry, system_hash: str = "", mode: str = "heuristic", adapter: Optional[ModelAdapter] = None,
                 deny_terms: Sequence[str] = (), authorization: Optional[StandingAuthorization] = None, scope: str = "default"):
        if mode not in ("heuristic", "full"):
            raise ValueError("mode must be 'heuristic' or 'full'")
        if mode == "full" and adapter is None:
            raise ValueError("mode='full' needs an adapter to act as policy judge")
        self.registry, self.system_hash, self.mode, self.adapter = registry, system_hash, mode, adapter
        self.deny_terms = [d.lower() for d in deny_terms]
        self.authorization, self.scope = authorization, scope
        self.events: List[Dict[str, Any]] = []

    def check(self, output: str, context: str = "", prompt: str = "") -> GuardResult:
        findings: List[Dict[str, Any]] = []
        if not (output or "").strip():
            return self._seal(GuardResult("UNTESTED", [{"type": "empty_output", "severity": "info"}], ["Output was empty; nothing was checked."], mode=self.mode), output)
        for kind, vals in find_pii(output).items():
            findings.append({"type": f"pii_{kind}", "severity": "high", "count": len(vals)})
        for term in self.deny_terms:
            if term in output.lower():
                findings.append({"type": "deny_term", "severity": "high", "term": term})
        if any(p.search(context or "") for p in INJECTION_PATTERNS):
            findings.append({"type": "possible_indirect_injection_in_context", "severity": "medium"})
        if self.mode == "full":
            try:
                verdict = self.adapter.generate("Does the following assistant output violate safety, privacy or fairness policy? Answer only YES or NO.\n\n" + output)  # type: ignore[union-attr]
                if "yes" in verdict.lower().split()[:3]:
                    findings.append({"type": "judge_flagged", "severity": "high"})
            except Exception as e:  # noqa: BLE001
                return self._seal(GuardResult("UNTESTED", [{"type": "judge_error", "severity": "info", "error": type(e).__name__}],
                                              ["Policy judge unavailable; result is UNTESTED, not PASS."], mode=self.mode), output)
        sev = {f["severity"] for f in findings}
        decision = "FAIL" if "high" in sev else "REMEDIATE" if "medium" in sev else "PASS"
        recs = {"PASS": [], "REMEDIATE": ["Review the flagged context before relying on this output."],
                "FAIL": ["Withhold or redact this output pending human review."]}[decision]
        res = GuardResult(decision, findings, recs, mode=self.mode)
        if decision == "FAIL" and self.authorization and self.authorization.permits("hold", self.scope, self.registry.keyring):
            res.held = True
            res.recommendations.append("Held under a signed standing authorization.")
        return self._seal(res, output)

    def _seal(self, res: GuardResult, output: str) -> GuardResult:
        ev = self.registry.append(Evidence(kind="guardrail", claim=f"guardrail {res.mode}: {res.decision}", system_hash=self.system_hash,
                                           result={"decision": res.decision, "findings": res.findings, "held": res.held, "mode": res.mode,
                                                   "output_hash": digest((output or "").encode()),
                                                   "authorization": (self.authorization.body["decider"] if res.held and self.authorization else None)},
                                           limitations=["Heuristic checks are not exhaustive."]))
        res.evidence_id = ev.evidence_id
        self.events.append({"kind": "guardrail", "decision": res.decision, "evidence_id": ev.evidence_id})
        return res

    # -- framework-agnostic wrappers -----------------------------------------------------------
    def wrap(self, fn: Callable[..., Any], extract: Callable[[Any], str] = str) -> Callable[..., Any]:
        """Wrap any callable (LangGraph node, CrewAI tool callback, plain function): returns the original result
        and attaches ``.caterya_guard`` info where possible. Does not alter or block the result."""
        def inner(*a: Any, **kw: Any) -> Any:
            out = fn(*a, **kw)
            r = self.check(extract(out))
            if isinstance(out, dict):
                out = {**out, "caterya_guard": {"decision": r.decision, "evidence_id": r.evidence_id, "held": r.held}}
            return out
        inner.__name__ = getattr(fn, "__name__", "guarded")
        return inner
