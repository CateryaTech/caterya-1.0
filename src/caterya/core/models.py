"""Core data model: SystemConfig, MetricSpec, MetricResult, Evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..version import SPEC_VERSION
from .canonical import digest


@dataclass
class SystemConfig:
    """Description of the *system* under assurance (model + tools + memory + policy + humans)."""

    name: str
    version: str = "0"
    provider: str = ""
    model_id: str = ""
    description: str = ""
    owner: str = ""
    intended_use: str = ""
    # risk_context drives the impact/exposure/context terms of the risk model (1..5 each)
    risk_context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def hash(self) -> str:
        return digest(self.to_dict())


@dataclass
class MetricSpec:
    """Formal, hash-bound definition of a metric. A changed definition changes ``spec_hash``."""

    id: str
    version: int
    domain: str
    description: str
    higher_is_better: bool = True
    maturity: str = "stable"  # stable | research
    cost: str = "light"  # light | deep
    requires: Tuple[str, ...] = ()
    parameters: Dict[str, Any] = field(default_factory=dict)
    assumptions: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for k in ("requires", "assumptions", "limitations"):
            d[k] = list(d[k])
        return d

    def spec_hash(self) -> str:
        return digest(self.to_dict())


@dataclass
class MetricResult:
    """Outcome of one metric. ``value is None`` means *untested* — never "passed"."""

    value: Optional[float] = None
    n: int = 0
    ci: Optional[Tuple[float, float]] = None
    details: Dict[str, Any] = field(default_factory=dict)
    untested: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    @property
    def tested(self) -> bool:
        return self.value is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": None if self.value is None else round(float(self.value), 6),
            "n": self.n,
            "ci": None if self.ci is None else [round(self.ci[0], 6), round(self.ci[1], 6)],
            "details": self.details,
            "untested": list(self.untested),
            "limitations": list(self.limitations),
        }


@dataclass
class Evidence:
    """A signed, hash-chained statement about a system. The atomic unit of CATERYA output."""

    kind: str  # metric | guardrail | decision | incident | mapping | monitor | note
    claim: str
    metric_id: str = ""
    spec_hash: str = ""
    system_hash: str = ""
    dataset_hash: str = ""
    seed: Optional[int] = None
    result: Dict[str, Any] = field(default_factory=dict)
    ci: Optional[List[float]] = None
    limitations: List[str] = field(default_factory=list)
    untested: List[str] = field(default_factory=list)
    actor: str = ""
    timestamp: str = ""
    prev_hash: str = ""
    spec: str = SPEC_VERSION
    # set by the registry:
    record_hash: str = ""
    evidence_id: str = ""
    signature: Dict[str, str] = field(default_factory=dict)

    def body(self) -> Dict[str, Any]:
        d = asdict(self)
        for k in ("record_hash", "evidence_id", "signature"):
            d.pop(k, None)
        return d

    def compute_hash(self) -> str:
        return digest(self.body())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Evidence":
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})
