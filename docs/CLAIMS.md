# Claims ledger

Every claim this project makes about itself, and the command that verifies it. If a claim is not here, treat it as **not claimed**.
Run everything with `pytest` (full environment: `pip install -e ".[dev,all]"`).

| # | Claim | Verified by |
|---|---|---|
| 1 | Editing, deleting or re-ordering evidence is detected; signature forgery is detected | `tests/test_core_provenance.py::test_chain_verifies_and_detects_tamper`, `::test_chain_detects_deletion_and_reorder`, `::test_signature_forgery_detected`, `::test_tree_head_signature_checked` |
| 2 | Merkle inclusion proofs verify for every leaf of every tree size 1–17 and reject wrong leaves | `::test_merkle_inclusion_all_sizes` |
| 3 | Bundles verify offline without private keys; "trusted keys" is only true when every signer is in your keyring | `::test_bundle_roundtrip_and_trusted_keys`, `::test_ed25519_signatures_are_asymmetric_and_verifiable_with_public_key_only` |
| 4 | Each metric detects the flaw it claims to detect (and passes a healthy system) | `tests/test_metrics.py::test_generative_metric_detects_its_flaw`, `::test_agent_metrics_detect_flaws`, `::test_demographic_parity_and_equalized_odds`, `::test_entropy_dispersion_and_calibration`, `::test_drift_psi_detects_shift`, `::test_quantum_metrics`, `::test_lyapunov_measures_growth_of_divergence_with_perturbation_size` |
| 5 | "Untested ≠ passed": missing inputs, crashes, unavailable backends and tiny groups become gaps | `tests/test_engine_governance.py::test_missing_inputs_are_gaps_not_passes`, `::test_crashing_metric_becomes_visible_gap_not_a_pass`; `tests/test_metrics.py::test_small_groups_are_suppressed_not_averaged`, `::test_requested_unavailable_quantum_backend_becomes_visible_gap` |
| 6 | Evidence binds metric definition+parameters, system and dataset | `::test_every_metric_is_sealed_with_spec_dataset_system_binding`, `::test_parameter_change_changes_spec_hash_and_dataset_change_changes_dataset_hash` |
| 7 | Reproduction passes for deterministic systems and flags non-deterministic ones | `::test_reproduction_ok_for_deterministic_and_flags_nondeterministic` |
| 8 | A named decider, rationale and (for contradicting a recommendation) an override are required; decisions are tamper-evident | `::test_decision_requires_named_decider_rationale_and_override`, `::test_decision_tamper_is_detected` |
| 9 | Levels: L0–L4 progression; separation of duties; owner-key independence; dev HMAC signer capped at L1; tampering drops to L0 | `::test_level_progression_l0_to_l4`, `::test_l4_needs_third_party_anchor_and_matching_attestation`, `::test_l3_blocked_without_separation_of_duties`, `::test_l3_blocked_when_keys_belong_to_owner`, `::test_rejected_decision_never_reaches_l3`, `::test_dev_hmac_signer_caps_level_at_1`, `::test_tamper_drops_level_to_zero` |
| 10 | Guardrails never hold without a valid signed standing authorization; judge errors are `UNTESTED`; only output hashes are stored | `tests/test_guardrails_monitoring.py::test_hold_only_with_valid_standing_authorization`, `::test_full_mode_judge_error_is_untested_not_pass`, `::test_guardrail_recommends_and_seals_hash_not_text`, `::test_wrap_does_not_alter_or_block_result` |
| 11 | Swarm: privacy/safety veto; voter errors recorded | `::test_swarm_veto_and_evidence`, `::test_swarm_voter_error_is_recorded_as_untested` |
| 12 | Incident loop enforces order, actor and evidence references | `::test_incident_loop_enforces_order_actor_and_evidence` |
| 13 | Swap-test fidelity equals the analytic value; shots converge and are seeded; PennyLane agrees (when installed) | `tests/test_quantum.py` |
| 14 | No silent backend substitution | `tests/test_quantum.py::test_no_silent_fallback`; `tests/test_metrics.py::test_requested_unavailable_quantum_backend_becomes_visible_gap` |
| 15 | Solidity contracts behave as specified on an in-process EVM (access control, levels, revocation, expiry, bond/slash/withdraw delay, consumer contract) | `tests/test_blockchain_defi.py` (skipped if `web3`/`eth-tester` are absent) |
| 16 | `ProofToken` rejects expiry, low level, wrong system, forgery, unknown issuer | `::test_proof_token_roundtrip_expiry_level_and_system_binding` |
| 17 | There is no ZK prover; the threshold claim is not ZK and refuses to sign a false claim | `::test_zk_is_honestly_unavailable_and_threshold_claim_is_not_zk` |
| 18 | Egress control: https-only, no private/loopback unless opted in, optional host allow-list; hosted adapters build the documented requests | `tests/test_adapters_net.py` (local HTTP server; **no live vendor calls**) |
| 19 | API: auth, validation, evaluate/verify flows, demo endpoint can be disabled; the one-call `CATERYAEvaluator` facade works | `tests/test_api_cli_compat_docs.py` |
| 20 | CLI: demo, evaluate-from-CSV, offline verify detects tampering, `keygen` never prints the key and refuses to overwrite | `tests/test_api_cli_compat_docs.py` |
| 21 | Generated docs/schemas are current; evidence validates against the JSON Schema | `::test_generated_docs_and_schemas_are_current`, `::test_evidence_validates_against_json_schema` |
| 22 | Every example runs; the CI-gate example fails a bad build | `tests/test_examples.py` |
| 23 | The core works with **zero third-party dependencies** | CI job `core-no-extras` (`pip install -e . pytest && pytest`); extras-dependent tests skip |
| 24 | All sources parse under Python 3.10 grammar | CI matrix (3.10–3.12). *Locally verified for syntax only; runtime was exercised on 3.12.* |

## Explicitly **not** claimed

Regulatory compliance or conformity; that any level means a system is safe; performance or throughput; quantum advantage; zero-knowledge proofs;
audited smart contracts; behaviour on public blockchains; behaviour against live model vendors; a working Qiskit path or a live IPFS node; the
statistical validity of the built-in probe sets or default thresholds; that `ID_AI_ETHICS_2026` matches an official text (it is a **draft** mapping).
