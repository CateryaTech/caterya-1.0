# Architecture

CATERYA is organised in six layers. Each layer depends only on the ones before it, and every layer above L3 produces **Evidence**.

| # | Layer | Package(s) | Responsibility |
|---|---|---|---|
| L1 | Adapters | `adapters` | Wrap the *system* under assurance (callable, OpenAI-compatible, Anthropic, Hugging Face, mock) behind `generate / predict / explain / run_agent`. Hosted adapters go through an egress-controlled HTTP helper (https only, optional host allow-list, no private IPs unless `allow_local=True`). |
| L2 | Metrics | `metrics`, `quantum` | 34 metrics with formal, hash-bound specs (`MetricSpec`), declared `requires`, parameters, assumptions and limitations. Missing inputs yield *untested*, never a pass. |
| L3 | Evidence & provenance | `provenance`, `core` | `Evidence` records → hash chain → RFC 6962-style Merkle log → signed tree head → bundle. DSSE/in-toto envelopes, salted selective disclosure, anchors. |
| L4 | Assurance | `assurance`, `pillars` | Profiles, risk heuristic, CAR (CATERYA Assurance Record), recommendation, named decisions with separation of duties, levels L0–L4, COS as a derived view. |
| L5 | Continuous assurance | `monitoring`, `guardrails` | Tiered re-evaluation (`pre_release`, `canary`, `post_release`, `drift`, `incident_replay`), PSI/KS/CUSUM, `CATERYAGuardrail`, `EthicsSwarm`, ordered incident loop. |
| L6 | Ledger / DeFi (optional) | `blockchain`, `contracts/` | Anchor registry, assurance gate, evaluator bond, `ProofToken`, content store/IPFS, ZK interface. |

Cross-cutting: `api` (REST + GraphQL), `cli`, `quick` (one-call facade), `telemetry` (Prometheus text, optional OpenTelemetry), `i18n` (en/id), `docgen`.

## Data flow

```
adapter / tabular / traces
        │
        ▼
 EvalContext ──► metric(ctx, params) ──► MetricResult(value | None, n, ci, details, untested, limitations)
        │                                      │
        │                                      ▼
        │                         Evidence(kind="metric", spec_hash, system_hash, dataset_hash, seed, ...)
        │                                      │  append → prev_hash, record_hash, signature
        ▼                                      ▼
 phase-2 metrics (provenance, regulatory,   EvidenceRegistry ── Merkle root ── signed tree head ── anchors
 sustainability need the evidence so far)         │
        │                                          ▼
        └──────────────► CAR (verdicts, coverage, gaps, risk, recommendation, COS view) ──► Evidence(kind="car")
                                                   │
                         named Decider + own key ──┴─► Evidence(kind="decision")  ──► level L0–L4
                                                   │
                                   DSSE attestation + anchor ──► (optional) on-chain gate
```

## Two-phase evaluation

Most metrics only need the inputs (phase 1). Metrics that talk *about the assessment itself* — `provenance_completeness_v1`,
`regulatory_mapping_coverage_v1` (need the evidence gathered so far) and `sustainability_estimate_v1` (needs measured token usage) — run in
phase 2, after phase 1 evidence is sealed.

## Verdicts

`PASS` / `FAIL` against the profile threshold (with a `borderline` flag when the 95% interval straddles it), `UNTESTED`, or `INFO` for
informational metrics that never affect risk, coverage or the recommendation. Small samples are visible: a perfect 10/10 has a Wilson lower
bound well below 1, is marked borderline, and contributes half-weight to the failure share *P* of the risk heuristic.

## Risk heuristic

`R = P × (0.5·I + 0.3·E + 0.2·C)`; *P* = weighted share of failing (+½ borderline) tested metrics; *I, E, C* = impact, exposure, context on 1–5 from
`SystemConfig.risk_context`. Bands: low < 0.1 ≤ moderate < 0.3 ≤ high < 0.6 ≤ critical. It is an **ordinal triage aid, not a probability of harm.**

## Recommendation logic

`INSUFFICIENT_EVIDENCE` if a required metric is untested or coverage < the profile minimum → `RECOMMEND_REJECT` if a required metric fails or the
band is critical → `RECOMMEND_CONDITIONAL` if anything fails or the band is high → otherwise `RECOMMEND_ASSURE`.

## Extension points

* **Metrics**: `@metric(...)` decorator, or the `caterya.metrics` entry-point group (see `examples/04_custom_metric.py`).
* **Adapters**: subclass `ModelAdapter` or use `CallableAdapter`.
* **Anchors**: subclass `provenance.anchors.Anchor` (`anchor`, `verify`, `third_party_verifiable`).
* **Quantum backends**: subclass `quantum.backends.QuantumBackend`.
* **ZK**: implement `blockchain.zk.ZKBackend`.
* **Profiles**: add to `assurance.profiles.PROFILES`.
