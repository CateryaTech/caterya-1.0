"""Quantum backends with explicit capability flags. There is NO silent fallback.

* ``classical-statevector`` — built-in pure-Python simulator (always available, deterministic).
* ``pennylane`` / ``qiskit`` — optional; raise ``BackendUnavailable`` if not installed.

The swap test measures ``|<a|b>|^2`` between two amplitude-encoded distributions:
``P(0) = (1 + |<a|b>|^2) / 2``. We report the resulting fidelity estimate together with the
backend name, version, shots and a circuit hash so that the evidence is reproducible.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence

from ..core.canonical import digest
from ..core.errors import BackendUnavailable
from .statevector import amplitude_encode, sample_p0, swap_test_p0


def _qubits_for(*vecs: Sequence[float]) -> int:
    longest = max(len(v) for v in vecs)
    return max(1, math.ceil(math.log2(max(2, longest))))


class QuantumBackend:
    name = "abstract"
    capabilities: frozenset = frozenset()

    def version(self) -> str:  # pragma: no cover
        return "0"

    def swap_test_fidelity(self, a: Sequence[float], b: Sequence[float], shots: Optional[int] = None, seed: int = 0) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def _record(self, a, b, n, p0, shots, seed) -> Dict[str, Any]:
        fid = max(0.0, min(1.0, 2 * p0 - 1))
        circuit = {"circuit": "swap_test", "n_qubits_per_register": n, "a": [round(x, 10) for x in a], "b": [round(x, 10) for x in b]}
        return {
            "fidelity": fid,
            "p0": p0,
            "backend": self.name,
            "backend_version": self.version(),
            "shots": shots,
            "seed": seed if shots else None,
            "circuit_hash": digest(circuit),
            "exact": shots is None,
        }


class ClassicalStatevectorBackend(QuantumBackend):
    name = "classical-statevector"
    capabilities = frozenset({"statevector", "shots", "deterministic"})

    def version(self) -> str:
        return "builtin-1"

    def swap_test_fidelity(self, a, b, shots=None, seed=0):
        n = _qubits_for(a, b)
        ea, eb = amplitude_encode(a, n), amplitude_encode(b, n)
        p0 = swap_test_p0(ea, eb, n)
        if shots:
            p0 = sample_p0(p0, shots, seed)
        return self._record(ea, eb, n, p0, shots, seed)


class PennyLaneBackend(QuantumBackend):
    name = "pennylane"
    capabilities = frozenset({"statevector", "shots", "noise-plugins"})

    def __init__(self, device: str = "default.qubit"):
        try:
            import pennylane as qml  # noqa: F401
        except Exception as e:  # pragma: no cover
            raise BackendUnavailable("PennyLane not installed: pip install 'caterya[quantum-backends]'") from e
        self._qml = qml
        self.device = device

    def version(self) -> str:
        return str(self._qml.__version__)

    def swap_test_fidelity(self, a, b, shots=None, seed=0):
        qml = self._qml
        n = _qubits_for(a, b)
        ea, eb = amplitude_encode(a, n), amplitude_encode(b, n)
        wires_a = list(range(1, n + 1))
        wires_b = list(range(n + 1, 2 * n + 1))
        dev = qml.device(self.device, wires=2 * n + 1, shots=shots, seed=seed) if shots else qml.device(self.device, wires=2 * n + 1)

        @qml.qnode(dev)
        def circuit():
            qml.AmplitudeEmbedding(ea, wires=wires_a, normalize=False)
            qml.AmplitudeEmbedding(eb, wires=wires_b, normalize=False)
            qml.Hadamard(wires=0)
            for wa, wb in zip(wires_a, wires_b):
                qml.CSWAP(wires=[0, wa, wb])
            qml.Hadamard(wires=0)
            return qml.probs(wires=0)

        p0 = float(circuit()[0])
        return self._record(ea, eb, n, p0, shots, seed)


class QiskitBackend(QuantumBackend):
    name = "qiskit"
    capabilities = frozenset({"statevector", "shots", "noise-models", "hardware-via-provider"})

    def __init__(self):
        try:
            import qiskit
            from qiskit_aer import AerSimulator  # noqa: F401
        except Exception as e:  # pragma: no cover
            raise BackendUnavailable("Qiskit/Aer not installed: pip install 'caterya[quantum-backends]'") from e
        self._qiskit = qiskit

    def version(self) -> str:
        return str(self._qiskit.__version__)

    def swap_test_fidelity(self, a, b, shots=None, seed=0):  # pragma: no cover - needs qiskit
        from qiskit import QuantumCircuit, transpile
        from qiskit_aer import AerSimulator

        n = _qubits_for(a, b)
        ea, eb = amplitude_encode(a, n), amplitude_encode(b, n)
        qc = QuantumCircuit(2 * n + 1, 1)
        qc.initialize(ea, list(range(1, n + 1)))
        qc.initialize(eb, list(range(n + 1, 2 * n + 1)))
        qc.h(0)
        for i in range(n):
            qc.cswap(0, 1 + i, 1 + n + i)
        qc.h(0)
        qc.measure(0, 0)
        sim = AerSimulator(seed_simulator=seed)
        shots_eff = shots or 8192
        counts = sim.run(transpile(qc, sim), shots=shots_eff).result().get_counts()
        p0 = counts.get("0", 0) / shots_eff
        return self._record(ea, eb, n, p0, shots_eff, seed)


_BACKENDS = {"classical": ClassicalStatevectorBackend, "classical-statevector": ClassicalStatevectorBackend,
             "pennylane": PennyLaneBackend, "qiskit": QiskitBackend}


def get_backend(name: str = "classical", **kw: Any) -> QuantumBackend:
    if name not in _BACKENDS:
        raise BackendUnavailable(f"unknown quantum backend {name!r}; choose from {sorted(set(_BACKENDS))}")
    return _BACKENDS[name](**kw)
