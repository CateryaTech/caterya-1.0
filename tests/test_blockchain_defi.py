import json
from pathlib import Path

import pytest

from caterya import AssuranceEngine, Decider, MockModel, new_signer
from caterya.blockchain.defi import ProofToken
from caterya.blockchain.ipfs import ContentStore
from caterya.blockchain.zk import SignedThresholdClaim, UnavailableZK
from caterya.core.errors import BackendUnavailable, VerificationError
from caterya.provenance.signing import HAS_ED25519, Keyring

ARTIFACTS = Path(__file__).resolve().parents[1] / "contracts" / "artifacts" / "contracts.json"


def test_proof_token_roundtrip_expiry_level_and_system_binding():
    s = new_signer()
    ring = Keyring().add(s)
    tok = ProofToken.issue(s, "sha256:" + "11" * 32, 3, "sha256:" + "22" * 32, ttl_seconds=60, now=1000)
    assert ProofToken.verify(tok, ring, now=1010, min_level=3)["lvl"] == 3
    for kw, msg in (({"now": 1100}, "expired"), ({"now": 1010, "min_level": 4}, "level"), ({"now": 1010, "system_hash": "sha256:" + "99" * 32}, "different system")):
        with pytest.raises(VerificationError, match=msg):
            ProofToken.verify(tok, ring, **kw)
    with pytest.raises(VerificationError):
        ProofToken.verify(tok[:-3] + "AAA", ring, now=1010)
    with pytest.raises(VerificationError):
        ProofToken.verify(tok, Keyring(), now=1010)  # unknown issuer
    with pytest.raises(VerificationError):
        ProofToken.verify("garbage", ring)


def test_content_store_detects_corruption(tmp_path):
    cs = ContentStore(str(tmp_path))
    addr = cs.put_json({"a": 1})
    assert json.loads(cs.get(addr)) == {"a": 1}
    (tmp_path / addr.split(":")[1]).write_bytes(b"tampered")
    with pytest.raises(VerificationError):
        cs.get(addr)


def test_zk_is_honestly_unavailable_and_threshold_claim_is_not_zk():
    with pytest.raises(BackendUnavailable):
        UnavailableZK().prove("c", {}, {})
    s = new_signer()
    claim = SignedThresholdClaim.make(s, "m_v1", 0.93, 0.9, "sha256:" + "aa" * 32)
    assert claim["zk"] is False and "0.93" not in json.dumps(claim)
    assert SignedThresholdClaim.verify(claim, Keyring().add(s))
    claim["threshold"] = 0.5
    assert not SignedThresholdClaim.verify(claim, Keyring().add(s))
    with pytest.raises(ValueError):
        SignedThresholdClaim.make(s, "m", 0.5, 0.9, "x")  # refuses to sign a false claim


# ----------------------------------------------------------------------------------------------------------
web3 = pytest.importorskip("web3", reason="web3 extra not installed")
pytest.importorskip("eth_tester", reason="eth-tester not installed")
from web3 import EthereumTesterProvider, Web3  # noqa: E402

from caterya.blockchain.evm import AssuranceGateClient, EVMAnchor, EvaluatorBondClient, iso_to_epoch, to_bytes32  # noqa: E402

pytestmark_evm = pytest.mark.skipif(not ARTIFACTS.exists(), reason="run `node contracts/scripts/compile.js --bytecode contracts/artifacts/contracts.json`")


@pytest.fixture
def chain():
    w3 = Web3(EthereumTesterProvider())
    art = json.loads(ARTIFACTS.read_text())

    def deploy(name, *args, frm=None):
        c = w3.eth.contract(abi=art[name]["abi"], bytecode=art[name]["bytecode"])
        return w3.eth.wait_for_transaction_receipt(c.constructor(*args).transact({"from": frm or w3.eth.accounts[0]})).contractAddress

    return w3, art, deploy


def revert(fn):
    from eth_tester.exceptions import TransactionFailed
    with pytest.raises(TransactionFailed):
        fn()


@pytestmark_evm
def test_evm_anchor(chain):
    w3, _, deploy = chain
    a = EVMAnchor(deploy("CateryaAnchorRegistry"), w3=w3, account=w3.eth.accounts[0])
    rc = a.anchor("ab" * 32, 7)
    assert rc.third_party and rc.meta["index"] == 0 and a.verify(rc)
    rc.root = "cd" * 32
    assert not a.verify(rc)


@pytestmark_evm
def test_anchor_registry_access_control(chain):
    w3, art, deploy = chain
    addr = deploy("CateryaAnchorRegistry")
    outsider = EVMAnchor(addr, w3=w3, account=w3.eth.accounts[5])
    revert(lambda: outsider.anchor("ab" * 32, 1))
    c = w3.eth.contract(address=addr, abi=art["CateryaAnchorRegistry"]["abi"])
    revert(lambda: c.functions.anchorRoot(b"\x00" * 32, 1, "u").transact({"from": w3.eth.accounts[0]}))  # zero root rejected


