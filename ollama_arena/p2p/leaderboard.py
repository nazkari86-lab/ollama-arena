"""Global Leaderboard with cryptographic verification.

This module implements a cryptographically verified global leaderboard
with fraud detection, result validation, and vendor score manipulation prevention.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import hashlib

from .crypto_proof import (
    ResultSignature,
    HardwareAttestation,
    BlockchainAnchor,
    ProofValidator,
)


@dataclass
class VerifiedEntry:
    """Cryptographically verified leaderboard entry."""
    model_name: str
    score: float
    category: str
    elo_rating: float
    
    # Verification data
    signature: ResultSignature
    hardware_attestation: HardwareAttestation
    blockchain_anchor: Optional[BlockchainAnchor] = None
    
    # Metadata
    node_id: str = ""
    timestamp: float = field(default_factory=time.time)
    task_count: int = 1
    verification_status: str = "pending"  # pending, verified, rejected
    
    # Consensus data
    consensus_score: float = 0.0
    verification_votes: int = 0
    rejection_votes: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "score": self.score,
            "category": self.category,
            "elo_rating": self.elo_rating,
            "signature": self.signature.to_dict(),
            "hardware_attestation": self.hardware_attestation.to_dict(),
            "blockchain_anchor": self.blockchain_anchor.to_dict() if self.blockchain_anchor else None,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "task_count": self.task_count,
            "verification_status": self.verification_status,
            "consensus_score": self.consensus_score,
            "verification_votes": self.verification_votes,
            "rejection_votes": self.rejection_votes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerifiedEntry":
        """Create from dictionary."""
        sig_data = data.get("signature", {})
        hw_data = data.get("hardware_attestation", {})
        anchor_data = data.get("blockchain_anchor")
        
        return cls(
            model_name=data["model_name"],
            score=data["score"],
            category=data["category"],
            elo_rating=data["elo_rating"],
            signature=ResultSignature.from_dict(sig_data),
            hardware_attestation=HardwareAttestation.from_dict(hw_data),
            blockchain_anchor=BlockchainAnchor.from_dict(anchor_data) if anchor_data else None,
            node_id=data.get("node_id", ""),
            timestamp=data.get("timestamp", time.time()),
            task_count=data.get("task_count", 1),
            verification_status=data.get("verification_status", "pending"),
            consensus_score=data.get("consensus_score", 0.0),
            verification_votes=data.get("verification_votes", 0),
            rejection_votes=data.get("rejection_votes", 0),
        )
    
    def get_confidence_score(self) -> float:
        """Calculate confidence score based on verification."""
        if self.verification_status != "verified":
            return 0.0
        
        total_votes = self.verification_votes + self.rejection_votes
        if total_votes == 0:
            return 0.5
        
        vote_ratio = self.verification_votes / total_votes
        consensus_weight = self.consensus_score
        
        return (vote_ratio * 0.7) + (consensus_weight * 0.3)


class FraudDetector:
    """Fraud detection for leaderboard entries."""
    
    def __init__(self):
        """Initialize fraud detector."""
        self.suspicious_entries: Set[str] = set()
        self.node_submission_counts: Dict[str, int] = defaultdict(int)
        self.model_score_history: Dict[str, List[float]] = defaultdict(list)
    
    def detect_anomalies(self, entry: VerifiedEntry) -> List[str]:
        """
        Detect anomalies in a leaderboard entry.
        
        Args:
            entry: Entry to analyze
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check for rapid score changes
        if entry.model_name in self.model_score_history:
            history = self.model_score_history[entry.model_name]
            if len(history) > 0:
                last_score = history[-1]
                score_change = abs(entry.score - last_score)
                if score_change > 20.0:  # More than 20 point jump
                    anomalies.append("rapid_score_increase")
        
        # Check for submission spam
        self.node_submission_counts[entry.node_id] += 1
        if self.node_submission_counts[entry.node_id] > 100:  # More than 100 submissions
            anomalies.append("excessive_submissions")
        
        # Check hardware consistency
        if not entry.hardware_attestation.cpu_signature:
            anomalies.append("missing_hardware_attestation")
        
        # Check timestamp freshness
        if time.time() - entry.timestamp > 3600:  # Older than 1 hour
            anomalies.append("stale_timestamp")
        
        # Update history
        self.model_score_history[entry.model_name].append(entry.score)
        
        return anomalies
    
    def is_suspicious(self, entry: VerifiedEntry) -> bool:
        """
        Check if an entry is suspicious.
        
        Args:
            entry: Entry to check
        
        Returns:
            True if entry is suspicious
        """
        anomalies = self.detect_anomalies(entry)
        entry_id = self._entry_id(entry)
        
        if anomalies:
            self.suspicious_entries.add(entry_id)
            return True
        
        return False
    
    def _entry_id(self, entry: VerifiedEntry) -> str:
        """Generate unique ID for an entry."""
        return hashlib.sha256(
            f"{entry.model_name}-{entry.node_id}-{entry.timestamp}".encode()
        ).hexdigest()[:16]
    
    def get_suspicious_entries(self) -> Set[str]:
        """Get all suspicious entry IDs."""
        return self.suspicious_entries.copy()


