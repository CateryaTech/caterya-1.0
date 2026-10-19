"""Developer-facing helpers: AgentGuard (records agent traces) and a one-call quick-start."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .core.errors import PolicyViolation


class AgentGuard:
    """Record an agent run as a ``caterya.trace/v1`` trace; optionally enforce the tool allow-list live."""

    def __init__(self, task_id: str, goal: str, policy: Optional[Dict[str, Any]] = None, enforce: bool = False):
        self.task_id, self.goal, self.policy, self.enforce = task_id, goal, policy or {}, enforce
        self.steps: List[Dict[str, Any]] = []

    def _add(self, **kw: Any) -> Dict[str, Any]:
        s = {"idx": len(self.steps), "ts": f"t{len(self.steps)}", "ok": True, "cost": 0.0, **kw}
        self.steps.append(s)
        return s

    def tool_call(self, tool: str, args: Optional[Dict[str, Any]] = None, ok: bool = True, cost: float = 0.0, write: bool = False,
                  scope: Optional[str] = None, risk: Optional[str] = None, requires_approval: bool = False, approved_by: str = "") -> Dict[str, Any]:
        allowed = self.policy.get("allowed_tools")
        if self.enforce and allowed is not None and tool not in allowed:
            raise PolicyViolation(f"tool {tool!r} is not in the allow-list {allowed}")
        extra = {k: v for k, v in (("scope", scope), ("risk", risk)) if v}
        return self._add(type="tool_call", tool=tool, args=args or {}, ok=ok, cost=cost, write=write, requires_approval=requires_approval,
                         approved_by=approved_by, **extra)

    def escalate(self, reason: str) -> Dict[str, Any]:
        return self._add(type="escalate", reason=reason)

    def message(self, text: str) -> Dict[str, Any]:
        return self._add(type="message", text=text)

    def finish(self, success: bool, injection_followed: Optional[bool] = None) -> Dict[str, Any]:
        return {"task_id": self.task_id, "goal": self.goal, "steps": self.steps, "policy": self.policy,
                "outcome": {"success": success}, "injection_followed": injection_followed}
