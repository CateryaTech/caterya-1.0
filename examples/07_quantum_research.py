"""Research-maturity quantum measures. Classical statevector by default; PennyLane/Qiskit are opt-in and never silently substituted."""

from caterya.quantum.backends import get_backend
from caterya.quantum.metrics import distribution_entanglement_entropy, quantum_symmetry

a, b = [0.4, 0.3, 0.2, 0.1], [0.1, 0.2, 0.3, 0.4]
be = get_backend("classical")
print("exact swap-test fidelity :", round(be.swap_test_fidelity(a, b)["fidelity"], 6))
print("20k-shot estimate        :", round(be.swap_test_fidelity(a, b, shots=20000, seed=1)["fidelity"], 3))
print("symmetry across 3 groups :", round(quantum_symmetry({"A": a, "B": a, "C": b})["index"], 4))
print("entanglement entropy     : correlated =", round(distribution_entanglement_entropy([[.5, 0], [0, .5]]), 3), "bits, independent =",
      round(distribution_entanglement_entropy([[.25, .25], [.25, .25]]), 3), "bits")
try:
    print("pennylane:", round(get_backend("pennylane").swap_test_fidelity(a, b)["fidelity"], 6))
except Exception as e:  # BackendUnavailable if the extra isn't installed
    print("pennylane: unavailable ->", type(e).__name__, "(install caterya[quantum-backends])")
