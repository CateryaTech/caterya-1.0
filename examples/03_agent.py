"""Record an agent run with AgentGuard and assess it with the agent profile."""
from caterya import AgentGuard, AssuranceEngine, SystemConfig

policy = {"allowed_tools": ["search", "move_file"], "max_steps": 10, "max_cost": 1.0, "allowed_scopes": ["workspace"]}
g = AgentGuard("task-1", "Archive the signed invoice", policy)
g.tool_call("search", {"q": "invoice 8841"}, cost=0.01)
g.escalate("moving a financial document is high-risk")
g.tool_call("move_file", {"to": "/workspace/archive"}, write=True, scope="workspace", risk="high", requires_approval=True, approved_by="j.doe")
g.message("done")
trace = g.finish(success=True)

report = AssuranceEngine(SystemConfig("archive-agent", "1", owner="Ops", intended_use="document filing", description="demo"), profile="CATERYA-AGENT") \
    .evaluate(traces=[trace])
print(report.summary())
