"""REST API (FastAPI). Extra: ``pip install 'caterya[api]'``.

Security defaults: set ``CATERYA_API_KEY`` to require ``X-API-Key``; request sizes are capped; the server never
holds a *decider* key (human decisions are made through the SDK/CLI so separation of duties is preserved).
State is in-memory per process - production deployments should mount durable storage (see docs/ROADMAP.md).
"""

import hmac
import os
from typing import Any, Dict, List, Optional

from ..assurance.engine import AssuranceEngine
from ..assurance.profiles import PROFILES
from ..adapters.mock import MockModel
from ..blockchain.defi import ProofToken
from ..quick import CATERYAEvaluator
from ..core.errors import VerificationError
from ..core.models import SystemConfig
from ..metrics import registry as mreg
from ..metrics.context import TabularData
from ..provenance.registry import EvidenceRegistry
from ..provenance.signing import new_signer
from ..regulatory.mapping import FRAMEWORKS
from ..telemetry import Telemetry
from ..version import __version__

MAX_ROWS = 200_000
UI = """<!doctype html><meta charset=utf-8><title>CATERYA AI Assurance Infrastructure</title>
<style>body{font:15px system-ui;margin:2rem auto;max-width:860px;padding:0 1rem}pre{background:#0001;padding:1rem;overflow:auto}button{padding:.5rem 1rem}</style>
<h1>CATERYA AI Assurance Infrastructure</h1><p>Measure. Verify. Assure. - <code>v__V__</code></p>
<button onclick="run()">Run demo evaluation (mock system)</button> <button onclick="verify()">Verify registry</button><pre id=o>ready</pre>
<script>
const H={'Content-Type':'application/json'};
async function run(){const r=await fetch('/v1/evaluate/mock',{method:'POST',headers:H,body:JSON.stringify({system:{name:'demo',version:'1',owner:'you',intended_use:'demo',description:'demo',model_id:'mock'},profile:'CATERYA-LLM',flaws:[]})});o.textContent=JSON.stringify((await r.json()).car,null,2)}
async function verify(){o.textContent=JSON.stringify(await (await fetch('/v1/registry/verify')).json(),null,2)}
</script>""".replace("__V__", __version__)


