"""Command-line interface: ``caterya <command>`` (or ``python -m caterya``)."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional

from .adapters.mock import FLAWS, MockModel
from .assurance.engine import AssuranceEngine
from .assurance.governance import Decider
from .assurance.profiles import PROFILES
from .core.models import SystemConfig
from .metrics import registry as mreg
from .metrics.context import TabularData
from .provenance.anchors import DryRunAnchor
from .provenance.registry import EvidenceRegistry
from .provenance.signing import HAS_ED25519, Ed25519Signer, Keyring, new_signer
from .regulatory.mapping import FRAMEWORKS
from .version import __version__


def _dump(obj: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def cmd_demo(a: argparse.Namespace) -> int:
    flaws = [f for f in a.flaws.split(",") if f]
    system = SystemConfig("demo-support-bot", "1.0.0", provider="mock", model_id="mock-1", owner="Demo Org", intended_use="customer-support chat (demo)",
                          description="Deterministic mock system used to demonstrate CATERYA end to end.", risk_context={"impact": 3, "exposure": 3, "context": 3})
    eng = AssuranceEngine(system, profile=a.profile)
    model = MockModel(flaws)
    rep = eng.evaluate(model)
    print(rep.summary(a.lang))
    rr = eng.reproduce(rep)
    print(f"\nReproduction: {'OK' if rr['ok'] else 'MISMATCH'} ({rr['checked']} metrics re-run, {len(rr['mismatches'])} mismatches)")
    decider = Decider("Demo Decider", "Head of AI Risk (demo)", new_signer())
    mapping = {"RECOMMEND_ASSURE": "ASSURED", "RECOMMEND_CONDITIONAL": "CONDITIONALLY_ASSURED", "RECOMMEND_REJECT": "REJECTED", "INSUFFICIENT_EVIDENCE": "DEFERRED"}
    dec = eng.decide(rep, decider, mapping[rep.recommendation], f"Demo decision following recommendation {rep.recommendation}.")
    attester = new_signer()
    eng.registry.keyring.add(attester)
    att = eng.attest(rep, dec, attester)
    anchor = DryRunAnchor()
    eng.registry.anchor(anchor)
    lvl = eng.level(rep, reproduced=rr, decision=dec, attestation=att, accredited=Keyring().add(attester), anchors=eng.registry.anchors)
    print(f"\nDecision: {dec.result['decision']} by {dec.result['decider']['name']} (key {dec.result['decider']['key_id']})")
    print(f"Assurance level (process depth): {lvl['label']}")
    print("  (demo: all keys are generated locally, so 'independent' here means key-separated only; organisational independence is established out-of-band)")
    for b in lvl["blockers"]:
        print(f"  next-level blocker: {b}")
    v = eng.registry.verify()
    print(f"Registry: {v.count} evidence records, chain/signatures {'VALID' if v.ok else 'INVALID'}, Merkle root {v.root[:16]}...")
    if not HAS_ED25519:
        print("NOTE: running with the DEV-ONLY HMAC signer; `pip install cryptography` for real signatures.")
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        _dump(eng.registry.export_bundle(), os.path.join(a.out, "bundle.json"))
        _dump(rep.to_dict(), os.path.join(a.out, "report.json"))
        _dump(att, os.path.join(a.out, "attestation.dsse.json"))
        print(f"Wrote {a.out}/bundle.json, report.json, attestation.dsse.json\nVerify offline:  caterya evidence verify {a.out}/bundle.json")
    return 0


def _col(rows: List[Dict[str, str]], name: str, cast=str) -> List[Any]:
    try:
        return [cast(r[name]) for r in rows]
    except KeyError:
        sys.exit(f"column {name!r} not found in CSV")


def cmd_evaluate(a: argparse.Namespace) -> int:
    with open(a.csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    t = TabularData(y_true=_col(rows, a.y_true, int) if a.y_true else None, y_prob=_col(rows, a.y_prob, float),
                    groups={g: _col(rows, g) for g in a.group}, threshold=a.threshold)
    system = SystemConfig(a.system_name, a.system_version, owner=a.owner, intended_use=a.intended_use, description=f"evaluated from {os.path.basename(a.csv)}")
    eng = AssuranceEngine(system, profile=a.profile)
    params = {m: {"min_group_size": a.min_group_size} for m in ("demographic_parity_v1", "equalized_odds_v1", "entropy_dispersion_v1", "quantum_symmetry_index_v1")}
    rep = eng.evaluate(profile=a.profile, tabular=t, params=params)
    print(rep.summary(a.lang))
    if a.out:
        _dump(eng.registry.export_bundle(), a.out)
        print(f"\nWrote {a.out}")
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    with open(a.bundle, encoding="utf-8") as fh:
        b = json.load(fh)
    trusted = None
    if a.trusted:
        with open(a.trusted, encoding="utf-8") as fh:
            trusted = Keyring(json.load(fh))
    rep = EvidenceRegistry.verify_bundle(b, trusted)
    print(json.dumps(rep.to_dict(), indent=2))
    if not trusted:
        print("note: no --trusted keyring given; this proves integrity/self-consistency, not WHO signed.", file=sys.stderr)
    return 0 if rep.ok else 1


def cmd_show(a: argparse.Namespace) -> int:
    with open(a.bundle, encoding="utf-8") as fh:
        b = json.load(fh)
    for e in b["evidence"]:
        if e["evidence_id"] == a.evidence_id:
            print(json.dumps(e, indent=2, sort_keys=True))
            return 0
    print("not found", file=sys.stderr)
    return 1


def cmd_keygen(a: argparse.Namespace) -> int:
    if not HAS_ED25519:
        sys.exit("keygen needs `pip install cryptography`")
    s = Ed25519Signer()
    fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(s.private_hex() + "\n")
    print(f"key_id: {s.key_id}\npublic_key: {s.public_key_hex()}\nprivate key written to {a.out} (mode 0600). Never commit it.")
    return 0


def cmd_list(a: argparse.Namespace) -> int:
    if a.what == "profiles":
        for p in PROFILES.values():
            print(f"{p.name:<20} {len(p.metrics):>2} metrics  {p.description}")
    elif a.what == "metrics":
        mreg.load_all()
        for m in mreg.REGISTRY.values():
            print(f"{m.id:<40} {m.domain:<16} {m.maturity:<9} requires={','.join(m.requires) or '-'}")
    elif a.what == "regulations":
        for k, v in FRAMEWORKS.items():
            print(f"{k:<20} {v['status']:<11} {len(v['themes'])} themes")
    elif a.what == "flaws":
        print("\n".join(FLAWS))
    return 0


def cmd_quantum(a: argparse.Namespace) -> int:
    from .quantum.backends import get_backend
    parse = lambda s: [float(x) for x in s.split(",")]  # noqa: E731
    rec = get_backend(a.backend).swap_test_fidelity(parse(a.a), parse(a.b), a.shots, a.seed)
    print(json.dumps(rec, indent=2))
    return 0


def cmd_serve(a: argparse.Namespace) -> int:
    try:
        import uvicorn
        from .api.app import create_app
    except ImportError:
        sys.exit("pip install 'caterya[api]'")
    uvicorn.run(create_app(), host=a.host, port=a.port)
    return 0


def cmd_docs(a: argparse.Namespace) -> int:
    from .docgen import generate
    generate(a.root)
    print(f"generated docs/METRICS.md, docs/PARAMETERS.md, docs/REGULATORY.md and schemas/ under {a.root}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="caterya", description="CATERYA AI Assurance Infrastructure - Measure. Verify. Assure.")
    ap.add_argument("--version", action="version", version=f"caterya {__version__}")
    sp = ap.add_subparsers(dest="cmd", required=True)

    d = sp.add_parser("demo", help="end-to-end demo on a mock system")
    d.add_argument("--flaws", default="", help=f"comma list from: {', '.join(FLAWS)}")
    d.add_argument("--profile", default="CATERYA-LLM", choices=sorted(PROFILES))
    d.add_argument("--lang", default="en", choices=["en", "id"])
    d.add_argument("--out", default="")
    d.set_defaults(fn=cmd_demo)

    e = sp.add_parser("evaluate", help="evaluate prediction-level data from a CSV")
    e.add_argument("--csv", required=True)
    e.add_argument("--y-prob", required=True)
    e.add_argument("--y-true", default="")
    e.add_argument("--group", action="append", default=[], required=True, help="sensitive-attribute column (repeatable)")
    e.add_argument("--threshold", type=float, default=0.5)
    e.add_argument("--min-group-size", type=int, default=10)
    e.add_argument("--profile", default="CATERYA-TABULAR", choices=sorted(PROFILES))
    e.add_argument("--system-name", default="csv-system")
    e.add_argument("--system-version", default="0")
    e.add_argument("--owner", default="")
    e.add_argument("--intended-use", default="")
    e.add_argument("--lang", default="en", choices=["en", "id"])
    e.add_argument("--out", default="")
    e.set_defaults(fn=cmd_evaluate)

    ev = sp.add_parser("evidence", help="inspect/verify evidence bundles")
    es = ev.add_subparsers(dest="sub", required=True)
    v = es.add_parser("verify")
    v.add_argument("bundle")
    v.add_argument("--trusted", default="", help="JSON keyring of keys you trust")
    v.set_defaults(fn=cmd_verify)
    s = es.add_parser("show")
    s.add_argument("bundle")
    s.add_argument("evidence_id")
    s.set_defaults(fn=cmd_show)

    k = sp.add_parser("keygen", help="generate an Ed25519 signing key (0600)")
    k.add_argument("--out", required=True)
    k.set_defaults(fn=cmd_keygen)

    l = sp.add_parser("list")
    l.add_argument("what", choices=["profiles", "metrics", "regulations", "flaws"])
    l.set_defaults(fn=cmd_list)

    q = sp.add_parser("quantum", help="research: swap-test fidelity between two distributions")
    q.add_argument("--a", required=True)
    q.add_argument("--b", required=True)
    q.add_argument("--backend", default="classical", choices=["classical", "pennylane", "qiskit"])
    q.add_argument("--shots", type=int, default=None)
    q.add_argument("--seed", type=int, default=0)
    q.set_defaults(fn=cmd_quantum)

    sv = sp.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)

    dc = sp.add_parser("docs", help="regenerate generated docs and JSON schemas")
    dc.add_argument("--root", default=".")
    dc.set_defaults(fn=cmd_docs)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
