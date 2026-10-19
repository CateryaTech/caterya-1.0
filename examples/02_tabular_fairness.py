"""Prediction-level fairness assessment (labels + scores + groups, no model access needed)."""
import random

from caterya import AssuranceEngine, SystemConfig, TabularData

rnd = random.Random(7)
groups = [rnd.choice(["A", "B"]) for _ in range(800)]
y_true = [int(rnd.random() < 0.5) for _ in range(800)]
y_prob = [min(1, max(0, 0.5 * y + 0.25 + rnd.gauss(0, 0.12) - (0.2 if g == "B" else 0))) for y, g in zip(y_true, groups)]  # group B is under-scored

system = SystemConfig("credit-scorer", "0.9", owner="Bank X", intended_use="credit pre-screening", description="gradient boosted scorer")
report = AssuranceEngine(system, profile="CATERYA-TABULAR").evaluate(
    tabular=TabularData(y_true=y_true, y_prob=y_prob, groups={"group": groups}),
    params={"demographic_parity_v1": {"min_group_size": 30}})        # parameters are hash-bound into the evidence
print(report.summary())
print("\nNote how metrics that need more inputs (model access, features, a reference sample) are listed as gaps, not scored 0.")
