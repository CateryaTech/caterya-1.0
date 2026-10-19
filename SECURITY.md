# Security policy

## Reporting a vulnerability
Please **do not** open a public issue. Use GitHub's *Report a vulnerability* (private advisory) on this repository, or email **aryhharyanto@proton.me** with
"CATERYA security" in the subject. Include affected version, reproduction steps and impact. We aim to acknowledge within 7 days; this is a small alpha project, so
timelines are best-effort.

## Scope
In scope: evidence/signature/Merkle verification flaws, key handling, SSRF/egress bypass in adapters, API authentication/validation, level/separation-of-duty bypasses,
the Solidity contracts. Out of scope: findings that require `allow_local=True` or the dev HMAC signer to be used as documented; denial of service via unbounded
client load on an unauthenticated demo server; the quality of the built-in probe sets.

## Supported versions
Only the latest `1.0.0a*`. Pre-1.0 APIs and the evidence spec may change.

## Cryptography and keys
* Production use requires `cryptography` (Ed25519). The HMAC signer is development-only and caps assurance at level 1.
* Private keys are read from environment variables or 0600 files, never printed or logged. Use an HSM/KMS for real deployments.

## Smart contracts
The contracts are **unaudited reference implementations**. Do not deploy them where they secure value without an independent audit.