def create_app(registry: Optional[EvidenceRegistry] = None):
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
        from fastapi.responses import HTMLResponse, PlainTextResponse
        from pydantic import BaseModel, Field
    except Exception as e:  # pragma: no cover
        raise ImportError("FastAPI not installed: pip install 'caterya[api]'") from e

    signer = registry.signer if registry is not None else new_signer()
    reg = registry if registry is not None else EvidenceRegistry(signer)
    tele = Telemetry()
    mreg.load_all()
    app = FastAPI(title="CATERYA AI Assurance Infrastructure", version=__version__)
    app.state.registry, app.state.telemetry = reg, tele

    def auth(x_api_key: Optional[str] = Header(default=None)) -> None:
        key = os.environ.get("CATERYA_API_KEY")
        if key and not (x_api_key and hmac.compare_digest(x_api_key, key)):
            raise HTTPException(401, "missing or invalid X-API-Key")

    class TabularReq(BaseModel):
        system: Dict[str, Any]
        profile: str = "CATERYA-TABULAR"
        y_prob: List[float] = Field(max_length=MAX_ROWS)
        y_true: Optional[List[int]] = Field(default=None, max_length=MAX_ROWS)
        groups: Dict[str, List[str]] = {}
        reference: Optional[List[float]] = Field(default=None, max_length=MAX_ROWS)
        threshold: float = 0.5
        seed: int = 0
        params: Optional[Dict[str, Dict[str, Any]]] = None

    class MockReq(BaseModel):
        system: Dict[str, Any]
        profile: str = "CATERYA-LLM"
        flaws: List[str] = []
        seed: int = 0

    class TokenReq(BaseModel):
        token: str
        min_level: int = 0

    class QuickReq(BaseModel):
        model_output: List[float] = Field(max_length=MAX_ROWS)
        ground_truth: Optional[List[int]] = Field(default=None, max_length=MAX_ROWS)
        sensitive_attributes: Dict[str, List[str]] = {}

    def _sys(d: Dict[str, Any]) -> SystemConfig:
        try:
            return SystemConfig(**d)
        except TypeError as e:
            raise HTTPException(422, f"invalid system: {e}")

    def _engine(d: Dict[str, Any], profile: str) -> AssuranceEngine:
        if profile not in PROFILES:
            raise HTTPException(422, f"unknown profile {profile!r}")
        return AssuranceEngine(_sys(d), registry=reg, profile=profile)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def ui() -> str:
        return UI

    @app.get("/v1/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "version": __version__, "signer": {"alg": signer.alg, "key_id": signer.key_id},
                "asymmetric": signer.is_asymmetric, "evidence_count": len(reg)}

    @app.get("/v1/profiles", dependencies=[Depends(auth)])
    def profiles() -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in PROFILES.items()}

    @app.get("/v1/metrics", dependencies=[Depends(auth)])
    def metrics() -> List[Dict[str, Any]]:
        return [{"id": m.id, "domain": m.domain, "maturity": m.maturity, "cost": m.cost, "requires": list(m.requires), "defaults": m.defaults,
                 "description": m.description} for m in mreg.REGISTRY.values()]

    @app.get("/v1/regulations", dependencies=[Depends(auth)])
    def regulations() -> Dict[str, Any]:
        return FRAMEWORKS

    @app.post("/v1/evaluate/tabular", dependencies=[Depends(auth)])
    def evaluate_tabular(r: TabularReq) -> Dict[str, Any]:
        try:
            t = TabularData(y_true=r.y_true, y_prob=r.y_prob, groups=r.groups, threshold=r.threshold)
        except ValueError as e:
            raise HTTPException(422, str(e))
        rep = _engine(r.system, r.profile).evaluate(tabular=t, reference=r.reference, seed=r.seed, params=r.params)
        tele.observe_report(rep)
        return rep.to_dict()

    @app.post("/v1/evaluate/mock", dependencies=[Depends(auth)])
    def evaluate_mock(r: MockReq) -> Dict[str, Any]:
        if os.environ.get("CATERYA_API_DEMO", "1") != "1":
            raise HTTPException(404, "demo endpoint disabled")
        try:
            model = MockModel(r.flaws)
        except ValueError as e:
            raise HTTPException(422, str(e))
        rep = _engine(r.system, r.profile).evaluate(model, seed=r.seed)
        tele.observe_report(rep)
        return rep.to_dict()

    @app.get("/v1/evidence/{evidence_id}", dependencies=[Depends(auth)])
    def evidence(evidence_id: str) -> Dict[str, Any]:
        try:
            return reg.get(evidence_id).to_dict()
        except KeyError:
            raise HTTPException(404, "unknown evidence id")

    @app.get("/v1/evidence/{evidence_id}/proof", dependencies=[Depends(auth)])
    def proof(evidence_id: str) -> Dict[str, Any]:
        try:
            return {"proof": reg.proof(evidence_id), "tree_head": reg.tree_head()}
        except KeyError:
            raise HTTPException(404, "unknown evidence id")

    @app.get("/v1/registry/verify", dependencies=[Depends(auth)])
    def registry_verify() -> Dict[str, Any]:
        return reg.verify().to_dict()

    @app.get("/v1/registry/bundle", dependencies=[Depends(auth)])
    def bundle() -> Dict[str, Any]:
        return reg.export_bundle()

    @app.post("/v1/bundle/verify", dependencies=[Depends(auth)])
    def bundle_verify(b: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return EvidenceRegistry.verify_bundle(b).to_dict()
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"malformed bundle: {type(e).__name__}")

    @app.post("/v1/proof-token/verify", dependencies=[Depends(auth)])
    def token_verify(r: TokenReq) -> Dict[str, Any]:
        try:
            return {"valid": True, "payload": ProofToken.verify(r.token, reg.keyring, min_level=r.min_level)}
        except VerificationError as e:
            return {"valid": False, "reason": str(e)}

    @app.get("/metrics", response_class=PlainTextResponse, dependencies=[Depends(auth)])
    def prom() -> str:
        return tele.render()

    @app.post("/v1/evaluate/quick", dependencies=[Depends(auth)])
    def quick(r: QuickReq) -> Dict[str, Any]:
        ev = CATERYAEvaluator()
        ev.engine.registry, ev.engine.signer = reg, signer
        try:
            return ev.evaluate_sync(r.model_output, r.ground_truth, r.sensitive_attributes).to_dict()
        except ValueError as e:
            raise HTTPException(422, str(e))

    from .graphql import build_router  # returns None when the optional strawberry extra is absent
    router = build_router(reg)
    if router is not None:
        app.include_router(router, prefix="/graphql")
    return app