@pytestmark_evm
def test_gate_levels_revoke_expiry_and_consumer_contract(chain):
    w3, art, deploy = chain
    acct = w3.eth.accounts
    gate_addr = deploy("CateryaAssuranceGate")
    g = AssuranceGateClient(gate_addr, w3=w3, account=acct[0])
    sh, car = "sha256:" + "11" * 32, "sha256:" + "22" * 32
    now = lambda: w3.eth.get_block("latest").timestamp  # noqa: E731
    revert(lambda: g.attest(sh, 3, car, now() + 3600))  # not an attester yet
    g.contract.functions.setAttester(acct[0], True).transact({"from": acct[0]})
    revert(lambda: g.attest(sh, 5, car, now() + 3600))  # level > MAX_LEVEL
    revert(lambda: g.attest(sh, 3, car, now() - 1))  # already expired
    g.attest(sh, 3, car, now() + 3600)
    assert g.is_assured(sh, 3) and not g.is_assured(sh, 4)

    pool_addr = deploy("AssuranceGatedPool", gate_addr, 3)
    pool = w3.eth.contract(address=pool_addr, abi=art["AssuranceGatedPool"]["abi"])
    pool.functions.setManager(to_bytes32(sh)).transact({"from": acct[0]})
    pool.functions.execute(b"\x01" * 32).transact({"from": acct[1]})
    revert(lambda: g.contract.functions.revoke(to_bytes32(sh), "x").transact({"from": acct[7]}))  # outsider cannot revoke
    g.revoke(sh, "incident INC-1")
    assert not g.is_assured(sh, 0) and g.get(sh)["revoked"]
    revert(lambda: pool.functions.execute(b"\x01" * 32).transact({"from": acct[1]}))  # revocation takes effect immediately

    g.attest(sh, 3, car, now() + 100)
    w3.provider.ethereum_tester.time_travel(now() + 1000)
    w3.provider.ethereum_tester.mine_block()
    assert not g.is_assured(sh, 0)  # expired
    # a de-listed attester invalidates its attestations
    g.attest(sh, 3, car, now() + 10_000)
    assert g.is_assured(sh, 3)
    g.contract.functions.setAttester(acct[0], False).transact({"from": acct[0]})
    assert not g.is_assured(sh, 3)


@pytestmark_evm
def test_evaluator_bond(chain):
    w3, art, deploy = chain
    acct = w3.eth.accounts
    addr = deploy("CateryaEvaluatorBond", 10**18, 3600, acct[2], acct[3])
    b = EvaluatorBondClient(addr, w3=w3, account=acct[1])
    c = w3.eth.contract(address=addr, abi=art["CateryaEvaluatorBond"]["abi"])
    assert not b.is_bonded(acct[1])
    b.deposit(2 * 10**18)
    assert b.is_bonded(acct[1])
    revert(lambda: c.functions.slash(acct[1], 10**18, b"\x09" * 32).transact({"from": acct[1]}))  # only arbiter
    before = w3.eth.get_balance(acct[3])
    c.functions.slash(acct[1], 10**18, b"\x09" * 32).transact({"from": acct[2]})
    assert w3.eth.get_balance(acct[3]) - before == 10**18
    revert(lambda: c.functions.slash(acct[1], 5 * 10**18, b"\x09" * 32).transact({"from": acct[2]}))  # more than bonded
    c.functions.requestWithdraw().transact({"from": acct[1]})
    assert not b.is_bonded(acct[1])  # withdrawing evaluators are not "bonded"
    revert(lambda: c.functions.withdraw().transact({"from": acct[1]}))  # delay not elapsed
    w3.provider.ethereum_tester.time_travel(w3.eth.get_block("latest").timestamp + 4000)
    w3.provider.ethereum_tester.mine_block()
    c.functions.withdraw().transact({"from": acct[1]})
    assert c.functions.bonds(acct[1]).call()[0] == 0


@pytestmark_evm
@pytest.mark.skipif(not HAS_ED25519, reason="needs Ed25519 for L3+")
def test_engine_to_chain_end_to_end(chain, system):
    """Off-chain evaluation -> named decision -> level -> on-chain attestation + anchor -> DeFi consumer check."""
    w3, art, deploy = chain
    acct = w3.eth.accounts
    eng = AssuranceEngine(system)
    rep = eng.evaluate(MockModel())
    rr = eng.reproduce(rep)
    dec = eng.decide(rep, Decider("Dr. Rina", "Head of Risk", new_signer()), "ASSURED", "ok")
    gate = AssuranceGateClient(deploy("CateryaAssuranceGate"), w3=w3, account=acct[0])
    gate.contract.functions.setAttester(acct[0], True).transact({"from": acct[0]})
    anchor = EVMAnchor(deploy("CateryaAnchorRegistry"), w3=w3, account=acct[0])
    eng.registry.anchor(anchor)
    lvl = eng.level(rep, reproduced=rr, decision=dec)["level"]
    assert lvl == 3
    gate.attest_from_decision(rep, dec, lvl)
    assert gate.is_assured(rep.system_hash, 3) and not gate.is_assured(rep.system_hash, 4)
    assert gate.get(rep.system_hash)["car_hash"] == "0x" + rep.car_evidence.record_hash.split(":")[1]
    assert iso_to_epoch(dec.result["valid_until"]) == gate.get(rep.system_hash)["expires_at"]


@pytestmark_evm
def test_deploy_script_helper_deploys_everything(chain):
    import importlib.util
    spec = importlib.util.spec_from_file_location("deploy_contracts", Path(__file__).resolve().parents[1] / "scripts" / "deploy_contracts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    w3, art, _ = chain
    acct = w3.eth.accounts

    def send(ctor):
        return w3.eth.wait_for_transaction_receipt(ctor.transact({"from": acct[0]}))
    addrs = mod.deploy_all(w3, send, 10**18, 3600, acct[1], acct[2])
    assert set(addrs) == {"CateryaAnchorRegistry", "CateryaAssuranceGate", "CateryaEvaluatorBond"}
    assert all(w3.eth.get_code(a) for a in addrs.values())
