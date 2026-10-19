# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Versions follow PEP 440 (`1.0.0a1` = 1.0.0-alpha.1).

## [1.0.0a1] — 2026-10-15
Initial release.

### Added
* Evidence model (`caterya.evidence/v1`): canonical hashing, hash chain, RFC 6962-style Merkle log, signed tree heads, portable bundles, DSSE/in-toto, salted selective disclosure, anchors.
* 34 metrics (fairness, Golden-Triangle, robustness, safety/privacy/security, reliability, agentic, provenance, regulatory coverage, sustainability estimate, 3 quantum research metrics, 2 guardrail metrics) with hash-bound specs.
* Profiles, CAR, risk heuristic, recommendation logic, named decisions with overrides, standing authorizations, assurance levels L0–L4, reproduction.
* Continuous monitor (5 modes), drift (PSI/KS/CUSUM), `CATERYAGuardrail`, `EthicsSwarm` (with veto), ordered `IncidentLoop`.
* Quantum research layer: pure-Python simulator, swap test, entanglement entropy, opt-in PennyLane/Qiskit backends with no silent fallback.
* Blockchain/DeFi: `CateryaAnchorRegistry`, `CateryaAssuranceGate`, `CateryaEvaluatorBond`, example `AssuranceGatedPool`, EVM clients, `ProofToken`, content store, IPFS (Kubo) client, honest ZK interface.
* REST + GraphQL API, CLI, one-call `CATERYAEvaluator` facade, Prometheus/OTel telemetry, en/id i18n, generated docs and JSON Schemas.

### Known gaps
See `docs/ROADMAP.md`.
