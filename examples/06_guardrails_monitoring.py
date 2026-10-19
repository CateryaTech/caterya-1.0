"""Guardrails recommend (never silently block), a swarm votes, the monitor runs tiers, incidents follow an ordered loop."""
from caterya import AssuranceEngine, CATERYAGuardrail, Decider, EthicsSwarm, MockModel, StandingAuthorization, SystemConfig, new_signer
from caterya.monitoring.continuous import ContinuousMonitor, IncidentLoop

engine = AssuranceEngine(SystemConfig("prod-bot", "5", owner="Acme", intended_use="chat", description="prod", model_id="m"))
decider = Decider("Dr. Rina", "Head of AI Risk", new_signer())          # a human with their OWN key
engine.registry.keyring.add(decider.signer)
auth = StandingAuthorization.issue(decider, scope="prod-chat", actions=("hold",))   # pre-authorises automated HOLDS only

guard = CATERYAGuardrail(engine.registry, engine.system.hash(), deny_terms=["internal-only"], authorization=auth, scope="prod-chat")
r = guard.check("Here is the internal-only roadmap...")
print("guardrail:", r.decision, "| held:", r.held, "|", r.recommendations)

print("swarm:", EthicsSwarm(engine.registry).vote("Call me on +62 812 5550 0199")["consensus"])

mon = ContinuousMonitor(engine)
print("canary (healthy):", mon.run("canary", MockModel()).needs_incident_replay)
bad = mon.run("canary", MockModel(["policy"]))
print("canary (regressed):", bad.needs_incident_replay)

loop = IncidentLoop(engine, "INC-7", "policy regression after release", "oncall-a")
loop.advance("TRIAGED", "oncall-a", "sev2")
loop.advance("CONTAINED", "oncall-a", "rolled back to build 4")
loop.advance("REPLAYED", "oncall-b", "replayed failing prompts", [bad.evidence_id])
print("incident stage:", loop.stage, "| chain valid:", engine.registry.verify().ok)
