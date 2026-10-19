"""Evidence registry: hash chain + Merkle transparency log + signed tree heads + bundles."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..core.canonical import canonical_json, strip_algo
from ..core.models import Evidence
from .anchors import Anchor, AnchorReceipt
from .merkle import inclusion_proof, leaf_hash, merkle_root, verify_inclusion
from .signing import Keyring, Signer

GENESIS = "sha256:" + "0" * 64
BUNDLE_VERSION = "caterya.bundle/v1"


def _utc(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _leaf(ev: Evidence) -> bytes:
    return leaf_hash(bytes.fromhex(strip_algo(ev.record_hash)))


@dataclass
class VerificationReport:
    ok: bool
    count: int = 0
    errors: List[str] = field(default_factory=list)
    keys_trusted: bool = False
    asymmetric_only: bool = False
    root: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "count": self.count, "errors": self.errors, "keys_trusted": self.keys_trusted,
                "asymmetric_only": self.asymmetric_only, "root": self.root}


class EvidenceRegistry:
    """Append-only, signed, tamper-evident store of :class:`Evidence`."""

    def __init__(self, signer: Signer, keyring: Optional[Keyring] = None, clock: Callable[[], float] = time.time, path: Optional[str] = None):
        self.signer = signer
        self.keyring = keyring if keyring is not None else Keyring()
        self.keyring.add(signer)
        self.clock = clock
        self.path = path
        self._items: List[Evidence] = []
        self._index: Dict[str, int] = {}
        self.anchors: List[AnchorReceipt] = []

    # -- writing ---------------------------------------------------------------------------
    def append(self, ev: Evidence, signer: Optional[Signer] = None) -> Evidence:
        signer = signer or self.signer
        self.keyring.add(signer)
        ev.timestamp = ev.timestamp or _utc(self.clock())
        ev.actor = ev.actor or signer.key_id
        ev.prev_hash = self._items[-1].record_hash if self._items else GENESIS
        ev.record_hash = ev.compute_hash()
        ev.evidence_id = "ev_" + strip_algo(ev.record_hash)[:16]
        ev.signature = signer.signature_dict(bytes.fromhex(strip_algo(ev.record_hash)))
        self._index[ev.evidence_id] = len(self._items)
        self._items.append(ev)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev.to_dict(), sort_keys=True) + "\n")
        return ev

    # -- reading ---------------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def get(self, evidence_id: str) -> Evidence:
        return self._items[self._index[evidence_id]]

    def all(self) -> List[Evidence]:
        return list(self._items)

    # -- verification ----------------------------------------------------------------------
    @staticmethod
    def verify_items(items: List[Evidence], keyring: Keyring) -> VerificationReport:
        errors: List[str] = []
        prev = GENESIS
        asym = True
        for i, ev in enumerate(items):
            if ev.compute_hash() != ev.record_hash:
                errors.append(f"[{i}] {ev.evidence_id}: record hash mismatch (content altered)")
            if ev.prev_hash != prev:
                errors.append(f"[{i}] {ev.evidence_id}: broken chain link")
            if ev.evidence_id != "ev_" + strip_algo(ev.record_hash)[:16]:
                errors.append(f"[{i}] {ev.evidence_id}: evidence id does not match hash")
            if not keyring.verify(ev.signature, bytes.fromhex(strip_algo(ev.record_hash)) if ev.record_hash else b""):
                errors.append(f"[{i}] {ev.evidence_id}: invalid signature")
            if not keyring.is_asymmetric(ev.signature.get("key_id", "")):
                asym = False
            prev = ev.record_hash
        root = merkle_root([_leaf(e) for e in items]).hex()
        return VerificationReport(not errors, len(items), errors, keys_trusted=True, asymmetric_only=asym, root=root)

    def verify(self) -> VerificationReport:
        return self.verify_items(self._items, self.keyring)

    # -- transparency log ------------------------------------------------------------------
    def root(self) -> str:
        return merkle_root([_leaf(e) for e in self._items]).hex()

    def root_at(self, size: int) -> str:
        """Merkle root of the first ``size`` entries (to check an older anchor against the current log)."""
        return merkle_root([_leaf(e) for e in self._items[:size]]).hex()

    def tree_head(self) -> Dict[str, Any]:
        """Signed tree head (size + root + time)."""
        head = {"size": len(self._items), "root": self.root(), "timestamp": _utc(self.clock())}
        head["signature"] = self.signer.signature_dict(canonical_json(head))
        return head

    def proof(self, evidence_id: str) -> Dict[str, Any]:
        i = self._index[evidence_id]
        leaves = [_leaf(e) for e in self._items]
        return {"evidence_id": evidence_id, "index": i, "size": len(leaves), "root": merkle_root(leaves).hex(),
                "path": [p.hex() for p in inclusion_proof(leaves, i)]}

    @staticmethod
    def verify_proof(ev: Evidence, proof: Dict[str, Any]) -> bool:
        return verify_inclusion(_leaf(ev), proof["index"], proof["size"], [bytes.fromhex(p) for p in proof["path"]], bytes.fromhex(proof["root"]))

    def anchor(self, backend: Anchor, meta: Optional[Dict[str, Any]] = None) -> AnchorReceipt:
        rc = backend.anchor(self.root(), len(self._items), meta)
        self.anchors.append(rc)
        return rc

    # -- portable bundle -------------------------------------------------------------------
    def export_bundle(self) -> Dict[str, Any]:
        return {
            "version": BUNDLE_VERSION,
            "keyring": self.keyring.to_dict(),
            "evidence": [e.to_dict() for e in self._items],
            "tree_head": self.tree_head(),
            "anchors": [a.to_dict() for a in self.anchors],
        }

    @staticmethod
    def verify_bundle(bundle: Dict[str, Any], trusted: Optional[Keyring] = None) -> VerificationReport:
        """Verify a bundle offline.

        If ``trusted`` is given, signatures are checked against *your* keys and ``keys_trusted``
        is True only if every signing key is in it. Otherwise the bundle's own keyring is used
        (self-consistency only — it proves integrity, not who signed).
        """
        items = [Evidence.from_dict(d) for d in bundle["evidence"]]
        ring = trusted if trusted is not None else Keyring(bundle.get("keyring", {}))
        rep = EvidenceRegistry.verify_items(items, ring)
        rep.keys_trusted = trusted is not None and all(e.signature.get("key_id") in trusted.keys for e in items)
        head = bundle.get("tree_head")
        if head:
            h = {k: head[k] for k in ("size", "root", "timestamp")}
            if head["root"] != rep.root or head["size"] != len(items):
                rep.errors.append("tree head does not match evidence list")
            if not ring.verify(head.get("signature", {}), canonical_json(h)):
                rep.errors.append("tree head signature invalid")
        rep.ok = not rep.errors
        return rep

    @classmethod
    def load_bundle(cls, bundle: Dict[str, Any], signer: Signer) -> "EvidenceRegistry":
        reg = cls(signer, Keyring(bundle.get("keyring", {})))
        reg._items = [Evidence.from_dict(d) for d in bundle["evidence"]]
        reg._index = {e.evidence_id: i for i, e in enumerate(reg._items)}
        reg.anchors = [AnchorReceipt(**a) for a in bundle.get("anchors", [])]
        return reg
