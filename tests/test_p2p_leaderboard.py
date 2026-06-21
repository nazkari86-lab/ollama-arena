"""Tests for P2P leaderboard — FraudDetector, GlobalLeaderboard, VerifiedEntry."""
from __future__ import annotations

import time
import unittest.mock as mock
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_sig(**kw):
    from ollama_arena.p2p.crypto_proof import ResultSignature
    defaults = dict(
        node_id="node_1",
        task_id="task_1",
        signature="sig_hex",
        public_key="pubkey_hex",
        timestamp=time.time(),
    )
    defaults.update(kw)
    return ResultSignature(**defaults)


def _make_hw(**kw):
    from ollama_arena.p2p.crypto_proof import HardwareAttestation
    defaults = dict(cpu_signature="cpu_sig", memory_signature="mem_sig")
    defaults.update(kw)
    return HardwareAttestation(**defaults)


def _make_entry(**kw):
    from ollama_arena.p2p.leaderboard import VerifiedEntry
    defaults = dict(
        model_name="llama3:8b",
        score=1200.0,
        category="coding",
        elo_rating=1200.0,
        signature=_make_sig(),
        hardware_attestation=_make_hw(),
        node_id="node_1",
        timestamp=time.time(),
    )
    defaults.update(kw)
    return VerifiedEntry(**defaults)


# ──────────────────────────────────────────────────────────────────────────────
# VerifiedEntry
# ──────────────────────────────────────────────────────────────────────────────

class TestVerifiedEntry:
    def test_creation(self):
        e = _make_entry()
        assert e.model_name == "llama3:8b"
        assert e.verification_status == "pending"

    def test_to_dict_has_keys(self):
        e = _make_entry()
        d = e.to_dict()
        for key in ["model_name", "score", "category", "elo_rating", "node_id", "verification_status"]:
            assert key in d

    def test_to_dict_model_name_value(self):
        e = _make_entry(model_name="phi3:3b")
        assert e.to_dict()["model_name"] == "phi3:3b"

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.leaderboard import VerifiedEntry
        e = _make_entry(node_id="node_99", score=1500.0)
        d = e.to_dict()
        e2 = VerifiedEntry.from_dict(d)
        assert e2.node_id == "node_99"
        assert e2.score == 1500.0
        assert e2.verification_status == e.verification_status

    def test_default_consensus_zero(self):
        e = _make_entry()
        assert e.consensus_score == 0.0
        assert e.verification_votes == 0
        assert e.rejection_votes == 0

    def test_blockchain_anchor_none_by_default(self):
        e = _make_entry()
        assert e.blockchain_anchor is None


# ──────────────────────────────────────────────────────────────────────────────
# FraudDetector
# ──────────────────────────────────────────────────────────────────────────────

class TestFraudDetector:
    def test_init_empty(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        assert len(fd.suspicious_entries) == 0
        assert len(fd.node_submission_counts) == 0

    def test_clean_entry_no_anomalies(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        entry = _make_entry(score=1200.0, node_id="node_clean")
        anomalies = fd.detect_anomalies(entry)
        # Fresh entry should have no anomalies (no rapid change, no spam, hw present, fresh ts)
        assert "missing_hardware_attestation" not in anomalies
        assert "excessive_submissions" not in anomalies

    def test_rapid_score_increase_detected(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        # First entry sets history
        fd.detect_anomalies(_make_entry(model_name="model_x", score=1000.0))
        # Second entry has huge jump
        anomalies = fd.detect_anomalies(_make_entry(model_name="model_x", score=1100.0))
        assert "rapid_score_increase" in anomalies

    def test_missing_hw_attestation_detected(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        entry = _make_entry(hardware_attestation=_make_hw(cpu_signature=""))
        anomalies = fd.detect_anomalies(entry)
        assert "missing_hardware_attestation" in anomalies

    def test_stale_timestamp_detected(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        entry = _make_entry(timestamp=time.time() - 7200)  # 2 hours ago
        anomalies = fd.detect_anomalies(entry)
        assert "stale_timestamp" in anomalies

    def test_excessive_submissions_detected(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        fd.node_submission_counts["spam_node"] = 101
        entry = _make_entry(node_id="spam_node")
        anomalies = fd.detect_anomalies(entry)
        assert "excessive_submissions" in anomalies

    def test_is_suspicious_with_anomalies(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        entry = _make_entry(timestamp=time.time() - 7200)  # stale
        assert fd.is_suspicious(entry) is True
        assert len(fd.get_suspicious_entries()) > 0

    def test_is_suspicious_clean_entry(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        entry = _make_entry()
        # Clean entry — check it just ran without crash
        result = fd.is_suspicious(entry)
        assert isinstance(result, bool)

    def test_get_suspicious_entries_is_copy(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        entries1 = fd.get_suspicious_entries()
        entries2 = fd.get_suspicious_entries()
        # Should be copies, not the same object
        assert entries1 is not fd.suspicious_entries

    def test_score_history_updated(self):
        from ollama_arena.p2p.leaderboard import FraudDetector
        fd = FraudDetector()
        fd.detect_anomalies(_make_entry(model_name="track_me", score=1000.0))
        assert "track_me" in fd.model_score_history
        assert 1000.0 in fd.model_score_history["track_me"]


# ──────────────────────────────────────────────────────────────────────────────
# GlobalLeaderboard (with mocked file I/O)
# ──────────────────────────────────────────────────────────────────────────────

class TestGlobalLeaderboard:
    def test_init_empty(self, tmp_path):
        from ollama_arena.p2p.leaderboard import GlobalLeaderboard
        lb = GlobalLeaderboard(data_path=tmp_path / "lb.json")
        assert lb.entries == []
        assert lb.pending_entries == []
        assert lb.rejected_entries == []

    def test_init_creates_fraud_detector(self, tmp_path):
        from ollama_arena.p2p.leaderboard import GlobalLeaderboard, FraudDetector
        lb = GlobalLeaderboard(data_path=tmp_path / "lb.json")
        assert isinstance(lb.fraud_detector, FraudDetector)

    def test_load_data_nonexistent_file(self, tmp_path):
        from ollama_arena.p2p.leaderboard import GlobalLeaderboard
        lb = GlobalLeaderboard(data_path=tmp_path / "nonexistent.json")
        assert lb.entries == []

    def test_leaderboard_data_path_stored(self, tmp_path):
        from ollama_arena.p2p.leaderboard import GlobalLeaderboard
        data_path = tmp_path / "lb.json"
        lb = GlobalLeaderboard(data_path=data_path)
        assert lb.data_path == data_path

    def test_proof_validator_initialized(self, tmp_path):
        from ollama_arena.p2p.leaderboard import GlobalLeaderboard
        from ollama_arena.p2p.crypto_proof import ProofValidator
        lb = GlobalLeaderboard(data_path=tmp_path / "lb.json")
        assert isinstance(lb.proof_validator, ProofValidator)

    def test_save_and_load_empty_leaderboard(self, tmp_path):
        from ollama_arena.p2p.leaderboard import GlobalLeaderboard
        data_path = tmp_path / "lb.json"
        lb = GlobalLeaderboard(data_path=data_path)
        lb._save_data()
        assert data_path.exists()

        # Reload
        lb2 = GlobalLeaderboard(data_path=data_path)
        assert lb2.entries == []
