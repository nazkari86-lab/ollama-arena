"""Tests for BlockchainAnchorer, ResultSignature, and ProofGenerator."""
from __future__ import annotations

import time

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# ResultSignature
# ──────────────────────────────────────────────────────────────────────────────

class TestResultSignature:
    def _make(self):
        from ollama_arena.p2p.crypto_proof import ResultSignature
        return ResultSignature(
            node_id="node_1",
            task_id="task_abc",
            signature="deadbeef",
            public_key="cafebabe",
            timestamp=time.time(),
        )

    def test_to_dict_has_node_id(self):
        d = self._make().to_dict()
        assert d["node_id"] == "node_1"

    def test_to_dict_has_task_id(self):
        d = self._make().to_dict()
        assert d["task_id"] == "task_abc"

    def test_to_dict_has_algorithm(self):
        d = self._make().to_dict()
        assert d["algorithm"] == "ed25519"

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.crypto_proof import ResultSignature
        original = self._make()
        d = original.to_dict()
        restored = ResultSignature.from_dict(d)
        assert restored.node_id == original.node_id
        assert restored.signature == original.signature

    def test_from_dict_default_algorithm(self):
        from ollama_arena.p2p.crypto_proof import ResultSignature
        d = {
            "node_id": "n",
            "task_id": "t",
            "signature": "sig",
            "public_key": "pub",
            "timestamp": time.time(),
        }
        rs = ResultSignature.from_dict(d)
        assert rs.algorithm == "ed25519"


# ──────────────────────────────────────────────────────────────────────────────
# BlockchainAnchorer — pure hashlib, no crypto needed
# ──────────────────────────────────────────────────────────────────────────────

class TestBlockchainAnchorer:
    def _make(self, network="ethereum"):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchorer
        return BlockchainAnchorer(network=network)

    def test_init_default_network(self):
        a = self._make()
        assert a.network == "ethereum"

    def test_init_custom_network(self):
        a = self._make("bitcoin")
        assert a.network == "bitcoin"

    def test_pending_anchors_initially_empty(self):
        a = self._make()
        assert a.pending_anchors == []

    def test_create_anchor_hash_deterministic(self):
        a = self._make()
        record = {"model": "llama3", "score": 0.95}
        h1 = a.create_anchor_hash(record)
        h2 = a.create_anchor_hash(record)
        assert h1 == h2

    def test_create_anchor_hash_is_string(self):
        a = self._make()
        h = a.create_anchor_hash({"k": "v"})
        assert isinstance(h, str)
        assert len(h) == 64

    def test_create_anchor_hash_different_records(self):
        a = self._make()
        h1 = a.create_anchor_hash({"a": 1})
        h2 = a.create_anchor_hash({"b": 2})
        assert h1 != h2

    def test_anchor_to_blockchain_returns_anchor(self):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchor
        a = self._make()
        bundle = {"task_id": "t1", "result": {"score": 0.9}}
        anchor = a.anchor_to_blockchain(bundle)
        assert isinstance(anchor, BlockchainAnchor)

    def test_anchor_has_transaction_hash(self):
        a = self._make()
        bundle = {"task_id": "t1"}
        anchor = a.anchor_to_blockchain(bundle)
        assert anchor.transaction_hash is not None
        assert len(anchor.transaction_hash) == 64

    def test_anchor_network_matches(self):
        a = self._make("bitcoin")
        anchor = a.anchor_to_blockchain({"data": "x"})
        assert anchor.network == "bitcoin"

    def test_anchor_block_height_zero_for_simulation(self):
        a = self._make()
        anchor = a.anchor_to_blockchain({"x": 1})
        assert anchor.block_height == 0

    def test_verify_anchor_valid_tx_hash(self):
        a = self._make()
        bundle = {"task_id": "t1"}
        anchor = a.anchor_to_blockchain(bundle)
        result = a.verify_anchor(bundle, anchor)
        assert result is True

    def test_verify_anchor_short_tx_hash_invalid(self):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchor
        a = self._make()
        anchor = BlockchainAnchor(
            transaction_hash="tooshort",
            block_height=1,
            block_hash="0x000",
            timestamp=time.time(),
        )
        result = a.verify_anchor({}, anchor)
        assert result is False

    def test_get_anchor_status_returns_simulated(self):
        a = self._make()
        status = a.get_anchor_status("abc123")
        assert status == "simulated"

    def test_anchor_has_timestamp(self):
        a = self._make()
        anchor = a.anchor_to_blockchain({"x": 1})
        assert anchor.timestamp > 0


# ──────────────────────────────────────────────────────────────────────────────
# ProofGenerator — requires cryptography library
# ──────────────────────────────────────────────────────────────────────────────

