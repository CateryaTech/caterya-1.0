"""CATERYA AI Assurance Infrastructure - Measure. Verify. Assure.

Open, vendor-neutral infrastructure that evaluates AI systems, produces verifiable evidence about their
behaviour and risk, preserves tamper-evident provenance, and supports continuous assurance.

Quick start::

    from caterya import AssuranceEngine, SystemConfig, MockModel
    rep = AssuranceEngine(SystemConfig("my-system", "1.0")).evaluate(MockModel())
    print(rep.summary())
"""
from .version import __version__  # noqa: F401
from .core.models import Evidence, MetricResult, MetricSpec, SystemConfig  # noqa: F401
from .assurance.engine import AssuranceEngine, AssuranceReport  # noqa: F401
from .assurance.governance import Decider, StandingAuthorization  # noqa: F401
from .adapters.base import CallableAdapter, ModelAdapter  # noqa: F401
from .adapters.mock import MockModel  # noqa: F401
from .metrics.context import TabularData  # noqa: F401
from .provenance.registry import EvidenceRegistry  # noqa: F401
from .provenance.signing import Keyring, new_signer  # noqa: F401
from .guardrails import CATERYAGuardrail, EthicsSwarm  # noqa: F401
from .sdk import AgentGuard  # noqa: F401

__all__ = ["AssuranceEngine", "AssuranceReport", "SystemConfig", "Evidence", "MetricResult", "MetricSpec", "Decider", "StandingAuthorization",
           "CallableAdapter", "ModelAdapter", "MockModel", "TabularData", "EvidenceRegistry", "Keyring", "new_signer",
           "CATERYAGuardrail", "EthicsSwarm", "AgentGuard", "__version__"]
