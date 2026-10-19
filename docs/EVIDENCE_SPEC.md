# Evidence specification (`caterya.evidence/v1`)

JSON Schemas are generated into [`schemas/`](../schemas) (`evidence.v1.json`, `bundle.v1.json`, `trace.v1.json`) and validated in the test-suite.

## Canonical encoding and hashing

* Canonical JSON: UTF-8, sorted keys, no insignificant whitespace, `NaN`/`Infinity` rejected, floats rounded to 10 decimals.
* `digest(x) = "sha256:" + hex(SHA-256(canonical_json(x)))`; raw bytes are hashed as-is.

## Evidence record

| field | meaning |
|---|---|
| `kind` | `metric`, `car`, `decision`, `guardrail`, `swarm`, `monitor`, `incident`, `mapping`, `note` |
| `claim` | human-readable statement |
| `metric_id`, `spec_hash` | which metric, and the hash of its *full definition incl. the parameters actually used* |
| `system_hash` | hash of the `SystemConfig` |
| `dataset_hash` | hash over every dataset/tabular payload/trace set/reference the metric consumed (`""` if none) |
| `seed` | evaluation seed |
| `result`, `ci` | metric result (`value=null` ⇒ untested), 95% interval where defined |
| `limitations`, `untested` | stated limitations; reasons the result is a gap |
| `actor`, `timestamp` | signer key id; UTC ISO-8601 |
| `prev_hash` | `record_hash` of the previous record (`sha256:000…0` for the first) |
| `record_hash` | `digest(all fields above)` |
| `evidence_id` | `"ev_" + first 16 hex of record_hash` |
| `signature` | `{alg, key_id, sig}` over the 32 raw hash bytes |

## Chain, log, tree head

* **Chain**: each record commits to its predecessor; deleting, reordering or editing any record breaks verification.
* **Merkle log** (RFC 6962 / RFC 9162 hashing): leaf = `SHA-256(0x00 ‖ record_hash_bytes)`, node = `SHA-256(0x01 ‖ left ‖ right)`.
  `EvidenceRegistry.proof(id)` returns an inclusion proof verified by the RFC 9162 §2.1.3.2 algorithm.
* **Signed tree head**: `{size, root, timestamp}` signed by the registry key. `root_at(size)` recomputes an older root so an old anchor can be
  checked against the grown log.
* **Bundle** (`caterya.bundle/v1`): `{keyring, evidence[], tree_head, anchors[]}`. `verify_bundle(bundle, trusted=None)` needs **no private keys**.
  Without a `trusted` keyring it proves *integrity and self-consistency* only; pass your own keyring to bind it to *who* signed
  (`keys_trusted=True` only if every signing key is in it).

## Signatures

* `Ed25519` (extra `crypto`) — asymmetric, third-party verifiable.
* `HMAC-SHA256-DEV` — symmetric, **development only** (verifier can forge); caps the assurance level at 1.

## Attestations

DSSE envelope (`payloadType = application/vnd.in-toto+json`) around an in-toto Statement v1 with `predicateType = https://caterya.tech/assurance/v1`;
the predicate carries the decision, `valid_until`, the CAR hash, profile, coverage and the standard disclaimer.

## Selective disclosure

`SelectiveDisclosure(fields)` publishes one Merkle root over salted per-field commitments; a field is later revealed with value, salt and inclusion
proof. Hiding and binding under SHA-256 — **not** zero-knowledge.

## CAR — CATERYA Assurance Record (`caterya.car/v1`)

System identity, profile, evidence ids and the evidence Merkle root *at the time*, coverage vs minimum, required-untested/failed lists, per-metric
verdicts with thresholds and borderline flags, gaps with reasons, risk, recommendation, the derived COS view and the disclaimer. Sealed as
`Evidence(kind="car")`.