class TestProofGenerator:
    @pytest.fixture(autouse=True)
    def skip_without_crypto(self):
        from ollama_arena.p2p import crypto_proof
        if not crypto_proof.CRYPTO_AVAILABLE:
            pytest.skip("cryptography library not available")

    def _make(self, node_id="node_test"):
        from ollama_arena.p2p.crypto_proof import CryptoProofGenerator
        return CryptoProofGenerator(node_id=node_id)

    def test_init_does_not_crash(self):
        g = self._make()
        assert g is not None

    def test_node_id_set(self):
        g = self._make("my_node")
        assert g.node_id == "my_node"

    def test_has_key_pair(self):
        from ollama_arena.p2p.crypto_proof import KeyPair
        g = self._make()
        assert isinstance(g.key_pair, KeyPair)

    def test_has_hardware_attestation(self):
        from ollama_arena.p2p.crypto_proof import HardwareAttestation
        g = self._make()
        assert isinstance(g.hardware_attestation, HardwareAttestation)

    def test_sign_result_returns_result_signature(self):
        from ollama_arena.p2p.crypto_proof import ResultSignature
        g = self._make()
        result = {"score": 0.95, "tps": 42.0}
        sig = g.sign_result("task_1", result)
        assert isinstance(sig, ResultSignature)

    def test_sign_result_node_id_matches(self):
        g = self._make("node_abc")
        sig = g.sign_result("task_1", {"x": 1})
        assert sig.node_id == "node_abc"

    def test_sign_result_has_task_id(self):
        g = self._make()
        sig = g.sign_result("my_task", {"x": 1})
        assert sig.task_id == "my_task"

    def test_verify_signature_valid(self):
        g = self._make()
        result = {"score": 0.9}
        sig = g.sign_result("task_1", result)
        assert g.verify_signature(sig, result) is True

    def test_verify_signature_tampered_result_returns_false(self):
        g = self._make()
        result = {"score": 0.9}
        sig = g.sign_result("task_1", result)
        tampered = {"score": 0.5}
        assert g.verify_signature(sig, tampered) is False

    def test_generate_execution_proof_returns_zkp(self):
        from ollama_arena.p2p.crypto_proof import ZeroKnowledgeProof
        g = self._make()
        trace = [{"step": 1, "output": "hello"}, {"step": 2, "output": "world"}]
        proof = g.generate_execution_proof("task_1", trace)
        assert isinstance(proof, ZeroKnowledgeProof)

    def test_execution_proof_has_correct_type(self):
        g = self._make()
        proof = g.generate_execution_proof("task_1", [{"step": 1}])
        assert proof.proof_type == "execution_proof"

    def test_execution_proof_has_step_count(self):
        g = self._make()
        trace = [{"a": 1}, {"b": 2}, {"c": 3}]
        proof = g.generate_execution_proof("task_1", trace)
        assert proof.proof_data["step_count"] == 3

    def test_verify_execution_proof_valid(self):
        g = self._make()
        trace = [{"step": 1}]
        proof = g.generate_execution_proof("task_1", trace)
        assert g.verify_execution_proof(proof) is True

    def test_verify_execution_proof_tampered_returns_false(self):
        g = self._make()
        trace = [{"step": 1}]
        proof = g.generate_execution_proof("task_1", trace)
        # Tamper with response
        proof.response = "wrong_commitment"
        assert g.verify_execution_proof(proof) is False

    def test_create_proof_bundle_has_task_id(self):
        g = self._make()
        bundle = g.create_proof_bundle("t1", {"score": 1.0})
        assert bundle["task_id"] == "t1"

    def test_create_proof_bundle_has_result(self):
        g = self._make()
        bundle = g.create_proof_bundle("t1", {"score": 1.0})
        assert bundle["result"]["score"] == 1.0

    def test_create_proof_bundle_has_signature(self):
        g = self._make()
        bundle = g.create_proof_bundle("t1", {"score": 1.0})
        assert "signature" in bundle

    def test_create_proof_bundle_with_trace_has_zk_proof(self):
        g = self._make()
        bundle = g.create_proof_bundle("t1", {"score": 1.0}, [{"step": 1}])
        assert "zk_proof" in bundle

    def test_create_proof_bundle_without_trace_no_zk_proof(self):
        g = self._make()
        bundle = g.create_proof_bundle("t1", {"score": 1.0})
        assert "zk_proof" not in bundle

    def test_verify_proof_bundle_valid(self):
        g = self._make()
        bundle = g.create_proof_bundle("t1", {"score": 1.0})
        ok, msg = g.verify_proof_bundle(bundle)
        assert ok is True
        assert msg == "valid"

    def test_verify_proof_bundle_missing_signature_fails(self):
        g = self._make()
        bundle = g.create_proof_bundle("t1", {"score": 1.0})
        del bundle["signature"]
        ok, msg = g.verify_proof_bundle(bundle)
        assert ok is False
        assert msg == "missing_signature"

    def test_verify_proof_bundle_node_id_mismatch_fails(self):
        g1 = self._make("node_1")
        g2 = self._make("node_2")
        bundle = g1.create_proof_bundle("t1", {"score": 1.0})
        ok, msg = g2.verify_proof_bundle(bundle)
        assert ok is False
        assert msg == "node_id_mismatch"
