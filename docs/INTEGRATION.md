# Integration recipes (Python)

## 1. Any model behind a function

```python
from caterya import CallableAdapter, AssuranceEngine, SystemConfig
adapter = CallableAdapter(generate=lambda prompt, system=None, seed=None: my_llm(prompt, system))
report = AssuranceEngine(SystemConfig("my-llm", "1")).evaluate(adapter, profile="CATERYA-LLM")
```
Provide `predict=` for scored/tabular models (enables noise-robustness) and `explain=` for explanation-faithfulness; `run_agent=` for agents.

## 2. Hosted models

```python
from caterya.adapters.hosted import OpenAICompatAdapter, AnthropicAdapter
OpenAICompatAdapter("gpt-x", base_url="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY")
OpenAICompatAdapter("llama3", base_url="http://localhost:11434/v1", allow_local=True)       # Ollama / vLLM / LM Studio
AnthropicAdapter(model="<model id you want evaluated>")                                       # ANTHROPIC_API_KEY; model is never hard-coded
```
Egress rules: https only (http requires `allow_local=True`), private/loopback addresses blocked unless `allow_local=True`, and
`CATERYA_ALLOWED_HOSTS=host1,host2` restricts everything. Check current model ids in your provider's documentation.

## 3. Your own data instead of the built-in probe sets

The built-in datasets are **smoke tests**. Replace them: `engine.evaluate(adapter, datasets={"policy": [...], "qa": [...]})`
(shapes in `caterya/metrics/datasets.py`). Their hashes are recorded in every Evidence.

## 4. Tabular / scored systems

```python
from caterya import TabularData
engine.evaluate(profile="CATERYA-TABULAR", tabular=TabularData(y_true=y, y_prob=p, groups={"gender": g, "region": r}, X=rows),
                reference=validated_scores, params={"demographic_parity_v1": {"min_group_size": 30, "intersectional": True}})
```
Add `adapter=` (with `predict`/`explain`) to unlock `gaussian_noise_accuracy_v1` and `explanation_faithfulness_v1`.

## 5. Agents

Record with `AgentGuard` (or emit `caterya.trace/v1` yourself, see `schemas/trace.v1.json`), then `evaluate(traces=[...], profile="CATERYA-AGENT")`.
`AgentGuard(..., enforce=True)` additionally raises `PolicyViolation` on an off-allow-list tool call.

## 6. CI gate

`examples/05_ci_gate.py` exits non-zero on `RECOMMEND_REJECT` or a failing required metric. A gate blocks known-bad builds; it does not replace the human decision.

## 7. Guardrails around a runtime path

```python
guard = CATERYAGuardrail(engine.registry, engine.system.hash(), deny_terms=[...])
safe = guard.wrap(my_langgraph_node, extract=lambda state: state["output"])   # annotates, never blocks
```

## 8. Serving and observability

`caterya serve` (needs `caterya[api]`): `/v1/*`, `/v1/evaluate/quick` (one-call facade), `/graphql` (with `caterya[graphql]`), `/metrics` (Prometheus text), `/` (minimal UI).
Set `CATERYA_API_KEY` to require `X-API-Key`. The server never holds a decider key. State is **in-memory** (see roadmap).

## 9. Keys

`caterya keygen --out evaluator.key` (mode 0600, refuses to overwrite, never prints the private key). The evaluator, the decider and the system owner
should use **different** keys; reuse is detected and blocks level 3.

## 10. On-chain

See [BLOCKCHAIN_DEFI.md](BLOCKCHAIN_DEFI.md) and `examples/08_onchain_gate.py`.

## Plugins

Third-party metrics register through the `caterya.metrics` entry-point group:

```toml
[project.entry-points."caterya.metrics"]
acme = "acme_caterya.metrics"      # importing the module runs its @metric decorators
```
