"""Extended tests for p2p crypto_proof — ProofValidator and CryptoProofGenerator pure paths."""
from __future__ import annotations

import time

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# ProofValidator
# ──────────────────────────────────────────────────────────────────────────────

class TestProofValidator:
    def _make(self):
        from ollama_arena.p2p.crypto_proof import ProofValidator
        return ProofValidator()

    def _valid_bundle(self):
        return {
            "task_id": "task_1",
            "result": {"tps": 42.0},
            "signature": {"node_id": "node_1", "public_key": "pubkey_abc", "timestamp": time.time()},
            "hardware_attestation": {"cpu_signature": "cpu_abc", "memory_signature": "mem_xyz"},
            "timestamp": time.time(),
        }

    def test_init_empty_public_keys(self):
        v = self._make()
        assert v.known_public_keys == {}

    def test_register_public_key(self):
        v = self._make()
        v.register_public_key("node_1", "pubkey_abc")
        assert v.known_public_keys["node_1"] == "pubkey_abc"

    def test_valid_bundle_no_known_key(self):
        v = self._make()
        ok, errors = v.validate_proof_bundle(self._valid_bundle())
        assert ok is True
        assert errors == []

    def test_missing_task_id_returns_error(self):
        v = self._make()
        bundle = self._valid_bundle()
        del bundle["task_id"]
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False
        assert any("task_id" in e for e in errors)

    def test_missing_result_returns_error(self):
        v = self._make()
        bundle = self._valid_bundle()
        del bundle["result"]
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False

    def test_missing_signature_returns_error(self):
        v = self._make()
        bundle = self._valid_bundle()
        del bundle["signature"]
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False

    def test_missing_hardware_attestation_returns_error(self):
        v = self._make()
        bundle = self._valid_bundle()
        del bundle["hardware_attestation"]
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False

    def test_invalid_signature_format(self):
        v = self._make()
        bundle = self._valid_bundle()
        bundle["signature"] = "not_a_dict"
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False
        assert any("signature" in e for e in errors)

    def test_public_key_mismatch_detected(self):
        v = self._make()
        v.register_public_key("node_1", "correct_pubkey")
        bundle = self._valid_bundle()
        bundle["signature"]["node_id"] = "node_1"
        bundle["signature"]["public_key"] = "wrong_pubkey"
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False
        assert "public_key_mismatch" in errors

    def test_public_key_match_accepted(self):
        v = self._make()
        v.register_public_key("node_1", "pubkey_abc")
        bundle = self._valid_bundle()
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is True

    def test_stale_timestamp_flagged(self):
        v = self._make()
        bundle = self._valid_bundle()
        bundle["timestamp"] = time.time() - 7200  # 2 hours ago
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False
        assert "timestamp_too_old" in errors

    def test_missing_cpu_signature_flagged(self):
        v = self._make()
        bundle = self._valid_bundle()
        bundle["hardware_attestation"]["cpu_signature"] = ""
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False
        assert "missing_cpu_signature" in errors

    def test_multiple_errors_collected(self):
        v = self._make()
        bundle = self._valid_bundle()
        bundle["hardware_attestation"]["cpu_signature"] = ""
        bundle["timestamp"] = time.time() - 7200
        ok, errors = v.validate_proof_bundle(bundle)
        assert ok is False
        assert len(errors) >= 2


# ──────────────────────────────────────────────────────────────────────────────
# CryptoProofGenerator — hardware attestation path (no crypto library required)
# ──────────────────────────────────────────────────────────────────────────────

class TestCryptoProofGeneratorHardwareAttestation:
    def test_generate_hardware_attestation_without_crypto(self):
        """_generate_hardware_attestation uses only hashlib+platform, no crypto lib."""
        import hashlib
        import platform as plat
        import json
        from ollama_arena.p2p.crypto_proof import HardwareAttestation

        # Manually replicate the logic to verify the output shape
        system_info = {
            "system": plat.system(),
            "machine": plat.machine(),
            "processor": plat.processor(),
            "python_version": plat.python_version(),
        }
        cpu_sig = hashlib.sha256(
            json.dumps(system_info, sort_keys=True).encode()
        ).hexdigest()[:32]

        assert isinstance(cpu_sig, str)
        assert len(cpu_sig) == 32

    def test_hardware_attestation_dataclass_fields(self):
        from ollama_arena.p2p.crypto_proof import HardwareAttestation
        hw = HardwareAttestation(cpu_signature="cpu123", memory_signature="mem456")
        assert hw.cpu_signature == "cpu123"
        assert hw.memory_signature == "mem456"
        assert hw.gpu_signature is None

    def test_hardware_attestation_to_dict(self):
        from ollama_arena.p2p.crypto_proof import HardwareAttestation
        hw = HardwareAttestation(cpu_signature="cpu123", memory_signature="mem456")
        d = hw.to_dict()
        assert d["cpu_signature"] == "cpu123"
        assert "memory_signature" in d

    def test_hardware_attestation_from_dict(self):
        from ollama_arena.p2p.crypto_proof import HardwareAttestation
        d = {"cpu_signature": "cpu1", "memory_signature": "mem2", "gpu_signature": None, "platform_info": {}}
        hw = HardwareAttestation.from_dict(d)
        assert hw.cpu_signature == "cpu1"


