import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from caterya.cli import main as cli_main
from caterya.quick import CATERYAEvaluator
from caterya.docgen import generate, schemas
from conftest import make_tabular

ROOT = Path(__file__).resolve().parents[1]


def test_quick_evaluator_and_async():
    t = make_tabular(bias=0.25)
    res = asyncio.run(CATERYAEvaluator().evaluate(model_output=t.y_prob, ground_truth=t.y_true, sensitive_attributes=t.groups))
    assert res.cos is not None and res.grade in "ABCDF" and res.report.recommendation in ("RECOMMEND_REJECT", "RECOMMEND_CONDITIONAL")
    assert any("missing inputs" in g["reason"] for g in res.gaps)  # untested parts are gaps, not zeros
    with pytest.raises(ValueError):
        CATERYAEvaluator().evaluate_sync([0.1, 0.2], [1], {"g": ["a", "b"]})  # inconsistent lengths rejected


def test_cli_demo_list_quantum_and_verify(tmp_path, capsys):
    assert cli_main(["demo", "--flaws", "pii", "--out", str(tmp_path), "--lang", "id"]) == 0
    out = capsys.readouterr().out
    assert "Rekomendasi" in out and "Reproduction: OK" in out
    assert cli_main(["evidence", "verify", str(tmp_path / "bundle.json")]) == 0
    bundle = json.loads((tmp_path / "bundle.json").read_text())
    bundle["evidence"][3]["claim"] = "edited"
    (tmp_path / "bad.json").write_text(json.dumps(bundle))
    assert cli_main(["evidence", "verify", str(tmp_path / "bad.json")]) == 1
    capsys.readouterr()
    for what in ("profiles", "metrics", "regulations", "flaws"):
        assert cli_main(["list", what]) == 0
    capsys.readouterr()
    assert cli_main(["quantum", "--a", "0.4,0.3,0.2,0.1", "--b", "0.4,0.3,0.2,0.1"]) == 0
    assert json.loads(capsys.readouterr().out)["fidelity"] == pytest.approx(1.0)


def test_cli_evaluate_csv(tmp_path, capsys):
    t = make_tabular(n=300, bias=0.25)
    p = tmp_path / "d.csv"
    p.write_text("y,p,group\n" + "\n".join(f"{y},{pr:.4f},{g}" for y, pr, g in zip(t.y_true, t.y_prob, t.groups["group"])))
    assert cli_main(["evaluate", "--csv", str(p), "--y-prob", "p", "--y-true", "y", "--group", "group", "--out", str(tmp_path / "b.json")]) == 0
    assert "demographic_parity_v1" in capsys.readouterr().out and (tmp_path / "b.json").exists()


def test_cli_keygen_never_prints_private_key_and_refuses_overwrite(tmp_path, capsys):
    pytest.importorskip("cryptography")
    k = tmp_path / "k"
    assert cli_main(["keygen", "--out", str(k)]) == 0
    priv = k.read_text().strip()
    assert priv not in capsys.readouterr().out and oct(k.stat().st_mode & 0o777) == "0o600"
    with pytest.raises(FileExistsError):
        cli_main(["keygen", "--out", str(k)])


def test_python_dash_m_entrypoint():
    r = subprocess.run([sys.executable, "-m", "caterya", "--version"], capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""})
    assert r.returncode == 0 and "caterya" in r.stdout


def test_generated_docs_and_schemas_are_current(tmp_path):
    generate(str(tmp_path))
    for name in ("METRICS.md", "PARAMETERS.md", "REGULATORY.md"):
        assert (tmp_path / "docs" / name).read_text() == (ROOT / "docs" / name).read_text(), f"docs/{name} is stale: run `caterya docs`"
    for name in schemas():
        assert (tmp_path / "schemas" / name).read_text() == (ROOT / "schemas" / name).read_text(), f"schemas/{name} is stale"


