"""Quantum-derived fairness / information measures (RESEARCH maturity).

These are *research* instruments: they compare amplitude-encoded group outcome distributions
with a swap test. They make no claim of quantum advantage and are never a substitute for the
classical fairness metrics.
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Dict, List, Sequence

from ..core.stats import normalise
from .backends import QuantumBackend, get_backend
from .statevector import amplitude_encode, entanglement_entropy


def quantum_symmetry(group_hist: Dict[str, Sequence[float]], backend: QuantumBackend = None, shots: int = None, seed: int = 0) -> Dict[str, Any]:
    """Pairwise swap-test fidelity between groups' outcome histograms.

    Returns ``{"index": min pairwise fidelity, "mean": ..., "pairs": [...]}``; 1.0 means all
    group outcome distributions coincide.
    """
    backend = backend or get_backend("classical")
    pairs: List[Dict[str, Any]] = []
    for (ga, ha), (gb, hb) in itertools.combinations(sorted(group_hist.items()), 2):
        rec = backend.swap_test_fidelity(normalise(ha), normalise(hb), shots=shots, seed=seed)
        pairs.append({"a": ga, "b": gb, **{k: rec[k] for k in ("fidelity", "backend", "backend_version", "shots", "circuit_hash", "exact")}})
    fids = [p["fidelity"] for p in pairs]
    return {"index": min(fids), "mean": sum(fids) / len(fids), "pairs": pairs}


def distribution_entanglement_entropy(joint: Sequence[Sequence[float]]) -> float:
    """Entanglement entropy (bits) of the amplitude-encoded joint distribution of two variables.

    ``joint[i][j]`` is a non-negative weight for (A=i, B=j). A product distribution gives 0.
    """
    na = max(1, math.ceil(math.log2(max(2, len(joint)))))
    nb = max(1, math.ceil(math.log2(max(2, max(len(r) for r in joint)))))
    da, db = 1 << na, 1 << nb
    flat = [0.0] * (da * db)
    for i, row in enumerate(joint):
        for j, v in enumerate(row):
            flat[i + (j << na)] = float(v)
    amps = amplitude_encode(flat, na + nb)
    return entanglement_entropy(amps, na, nb)
