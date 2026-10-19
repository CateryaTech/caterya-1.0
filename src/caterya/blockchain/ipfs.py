"""Content-addressed storage for evidence bundles: local store (default) and optional IPFS (Kubo RPC)."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
import urllib.request
from typing import Any, Dict

from ..adapters.net import check_url
from ..core.errors import VerificationError


class ContentStore:
    """Local content-addressed store: address = ``sha256:<hex>``. Reads are always re-hashed."""

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def put(self, data: bytes) -> str:
        h = hashlib.sha256(data).hexdigest()
        with open(os.path.join(self.root, h), "wb") as fh:
            fh.write(data)
        return f"sha256:{h}"

    def get(self, address: str) -> bytes:
        h = address.split(":", 1)[-1]
        with open(os.path.join(self.root, h), "rb") as fh:
            data = fh.read()
        if hashlib.sha256(data).hexdigest() != h:
            raise VerificationError("stored content does not match its address")
        return data

    def put_json(self, obj: Dict[str, Any]) -> str:
        return self.put(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())


class IPFSKuboClient:  # pragma: no cover - needs a running IPFS node
    """Pin/read via a Kubo node's HTTP RPC (default http://127.0.0.1:5001). Status: untested against a live node."""

    def __init__(self, api_url: str = "http://127.0.0.1:5001", allow_local: bool = True, timeout: float = 60.0):
        self.api, self.allow_local, self.timeout = api_url.rstrip("/"), allow_local, timeout

    def add(self, data: bytes, pin: bool = True) -> str:
        url = f"{self.api}/api/v0/add?pin={'true' if pin else 'false'}&cid-version=1"
        check_url(url, self.allow_local)
        b = uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"bundle.json\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
            return json.loads(r.read().decode())["Hash"]

    def cat(self, cid: str) -> bytes:
        url = f"{self.api}/api/v0/cat?arg={cid}"
        check_url(url, self.allow_local)
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
            return r.read()
