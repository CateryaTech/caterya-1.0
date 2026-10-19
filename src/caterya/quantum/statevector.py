"""Minimal pure-Python state-vector simulator (real/complex amplitudes, <= ~12 qubits).

Qubit ``q`` corresponds to bit ``q`` (LSB = qubit 0) of the basis-state index. Purpose: a
dependency-free, deterministic reference implementation for the swap test and entanglement
entropy used by CATERYA's *research* metrics. It is a simulator, not quantum hardware.
"""
from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple

SQRT1_2 = 1 / math.sqrt(2)


class StateVector:
    def __init__(self, n_qubits: int, amps: Sequence[complex] = None):
        if n_qubits < 1 or n_qubits > 14:
            raise ValueError("n_qubits must be in 1..14 for the reference simulator")
        self.n = n_qubits
        self.amps: List[complex] = list(amps) if amps is not None else [0j] * (1 << n_qubits)
        if amps is None:
            self.amps[0] = 1 + 0j
        elif len(self.amps) != 1 << n_qubits:
            raise ValueError("amplitude vector has wrong length")

    def apply_1q(self, gate: Tuple[Tuple[complex, complex], Tuple[complex, complex]], q: int) -> None:
        bit = 1 << q
        a = self.amps
        for i in range(len(a)):
            if not i & bit:
                x, y = a[i], a[i | bit]
                a[i] = gate[0][0] * x + gate[0][1] * y
                a[i | bit] = gate[1][0] * x + gate[1][1] * y

    def h(self, q: int) -> None:
        self.apply_1q(((SQRT1_2, SQRT1_2), (SQRT1_2, -SQRT1_2)), q)

    def x(self, q: int) -> None:
        self.apply_1q(((0, 1), (1, 0)), q)

    def cswap(self, control: int, t1: int, t2: int) -> None:
        cb, b1, b2 = 1 << control, 1 << t1, 1 << t2
        a = self.amps
        for i in range(len(a)):
            if (i & cb) and (i & b1) and not (i & b2):
                j = (i & ~b1) | b2
                a[i], a[j] = a[j], a[i]

    def prob(self, q: int, outcome: int = 0) -> float:
        bit = 1 << q
        return sum(abs(v) ** 2 for i, v in enumerate(self.amps) if bool(i & bit) == bool(outcome))

    def norm(self) -> float:
        return math.sqrt(sum(abs(v) ** 2 for v in self.amps))


def amplitude_encode(vec: Sequence[float], n_qubits: int) -> List[float]:
    """Amplitude-encode a non-negative vector as sqrt-probabilities on ``n_qubits`` (zero-padded, L2-normalised)."""
    dim = 1 << n_qubits
    if len(vec) > dim:
        raise ValueError("vector longer than 2**n_qubits")
    v = [math.sqrt(max(0.0, float(x))) for x in vec] + [0.0] * (dim - len(vec))
    nrm = math.sqrt(sum(x * x for x in v))
    if nrm == 0:
        raise ValueError("cannot encode an all-zero vector")
    return [x / nrm for x in v]


def swap_test_state(a: Sequence[float], b: Sequence[float], n: int) -> StateVector:
    """|0>_anc (x) |a> (x) |b> with ancilla = qubit 0, A = qubits 1..n, B = qubits n+1..2n."""
    dim = 1 << n
    amps = [0j] * (1 << (2 * n + 1))
    for ia in range(dim):
        for ib in range(dim):
            amps[(ia << 1) | (ib << (n + 1))] = complex(a[ia] * b[ib])
    return StateVector(2 * n + 1, amps)


def swap_test_p0(a: Sequence[float], b: Sequence[float], n: int) -> float:
    """Run H - CSWAP^n - H on the ancilla and return P(ancilla = 0) = (1 + |<a|b>|^2) / 2."""
    sv = swap_test_state(a, b, n)
    sv.h(0)
    for i in range(n):
        sv.cswap(0, 1 + i, 1 + n + i)
    sv.h(0)
    return sv.prob(0, 0)


def sample_p0(p0: float, shots: int, seed: int) -> float:
    rng = random.Random(seed)
    return sum(1 for _ in range(shots) if rng.random() < p0) / shots


def jacobi_eigvalsh(m: List[List[float]], tol: float = 1e-12, max_sweeps: int = 60) -> List[float]:
    """Eigenvalues of a real symmetric matrix via cyclic Jacobi rotations."""
    n = len(m)
    a = [row[:] for row in m]
    for _ in range(max_sweeps):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < tol:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-15:
                    continue
                theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
    return sorted(a[i][i] for i in range(n))


def entanglement_entropy(amps: Sequence[float], n_a: int, n_b: int) -> float:
    """Von Neumann entropy (bits) of subsystem A for a *real* pure state on n_a + n_b qubits.

    Index layout: ``idx = ia + (ib << n_a)``. rho_A = M M^T with M[ia][ib] = amps[idx].
    """
    da, db = 1 << n_a, 1 << n_b
    if len(amps) != da * db:
        raise ValueError("amplitude length mismatch")
    M = [[amps[ia + (ib << n_a)] for ib in range(db)] for ia in range(da)]
    rho = [[sum(M[i][k] * M[j][k] for k in range(db)) for j in range(da)] for i in range(da)]
    ev = [max(0.0, v) for v in jacobi_eigvalsh(rho)]
    s = sum(ev)
    return max(0.0, -sum((v / s) * math.log2(v / s) for v in ev if v > 1e-12))
