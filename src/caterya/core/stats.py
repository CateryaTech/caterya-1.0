"""Small, dependency-free statistics helpers used by metrics and monitoring."""
from __future__ import annotations

import math
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def wilson_ci(successes: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score interval for a proportion (95% by default)."""
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(values: Sequence[float], seed: int = 0, n_boot: int = 500, alpha: float = 0.05) -> Tuple[float, float]:
    if not values:
        return (0.0, 1.0)
    rng = random.Random(seed)
    k = len(values)
    means = sorted(sum(values[rng.randrange(k)] for _ in range(k)) / k for _ in range(n_boot))
    return (means[int(alpha / 2 * n_boot)], means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))])


def entropy(p: Iterable[float], base: float = 2.0) -> float:
    return -sum(x * math.log(x, base) for x in p if x > 0)


def normalise(counts: Sequence[float]) -> List[float]:
    s = float(sum(counts))
    return [c / s for c in counts] if s > 0 else [1.0 / len(counts)] * len(counts)


def _kl(p: Sequence[float], q: Sequence[float]) -> float:
    return sum(a * math.log2(a / b) for a, b in zip(p, q) if a > 0 and b > 0)


def js_divergence(p: Sequence[float], q: Sequence[float]) -> float:
    """Jensen-Shannon divergence in bits, bounded in [0, 1]."""
    m = [(a + b) / 2 for a, b in zip(p, q)]
    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def histogram(values: Sequence[float], bins: int, lo: float = 0.0, hi: float = 1.0) -> List[int]:
    out = [0] * bins
    for v in values:
        i = int((min(max(v, lo), hi) - lo) / (hi - lo) * bins)
        out[min(i, bins - 1)] += 1
    return out


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm_edit_distance(a: str, b: str) -> float:
    m = max(len(a), len(b))
    return levenshtein(a, b) / m if m else 0.0


def group_counts(preds: Sequence[int], groups: Sequence[str], mask: Optional[Sequence[bool]] = None) -> Dict[str, Tuple[int, int]]:
    """Return {group: (positives, n)} optionally restricted by ``mask``."""
    out: Dict[str, List[int]] = {}
    for i, (p, g) in enumerate(zip(preds, groups)):
        if mask is not None and not mask[i]:
            continue
        o = out.setdefault(g, [0, 0])
        o[0] += int(p)
        o[1] += 1
    return {g: (v[0], v[1]) for g, v in out.items()}
