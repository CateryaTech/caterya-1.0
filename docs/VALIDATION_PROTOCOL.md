# Validation protocol

A metric that is *computed* is not thereby *valid*. This protocol is how a metric, a probe set or a threshold earns trust. The test-suite already does
step 1 for every metric; steps 2–6 are the work **you** do for your own risk context. Until they are done, results are indicative.

1. **Known-groups validity (automated here).** Each metric must separate a known-good from a known-bad system. `tests/test_metrics.py` injects the
   specific flaw each metric claims to detect (`MockModel(flaws=…)`) and asserts the score moves the right way. A new metric ships with such a test.
2. **Construct validity.** Write down what the metric is *meant* to measure and what it does **not** (the `assumptions` / `limitations` fields). Have a
   domain expert review that a high score is plausible evidence for the property, and that obvious gaming (e.g. memorising the probe set) is addressed.
3. **Probe-set quality.** Replace the built-in smoke-test datasets with a set that matches your deployment (language, domain, user population), versioned
   and hashed. Record provenance, labelling process and inter-annotator agreement for any human labels.
4. **Reliability.** Repeat runs with different seeds; the spread must be small relative to the threshold margin. Report the 95% interval (Wilson for
   proportions, bootstrap for continuous values — both built in) and treat `borderline` verdicts as inconclusive, not as passes.
5. **Threshold setting.** Thresholds are *policy*. Derive them from a stated risk tolerance, historical incidents or user-harm estimates, then record the
   rationale next to the profile. Pre-register thresholds before running the evaluation you intend to rely on.
6. **External review.** Before promoting a metric from `research` to `stable`, obtain review by someone independent of the author, publish the review, and
   record the decision in the changelog.

## Reporting template (attach to a decision)

* System and version (`system_hash`), profile and any parameter overrides (`spec_hash` of each metric).
* Datasets used (`dataset_hash`) and how they were built; their known blind spots.
* Coverage and the list of gaps, with reasons.
* Which results were `borderline`; reproduction result.
* Residual risks accepted, by whom (named), until when (`valid_until`), and any override reason.

## Research-maturity metrics

`behavioral_lyapunov_v1`, `sustainability_estimate_v1` and the three `quantum_*` metrics are **research**: they are informative instruments, have not
been through steps 2–6, and must not be the sole basis for a decision. `sustainability_estimate_v1` depends on a **placeholder** Wh-per-1k-tokens constant
you must replace with provider/hardware data.