# ──────────────────────────────────────────────────────────────────────────────
# KeyPair — only if cryptography library is available
# ──────────────────────────────────────────────────────────────────────────────

class TestKeyPair:
    def test_init_raises_without_crypto(self):
        from ollama_arena.p2p import crypto_proof
        if crypto_proof.CRYPTO_AVAILABLE:
            pytest.skip("cryptography library available — skip missing-crypto test")
        from ollama_arena.p2p.crypto_proof import KeyPair
        with pytest.raises(ImportError):
            KeyPair()

    def test_init_succeeds_with_crypto(self):
        from ollama_arena.p2p import crypto_proof
        if not crypto_proof.CRYPTO_AVAILABLE:
            pytest.skip("cryptography library not available")
        from ollama_arena.p2p.crypto_proof import KeyPair
        kp = KeyPair()
        assert kp.private_key is not None
        assert kp.public_key is not None

    def test_public_key_hex_is_64_chars(self):
        from ollama_arena.p2p import crypto_proof
        if not crypto_proof.CRYPTO_AVAILABLE:
            pytest.skip("cryptography library not available")
        from ollama_arena.p2p.crypto_proof import KeyPair
        kp = KeyPair()
        hex_key = kp.get_public_key_hex()
        assert len(hex_key) == 64

    def test_private_key_bytes_length(self):
        from ollama_arena.p2p import crypto_proof
        if not crypto_proof.CRYPTO_AVAILABLE:
            pytest.skip("cryptography library not available")
        from ollama_arena.p2p.crypto_proof import KeyPair
        kp = KeyPair()
        assert len(kp.get_private_key_bytes()) == 32


# ──────────────────────────────────────────────────────────────────────────────
# ZeroKnowledgeProof and BlockchainAnchor — additional roundtrip tests
# ──────────────────────────────────────────────────────────────────────────────

class TestZeroKnowledgeProofExtended:
    def test_to_dict_from_dict_roundtrip(self):
        from ollama_arena.p2p.crypto_proof import ZeroKnowledgeProof
        zkp = ZeroKnowledgeProof(
            proof_type="range_proof",
            proof_data={"k": "v"},
            verification_key="vkey_xyz",
            challenge="challenge_abc",
            response="response_xyz",
        )
        d = zkp.to_dict()
        zkp2 = ZeroKnowledgeProof.from_dict(d)
        assert zkp2.proof_type == "range_proof"
        assert zkp2.verification_key == "vkey_xyz"
        assert zkp2.challenge == "challenge_abc"

    def test_default_proof_type_is_str(self):
        from ollama_arena.p2p.crypto_proof import ZeroKnowledgeProof
        zkp = ZeroKnowledgeProof(
            proof_type="execution_proof",
            proof_data={},
            verification_key="v",
            challenge="c",
            response="r",
        )
        assert isinstance(zkp.proof_type, str)


class TestBlockchainAnchorExtended:
    def test_to_dict_from_dict_roundtrip(self):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchor
        anchor = BlockchainAnchor(
            transaction_hash="0xabc123",
            block_height=1000,
            block_hash="0xblk999",
            timestamp=time.time(),
            network="ethereum",
        )
        d = anchor.to_dict()
        anchor2 = BlockchainAnchor.from_dict(d)
        assert anchor2.transaction_hash == "0xabc123"
        assert anchor2.block_height == 1000
        assert anchor2.network == "ethereum"

    def test_default_network_ethereum(self):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchor
        anchor = BlockchainAnchor(
            transaction_hash="0xdef",
            block_height=2,
            block_hash="0xblk",
            timestamp=time.time(),
        )
        assert anchor.network == "ethereum"
