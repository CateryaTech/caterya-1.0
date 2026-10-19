"""Metric registry: decorator, spec binding, plugin discovery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.models import MetricResult, MetricSpec

PHASE2_TOKENS = ("evidence", "usage")


@dataclass
class RegisteredMetric:
    id: str
    version: int
    domain: str
    description: str
    fn: Callable[[Any, Dict[str, Any]], MetricResult]
    requires: Tuple[str, ...]
    defaults: Dict[str, Any]
    higher_is_better: bool
    maturity: str
    cost: str
    assumptions: Tuple[str, ...]
    limitations: Tuple[str, ...]

    @property
    def phase(self) -> int:
        return 2 if any(r in PHASE2_TOKENS for r in self.requires) else 1

    def spec(self, params: Optional[Dict[str, Any]] = None) -> MetricSpec:
        return MetricSpec(id=self.id, version=self.version, domain=self.domain, description=self.description,
                          higher_is_better=self.higher_is_better, maturity=self.maturity, cost=self.cost,
                          requires=self.requires, parameters=dict(params if params is not None else self.defaults),
                          assumptions=self.assumptions, limitations=self.limitations)


REGISTRY: Dict[str, RegisteredMetric] = {}


def metric(id: str, domain: str, description: str, *, version: int = 1, requires: Tuple[str, ...] = (), defaults: Optional[Dict[str, Any]] = None,
           higher_is_better: bool = True, maturity: str = "stable", cost: str = "light", assumptions: Tuple[str, ...] = (), limitations: Tuple[str, ...] = ()):
    def deco(fn):
        if id in REGISTRY:
            raise ValueError(f"duplicate metric id {id}")
        REGISTRY[id] = RegisteredMetric(id, version, domain, description, fn, tuple(requires), dict(defaults or {}), higher_is_better,
                                        maturity, cost, tuple(assumptions), tuple(limitations))
        return fn
    return deco


def load_all() -> Dict[str, RegisteredMetric]:
    """Import every built-in metric module (idempotent) and any entry-point plugins."""
    from . import (agentic, fairness, golden_triangle, guardrail_metrics, provenance_metrics, quantum_metrics,  # noqa: F401
                   reliability, robustness, safety, sustainability)
    try:
        from importlib.metadata import entry_points
        for ep in entry_points(group="caterya.metrics"):
            ep.load()
    except Exception:  # pragma: no cover - plugin discovery must never break the core
        pass
    return REGISTRY


def get(metric_id: str) -> RegisteredMetric:
    load_all()
    if metric_id not in REGISTRY:
        raise KeyError(f"unknown metric {metric_id!r}")
    return REGISTRY[metric_id]


def by_domain() -> Dict[str, List[str]]:
    load_all()
    out: Dict[str, List[str]] = {}
    for m in REGISTRY.values():
        out.setdefault(m.domain, []).append(m.id)
    return out
