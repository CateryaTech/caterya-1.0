"""Evaluate a system, inspect the signed evidence, verify it offline. Run: python examples/01_quickstart.py"""
from caterya import AssuranceEngine, EvidenceRegistry, MockModel, SystemConfig

system = SystemConfig("support-bot", "2.3.0", provider="acme", model_id="acme-chat-1", owner="Acme Corp",
                      intended_use="customer-support chat", description="RAG support assistant",
                      risk_context={"impact": 3, "exposure": 4, "context": 3})   # 1..5 each
engine = AssuranceEngine(system, profile="CATERYA-LLM")

report = engine.evaluate(MockModel())           # <- any ModelAdapter / CallableAdapter works here
print(report.summary())

# Every metric result is a signed, hash-chained Evidence record bound to the metric definition, system and dataset.
ev = engine.registry.get(report.outcomes[0].evidence_id)
print("\nfirst evidence:", ev.evidence_id, ev.metric_id, ev.spec_hash[:20], "...")

# A bundle is verifiable offline by anyone, without your private keys.
bundle = engine.registry.export_bundle()
print("offline verification:", EvidenceRegistry.verify_bundle(bundle).to_dict())
