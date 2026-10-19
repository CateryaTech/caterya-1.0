# Quantum (research layer)

**Status: research. No quantum advantage is claimed. These are instruments, not verdicts.**

## What is implemented

* **Swap test** between two amplitude-encoded distributions `a`, `b`: `P(ancilla = 0) = (1 + |⟨a|b⟩|²)/2`, so fidelity `F = 2·P(0) − 1`.
  Amplitude encoding uses `√p` normalised to unit L2 norm (zero-padded to `2ⁿ`).
* **`quantum_symmetry_index_v1`** — minimum pairwise swap-test fidelity between groups' score histograms (1 = identical distributions).
* **`quantum_fidelity_v1`** — fidelity between a reference and the current score histogram (a drift cousin of PSI).
* **`quantum_entanglement_entropy_v1`** — `1 − S/S_max`, where `S` is the entanglement entropy of the amplitude-encoded joint (group × score-bin)
  distribution. A product (independent) distribution has `S = 0`, so a high value means *the score distribution does not depend on group*.

## Backends (explicit, never substituted)

| Backend | Install | Notes |
|---|---|---|
| `classical` (`classical-statevector`) | built in | Pure-Python state-vector simulator (≤14 qubits), deterministic, exact or shot-sampled with a seed. |
| `pennylane` | `caterya[quantum-backends]` | `default.qubit`; cross-checked against the built-in simulator to ~1e-15 in our environment. |
| `qiskit` | `caterya[quantum-backends]` | Aer simulator. **The code path is not exercised by CI** (only the "unavailable ⇒ error" behaviour is). |

Select with `params={"quantum_symmetry_index_v1": {"backend": "pennylane", "shots": 4096}}`. If the backend is missing the metric becomes an
`UNTESTED` gap with a `BackendUnavailable` reason — it does **not** quietly fall back to the classical simulator. Every result records backend,
backend version, shots, seed and a circuit hash.

## Honest limitations

* Histogram summaries discard information; small groups give noisy distributions (minimum group size is enforced).
* A swap test of classical histograms computes a quantity that is trivially available classically (`Σ√pᵢ√qᵢ`); the quantum framing is a
  research vehicle for hardware/noise studies, not a more powerful metric.
* Variational quantum-circuit training and "quantum supremacy" style claims are **out of scope** here.
* Ethical-physics analogies (energy, curvature) are not promoted to metrics without a validation protocol
  ([VALIDATION_PROTOCOL.md](VALIDATION_PROTOCOL.md)).

CLI: `caterya quantum --a 0.4,0.3,0.2,0.1 --b 0.1,0.2,0.3,0.4 [--backend pennylane] [--shots 20000]`.
