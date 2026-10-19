"""Optional GraphQL surface (extra: ``caterya[graphql]``). Read-only: health, profiles, metrics, evidence."""

from typing import List, Optional

from ..assurance.profiles import PROFILES
from ..metrics import registry as mreg
from ..provenance.registry import EvidenceRegistry
from ..version import __version__


def build_router(reg: EvidenceRegistry):
    try:
        import strawberry
        from strawberry.fastapi import GraphQLRouter
    except Exception:
        return None

    @strawberry.type
    class MetricInfo:
        id: str
        domain: str
        maturity: str

    @strawberry.type
    class EvidenceInfo:
        evidence_id: str
        kind: str
        claim: str
        metric_id: str
        record_hash: str
        timestamp: str

    @strawberry.type
    class Query:
        @strawberry.field
        def health(self) -> str:
            return f"ok {__version__}"

        @strawberry.field
        def profiles(self) -> List[str]:
            return sorted(PROFILES)

        @strawberry.field
        def metrics(self) -> List[MetricInfo]:
            return [MetricInfo(m.id, m.domain, m.maturity) for m in mreg.REGISTRY.values()]

        @strawberry.field
        def evidence(self, id: str) -> Optional[EvidenceInfo]:
            try:
                e = reg.get(id)
            except KeyError:
                return None
            return EvidenceInfo(e.evidence_id, e.kind, e.claim, e.metric_id, e.record_hash, e.timestamp)

    return GraphQLRouter(strawberry.Schema(Query))
