"""Zero-knowledge interface — HONEST STATUS: there is no ZK prover in this repository.

``ZKBackend`` defines where a real prover (e.g. a Groth16/PLONK circuit proving "COS >= t without revealing
the evidence") would plug in. Until one exists, ``SignedThresholdClaim`` offers a *non-ZK* alternative: a
signed statement "metric >= threshold" that reveals the threshold, hides the value, and is only as
trustworthy as the signer.
"""
from __future__ import annotations

from typing import Any, Dict, Protocol

from ..core.canonical import canonical_json
from ..core.errors import BackendUnavailable
from ..provenance.signing import Keyring, Signer


class ZKBackend(Protocol):  # pragma: no cover - interface
    name: str

    def prove(self, circuit_id: str, public_inputs: Dict[str, Any], witness: Dict[str, Any]) -> bytes: ...
    def verify(self, circuit_id: str, public_inputs: Dict[str, Any], proof: bytes) -> bool: ...


class UnavailableZK:
    name = "none"

    def prove(self, *a: Any, **k: Any) -> bytes:
        raise BackendUnavailable("no ZK backend is configured; see docs/BLOCKCHAIN_DEFI.md (roadmap)")

    def verify(self, *a: Any, **k: Any) -> bool:
        raise BackendUnavailable("no ZK backend is configured")


class SignedThresholdClaim:
    @staticmethod
    def make(signer: Signer, metric_id: str, value: float, threshold: float, system_hash: str) -> Dict[str, Any]:
        if value < threshold:
            raise ValueError("value is below threshold; refusing to sign a false claim")
        body = {"claim": "metric>=threshold", "metric": metric_id, "threshold": threshold, "system_hash": system_hash, "zk": False}
        return {**body, "signature": signer.signature_dict(canonical_json(body))}

    @staticmethod
    def verify(claim: Dict[str, Any], keyring: Keyring) -> bool:
        body = {k: v for k, v in claim.items() if k != "signature"}
        return keyring.verify(claim.get("signature", {}), canonical_json(body))
