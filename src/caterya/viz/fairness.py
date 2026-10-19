"""Fairness 'energy' surface: how far each group's score distribution deviates from the overall one.

energy[g][b] = (share of group g in score-bin b - overall share in bin b)^2. Output is a plain, hashable
dict plus a dependency-free HTML heat-map;
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..core.canonical import digest
from ..core.stats import histogram, normalise
from ..metrics.context import TabularData


def energy_surface(t: TabularData, attribute: str, bins: int = 10, min_group_size: int = 10) -> Dict[str, Any]:
    labels = t.groups[attribute]
    overall = normalise([c + 1e-9 for c in histogram(t.y_prob, bins)])
    by: Dict[str, List[float]] = {}
    for p, g in zip(t.y_prob, labels):
        by.setdefault(g, []).append(p)
    groups = sorted(g for g, v in by.items() if len(v) >= min_group_size)
    energy = [[(normalise([c + 1e-9 for c in histogram(by[g], bins)])[b] - overall[b]) ** 2 for b in range(bins)] for g in groups]
    out = {"attribute": attribute, "groups": groups, "bins": bins, "energy": [[round(x, 6) for x in r] for r in energy],
           "total_energy": round(sum(sum(r) for r in energy), 6), "suppressed": sorted(set(by) - set(groups))}
    out["hash"] = digest({k: v for k, v in out.items()})
    return out


def to_html(surface: Dict[str, Any]) -> str:
    mx = max((max(r) for r in surface["energy"]), default=0) or 1.0
    rows = []
    for g, r in zip(surface["groups"], surface["energy"]):
        cells = "".join(f'<td style="background:rgba(200,60,60,{x / mx:.2f})" title="{x}">{x:.3f}</td>' for x in r)
        rows.append(f"<tr><th>{g}</th>{cells}</tr>")
    head = "".join(f"<th>bin {i}</th>" for i in range(surface["bins"]))
    return (f"<table style='border-collapse:collapse;font:13px sans-serif'><caption>Fairness energy: {surface['attribute']} "
            f"(total {surface['total_energy']}, hash {surface['hash'][:19]}...)</caption><tr><th></th>{head}</tr>{''.join(rows)}</table>")
