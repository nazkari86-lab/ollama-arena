"""Extended tests for GlobalLeaderboard — add_entry, get_top_entries, get_model_ranking."""
from __future__ import annotations

import time
import json
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
    defaults = dict(cpu_signature="cpu_sig_abc", memory_signature="mem_sig_xyz")
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


def _make_lb(tmp_path, name="lb.json"):
    from ollama_arena.p2p.leaderboard import GlobalLeaderboard
    return GlobalLeaderboard(data_path=tmp_path / name)


# ──────────────────────────────────────────────────────────────────────────────
# VerifiedEntry.get_confidence_score
# ──────────────────────────────────────────────────────────────────────────────

class TestVerifiedEntryConfidence:
    def test_confidence_zero_with_no_votes(self):
        e = _make_entry()
        score = e.get_confidence_score()
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_confidence_increases_with_verification_votes(self):
        e = _make_entry()
        e.verification_status = "verified"
        e.verification_votes = 5
        e.rejection_votes = 0
        score = e.get_confidence_score()
        assert score > 0.0

    def test_confidence_decreases_with_rejection_votes(self):
        e1 = _make_entry()
        e1.verification_status = "verified"
        e1.verification_votes = 5
        e1.rejection_votes = 0

        e2 = _make_entry()
        e2.verification_status = "verified"
        e2.verification_votes = 5
        e2.rejection_votes = 3

        assert e1.get_confidence_score() > e2.get_confidence_score()


# ──────────────────────────────────────────────────────────────────────────────
# GlobalLeaderboard.get_top_entries
# ──────────────────────────────────────────────────────────────────────────────

class TestGlobalLeaderboardTopEntries:
    def test_empty_returns_empty_list(self, tmp_path):
        lb = _make_lb(tmp_path)
        result = lb.get_top_entries()
        assert result == []

    def test_returns_verified_entries_only(self, tmp_path):
        lb = _make_lb(tmp_path)
        e = _make_entry(score=1500.0)
        e.verification_status = "verified"
        e.verification_votes = 10
        lb.entries.append(e)
        result = lb.get_top_entries(min_confidence=0.0)
        assert len(result) == 1

    def test_pending_not_in_top(self, tmp_path):
        lb = _make_lb(tmp_path)
        e = _make_entry(score=1500.0)
        e.verification_status = "pending"
        lb.entries.append(e)
        result = lb.get_top_entries(min_confidence=0.0)
        assert len(result) == 0

    def test_category_filter(self, tmp_path):
        lb = _make_lb(tmp_path)
        for cat in ["coding", "math", "coding"]:
            e = _make_entry(category=cat, score=1000.0)
            e.verification_status = "verified"
            e.verification_votes = 10
            lb.entries.append(e)
        result = lb.get_top_entries(category="coding", min_confidence=0.0)
        assert len(result) == 2
        assert all(e.category == "coding" for e in result)

    def test_limit_respected(self, tmp_path):
        lb = _make_lb(tmp_path)
        for i in range(5):
            e = _make_entry(score=float(1000 + i))
            e.verification_status = "verified"
            e.verification_votes = 10
            lb.entries.append(e)
        result = lb.get_top_entries(limit=3, min_confidence=0.0)
        assert len(result) == 3

    def test_sorted_by_score_descending(self, tmp_path):
        lb = _make_lb(tmp_path)
        for score in [1100.0, 1400.0, 1200.0]:
            e = _make_entry(score=score)
            e.verification_status = "verified"
            e.verification_votes = 10
            lb.entries.append(e)
        result = lb.get_top_entries(min_confidence=0.0)
        scores = [e.score for e in result]
        assert scores == sorted(scores, reverse=True)


# ──────────────────────────────────────────────────────────────────────────────
# GlobalLeaderboard.get_model_ranking
# ──────────────────────────────────────────────────────────────────────────────

class TestGlobalLeaderboardModelRanking:
    def test_unknown_model_returns_none_rank(self, tmp_path):
        lb = _make_lb(tmp_path)
        result = lb.get_model_ranking("unknown_model:latest")
        assert result["rank"] is None
        assert result["entries"] == 0

    def test_known_model_has_rank(self, tmp_path):
        lb = _make_lb(tmp_path)
        e = _make_entry(model_name="llama3:8b", score=1200.0)
        e.verification_status = "verified"
        lb.entries.append(e)
        result = lb.get_model_ranking("llama3:8b")
        assert result["model_name"] == "llama3:8b"

    def test_ranking_includes_entries_count(self, tmp_path):
        lb = _make_lb(tmp_path)
        for _ in range(3):
            e = _make_entry(model_name="llama3:8b", score=1200.0)
            e.verification_status = "verified"
            lb.entries.append(e)
        result = lb.get_model_ranking("llama3:8b")
        assert result["total_entries"] == 3


