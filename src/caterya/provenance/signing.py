"""Signing and key management.

* ``Ed25519Signer`` — real asymmetric signatures (needs the ``cryptography`` extra).
* ``HmacDevSigner`` — symmetric, *development only*. Anyone who can verify can also forge,
  so evidence signed this way can never reach assurance level >= 2.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import warnings
from typing import Dict, Optional

try:  # optional dependency
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    HAS_ED25519 = True
except Exception:  # pragma: no cover - exercised when extra is missing
    HAS_ED25519 = False

    class InvalidSignature(Exception):  # type: ignore[no-redef]
        pass

ED25519 = "Ed25519"
HMAC_DEV = "HMAC-SHA256-DEV"


def _kid(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


class Signer:
    alg: str = ""
    key_id: str = ""

    def sign(self, msg: bytes) -> bytes:  # pragma: no cover - interface
        raise NotImplementedError

    def public_key_hex(self) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def is_asymmetric(self) -> bool:
        return self.alg == ED25519

    def signature_dict(self, msg: bytes) -> Dict[str, str]:
        return {"alg": self.alg, "key_id": self.key_id, "sig": self.sign(msg).hex()}


class Ed25519Signer(Signer):
    alg = ED25519

    def __init__(self, private_key: Optional["ed25519.Ed25519PrivateKey"] = None):
        if not HAS_ED25519:
            raise ImportError("Ed25519 requires `pip install cryptography` (extra: caterya[crypto])")
        self._sk = private_key or ed25519.Ed25519PrivateKey.generate()
        pub = self._sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self._pub = pub
        self.key_id = _kid(pub)

    @classmethod
    def from_private_hex(cls, hexstr: str) -> "Ed25519Signer":
        return cls(ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hexstr)))

    def private_hex(self) -> str:
        raw = self._sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        return raw.hex()

    def sign(self, msg: bytes) -> bytes:
        return self._sk.sign(msg)

    def public_key_hex(self) -> str:
        return self._pub.hex()


class HmacDevSigner(Signer):
    alg = HMAC_DEV

    def __init__(self, secret: Optional[bytes] = None):
        self._secret = secret or os.urandom(32)
        self.key_id = _kid(self._secret)

    def sign(self, msg: bytes) -> bytes:
        return hmac.new(self._secret, msg, hashlib.sha256).digest()

    def public_key_hex(self) -> str:  # the "public" key of a symmetric scheme IS the secret
        return self._secret.hex()


def new_signer(prefer: str = ED25519) -> Signer:
    """Create a signer. Falls back to the dev-only HMAC signer *loudly* if Ed25519 is unavailable."""
    if prefer == ED25519 and HAS_ED25519:
        return Ed25519Signer()
    if prefer == ED25519:
        warnings.warn("cryptography not installed: using DEV-ONLY HMAC signer (max assurance level 1).", stacklevel=2)
    return HmacDevSigner()


class Keyring:
    """Maps ``key_id`` -> ``{alg, public}``; used to verify signatures."""

    def __init__(self, keys: Optional[Dict[str, Dict[str, str]]] = None):
        self.keys: Dict[str, Dict[str, str]] = dict(keys or {})

    def add(self, signer: Signer) -> "Keyring":
        self.keys[signer.key_id] = {"alg": signer.alg, "public": signer.public_key_hex()}
        return self

    def add_public(self, key_id: str, alg: str, public_hex: str) -> "Keyring":
        self.keys[key_id] = {"alg": alg, "public": public_hex}
        return self

    def to_dict(self) -> Dict[str, Dict[str, str]]:
        return {k: dict(v) for k, v in self.keys.items()}

    def verify(self, sig: Dict[str, str], msg: bytes) -> bool:
        if not sig:
            return False
        entry = self.keys.get(sig.get("key_id", ""))
        if not entry or entry["alg"] != sig.get("alg"):
            return False
        try:
            raw = bytes.fromhex(sig["sig"])
            if entry["alg"] == ED25519:
                if not HAS_ED25519:
                    return False
                ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(entry["public"])).verify(raw, msg)
                return True
            if entry["alg"] == HMAC_DEV:
                expect = hmac.new(bytes.fromhex(entry["public"]), msg, hashlib.sha256).digest()
                return hmac.compare_digest(raw, expect)
        except (InvalidSignature, ValueError, KeyError):
            return False
        return False

    def is_asymmetric(self, key_id: str) -> bool:
        return self.keys.get(key_id, {}).get("alg") == ED25519
