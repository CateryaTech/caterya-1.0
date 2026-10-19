"""EVM integration (optional extra: ``caterya[web3]``).

* ``EVMAnchor``            - anchor evidence Merkle roots in ``CateryaAnchorRegistry``.
* ``AssuranceGateClient``  - publish/read attestations in ``CateryaAssuranceGate`` (what DeFi contracts query).
* ``EvaluatorBondClient``  - bond/slash helpers for ``CateryaEvaluatorBond``.

Keys: a private key is read ONLY from an environment variable (default ``CATERYA_EVM_PRIVATE_KEY``);
it is never accepted as an argument, logged, or stored. For local chains (eth-tester, anvil, hardhat)
pass an unlocked ``account`` instead. Status: tested against an in-process EVM; not run on public networks.
"""
from __future__ import annotations

import calendar
import json
import os
import time
from importlib import resources
from typing import Any, Dict, Optional

from ..core.errors import BackendUnavailable
from ..provenance.anchors import Anchor, AnchorReceipt


def _web3():
    try:
        import web3
        return web3
    except Exception as e:  # pragma: no cover
        raise BackendUnavailable("web3 not installed: pip install 'caterya[web3]'") from e


def load_abi(name: str) -> list:
    return json.loads(resources.files("caterya.blockchain").joinpath("abi", f"{name}.json").read_text(encoding="utf-8"))


def to_bytes32(hex_or_digest: str) -> bytes:
    h = hex_or_digest.split(":", 1)[-1]
    if h.startswith("0x"):
        h = h[2:]
    b = bytes.fromhex(h)
    if len(b) != 32:
        raise ValueError("expected a 32-byte hash")
    return b


def iso_to_epoch(ts: str) -> int:
    return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))


class _Sender:
    """Shared transaction plumbing: unlocked account (dev chains) or env-var private key (real RPC)."""

    def __init__(self, w3=None, rpc_url: Optional[str] = None, account: Optional[str] = None, private_key_env: str = "CATERYA_EVM_PRIVATE_KEY", timeout: int = 120):
        web3 = _web3()
        if w3 is None:
            if not rpc_url:
                raise ValueError("pass w3=... or rpc_url=...")
            w3 = web3.Web3(web3.Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout}))
        self.w3, self.account, self.private_key_env, self.timeout = w3, account, private_key_env, timeout
        self._acct = None
        if account is None:
            key = os.environ.get(private_key_env)
            if not key:
                raise ValueError(f"set {private_key_env} or pass account= (unlocked dev account)")
            self._acct = w3.eth.account.from_key(key)
            self.account = self._acct.address

    def send(self, fn) -> Any:
        w3 = self.w3
        if self._acct is None:
            txh = fn.transact({"from": self.account})
        else:
            tx = fn.build_transaction({"from": self.account, "nonce": w3.eth.get_transaction_count(self.account), "chainId": w3.eth.chain_id})
            txh = w3.eth.send_raw_transaction(self._acct.sign_transaction(tx).raw_transaction)
        rc = w3.eth.wait_for_transaction_receipt(txh, timeout=self.timeout)
        if rc.status != 1:
            raise RuntimeError(f"transaction reverted: {txh.hex()}")
        return rc


class EVMAnchor(Anchor):
    name = "evm"
    third_party_verifiable = True

    def __init__(self, contract_address: str, w3=None, rpc_url: Optional[str] = None, account: Optional[str] = None, uri_prefix: str = "caterya://", **kw: Any):
        self._s = _Sender(w3, rpc_url, account, **kw)
        self.contract = self._s.w3.eth.contract(address=_web3().Web3.to_checksum_address(contract_address), abi=load_abi("CateryaAnchorRegistry"))
        self.uri_prefix = uri_prefix

    def anchor(self, root_hex: str, size: int, meta: Optional[Dict[str, Any]] = None) -> AnchorReceipt:
        uri = (meta or {}).get("uri", f"{self.uri_prefix}{root_hex}")
        rc = self._s.send(self.contract.functions.anchorRoot(to_bytes32(root_hex), int(size), uri))
        ev = self.contract.events.Anchored().process_receipt(rc)
        index = ev[0]["args"]["index"] if ev else -1
        block = self._s.w3.eth.get_block(rc.blockNumber)
        return AnchorReceipt(self.name, rc.transactionHash.hex(), root_hex, size, float(block.timestamp),
                             {"chain_id": self._s.w3.eth.chain_id, "contract": self.contract.address, "block": rc.blockNumber, "index": index, "uri": uri}, True)

    def verify(self, receipt: AnchorReceipt) -> bool:
        ok, _ts = self.contract.functions.isAnchored(to_bytes32(receipt.root)).call()
        return bool(ok)


class AssuranceGateClient:
    def __init__(self, contract_address: str, w3=None, rpc_url: Optional[str] = None, account: Optional[str] = None, **kw: Any):
        self._s = _Sender(w3, rpc_url, account, **kw)
        self.contract = self._s.w3.eth.contract(address=_web3().Web3.to_checksum_address(contract_address), abi=load_abi("CateryaAssuranceGate"))

    def attest(self, system_hash: str, level: int, car_hash: str, expires_at: int) -> str:
        return self._s.send(self.contract.functions.attest(to_bytes32(system_hash), int(level), to_bytes32(car_hash), int(expires_at))).transactionHash.hex()

    def attest_from_decision(self, report: Any, decision_evidence: Any, level: int) -> str:
        """Publish a verified off-chain decision. ``level`` should come from ``engine.level(...)['level']``."""
        return self.attest(report.system_hash, level, report.car_evidence.record_hash, iso_to_epoch(decision_evidence.result["valid_until"]))

    def revoke(self, system_hash: str, reason: str) -> str:
        return self._s.send(self.contract.functions.revoke(to_bytes32(system_hash), reason)).transactionHash.hex()

    def is_assured(self, system_hash: str, min_level: int) -> bool:
        return bool(self.contract.functions.isAssured(to_bytes32(system_hash), int(min_level)).call())

    def get(self, system_hash: str) -> Dict[str, Any]:
        lvl, car, issued, exp, att, rev = self.contract.functions.getAttestation(to_bytes32(system_hash)).call()
        return {"level": lvl, "car_hash": "0x" + car.hex(), "issued_at": issued, "expires_at": exp, "attester": att, "revoked": rev}


class EvaluatorBondClient:
    def __init__(self, contract_address: str, w3=None, rpc_url: Optional[str] = None, account: Optional[str] = None, **kw: Any):
        self._s = _Sender(w3, rpc_url, account, **kw)
        self.contract = self._s.w3.eth.contract(address=_web3().Web3.to_checksum_address(contract_address), abi=load_abi("CateryaEvaluatorBond"))

    def deposit(self, wei: int) -> str:
        w3 = self._s.w3
        fn = self.contract.functions.deposit()
        if self._s._acct is None:
            txh = fn.transact({"from": self._s.account, "value": wei})
        else:  # pragma: no cover - real RPC path
            tx = fn.build_transaction({"from": self._s.account, "value": wei, "nonce": w3.eth.get_transaction_count(self._s.account), "chainId": w3.eth.chain_id})
            txh = w3.eth.send_raw_transaction(self._s._acct.sign_transaction(tx).raw_transaction)
        return w3.eth.wait_for_transaction_receipt(txh).transactionHash.hex()

    def is_bonded(self, evaluator: str) -> bool:
        return bool(self.contract.functions.isBonded(_web3().Web3.to_checksum_address(evaluator)).call())
