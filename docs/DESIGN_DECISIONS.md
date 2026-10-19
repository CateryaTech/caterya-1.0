# Design decisions

1. **Evidence over scores.** A number without provenance cannot be audited. The unit of output is a signed, hash-chained record; any score (COS) is a view.
2. **Untested ≠ passed.** A gap lowers coverage and can force `INSUFFICIENT_EVIDENCE`. Crashes, missing inputs, unavailable backends and groups below the
   minimum size all land in the same visible place.
3. **Human decision, machine recommendation.** The engine recommends; a named person with their own key decides; contradicting the recommendation needs a
   written override. Automated holds exist only under a signed, scoped, expiring standing authorization.
4. **Levels measure process, not safety.** Depth and independence of the process are checkable; "safe" is not.
5. **Key separation as the checkable form of independence.** Evaluator, decider and owner keys must differ for L3; organisational independence is out-of-band.
6. **Stdlib-only core.** Evaluation, evidence, Merkle logs, the quantum simulator, guardrails, monitoring and the CLI run with no third-party packages; crypto,
   API, web3, telemetry and heavy quantum/ML backends are opt-in. Without `cryptography` a dev-only HMAC signer is used *loudly* and capped at L1.
7. **No silent substitution.** A requested backend either works or becomes a visible gap. We never fall back to something else and report it as the requested thing.
8. **Spec-bound evidence.** `spec_hash` covers the metric definition *and the parameters actually used*; changing a threshold-relevant parameter changes the hash.
9. **Thresholds are profile policy, not metric facts.** Metrics report values; profiles decide pass/fail. `INFO` metrics never affect verdicts.
10. **Small samples are visible.** Wilson/bootstrap intervals; `borderline` verdicts; half-weight in the risk heuristic.
11. **Privacy by hash.** Guardrail/swarm evidence stores output hashes, not text. Selective disclosure is salted.
12. **Ledger as an optional witness.** Evidence stays off-chain; the chain contributes timestamps and a machine-readable gate. The oracle problem is stated, not hidden.
13. **No tokens.** Attestations are records, not assets. The bond uses native currency and a trusted arbiter, and says so.
14. **Honesty is a feature.** Claims ledger, maturity table, explicit non-claims, generated docs that tests keep in sync with the code.
