# Roadmap and known gaps

Nothing below is a promise or a date. It is the honest list of what is **not** done.

## Known gaps in this release (1.0.0-alpha.1)

* **Persistence**: the API keeps state in memory. Needed: durable registry storage (append-only store + key management) and bundle export on shutdown.
* **Qiskit path** is not exercised by CI. **IPFS (Kubo)** is not tested against a live node. **Hosted adapters** are tested against a local HTTP server only.
* **Python 3.10/3.11 runtime** is covered by the CI matrix but was only syntax-checked locally.
* **Smart contracts**: unaudited; no public-network deployment; no formal verification; no gas benchmarks.
* **Probe sets** are small smoke tests; default thresholds are illustrative (see [VALIDATION_PROTOCOL.md](VALIDATION_PROTOCOL.md)).
* **Independence** for L3/L4 is key-based; organisational independence/accreditation is a governance process, not code.
* **i18n**: English and Indonesian only. **GraphQL** is read-only.
* **Regulatory mapping** is thematic; `ID_AI_ETHICS_2026` needs verification against an official text.

## Candidates (unordered)

* Durable evidence store + REST write path with decider-signed decisions (client-side signing).
* A real ZK backend (e.g. a circuit proving "metric ≥ t" for a committed value) behind `ZKBackend`; until then `SignedThresholdClaim` is the honest option.
* Soulbound (non-transferable) ERC-721 wrapper around `CateryaAssuranceGate` attestations, if token semantics are wanted.
* Decentralised attester selection and dispute resolution for the gate; on-chain verification of Merkle inclusion for evidence disputes.
* Cross-chain gate readers; account-abstraction friendly attest flows.
* Statistical hardening: multiple-testing correction across metrics, sequential testing for canaries, power analysis for probe-set sizes.
* Larger, community-reviewed probe sets per language/domain; red-team adaptive attackers instead of fixed injection probes.
* Hardware-backed keys (HSM/KMS) for evaluator and decider signers; threshold signatures.
* Streaming/OTel integration of monitor runs; Grafana dashboards.
* Promote research metrics to stable only after external review.

## Versioning

Pre-1.0 (alpha): APIs and the evidence spec may change; any change to hashing or the evidence schema bumps `caterya.evidence/vN` and is called out in the
[changelog](../CHANGELOG.md).
