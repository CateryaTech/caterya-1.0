# Guardrails, swarm, monitoring, incidents

## Principle

Guardrails **recommend**. They never silently block. An automated `held` outcome exists only if a human decider pre-signed a
`StandingAuthorization` that permits that action in that scope and the signature verifies against the registry keyring.

## `CATERYAGuardrail`

* `mode="heuristic"`: PII (email, phone, 16-digit national-ID-like numbers, Luhn-valid card numbers), configured deny terms, indirect-injection
  phrases in the supplied context.
* `mode="full"`: additionally asks an adapter to act as a policy judge. If the judge errors the result is **`UNTESTED`, never `PASS`**.
* Decisions: `PASS`, `REMEDIATE` (medium findings), `FAIL` (high findings), `UNTESTED` (empty output / judge unavailable).
* Every check is sealed as `Evidence(kind="guardrail")`. **Only a hash of the output is stored**, never the text.
* `guard.wrap(fn, extract=...)` wraps any callable (LangGraph node, CrewAI callback) and annotates dict results with `caterya_guard`; it never
  alters or blocks the original result. No framework dependency is required.

## `EthicsSwarm`

Independent voters return acceptability in `[0,1]`. Consensus is a majority vote, **except** that a rejection by a *veto* voter (default:
`privacy`, `safety`) forces `REJECT`. Agreement, dissent and voter errors are sealed as Evidence; `swarm_consensus_v1` aggregates agreement
(agreement is not correctness).

## `ContinuousMonitor`

| mode | profile | depth | purpose |
|---|---|---|---|
| `pre_release` | caller's | full | gate a candidate |
| `canary` | `CATERYA-MONITOR` | light | early signal on a small slice |
| `post_release` | `CATERYA-MONITOR` | light | routine checks |
| `drift` | `CATERYA-MONITOR` | light | distribution shift (PSI/KS; CUSUM helper in `monitoring.drift`) |
| `incident_replay` | caller's | full | re-evaluate after an incident |

Each run seals a `monitor` Evidence with pass-rate, per-metric deltas against the previous run, and `needs_incident_replay`
(a required metric failed, or a canary/post-release pass-rate fell below `canary_min_pass`).

## `IncidentLoop`

`DETECTED → TRIAGED → CONTAINED → REPLAYED → REMEDIATED → VERIFIED → CLOSED`. Stages cannot be skipped, reordered or repeated; every
transition needs a named actor; `REPLAYED` and `VERIFIED` require evidence references. Each transition is sealed as Evidence.
