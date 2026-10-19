# Blockchain / DeFi layer (optional)

**Status:** Solidity sources compile with solc 0.8.26 and behave as specified on an **in-process EVM** (eth-tester) — see
`tests/test_blockchain_defi.py`. They are **unaudited**, have **not** been deployed to any public network, and must not hold value before an
independent audit. Nothing here is financial advice and **no token is issued**.

## Why a ledger at all

An evidence bundle is already tamper-evident and signed. A public ledger adds two things CATERYA cannot provide alone:

1. **Timestamp / non-equivocation**: an operator cannot later present a different history for a root that was already anchored.
2. **Machine-readable assurance for other contracts**: a DeFi protocol can refuse to let an AI "manager" act unless it holds a valid attestation.

## Contracts (`contracts/`, no external dependencies)

| Contract | Purpose | Trust assumptions |
|---|---|---|
| `CateryaAnchorRegistry` | Append-only log of `(root, size, timestamp, by, uri)`; `isAnchored(root)`. Only owner-approved *anchorers* can write. | Anchorer set is governance-controlled; the chain proves *time of anchoring* only. |
| `CateryaAssuranceGate` | `attest(systemHash, level ≤ 4, carHash, expiresAt)` by approved *attesters*; `revoke` by the issuing attester or owner; `isAssured(systemHash, minLevel)` is true only if not revoked, not expired, level sufficient **and the attester is still approved**. | **Whoever the owner approves as attester is trusted** to publish honest levels. This is the oracle problem; see below. |
| `CateryaEvaluatorBond` | Evaluators stake the native currency, withdraw after a delay, can be slashed by an **arbiter** (to a treasury) with an evidence hash. Re-entrancy guarded; checks-effects-interactions. | The arbiter is a *trusted* role; slashing is governance, not trustless. |
| `ICateryaAssuranceGate` | The one-function interface consumers call. | — |
| `examples/AssuranceGatedPool` | Illustration: a pool that only lets a manager system act while `isAssured(…, minLevel)`, re-checked on **every call**. | Illustration only. |

`Owned2Step` provides two-step ownership transfer. Use a multisig (and ideally a timelock) as owner in any real deployment.

## End-to-end flow (`examples/08_onchain_gate.py`)

```
engine.evaluate → engine.reproduce → engine.decide (named human, own key) → registry.anchor(EVMAnchor) → engine.level
        → AssuranceGateClient.attest_from_decision(report, decision, level)   # expiry = decision.valid_until
        → consumer contract: gate.isAssured(systemHash, 3)                    # revocation/expiry bite immediately
```

`systemHash` on-chain is `SystemConfig.hash()`; `carHash` is the CAR evidence `record_hash`; anyone can fetch the off-chain bundle (URI in the anchor)
and check the on-chain level against the evidence.

## Python clients (`pip install "caterya[web3]"`)

* `EVMAnchor(contract, w3=… | rpc_url=…, account=… | private-key env)` — an `Anchor` with `third_party_verifiable = True`; unlocks L4.
* `AssuranceGateClient` — `attest`, `attest_from_decision`, `revoke`, `is_assured`, `get`.
* `EvaluatorBondClient` — `deposit`, `is_bonded`.
* **Keys**: a private key is read **only** from `CATERYA_EVM_PRIVATE_KEY` (or the env var you name). It is never accepted as an argument, logged, or stored.
  For local chains pass an unlocked `account`.

## Off-chain helpers

* **`ProofToken`** — `ctok1.<payload>.<signature>`: a compact signed claim *"system S holds level L (CAR C) until T"*, verifiable offline against a
  keyring, with expiry, minimum-level and system-binding checks. For gateways/keepers that cannot afford an RPC call per request.
* **`ContentStore`** — local content-addressed store (`sha256:…`), re-hashing on read. **`IPFSKuboClient`** — Kubo HTTP RPC pin/cat, **untested against a live node**.
* **`SignedThresholdClaim`** — "metric ≥ threshold" signed by the evaluator; hides the value, **is not zero-knowledge**, and is only as trustworthy as the signer.
* **`ZKBackend`** — interface only. `UnavailableZK` raises `BackendUnavailable`. There is **no ZK prover** in this repository.

## The oracle problem (read this)

The chain cannot know whether a level is *true*. `isAssured` is exactly as trustworthy as the governance that approves attesters and the
evidence behind each attestation. Mitigations built in: levels are process-depth (not "safe"), attestations expire, attesters can be de-listed
(which invalidates their attestations), revocation is immediate, evaluators can be bonded, and the off-chain evidence is independently verifiable.
Mitigations *not* built in: decentralised attester selection, dispute resolution, on-chain evidence verification.

## Deployment checklist

1. Independent audit of all contracts. 2. Owner = multisig + timelock. 3. Testnet dry-run with `scripts/deploy_contracts.py` (key via env var).
4. Publish the attester admission policy ([`governance/ACCREDITATION.md`](../governance/ACCREDITATION.md)). 5. Decide expiry/renewal and revocation procedures.
6. Rehearse the incident loop → on-chain `revoke`. 7. Confirm legal/regulatory treatment of the bond mechanism in your jurisdiction.

## Reproducing the contract build

```bash
cd contracts && npm install && node scripts/compile.js --bytecode artifacts/contracts.json   # also refreshes src/caterya/blockchain/abi/*.json
```
CI recompiles and fails if the committed artifacts drift.
