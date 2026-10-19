"""Salted commitments and selective disclosure.

A prover publishes one Merkle root over per-field commitments and later reveals chosen
fields (value + salt + inclusion proof) without revealing the others. This is hiding and
binding under SHA-256; it is **not** a zero-knowledge proof.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from ..core.canonical import canonical_json
from .merkle import inclusion_proof, leaf_hash, merkle_root, verify_inclusion


def commit_value(value: Any, salt: bytes) -> bytes:
    return leaf_hash(salt + canonical_json(value))


class SelectiveDisclosure:
    def __init__(self, fields: Dict[str, Any]):
        self.names: List[str] = sorted(fields)
        self.salts: Dict[str, bytes] = {k: os.urandom(16) for k in self.names}
        self.fields = dict(fields)
        self._leaves = [commit_value([k, fields[k]], self.salts[k]) for k in self.names]

    @property
    def root(self) -> str:
        return merkle_root(self._leaves).hex()

    @property
    def size(self) -> int:
        return len(self._leaves)

    def reveal(self, name: str) -> Dict[str, Any]:
        i = self.names.index(name)
        return {
            "name": name,
            "value": self.fields[name],
            "salt": self.salts[name].hex(),
            "index": i,
            "size": self.size,
            "proof": [p.hex() for p in inclusion_proof(self._leaves, i)],
        }


def verify_disclosure(root_hex: str, opening: Dict[str, Any]) -> bool:
    leaf = commit_value([opening["name"], opening["value"]], bytes.fromhex(opening["salt"]))
    return verify_inclusion(leaf, opening["index"], opening["size"], [bytes.fromhex(p) for p in opening["proof"]], bytes.fromhex(root_hex))
