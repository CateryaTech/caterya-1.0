"""One-call evaluation of prediction-level data - still produces signed evidence and a CAR."""
import asyncio
import random

from caterya.quick import CATERYAEvaluator

rnd = random.Random(3)
sensitive = {"gender": [rnd.choice(["F", "M"]) for _ in range(500)]}
truth = [int(rnd.random() < 0.5) for _ in range(500)]
scores = [min(1, max(0, 0.5 * t + 0.25 + rnd.gauss(0, 0.12))) for t in truth]

result = asyncio.run(CATERYAEvaluator().evaluate(model_output=scores, ground_truth=truth, sensitive_attributes=sensitive))
print("COS (derived):", round(result.cos, 3), result.grade)
print("pillars      :", {k: None if v is None else round(v, 3) for k, v in result.pillar_scores.items()})
print("gaps         :", [g["metric"] for g in result.gaps])
print("evidence     :", len(result.report.evidence_ids), "signed records; CAR", result.report.car_evidence.evidence_id)