def test_evidence_validates_against_json_schema(engine):
    jsonschema = pytest.importorskip("jsonschema")
    from caterya import MockModel
    from caterya.assurance.engine import AssuranceEngine  # noqa: F401
    engine.evaluate(MockModel())
    bundle = engine.registry.export_bundle()
    sch = schemas()
    store = {s["$id"].split("/")[-1]: s for s in sch.values()}
    resolver = jsonschema.RefResolver.from_schema(sch["bundle.v1.json"], store=store)
    ev_schema = sch["evidence.v1.json"]
    for e in bundle["evidence"]:
        jsonschema.validate(e, ev_schema)
    jsonschema.validate(bundle, sch["bundle.v1.json"], resolver=resolver)


def test_agent_trace_schema_accepts_mock_traces():
    jsonschema = pytest.importorskip("jsonschema")
    from caterya import MockModel
    from caterya.metrics.datasets import AGENT_TASKS
    for t in AGENT_TASKS:
        jsonschema.validate(MockModel(["tool_misuse"]).run_agent(t), schemas()["trace.v1.json"])


# ---- API ------------------------------------------------------------------------------------------------
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from caterya.api.app import create_app  # noqa: E402

SYS = {"name": "api-sys", "version": "1", "owner": "o", "intended_use": "u", "description": "d", "model_id": "m"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("CATERYA_API_KEY", raising=False)
    return TestClient(create_app())


def test_api_flow(client):
    assert client.get("/v1/health").json()["status"] == "ok" and "CATERYA" in client.get("/").text
    assert len(client.get("/v1/metrics").json()) >= 34 and "CATERYA-LLM" in client.get("/v1/profiles").json()
    r = client.post("/v1/evaluate/mock", json={"system": SYS, "profile": "CATERYA-LLM", "flaws": ["pii"]})
    assert r.status_code == 200 and r.json()["car"]["verdicts"]["pii_leakage_v1"]["verdict"] == "FAIL"
    eid = r.json()["car"]["evidence_ids"][0]
    assert client.get(f"/v1/evidence/{eid}").json()["evidence_id"] == eid
    assert client.get("/v1/registry/verify").json()["ok"]
    bundle = client.get("/v1/registry/bundle").json()
    assert client.post("/v1/bundle/verify", json=bundle).json()["ok"]
    bundle["evidence"][0]["claim"] = "x"
    assert not client.post("/v1/bundle/verify", json=bundle).json()["ok"]
    assert "caterya_evaluations_total" in client.get("/metrics").text
    assert client.get("/v1/evidence/ev_nope").status_code == 404


def test_api_tabular_and_quick_and_validation(client):
    t = make_tabular(n=300, bias=0.25)
    r = client.post("/v1/evaluate/tabular", json={"system": SYS, "y_prob": t.y_prob, "y_true": t.y_true, "groups": t.groups})
    assert r.status_code == 200 and r.json()["car"]["verdicts"]["demographic_parity_v1"]["verdict"] == "FAIL"
    assert client.post("/v1/evaluate/quick", json={"model_output": t.y_prob, "ground_truth": t.y_true, "sensitive_attributes": t.groups}).json()["cos"] is not None
    assert client.post("/v1/evaluate/tabular", json={"system": SYS, "y_prob": [0.1, 0.2], "groups": {"g": ["a"]}}).status_code == 422
    assert client.post("/v1/evaluate/mock", json={"system": SYS, "flaws": ["nope"]}).status_code == 422
    assert client.post("/v1/evaluate/mock", json={"system": {"bogus": 1}}).status_code == 422
    assert client.post("/v1/evaluate/mock", json={"system": SYS, "profile": "NOPE"}).status_code == 422


def test_api_key_enforced_when_configured(monkeypatch):
    monkeypatch.setenv("CATERYA_API_KEY", "s3cret")
    c = TestClient(create_app())
    assert c.get("/v1/profiles").status_code == 401 and c.get("/v1/profiles", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/v1/profiles", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert c.get("/v1/health").status_code == 200  # health stays open for load balancers


def test_demo_endpoint_can_be_disabled(monkeypatch):
    monkeypatch.setenv("CATERYA_API_DEMO", "0")
    assert TestClient(create_app()).post("/v1/evaluate/mock", json={"system": SYS}).status_code == 404


def test_graphql_if_available(client):
    pytest.importorskip("strawberry")
    r = client.post("/graphql", json={"query": "{ health profiles }"})
    assert r.status_code == 200 and "CATERYA-LLM" in r.json()["data"]["profiles"]