class GlobalLeaderboard:
    """Cryptographically verified global leaderboard."""
    
    def __init__(
        self,
        data_path: Optional[Path] = None,
        proof_validator: Optional[ProofValidator] = None,
    ):
        """
        Initialize global leaderboard.
        
        Args:
            data_path: Path to store leaderboard data
            proof_validator: Proof validator instance
        """
        if data_path is None:
            data_path = Path.home() / ".ollama-arena" / "global_leaderboard.json"
        
        self.data_path = data_path
        self.proof_validator = proof_validator or ProofValidator()
        self.fraud_detector = FraudDetector()
        
        self.entries: List[VerifiedEntry] = []
        self.pending_entries: List[VerifiedEntry] = []
        self.rejected_entries: List[VerifiedEntry] = []
        
        self._load_data()
    
    def _load_data(self) -> None:
        """Load leaderboard data from file."""
        if self.data_path.exists():
            try:
                with open(self.data_path, 'r') as f:
                    data = json.load(f)
                    self.entries = [
                        VerifiedEntry.from_dict(e)
                        for e in data.get('entries', [])
                    ]
                    self.pending_entries = [
                        VerifiedEntry.from_dict(e)
                        for e in data.get('pending_entries', [])
                    ]
                    self.rejected_entries = [
                        VerifiedEntry.from_dict(e)
                        for e in data.get('rejected_entries', [])
                    ]
                    
                    # Load known public keys
                    for node_id, pub_key in data.get('public_keys', {}).items():
                        self.proof_validator.register_public_key(node_id, pub_key)
            except Exception as e:
                print(f"Warning: Failed to load leaderboard data: {e}")
                self.entries = []
    
    def _save_data(self) -> None:
        """Save leaderboard data to file."""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_path, 'w') as f:
                json.dump({
                    'entries': [e.to_dict() for e in self.entries],
                    'pending_entries': [e.to_dict() for e in self.pending_entries],
                    'rejected_entries': [e.to_dict() for e in self.rejected_entries],
                    'public_keys': self.proof_validator.known_public_keys,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save leaderboard data: {e}")
    
    def add_entry(self, entry: VerifiedEntry) -> bool:
        """
        Add a new entry to the leaderboard.
        
        Args:
            entry: Entry to add
        
        Returns:
            True if entry was added successfully
        """
        # Validate proof bundle
        is_valid, errors = self.proof_validator.validate_proof_bundle(
            entry.to_dict()
        )
        
        if not is_valid:
            print(f"Entry validation failed: {errors}")
            entry.verification_status = "rejected"
            self.rejected_entries.append(entry)
            self._save_data()
            return False
        
        # Check for fraud
        if self.fraud_detector.is_suspicious(entry):
            print(f"Suspicious entry detected from node {entry.node_id}")
            entry.verification_status = "pending"
            self.pending_entries.append(entry)
            self._save_data()
            return False
        
        # Register public key
        self.proof_validator.register_public_key(
            entry.node_id,
            entry.signature.public_key
        )
        
        # Add to pending for verification
        entry.verification_status = "pending"
        self.pending_entries.append(entry)
        self._save_data()
        
        return True
    
    def verify_entry(
        self,
        entry_id: str,
        vote: bool,
        verifier_node_id: str,
    ) -> bool:
        """
        Vote on entry verification.
        
        Args:
            entry_id: Entry ID to verify
            vote: True to verify, False to reject
            verifier_node_id: ID of voting node
        
        Returns:
            True if vote was recorded
        """
        # Find entry in pending
        for entry in self.pending_entries:
            entry_hash = hashlib.sha256(
                json.dumps(entry.to_dict(), sort_keys=True).encode()
            ).hexdigest()[:16]
            
            if entry_hash == entry_id:
                if vote:
                    entry.verification_votes += 1
                else:
                    entry.rejection_votes += 1
                
                # Check if consensus reached
                total_votes = entry.verification_votes + entry.rejection_votes
                if total_votes >= 5:  # Need at least 5 votes
                    if entry.verification_votes > entry.rejection_votes:
                        # Verified
                        entry.verification_status = "verified"
                        self.entries.append(entry)
                        self.pending_entries.remove(entry)
                    else:
                        # Rejected
                        entry.verification_status = "rejected"
                        self.rejected_entries.append(entry)
                        self.pending_entries.remove(entry)
                
                self._save_data()
                return True
        
        return False
    
    def get_top_entries(
        self,
        category: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = 0.5,
    ) -> List[VerifiedEntry]:
        """
        Get top entries from the leaderboard.
        
        Args:
            category: Filter by category
            limit: Maximum number of entries
            min_confidence: Minimum confidence score
        
        Returns:
            List of top verified entries
        """
        filtered = [
            e for e in self.entries
            if e.verification_status == "verified"
            and e.get_confidence_score() >= min_confidence
        ]
        
        if category:
            filtered = [e for e in filtered if e.category == category]
        
        # Sort by score descending
        filtered.sort(key=lambda x: x.score, reverse=True)
        
        return filtered[:limit]
    
    def get_model_ranking(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """
        Get ranking information for a specific model.
        
        Args:
            model_name: Model name
        
        Returns:
            Dictionary with ranking information
        """
        model_entries = [
            e for e in self.entries
            if e.model_name == model_name and e.verification_status == "verified"
        ]
        
        if not model_entries:
            return {"model_name": model_name, "rank": None, "entries": 0}
        
        # Calculate average score
        scores = [e.score for e in model_entries]
        avg_score = sum(scores) / len(scores)

        # Rank this model's average score among every other model's average
        # score. Group by model_name first — the previous implementation
        # built a {model_name: score} dict directly from individual entries,
        # which silently dropped all but one entry per model and ranked
        # against single, arbitrary scores instead of per-model averages.
        all_verified = [e for e in self.entries if e.verification_status == "verified"]
        scores_by_model: Dict[str, List[float]] = defaultdict(list)
        for e in all_verified:
            scores_by_model[e.model_name].append(e.score)

        model_avg_scores = sorted(
            (sum(s) / len(s) for s in scores_by_model.values()),
            reverse=True,
        )

        rank = None
        for i, score in enumerate(model_avg_scores):
            if abs(score - avg_score) < 0.01:
                rank = i + 1
                break
        
        return {
            "model_name": model_name,
            "rank": rank,
            "average_score": avg_score,
            "total_entries": len(model_entries),
            "highest_score": max(scores),
            "lowest_score": min(scores),
            "confidence": model_entries[0].get_confidence_score() if model_entries else 0.0,
        }
    
    def get_leaderboard_stats(self) -> Dict[str, Any]:
        """Get overall leaderboard statistics."""
        verified_entries = [e for e in self.entries if e.verification_status == "verified"]
        
        if not verified_entries:
            return {
                "total_entries": 0,
                "pending_entries": len(self.pending_entries),
                "rejected_entries": len(self.rejected_entries),
                "unique_models": 0,
                "average_score": 0.0,
            }
        
        unique_models = len(set(e.model_name for e in verified_entries))
        scores = [e.score for e in verified_entries]
        
        category_breakdown: Dict[str, int] = defaultdict(int)
        for entry in verified_entries:
            category_breakdown[entry.category] += 1
        
        return {
            "total_entries": len(verified_entries),
            "pending_entries": len(self.pending_entries),
            "rejected_entries": len(self.rejected_entries),
            "unique_models": unique_models,
            "average_score": sum(scores) / len(scores),
            "top_score": max(scores),
            "category_breakdown": dict(category_breakdown),
            "suspicious_entries": len(self.fraud_detector.get_suspicious_entries()),
        }
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export leaderboard to dictionary."""
        return {
            "verified_entries": [e.to_dict() for e in self.entries],
            "pending_entries": [e.to_dict() for e in self.pending_entries],
            "rejected_entries": [e.to_dict() for e in self.rejected_entries],
            "stats": self.get_leaderboard_stats(),
            "last_updated": datetime.now().isoformat(),
        }
    
    def get_vendor_manipulation_report(self) -> Dict[str, Any]:
        """
        Generate report on potential vendor manipulation attempts.
        
        Returns:
            Dictionary with manipulation analysis
        """
        # Analyze by node
        node_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_submissions": 0,
            "verified_count": 0,
            "rejected_count": 0,
            "models": set(),
        })
        
        for entry in self.entries + self.pending_entries + self.rejected_entries:
            stats = node_stats[entry.node_id]
            stats["total_submissions"] += 1
            stats["models"].add(entry.model_name)
            
            if entry.verification_status == "verified":
                stats["verified_count"] += 1
            elif entry.verification_status == "rejected":
                stats["rejected_count"] += 1
        
        # Flag suspicious nodes
        suspicious_nodes = []
        for node_id, stats in node_stats.items():
            rejection_rate = (
                stats["rejected_count"] / stats["total_submissions"]
                if stats["total_submissions"] > 0 else 0
            )
            
            if rejection_rate > 0.5 or stats["total_submissions"] > 50:
                suspicious_nodes.append({
                    "node_id": node_id,
                    "rejection_rate": rejection_rate,
                    "total_submissions": stats["total_submissions"],
                    "unique_models": len(stats["models"]),
                })
        
        return {
            "total_nodes": len(node_stats),
            "suspicious_nodes": suspicious_nodes,
            "suspicious_entries": len(self.fraud_detector.get_suspicious_entries()),
        }
    
    def anchor_to_blockchain(
        self,
        blockchain_anchorer,
    ) -> Optional[BlockchainAnchor]:
        """
        Anchor current leaderboard state to blockchain.
        
        Args:
            blockchain_anchorer: BlockchainAnchorer instance
        
        Returns:
            Blockchain anchor or None if failed
        """
        # Create proof bundle of entire leaderboard
        proof_bundle = {
            "leaderboard_hash": hashlib.sha256(
                json.dumps(self.export_to_dict(), sort_keys=True).encode()
            ).hexdigest(),
            "timestamp": time.time(),
            "entry_count": len(self.entries),
        }
        
        return blockchain_anchorer.anchor_to_blockchain(proof_bundle)
