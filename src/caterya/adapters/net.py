"""Egress-controlled HTTP helper (stdlib only). Used by hosted-model adapters and IPFS/RPC clients."""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ..core.errors import PolicyViolation


def check_url(url: str, allow_local: bool = False) -> None:
    """Enforce https, an optional host allow-list (``CATERYA_ALLOWED_HOSTS``) and no private IPs."""
    u = urlparse(url)
    if u.scheme not in ("https", "http"):
        raise PolicyViolation(f"unsupported scheme: {u.scheme!r}")
    host = u.hostname or ""
    allowed = [h.strip().lower() for h in os.environ.get("CATERYA_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if allowed and host.lower() not in allowed:
        raise PolicyViolation(f"host {host!r} is not in CATERYA_ALLOWED_HOSTS")
    if u.scheme == "http" and not allow_local:
        raise PolicyViolation("plain http is only allowed with allow_local=True")
    if not allow_local:
        try:
            for _fam, _, _, _, sa in socket.getaddrinfo(host, None):
                ip = ipaddress.ip_address(sa[0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise PolicyViolation(f"host {host!r} resolves to a non-public address")
        except socket.gaierror as e:
            raise PolicyViolation(f"cannot resolve host {host!r}") from e


def post_json(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: float = 60.0, allow_local: bool = False) -> Dict[str, Any]:
    check_url(url, allow_local)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - scheme validated above
        return json.loads(resp.read().decode())
