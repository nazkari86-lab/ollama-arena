"""Read-only web routes for the p2p/ module (node status, leaderboard,
reputation/distribution stats).

Deliberately read-only: crypto_proof.py signing/payment actions are out
of scope here given the web3/crypto dependencies involved -- a write
surface for those is a separately-scoped future addition, not bundled
into this pass.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from ..p2p.distribution import ReputationDatabase
from ..p2p.leaderboard import GlobalLeaderboard
from ..p2p.node import P2PNode


def build_p2p_router(leaderboard_data_path: Path | None = None) -> APIRouter:
    """`leaderboard_data_path` overrides GlobalLeaderboard's default
    ~/.ollama-arena/global_leaderboard.json -- used by tests to avoid
    reading/writing the real home directory; web.py's call site leaves
    it None to match the existing `ollama-arena p2p leaderboard` CLI
    command's storage location."""
    router = APIRouter(prefix="/api/p2p", tags=["p2p"])

    # Constructed once per process. .start() (real networking: peer
    # discovery, heartbeats) is deliberately never called here -- this is
    # a read-only status surface, not a live P2P network participant.
    node = P2PNode()
    leaderboard = GlobalLeaderboard(data_path=leaderboard_data_path)
    reputation_db = ReputationDatabase()

    @router.get("/status")
    def p2p_status():
        return node.get_stats()

    @router.get("/leaderboard")
    def p2p_leaderboard(category: str | None = None, limit: int = 10):
        entries = leaderboard.get_top_entries(category=category, limit=limit)
        return {
            "entries": [e.to_dict() for e in entries],
            "stats": leaderboard.get_leaderboard_stats(),
        }

    @router.get("/reputation")
    def p2p_reputation(limit: int = 10):
        return {"nodes": [n.to_dict() for n in reputation_db.get_top_trusted_nodes(limit=limit)]}

    return router
