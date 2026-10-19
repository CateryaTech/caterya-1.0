# Attester accreditation (for assurance level 4 and on-chain gates)

"Accredited" means: *you* (the relying party) have decided to trust this key to attest. CATERYA only checks the signature against **your** accreditation keyring; it does
not decide who deserves trust. This document is a **template policy** — adapt it, publish it, and keep the list.

## Minimum criteria for an attester

1. **Identity**: a legal entity or named accountable body, with a public contact and a published signing key id.
2. **Independence**: no ownership or control relationship with the assessed system's owner; declared conflicts recorded in the attestation process.
3. **Competence**: documented methodology following `docs/VALIDATION_PROTOCOL.md`; named, qualified decision-makers.
4. **Key management**: Ed25519 keys held in an HSM/KMS or equivalent; separate keys for evaluators and deciders; documented rotation and revocation.
5. **Transparency**: evidence bundles for each attestation are published (or escrowed) and anchored; the attester's decisions can be re-verified.
6. **Accountability**: bonded (see `CateryaEvaluatorBond`) or insured, with a published dispute and slashing/arbitration procedure.
7. **Review cycle**: re-accreditation at least annually or after any upheld complaint; immediate suspension on credible evidence of a false attestation.

## Operating the list

* Keep the accreditation keyring under change control (reviewed, signed commits).
* On-chain: add the attester only after the above, via the contract owner (multisig + timelock). De-listing invalidates that attester's attestations immediately.
* Publish: who is accredited, since when, scope (profiles/sectors), and the revocation log.

## What accreditation does not mean

It is not a statement that any assessed system is safe, lawful or fit for purpose, and it is not a regulatory licence.