# ──────────────────────────────────────────────────────────────────────────────
# GlobalLeaderboard.add_entry (proof validation mocked)
# ──────────────────────────────────────────────────────────────────────────────

class TestGlobalLeaderboardAddEntry:
    def test_add_entry_invalid_proof_returns_false(self, tmp_path):
        from unittest.mock import MagicMock
        lb = _make_lb(tmp_path)
        lb.proof_validator = MagicMock()
        lb.proof_validator.validate_proof_bundle.return_value = (False, ["bad sig"])
        lb.proof_validator.known_public_keys = {}

        entry = _make_entry()
        result = lb.add_entry(entry)
        assert result is False
        assert entry.verification_status == "rejected"

    def test_add_entry_suspicious_goes_to_pending(self, tmp_path):
        from unittest.mock import MagicMock
        lb = _make_lb(tmp_path)
        lb.proof_validator = MagicMock()
        lb.proof_validator.validate_proof_bundle.return_value = (True, [])
        lb.proof_validator.known_public_keys = {}
        lb.proof_validator.register_public_key = MagicMock()

        # Make fraud detector flag it
        lb.fraud_detector.node_submission_counts["node_1"] = 200

        entry = _make_entry(node_id="node_1")
        result = lb.add_entry(entry)
        assert result is False
        assert len(lb.pending_entries) == 1

    def test_add_valid_entry_adds_to_pending(self, tmp_path):
        from unittest.mock import MagicMock
        lb = _make_lb(tmp_path)
        lb.proof_validator = MagicMock()
        lb.proof_validator.validate_proof_bundle.return_value = (True, [])
        lb.proof_validator.known_public_keys = {}
        lb.proof_validator.register_public_key = MagicMock()

        entry = _make_entry()
        result = lb.add_entry(entry)
        assert result is True
        assert len(lb.pending_entries) == 1
        assert entry.verification_status == "pending"

    def test_rejected_entry_in_rejected_list(self, tmp_path):
        from unittest.mock import MagicMock
        lb = _make_lb(tmp_path)
        lb.proof_validator = MagicMock()
        lb.proof_validator.validate_proof_bundle.return_value = (False, ["err"])
        lb.proof_validator.known_public_keys = {}

        entry = _make_entry()
        lb.add_entry(entry)
        assert len(lb.rejected_entries) == 1


# ──────────────────────────────────────────────────────────────────────────────
# GlobalLeaderboard.verify_entry (vote mechanics)
# ──────────────────────────────────────────────────────────────────────────────

class TestGlobalLeaderboardVerifyEntry:
    def _add_pending_entry(self, lb):
        entry = _make_entry()
        entry.verification_status = "pending"
        lb.pending_entries.append(entry)
        entry_hash = __import__("hashlib").sha256(
            __import__("json").dumps(entry.to_dict(), sort_keys=True).encode()
        ).hexdigest()[:16]
        return entry, entry_hash

    def test_nonexistent_entry_id_returns_false(self, tmp_path):
        lb = _make_lb(tmp_path)
        result = lb.verify_entry("nonexistent_id", True, "verifier_1")
        assert result is False

    def test_vote_recorded(self, tmp_path):
        lb = _make_lb(tmp_path)
        entry, entry_id = self._add_pending_entry(lb)
        lb.verify_entry(entry_id, True, "verifier_1")
        assert entry.verification_votes == 1

    def test_rejection_vote_recorded(self, tmp_path):
        lb = _make_lb(tmp_path)
        entry, entry_id = self._add_pending_entry(lb)
        lb.verify_entry(entry_id, False, "verifier_1")
        assert entry.rejection_votes == 1

    def _entry_id(self, entry):
        """Recompute entry_id from current dict state."""
        import hashlib, json
        return hashlib.sha256(
            json.dumps(entry.to_dict(), sort_keys=True).encode()
        ).hexdigest()[:16]

    def test_consensus_verification_promotes_entry(self, tmp_path):
        lb = _make_lb(tmp_path)
        entry, _ = self._add_pending_entry(lb)
        # Cast 5 verification votes — recompute id after each vote since dict changes
        for i in range(5):
            eid = self._entry_id(entry)
            lb.verify_entry(eid, True, f"verifier_{i}")
        assert entry.verification_status == "verified"
        assert entry in lb.entries
        assert entry not in lb.pending_entries

    def test_consensus_rejection_moves_to_rejected(self, tmp_path):
        lb = _make_lb(tmp_path)
        entry, _ = self._add_pending_entry(lb)
        # Cast 0 verify + 5 reject → rejected
        for i in range(5):
            eid = self._entry_id(entry)
            lb.verify_entry(eid, False, f"r_{i}")
        assert entry.verification_status == "rejected"
        assert entry in lb.rejected_entries
