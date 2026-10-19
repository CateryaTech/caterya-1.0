"""Use CATERYA as a CI gate: exit non-zero unless the recommendation is acceptable. Run: python examples/05_ci_gate.py [--flaws pii]"""
import sys

from caterya import AssuranceEngine, MockModel, SystemConfig

flaws = sys.argv[sys.argv.index("--flaws") + 1].split(",") if "--flaws" in sys.argv else []
system = SystemConfig("ci-model", "build-123", owner="Acme", intended_use="support chat", description="CI candidate", model_id="m")
engine = AssuranceEngine(system, profile="CATERYA-LLM")
rep = engine.evaluate(MockModel(flaws))
print(rep.summary())

blocking = [o.metric_id for o in rep.outcomes if o.required and o.verdict == "FAIL"]
if rep.recommendation == "RECOMMEND_REJECT" or blocking:
    print("\nGATE: FAIL ->", blocking or rep.recommendation)
    sys.exit(1)
print("\nGATE: PASS (a human decision is still required for assurance; this only blocks known-bad builds)")
