# Threat model (summary)

| Threat | Mitigation | Residual |
|---|---|---|
| Operator edits/deletes/reorders evidence after the fact | Hash chain + Merkle log + signed tree head; third-party verifiable bundle; external anchor | An operator who never publishes the bundle/anchor can still withhold evidence. |
| Operator presents different histories to different parties (equivocation) | Anchor roots publicly (EVM) and compare `root_at(size)` | Needs the anchor to be checked by someone. |
| Forged evidence signed by an unknown key | Keyring verification; `keys_trusted` only if every signer is in *your* keyring | A bundle's own keyring proves consistency, not identity. |
| Evaluator = owner = decider (no independence) | L3 requires distinct evaluator/decider/owner keys | Key distinctness ≠ organisational independence. |
| Weak signer in production | HMAC dev signer capped at L1 and warns loudly | Operator can still choose to ignore warnings at L1. |
| Probe-set gaming / metric Goodhart | Dataset hashes recorded; replace probe sets; validation protocol | Fixed probes can be memorised by a determined vendor. |
| Prompt injection against a judge/guardrail | Judge errors → `UNTESTED`; heuristic mode available; swarm veto | LLM judges remain attackable. |
| SSRF / data exfiltration through adapters | https-only, no private IPs unless opted in, host allow-list env | `allow_local=True` widens reach by design. |
| Private-key leakage | Keys only from env/files with 0600; never printed/logged; `keygen` refuses overwrite | Key custody is the operator's problem (use HSM/KMS). |
| Over-trust in an on-chain level | Levels are process-depth; expiry; revocation; attester de-listing; bond | Attester governance is the trust root. |
| Smart-contract bugs | Minimal, dependency-free, access-controlled, custom errors, tests on an EVM | **Unaudited.** |
| Denial of service on the API | Request-size caps, optional API key | No rate limiting in-process; put a gateway in front. |
| Sensitive text in evidence | Only output hashes stored for guardrail/swarm | Metric `details` may include prompts you supply; review before publishing bundles. |

Report vulnerabilities per [SECURITY.md](../SECURITY.md).
