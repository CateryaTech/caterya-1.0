"""Off-chain evaluation -> named decision -> on-chain attestation -> a DeFi-style consumer contract checks it.

Runs on an IN-PROCESS test chain (eth-tester): pip install "web3[tester]" cryptography. For a real network use scripts/deploy_contracts.py."""
import json
import pathlib

from web3 import EthereumTesterProvider, Web3

from caterya import AssuranceEngine, Decider, MockModel, SystemConfig, new_signer
from caterya.blockchain.evm import AssuranceGateClient, EVMAnchor, to_bytes32

art = json.loads((pathlib.Path(__file__).parents[1] / "contracts" / "artifacts" / "contracts.json").read_text())
w3 = Web3(EthereumTesterProvider())
me = w3.eth.accounts[0]


def deploy(name, *args):
    c = w3.eth.contract(abi=art[name]["abi"], bytecode=art[name]["bytecode"])
    return w3.eth.wait_for_transaction_receipt(c.constructor(*args).transact({"from": me})).contractAddress


gate_addr, anchor_addr = deploy("CateryaAssuranceGate"), deploy("CateryaAnchorRegistry")
gate = AssuranceGateClient(gate_addr, w3=w3, account=me)
gate.contract.functions.setAttester(me, True).transact({"from": me})        # governance: who may attest

engine = AssuranceEngine(SystemConfig("trading-agent", "1", owner="Fund Y", intended_use="portfolio rebalancing", description="demo", model_id="m"))
report = engine.evaluate(MockModel())
reproduced = engine.reproduce(report)
decision = engine.decide(report, Decider("Dr. Rina", "Head of AI Risk", new_signer()), "ASSURED", "Evidence reviewed; residual risk accepted.")
engine.registry.anchor(EVMAnchor(anchor_addr, w3=w3, account=me))          # public timestamp of the evidence root
level = engine.level(report, reproduced=reproduced, decision=decision)
print("off-chain level:", level["label"])

gate.attest_from_decision(report, decision, level["level"])                 # publish the verified decision on-chain
print("gate says assured >= 3:", gate.is_assured(report.system_hash, 3), "| >= 4:", gate.is_assured(report.system_hash, 4))

pool = w3.eth.contract(address=deploy("AssuranceGatedPool", gate_addr, 3), abi=art["AssuranceGatedPool"]["abi"])
pool.functions.setManager(to_bytes32(report.system_hash)).transact({"from": me})
pool.functions.execute(b"\x01" * 32).transact({"from": me})
print("consumer contract executed while assured")
gate.revoke(report.system_hash, "incident INC-7")
print("after revocation, assured:", gate.is_assured(report.system_hash, 1))
try:
    pool.functions.execute(b"\x01" * 32).transact({"from": me})
except Exception as e:
    print("consumer contract now refuses:", type(e).__name__)
