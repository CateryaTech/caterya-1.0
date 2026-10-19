import pytest

from caterya.core.canonical import canonical_json, digest
from caterya.core.models import Evidence, MetricSpec
from caterya.core.stats import wilson_ci
from caterya.provenance.anchors import DryRunAnchor, FileAnchor
from caterya.provenance.attestation import dsse_sign, dsse_verify, in_toto_statement
from caterya.provenance.commitments import SelectiveDisclosure, verify_disclosure
from caterya.provenance.merkle import inclusion_proof, leaf_hash, merkle_root, verify_inclusion
from caterya.provenance.registry import EvidenceRegistry
from caterya.provenance.signing import HAS_ED25519, HmacDevSigner, Keyring, new_signer


def test_canonical_is_order_independent_and_rejects_nan():
    assert canonical_json({"b": 1, "a": [1.0, 2]}) == canonical_json({"a": [1.0, 2], "b": 1})
    assert digest({"x": 1}).startswith("sha256:")
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def test_spec_hash_changes_with_parameters():
    a = MetricSpec("m", 1, "d", "desc", parameters={"k": 1})
    b = MetricSpec("m", 1, "d", "desc", parameters={"k": 2})
    assert a.spec_hash() != b.spec_hash()


def test_wilson_interval_bounds():
    lo, hi = wilson_ci(10, 10)
    assert 0.6 < lo < 1.0 and hi == pytest.approx(1.0)
    assert wilson_ci(0, 0) == (0.0, 1.0)


@pytest.mark.parametrize("n", list(range(1, 18)))
def test_merkle_inclusion_all_sizes(n):
    leaves = [leaf_hash(bytes([i])) for i in range(n)]
    root = merkle_root(leaves)
    for i in range(n):
        assert verify_inclusion(leaves[i], i, n, inclusion_proof(leaves, i), root)
        wrong = leaf_hash(b"x")
        assert not verify_inclusion(wrong, i, n, inclusion_proof(leaves, i), root)


def _registry(n=5):
    reg = EvidenceRegistry(new_signer())
    for i in range(n):
        reg.append(Evidence(kind="note", claim=f"c{i}", result={"v": i}))
    return reg


def test_chain_verifies_and_detects_tamper():
    reg = _registry()
    assert reg.verify().ok
    reg._items[2].claim = "tampered"
    rep = reg.verify()
    assert not rep.ok and any("altered" in e for e in rep.errors)


def test_chain_detects_deletion_and_reorder():
    reg = _registry()
    items = reg.all()
    assert not EvidenceRegistry.verify_items(items[:1] + items[2:], reg.keyring).ok
    assert not EvidenceRegistry.verify_items([items[1], items[0], *items[2:]], reg.keyring).ok


def test_signature_forgery_detected():
    reg = _registry(3)
    other = new_signer()
    ev = reg.get(reg.all()[1].evidence_id)
    ev.signature = other.signature_dict(bytes.fromhex(ev.record_hash.split(":")[1]))
    assert not reg.verify().ok  # other key is not in the keyring


def test_bundle_roundtrip_and_trusted_keys():
    reg = _registry()
    b = reg.export_bundle()
    assert EvidenceRegistry.verify_bundle(b).ok
    rep = EvidenceRegistry.verify_bundle(b, Keyring(b["keyring"]))
    assert rep.ok and rep.keys_trusted
    assert not EvidenceRegistry.verify_bundle(b, Keyring()).keys_trusted
    b["evidence"][0]["claim"] = "x"
    assert not EvidenceRegistry.verify_bundle(b).ok


def test_tree_head_signature_checked():
    reg = _registry()
    b = reg.export_bundle()
    b["tree_head"]["root"] = "00" * 32
    assert not EvidenceRegistry.verify_bundle(b).ok


def test_inclusion_proof_via_registry():
    reg = _registry(7)
    for e in reg:
        assert EvidenceRegistry.verify_proof(e, reg.proof(e.evidence_id))


def test_hmac_dev_signer_is_never_asymmetric():
    reg = EvidenceRegistry(HmacDevSigner())
    reg.append(Evidence(kind="note", claim="x"))
    rep = reg.verify()
    assert rep.ok and not rep.asymmetric_only


@pytest.mark.skipif(not HAS_ED25519, reason="cryptography not installed")
def test_ed25519_signatures_are_asymmetric_and_verifiable_with_public_key_only():
    reg = _registry()
    ring = Keyring()
    for kid, e in reg.keyring.keys.items():
        ring.add_public(kid, e["alg"], e["public"])
    assert EvidenceRegistry.verify_items(reg.all(), ring).asymmetric_only


def test_selective_disclosure():
    sd = SelectiveDisclosure({"a": 1, "b": [1, 2], "c": "secret", "d": 0.5})
    op = sd.reveal("b")
    assert verify_disclosure(sd.root, op)
    op["value"] = [9]
    assert not verify_disclosure(sd.root, op)
    assert "secret" not in str(sd.reveal("a"))


def test_dsse_roundtrip_and_tamper():
    s = new_signer()
    ring = Keyring().add(s)
    env = dsse_sign(in_toto_statement("sys", "ab" * 32, {"level": 2}), s)
    assert dsse_verify(env, ring)["predicate"]["level"] == 2
    env["payload"] = env["payload"][:-4] + "AAAA"
    with pytest.raises(Exception):
        dsse_verify(env, ring)


def test_anchors(tmp_path):
    reg = _registry()
    fa = FileAnchor(str(tmp_path / "a.jsonl"))
    rc = reg.anchor(fa)
    assert fa.verify(rc) and not rc.third_party
    dr = DryRunAnchor()
    rc2 = reg.anchor(dr)
    assert dr.verify(rc2) and not rc2.third_party
