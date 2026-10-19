#!/usr/bin/env python3
"""Measure evaluation/sealing/verification throughput on YOUR machine. This repository publishes no performance numbers.

    python benchmarks/bench.py [--rows 20000] [--evidence 5000]
"""
import argparse
import pathlib
import platform
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from caterya import AssuranceEngine, Evidence, EvidenceRegistry, MockModel, SystemConfig, TabularData, new_signer  # noqa: E402


def timed(label, fn, n=None):
    t = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t
    print(f"{label:<44} {dt * 1000:10.1f} ms" + (f"   ({n / dt:,.0f} /s)" if n else ""))
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--rows", type=int, default=20000)
ap.add_argument("--evidence", type=int, default=5000)
a = ap.parse_args()
print(f"python {platform.python_version()} on {platform.platform()} - signer: ", end="")
signer = new_signer()
print(signer.alg)

reg = EvidenceRegistry(signer)
timed(f"seal {a.evidence} evidence records", lambda: [reg.append(Evidence(kind="note", claim=f"c{i}", result={"i": i})) for i in range(a.evidence)], a.evidence)
timed("verify chain + signatures", reg.verify, a.evidence)
timed("Merkle root", reg.root)
timed("inclusion proof (1 record)", lambda: reg.proof(reg.all()[a.evidence // 2].evidence_id))

rnd = random.Random(0)
g = [rnd.choice("AB") for _ in range(a.rows)]
y = [int(rnd.random() < .5) for _ in range(a.rows)]
p = [min(1, max(0, .5 * v + .25 + rnd.gauss(0, .12))) for v in y]
sysc = SystemConfig("bench", "1", owner="o", intended_use="u", description="d", model_id="m")
timed(f"tabular profile on {a.rows} rows", lambda: AssuranceEngine(sysc, signer=signer).evaluate(profile="CATERYA-TABULAR", tabular=TabularData(y_true=y, y_prob=p, groups={"g": g})))
timed("LLM profile on the mock model", lambda: AssuranceEngine(sysc, signer=signer, profile="CATERYA-LLM").evaluate(MockModel()))
