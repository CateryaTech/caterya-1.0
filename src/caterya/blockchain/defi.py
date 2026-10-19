"""Off-chain helpers for DeFi-style integrations: compact signed proof tokens and gate payloads."""
from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, Optional

from ..core.errors import VerificationError
from ..provenance.signing import Keyring, Signer

TOKEN_PREFIX = "ctok1"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class ProofToken:
    """Compact, signed assertion ``"system S held assurance level L (CAR C) until T"``.

    Intended for API gateways / off-chain keepers / bridges that cannot afford an RPC call per request.
    Format: ``ctok1.<b64url(json payload)>.<b64url(signature)>`` - verifiable offline with the issuer's public key.
    """

    @staticmethod
    def issue(signer: Signer, system_hash: str, level: int, car_hash: str, ttl_seconds: int = 3600, now: Optional[float] = None) -> str:
        t = int(now if now is not None else time.time())
        payload = {"sys": system_hash, "lvl": int(level), "car": car_hash, "iat": t, "exp": t + ttl_seconds, "iss": signer.key_id, "alg": signer.alg}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        body = f"{TOKEN_PREFIX}.{_b64(raw)}"
        return f"{body}.{_b64(signer.sign(body.encode()))}"

    @staticmethod
    def verify(token: str, keyring: Keyring, now: Optional[float] = None, min_level: int = 0, system_hash: Optional[str] = None) -> Dict[str, Any]:
        try:
            prefix, p, s = token.split(".")
            if prefix != TOKEN_PREFIX:
                raise ValueError("bad prefix")
            payload = json.loads(_unb64(p))
            sig = {"alg": payload["alg"], "key_id": payload["iss"], "sig": _unb64(s).hex()}
        except Exception as e:  # noqa: BLE001
            raise VerificationError("malformed proof token") from e
        if not keyring.verify(sig, f"{prefix}.{p}".encode()):
            raise VerificationError("invalid proof token signature")
        t = now if now is not None else time.time()
        if t >= payload["exp"]:
            raise VerificationError("proof token expired")
        if payload["lvl"] < min_level:
            raise VerificationError(f"assurance level {payload['lvl']} < required {min_level}")
        if system_hash and payload["sys"] != system_hash:
            raise VerificationError("proof token is for a different system")
        return payload
