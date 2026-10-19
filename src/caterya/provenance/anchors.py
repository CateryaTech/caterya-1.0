"""External anchoring of Merkle roots.

An anchor proves *"this root existed no later than T"* to a party that trusts the anchor
medium. Backends: local file (audit trail), dry-run (tests), EVM chain (see
``caterya.blockchain.evm``), or any custom ``Anchor``.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AnchorReceipt:
    backend: str
    ref: str  # file path#line, tx hash, ...
    root: str  # hex Merkle root
    size: int
    timestamp: float
    meta: Dict[str, Any] = field(default_factory=dict)
    third_party: bool = False  # True only if the medium is verifiable by parties who do not trust the operator

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Anchor:
    name = "abstract"
    #: whether the medium gives *third-party* verifiable timestamping
    third_party_verifiable = False

    def anchor(self, root_hex: str, size: int, meta: Optional[Dict[str, Any]] = None) -> AnchorReceipt:  # pragma: no cover
        raise NotImplementedError

    def verify(self, receipt: AnchorReceipt) -> bool:  # pragma: no cover
        raise NotImplementedError


class FileAnchor(Anchor):
    """Append-only JSONL file. Useful as an operator-side audit trail; NOT third-party verifiable."""

    name = "file"

    def __init__(self, path: str):
        self.path = path

    def anchor(self, root_hex, size, meta=None):
        rec = {"root": root_hex, "size": size, "ts": time.time(), "meta": meta or {}}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        with open(self.path, "r", encoding="utf-8") as fh:
            line_no = sum(1 for _ in fh)
        return AnchorReceipt(self.name, f"{self.path}#{line_no}", root_hex, size, rec["ts"], rec["meta"], self.third_party_verifiable)

    def verify(self, receipt):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    if r["root"] == receipt.root and r["size"] == receipt.size:
                        return True
        except FileNotFoundError:
            return False
        return False


class DryRunAnchor(Anchor):
    """Deterministic fake anchor for tests/CI. Provides no external trust whatsoever."""

    name = "dry-run"

    def __init__(self):
        self._seen: Dict[str, AnchorReceipt] = {}

    def anchor(self, root_hex, size, meta=None):
        ref = "dryrun:" + hashlib.sha256(f"{root_hex}:{size}".encode()).hexdigest()[:24]
        rc = AnchorReceipt(self.name, ref, root_hex, size, time.time(), dict(meta or {}, warning="no external trust"), False)
        self._seen[ref] = rc
        return rc

    def verify(self, receipt):
        return receipt.ref in self._seen and self._seen[receipt.ref].root == receipt.root
