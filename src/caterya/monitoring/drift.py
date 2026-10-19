"""Drift statistics and a CUSUM change detector (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from ..metrics.reliability import psi  # re-exported


def ks_statistic(a: Sequence[float], b: Sequence[float]) -> float:
    """Two-sample Kolmogorov-Smirnov statistic."""
    sa, sb = sorted(a), sorted(b)
    i = j = 0
    d = 0.0
    while i < len(sa) and j < len(sb):
        x = min(sa[i], sb[j])
        while i < len(sa) and sa[i] <= x:
            i += 1
        while j < len(sb) and sb[j] <= x:
            j += 1
        d = max(d, abs(i / len(sa) - j / len(sb)))
    return d


@dataclass
class CUSUM:
    """One-sided upper+lower CUSUM on a stream of values around ``target``."""

    target: float
    k: float = 0.02  # slack
    h: float = 0.15  # decision interval
    hi: float = 0.0
    lo: float = 0.0
    alarms: List[int] = field(default_factory=list)
    _n: int = 0

    def update(self, x: float) -> bool:
        self.hi = max(0.0, self.hi + (x - self.target) - self.k)
        self.lo = max(0.0, self.lo + (self.target - x) - self.k)
        self._n += 1
        fired = self.hi > self.h or self.lo > self.h
        if fired:
            self.alarms.append(self._n - 1)
            self.hi = self.lo = 0.0
        return fired


def drift_summary(reference: Sequence[float], current: Sequence[float]) -> Dict[str, float]:
    return {"psi": psi(reference, current), "ks": ks_statistic(reference, current)}
