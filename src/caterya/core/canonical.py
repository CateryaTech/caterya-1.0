"""Canonical JSON and hashing.

All hashes in CATERYA are taken over canonical JSON (sorted keys, no whitespace,
UTF-8, finite floats rounded to 10 decimals) so that they are reproducible across
platforms and languages.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _clean(o: Any) -> Any:
    if isinstance(o, bool) or o is None or isinstance(o, (int, str)):
        return o
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            raise ValueError("non-finite float is not allowed in canonical JSON")
        return round(o, 10)
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        seq = sorted(o, key=repr) if isinstance(o, (set, frozenset)) else o
        return [_clean(v) for v in seq]
    if hasattr(o, "to_dict"):
        return _clean(o.to_dict())
    if isinstance(o, bytes):
        return o.hex()
    raise TypeError(f"cannot canonicalise object of type {type(o).__name__}")


def canonical_json(obj: Any) -> bytes:
    return json.dumps(_clean(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(obj: Any, algo: str = "sha256") -> str:
    """Return ``"<algo>:<hex>"`` of the canonical JSON of ``obj`` (bytes are hashed raw)."""
    raw = obj if isinstance(obj, (bytes, bytearray)) else canonical_json(obj)
    h = hashlib.new(algo)
    h.update(raw)
    return f"{algo}:{h.hexdigest()}"


def strip_algo(d: str) -> str:
    return d.split(":", 1)[1] if ":" in d else d
