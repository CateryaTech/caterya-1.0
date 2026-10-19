# Assurance levels

Levels describe the **depth and independence of the assurance process**. They say nothing about whether the system is safe.

| Level | Criteria (all must hold) |
|---|---|
| **L0 Unverified** | No verifiable evidence, or the chain/signatures fail verification (a tampered registry drops to L0). |
| **L1 Self-assessed** | Chain and signatures verify and at least one metric was tested. |
| **L2 Evidence-backed** | L1 **and** every signature is asymmetric (Ed25519) **and** weighted coverage ≥ the profile minimum **and** no required metric is untested **and** the evaluation was **reproduced** (`engine.reproduce`) with no mismatches. |
| **L3 Independently evaluated and decided** | L2 **and** a verifiable *named* decision (`ASSURED` / `CONDITIONALLY_ASSURED`) signed with the decider's **own asymmetric key**, where the decider key ≠ every evaluator key and neither is a declared *system-owner* key. |
| **L4 Independently attested and anchored** | L3 **and** a DSSE attestation referencing this CAR, signed by a key in your **accreditation keyring**, **and** a **third-party-verifiable anchor** (e.g. EVM) whose root equals the log's root at that size and covers the decision. |

`engine.level(report, reproduced=..., decision=..., attestation=..., accredited=..., owner_key_ids=..., anchors=...)` returns the level, the reasons,
and the exact **blockers** for the next level.

## What "independent" means here

Independence is checked **by key separation**: evaluator, decider and owner use different keys. Whether those keys belong to genuinely separate
*organisations* cannot be proven in code; that is established out-of-band (see [`governance/ACCREDITATION.md`](../governance/ACCREDITATION.md)).
The local demo generates every key on one machine, so its "L3" demonstrates the mechanism, not real independence.

## Decisions

`DECISIONS = ASSURED | CONDITIONALLY_ASSURED | REJECTED | DEFERRED`. A decision requires a named decider and role and a written rationale.
A positive decision that contradicts `RECOMMEND_REJECT` or `INSUFFICIENT_EVIDENCE` additionally requires an `override_reason`. The decider signs
the decision body with their own key; the registry then seals it as `Evidence(kind="decision")` with a `valid_until` (default 90 days).

## Standing authorizations

A decider may pre-sign a `StandingAuthorization` permitting *automated holds/throttles/rollbacks* in one scope for a limited time. Approvals can never
be pre-authorised. Guardrails only enact a hold when such an authorization verifies against the keyring.
