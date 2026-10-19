#!/usr/bin/env python3
"""Deploy CATERYA contracts to an EVM network.

    export CATERYA_EVM_PRIVATE_KEY=0x...      # read from the environment only; never passed as an argument
    python scripts/deploy_contracts.py --rpc https://... [--min-bond-wei 1000000000000000000 --withdraw-delay 604800 --arbiter 0x.. --treasury 0x..]

Status: exercised against an in-process test chain (see tests/test_blockchain_defi.py); NOT run on public networks and the
contracts are UNAUDITED. Read docs/BLOCKCHAIN_DEFI.md before deploying anywhere that holds value.
"""
import argparse
import json
import pathlib
import sys

ART = pathlib.Path(__file__).resolve().parents[1] / "contracts" / "artifacts" / "contracts.json"


def deploy_all(w3, send, min_bond_wei=0, withdraw_delay=0, arbiter=None, treasury=None, with_bond=True):
    """``send(contract_constructor_call) -> receipt``. Returns {name: address}."""
    art = json.loads(ART.read_text())
    out = {}
    for name, args in (("CateryaAnchorRegistry", ()), ("CateryaAssuranceGate", ()),
                       *((("CateryaEvaluatorBond", (min_bond_wei, withdraw_delay, arbiter, treasury)),) if with_bond else ())):
        c = w3.eth.contract(abi=art[name]["abi"], bytecode=art[name]["bytecode"])
        out[name] = send(c.constructor(*args)).contractAddress
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", required=True)
    ap.add_argument("--min-bond-wei", type=int, default=10**18)
    ap.add_argument("--withdraw-delay", type=int, default=7 * 86400)
    ap.add_argument("--arbiter")
    ap.add_argument("--treasury")
    ap.add_argument("--no-bond", action="store_true")
    a = ap.parse_args()
    from caterya.blockchain.evm import _Sender
    s = _Sender(rpc_url=a.rpc)

    def send(ctor):
        tx = ctor.build_transaction({"from": s.account, "nonce": s.w3.eth.get_transaction_count(s.account), "chainId": s.w3.eth.chain_id})
        h = s.w3.eth.send_raw_transaction(s._acct.sign_transaction(tx).raw_transaction)
        rc = s.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if rc.status != 1:
            sys.exit("deployment reverted")
        return rc

    if not a.no_bond and not (a.arbiter and a.treasury):
        sys.exit("--arbiter and --treasury are required unless --no-bond")
    print(json.dumps(deploy_all(s.w3, send, a.min_bond_wei, a.withdraw_delay, a.arbiter, a.treasury, not a.no_bond), indent=2))


if __name__ == "__main__":
    main()
