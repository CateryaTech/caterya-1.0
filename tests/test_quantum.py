import math

import pytest

from caterya.core.errors import BackendUnavailable
from caterya.quantum.backends import get_backend
from caterya.quantum.metrics import distribution_entanglement_entropy, quantum_symmetry
from caterya.quantum.statevector import amplitude_encode


def analytic(a, b):
    n = max(1, math.ceil(math.log2(max(len(a), len(b)))))
    return sum(x * y for x, y in zip(amplitude_encode(a, n), amplitude_encode(b, n))) ** 2


def test_swap_test_identical_orthogonal_and_analytic():
    b = get_backend("classical")
    assert b.swap_test_fidelity([.5, .5, 0, 0], [.5, .5, 0, 0])["fidelity"] == pytest.approx(1.0)
    assert b.swap_test_fidelity([.5, .5, 0, 0], [0, 0, .5, .5])["fidelity"] == pytest.approx(0.0, abs=1e-12)
    d, e = [.4, .3, .2, .1], [.1, .2, .3, .4]
    assert b.swap_test_fidelity(d, e)["fidelity"] == pytest.approx(analytic(d, e), abs=1e-10)


def test_shots_converge_and_are_seeded():
    b = get_backend("classical")
    d, e = [.4, .3, .2, .1], [.1, .2, .3, .4]
    r1 = b.swap_test_fidelity(d, e, shots=20000, seed=5)
    r2 = b.swap_test_fidelity(d, e, shots=20000, seed=5)
    assert r1["fidelity"] == r2["fidelity"] and abs(r1["fidelity"] - analytic(d, e)) < 0.05 and r1["exact"] is False


def test_circuit_hash_depends_on_inputs():
    b = get_backend("classical")
    assert b.swap_test_fidelity([1, 2], [2, 1])["circuit_hash"] != b.swap_test_fidelity([1, 2], [1, 2])["circuit_hash"]


def test_symmetry_index_min_over_pairs():
    res = quantum_symmetry({"A": [.4, .3, .2, .1], "B": [.4, .3, .2, .1], "C": [.1, .2, .3, .4]})
    assert res["index"] == pytest.approx(analytic([.4, .3, .2, .1], [.1, .2, .3, .4]), abs=1e-10)


def test_entanglement_entropy():
    assert distribution_entanglement_entropy([[.5, 0], [0, .5]]) == pytest.approx(1.0, abs=1e-9)  # maximally correlated
    assert distribution_entanglement_entropy([[.25, .25], [.25, .25]]) == pytest.approx(0.0, abs=1e-9)  # independent


def test_no_silent_fallback():
    with pytest.raises(BackendUnavailable):
        get_backend("does-not-exist")
    try:
        import qiskit  # noqa: F401
    except Exception:
        with pytest.raises(BackendUnavailable):
            get_backend("qiskit")


def test_pennylane_matches_builtin_if_installed():
    pytest.importorskip("pennylane")
    d, e = [.4, .3, .2, .1], [.1, .2, .3, .4]
    assert get_backend("pennylane").swap_test_fidelity(d, e)["fidelity"] == pytest.approx(get_backend("classical").swap_test_fidelity(d, e)["fidelity"], abs=1e-9)
