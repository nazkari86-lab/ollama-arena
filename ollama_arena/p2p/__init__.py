"""Global P2P Grid system for distributed model evaluation.

This package implements a peer-to-peer network for running model evaluations
across distributed nodes with cryptographic proof of work and verification.
"""
from __future__ import annotations

from .node import P2PNode, NodeDiscovery, P2PMessage
from .distribution import TaskGossipProtocol, TaskDistributor, ResultAggregator
from .crypto_proof import (
    CryptoProofGenerator,
    ResultSignature,
    ZeroKnowledgeProof,
    BlockchainAnchor,
)
from .leaderboard import GlobalLeaderboard, VerifiedEntry, FraudDetector

__all__ = [
    "P2PNode",
    "NodeDiscovery",
    "P2PMessage",
    "TaskGossipProtocol",
    "TaskDistributor",
    "ResultAggregator",
    "CryptoProofGenerator",
    "ResultSignature",
    "ZeroKnowledgeProof",
    "BlockchainAnchor",
    "GlobalLeaderboard",
    "VerifiedEntry",
    "FraudDetector",
]
