"""Evaluation context handed to every metric function."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..adapters.base import ModelAdapter
from ..core.models import SystemConfig
from . import datasets as ds


@dataclass
class TabularData:
    """Prediction-level data: labels, scores, groups, features."""

    y_true: Optional[List[int]] = None
    y_prob: Optional[List[float]] = None
    y_pred: Optional[List[int]] = None
    groups: Dict[str, List[str]] = field(default_factory=dict)
    X: Optional[List[Dict[str, Any]]] = None
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if self.y_pred is None and self.y_prob is not None:
            self.y_pred = [int(p >= self.threshold) for p in self.y_prob]
        n = {len(v) for v in (self.y_true, self.y_prob, self.y_pred, self.X, *self.groups.values()) if v is not None}
        if len(n) > 1:
            raise ValueError(f"tabular inputs have inconsistent lengths: {sorted(n)}")

    def hash_payload(self) -> Dict[str, Any]:
        return {"y_true": self.y_true, "y_prob": self.y_prob, "y_pred": self.y_pred, "groups": self.groups, "X": self.X}


class EvalContext:
    def __init__(self, system: SystemConfig, adapter: Optional[ModelAdapter] = None, seed: int = 0, tabular: Optional[TabularData] = None,
                 traces: Optional[List[Dict[str, Any]]] = None, events: Optional[List[Dict[str, Any]]] = None,
                 datasets: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Dict[str, Any]]] = None,
                 reference: Optional[Sequence[float]] = None, max_calls: int = 5000):
        self.system, self.adapter, self.seed = system, adapter, seed
        self.tabular, self.traces, self.events = tabular, traces or [], events or []
        self._datasets = datasets or {}
        self.params = params or {}
        self.reference = list(reference) if reference is not None else None
        self.max_calls = max_calls
        self.stats = {"calls": 0, "errors": 0, "tokens_in": 0, "tokens_out": 0}
        self.used: Dict[str, str] = {}
        self.current: Dict[str, str] = {}  # datasets used by the metric currently running
        self.evidence: Optional[Dict[str, Any]] = None  # filled for phase-2 metrics

    # -- capabilities ---------------------------------------------------------------------
    def begin_metric(self) -> None:
        self.current = {}

    def has(self, token: str) -> bool:
        caps = self.adapter.capabilities() if self.adapter else frozenset()
        t = self.tabular
        return {
            "generate": "generate" in caps, "predict": "predict" in caps, "explain": "explain" in caps,
            "agent": "agent" in caps or bool(self.traces),
            "tabular": bool(t and t.y_prob is not None and t.groups),
            "tabular_labels": bool(t and t.y_true is not None and t.y_prob is not None and t.groups),
            "probs": bool(t and t.y_prob is not None),
            "labels": bool(t and t.y_true is not None),
            "features": bool(t and t.X),
            "events": bool(self.events), "reference": self.reference is not None and bool(t and t.y_prob),
            "evidence": self.evidence is not None, "usage": self.stats["calls"] > 0,
        }.get(token, False)

    def missing(self, requires: Sequence[str]) -> List[str]:
        return [r for r in requires if not self.has(r)]

    # -- helpers --------------------------------------------------------------------------
    def rng(self, label: str) -> random.Random:
        return random.Random(f"{self.seed}:{label}")

    def data(self, name: str) -> Any:
        d = self._datasets.get(name, ds.REGISTRY.get(name))
        if d is None:
            raise KeyError(f"unknown dataset {name!r}")
        self.used[name] = self.current[name] = ds.dataset_hash(name, d)
        return d

    def call(self, prompt: str, system: Optional[str] = None, seed: Optional[int] = None) -> Optional[str]:
        """Call the adapter; never raises. Returns ``None`` on error (counted for availability)."""
        if self.stats["calls"] >= self.max_calls:
            raise RuntimeError("max_calls budget exhausted")
        self.stats["calls"] += 1
        self.stats["tokens_in"] += max(1, (len(prompt) + len(system or "")) // 4)
        try:
            out = self.adapter.generate(prompt, system=system, seed=seed)  # type: ignore[union-attr]
        except Exception:
            self.stats["errors"] += 1
            return None
        out = out if isinstance(out, str) else str(out)
        self.stats["tokens_out"] += max(1, len(out) // 4)
        return out

    def p(self, metric_id: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
        return {**defaults, **self.params.get(metric_id, {})}
