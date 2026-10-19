"""DSSE envelopes and in-toto Statements for portable, third-party-checkable attestations."""
from __future__ import annotations

import base64
import json
from typing import Any, Dict

from .signing import Keyring, Signer

PAYLOAD_TYPE = "application/vnd.in-toto+json"
PREDICATE_TYPE = "https://caterya.tech/assurance/v1"


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding."""
    t = payload_type.encode()
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(payload)).encode() + b" " + payload


def in_toto_statement(subject_name: str, subject_digest_hex: str, predicate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": subject_name, "digest": {"sha256": subject_digest_hex}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate,
    }


def dsse_sign(statement: Dict[str, Any], signer: Signer, payload_type: str = PAYLOAD_TYPE) -> Dict[str, Any]:
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    sig = signer.sign(pae(payload_type, payload))
    return {
        "payloadType": payload_type,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [{"keyid": signer.key_id, "alg": signer.alg, "sig": sig.hex()}],
    }


def dsse_verify(envelope: Dict[str, Any], keyring: Keyring) -> Dict[str, Any]:
    """Return the decoded statement if at least one signature verifies, else raise ValueError."""
    payload = base64.b64decode(envelope["payload"])
    msg = pae(envelope["payloadType"], payload)
    for s in envelope.get("signatures", []):
        if keyring.verify({"alg": s.get("alg", ""), "key_id": s["keyid"], "sig": s["sig"]}, msg):
            return json.loads(payload)
    raise ValueError("no valid DSSE signature")
