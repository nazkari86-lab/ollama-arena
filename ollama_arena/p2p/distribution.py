"""P2P Task Distribution with Gossip Protocol.

This module implements a gossip-based task distribution protocol for
propagating evaluation tasks across the P2P network and aggregating results.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import hashlib
import random
from collections import defaultdict

from .node import P2PNode, NodeInfo, P2PMessage, MessageType


class TaskState(Enum):
    """States of a distributed task."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class DistributedTask:
    """A task distributed across the P2P network."""
    task_id: str
    task_type: str  # "ab_test", "benchmark", "tournament"
    payload: Dict[str, Any]
    state: TaskState = TaskState.PENDING
    assigned_node: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    assigned_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Gossip protocol fields
    origin_node: str = ""
    seen_by: Set[str] = field(default_factory=set)
    gossip_count: int = 0
    ttl: int = 10  # Time-to-live for gossip
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "state": self.state.value,
            "assigned_node": self.assigned_node,
            "created_at": self.created_at,
            "assigned_at": self.assigned_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "origin_node": self.origin_node,
            "seen_by": list(self.seen_by),
            "gossip_count": self.gossip_count,
            "ttl": self.ttl,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DistributedTask":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            payload=data["payload"],
            state=TaskState(data.get("state", "pending")),
            assigned_node=data.get("assigned_node"),
            created_at=data.get("created_at", time.time()),
            assigned_at=data.get("assigned_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            error=data.get("error"),
            origin_node=data.get("origin_node", ""),
            seen_by=set(data.get("seen_by", [])),
            gossip_count=data.get("gossip_count", 0),
            ttl=data.get("ttl", 10),
        )


@dataclass
class NodeReputation:
    """Reputation tracking for P2P nodes."""
    node_id: str
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_tasks: int = 0
    trust_score: float = 1.0  # Starts at 1.0, can go up to 2.0 for trusted nodes, down to 0.0 for untrusted
    last_update: float = field(default_factory=time.time)
    
    # Fraud detection
    suspicious_reports: int = 0
    consensus_violations: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tasks == 0:
            return 1.0
        return self.successful_tasks / self.total_tasks
    
    def update_score(self, success: bool, consensus_match: bool = True) -> None:
        """Update trust score based on task outcome."""
        self.total_tasks += 1
        self.last_update = time.time()
        
        if success:
            self.successful_tasks += 1
            # Increase trust score (can go up to 2.0 for trusted nodes)
            self.trust_score = min(2.0, self.trust_score + 0.01)
        else:
            self.failed_tasks += 1
            # Decrease trust score
            self.trust_score = max(0.0, self.trust_score - 0.05)
        
        if not consensus_match:
            self.consensus_violations += 1
            self.trust_score = max(0.0, self.trust_score - 0.1)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "total_tasks": self.total_tasks,
            "trust_score": self.trust_score,
            "success_rate": self.success_rate,
            "last_update": self.last_update,
            "suspicious_reports": self.suspicious_reports,
            "consensus_violations": self.consensus_violations,
        }


class TaskGossipProtocol:
    """Gossip protocol for distributing tasks across the P2P network."""
    
    def __init__(
        self,
        node: P2PNode,
        gossip_interval: float = 5.0,
        gossip_fanout: int = 3,
    ):
        """
        Initialize gossip protocol.
        
        Args:
            node: P2P node instance
            gossip_interval: Interval between gossip rounds
            gossip_fanout: Number of peers to gossip to per round
        """
        self.node = node
        self.gossip_interval = gossip_interval
        self.gossip_fanout = gossip_fanout
        
        self.task_cache: Dict[str, DistributedTask] = {}
        self.seen_task_ids: Set[str] = set()
        
        self.is_running = False
        self.gossip_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.tasks_gossiped = 0
        self.gossip_rounds = 0
    
    async def start(self) -> None:
        """Start gossip protocol."""
        if self.is_running:
            return
        
        self.is_running = True
        self.gossip_task = asyncio.create_task(self._gossip_loop())
        print("Task Gossip Protocol started")
    
    async def stop(self) -> None:
        """Stop gossip protocol."""
        self.is_running = False
        
        if self.gossip_task:
            self.gossip_task.cancel()
            try:
                await self.gossip_task
            except asyncio.CancelledError:
                pass
        
        print("Task Gossip Protocol stopped")
    
    async def _gossip_loop(self) -> None:
        """Main gossip loop."""
        while self.is_running:
            await asyncio.sleep(self.gossip_interval)
            
            # Get pending tasks to gossip
            pending_tasks = [
                task for task in self.task_cache.values()
                if task.state == TaskState.PENDING and task.ttl > 0
            ]
            
            if pending_tasks:
                await self._gossip_tasks(pending_tasks)
                self.gossip_rounds += 1
    
    async def _gossip_tasks(self, tasks: List[DistributedTask]) -> None:
        """Gossip tasks to random peers."""
        peers = list(self.node.peers.values())
        
        if not peers:
            return
        
        for task in tasks:
            # Decrease TTL
            task.ttl -= 1
            
            # Select random peers
            gossip_peers = random.sample(
                peers,
                min(self.gossip_fanout, len(peers))
            )
            
            # Mark this node as seen
            task.seen_by.add(self.node.local_node_id)
            task.gossip_count += 1
            
            for peer in gossip_peers:
                if peer.node_id not in task.seen_by:
                    message = P2PMessage(
                        msg_type=MessageType.TASK_OFFER,
                        sender_id=self.node.local_node_id,
                        payload=task.to_dict(),
                    )
                    
                    try:
                        await self.node._send_message(peer, message)
                        self.tasks_gossiped += 1
                    except Exception as e:
                        print(f"Failed to gossip task to {peer.node_id}: {e}")
            
            # Remove expired tasks
            if task.ttl <= 0:
                del self.task_cache[task.task_id]
    
    async def submit_task(self, task: DistributedTask) -> str:
        """
        Submit a new task to the network.
        
        Args:
            task: Task to distribute
        
        Returns:
            Task ID
        """
        task.origin_node = self.node.local_node_id
        task.seen_by.add(self.node.local_node_id)
        
        self.task_cache[task.task_id] = task
        self.seen_task_ids.add(task.task_id)
        
        # Immediate gossip
        await self._gossip_tasks([task])
        
        return task.task_id
    
    def receive_task(self, task_dict: Dict[str, Any]) -> bool:
        """
        Receive a task from gossip.
        
        Args:
            task_dict: Task dictionary from peer
        
        Returns:
            True if task was accepted
        """
        task = DistributedTask.from_dict(task_dict)
        
        # Check if already seen
        if task.task_id in self.seen_task_ids:
            return False
        
        # Check TTL
        if task.ttl <= 0:
            return False
        
        # Add to cache
        self.task_cache[task.task_id] = task
        self.seen_task_ids.add(task.task_id)
        
        return True
    
    def get_task_status(self, task_id: str) -> Optional[DistributedTask]:
        """Get status of a task."""
        return self.task_cache.get(task_id)
    
    def get_pending_tasks(self) -> List[DistributedTask]:
        """Get all pending tasks."""
        return [
            task for task in self.task_cache.values()
            if task.state == TaskState.PENDING
        ]


class TaskDistributor:
    """Task distribution coordinator for the P2P network."""
    
    def __init__(
        self,
        node: P2PNode,
        gossip_protocol: TaskGossipProtocol,
        reputation_db: "ReputationDatabase",
    ):
        """
        Initialize task distributor.
        
        Args:
            node: P2P node instance
            gossip_protocol: Gossip protocol instance
            reputation_db: Reputation database
        """
        self.node = node
        self.gossip = gossip_protocol
        self.reputation = reputation_db
        
        self.active_tasks: Dict[str, DistributedTask] = {}
        self.task_assignments: Dict[str, str] = {}  # task_id -> node_id
    
    async def distribute_ab_test(
        self,
        model_a: str,
        model_b: str,
        task_spec: Dict[str, Any],
        required_nodes: int = 3,
    ) -> str:
        """
        Distribute an A/B test across multiple nodes.
        
        Args:
            model_a: First model
            model_b: Second model
            task_spec: Task specification
            required_nodes: Number of nodes to run test on
        
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        
        task = DistributedTask(
            task_id=task_id,
            task_type="ab_test",
            payload={
                "model_a": model_a,
                "model_b": model_b,
                "task_spec": task_spec,
                "required_nodes": required_nodes,
            },
        )
        
        # Submit to gossip protocol
        await self.gossip.submit_task(task)
        self.active_tasks[task_id] = task
        
        return task_id
    
    async def assign_task(self, task: DistributedTask, assignee: NodeInfo) -> bool:
        """
        Assign a task to a specific node.
        
        Args:
            task: Task to assign
            assignee: Node to assign to
        
        Returns:
            True if assignment successful
        """
        if task.state != TaskState.PENDING:
            return False
        
        # Check node reputation
        rep = self.reputation.get_node_reputation(assignee.node_id)
        if rep and rep.trust_score < 0.5:
            print(f"Node {assignee.node_id} has low trust score: {rep.trust_score}")
            return False
        
        # Assign task
        task.state = TaskState.ASSIGNED
        task.assigned_node = assignee.node_id
        task.assigned_at = time.time()
        
        self.task_assignments[task.task_id] = assignee.node_id
        
        # Send task assignment message
        message = P2PMessage(
            msg_type=MessageType.TASK_OFFER,
            sender_id=self.node.local_node_id,
            payload=task.to_dict(),
        )
        
        success = await self.node._send_message(assignee, message)
        
        if not success:
            # Revert assignment
            task.state = TaskState.PENDING
            task.assigned_node = None
            del self.task_assignments[task.task_id]
        
        return success
    
    def select_best_node(self, task: DistributedTask) -> Optional[NodeInfo]:
        """
        Select the best node for a task based on capabilities and reputation.
        
        Args:
            task: Task to assign
        
        Returns:
            Best node or None
        """
        available_peers = [
            peer for peer in self.node.peers.values()
            if peer.node_id != self.node.local_node_id
        ]
        
        if not available_peers:
            return None
        
        # Score each peer
        scored_peers = []
        for peer in available_peers:
            rep = self.reputation.get_node_reputation(peer.node_id)
            trust_score = rep.trust_score if rep else 0.5
            
            # Consider load
            load_factor = 1.0 - (peer.reputation_score * 0.1)
            
            # Final score
            score = trust_score * load_factor * 100
            scored_peers.append((score, peer))
        
        # Sort by score descending
        scored_peers.sort(key=lambda x: x[0], reverse=True)
        
        return scored_peers[0][1] if scored_peers else None


class ResultAggregator:
    """Aggregates results from distributed tasks with consensus mechanism."""
    
    def __init__(self, reputation_db: "ReputationDatabase"):
        """
        Initialize result aggregator.
        
        Args:
            reputation_db: Reputation database for weighted consensus
        """
        self.reputation = reputation_db
        self.task_results: Dict[str, List[Dict[str, Any]]] = {}
        self.consensus_threshold = 0.6  # 60% agreement needed
    
    async def collect_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """
        Collect a result from a node.
        
        Args:
            task_id: Task ID
            result: Result data
        """
        if task_id not in self.task_results:
            self.task_results[task_id] = []
        
        self.task_results[task_id].append(result)
    
    def compute_consensus(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Compute consensus from collected results.
        
        Args:
            task_id: Task ID
        
        Returns:
            Consensus result or None if insufficient data
        """
        results = self.task_results.get(task_id, [])
        
        if not results:
            return None
        
        if len(results) < 2:
            # Single result, use as-is with metadata
            return {
                **results[0],
                "result_count": 1,
                "consensus_score": results[0].get("score", 0.0),
                "confidence": 1.0,
            }
        
        # Weight results by node reputation
        weighted_results = []
        total_weight = 0.0
        
        for result in results:
            node_id = result.get("node_id", "")
            rep = self.reputation.get_node_reputation(node_id)
            weight = rep.trust_score if rep else 0.5
            
            weighted_results.append((weight, result))
            total_weight += weight
        
        # Simple weighted average for numeric scores
        # For more complex results, use majority voting
        if total_weight == 0:
            # Fallback to simple average
            return {
                "task_id": task_id,
                "results": results,
                "result_count": len(results),
                "consensus_method": "simple_average",
            }
        
        # Weighted consensus
        consensus = {
            "task_id": task_id,
            "result_count": len(results),
            "consensus_method": "weighted_average",
            "weighted_results": weighted_results,
        }
        
        return consensus
    
    def detect_fraud(
        self,
        task_id: str,
        result: Dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Detect potential fraud in results.
        
        Args:
            task_id: Task ID
            result: Result to validate
        
        Returns:
            Tuple of (is_fraudulent, reason)
        """
        results = self.task_results.get(task_id, [])
        
        if len(results) < 2:
            return False, "insufficient_data"
        
        # Check if result is an outlier
        # This is a simple implementation
        # In production, use statistical anomaly detection
        return False, "ok"


class ReputationDatabase:
    """Database for tracking node reputation and trust scores."""
    
    def __init__(self):
        """Initialize reputation database."""
        self.reputations: Dict[str, NodeReputation] = {}
        self.consensus_history: Dict[str, List[bool]] = defaultdict(list)
    
    def get_node_reputation(self, node_id: str) -> Optional[NodeReputation]:
        """Get reputation for a node."""
        return self.reputations.get(node_id)
    
    def update_node_reputation(
        self,
        node_id: str,
        success: bool,
        consensus_match: bool = True,
    ) -> None:
        """
        Update node reputation.
        
        Args:
            node_id: Node ID
            success: Whether task succeeded
            consensus_match: Whether result matched consensus
        """
        if node_id not in self.reputations:
            self.reputations[node_id] = NodeReputation(node_id=node_id)
        
        self.reputations[node_id].update_score(success, consensus_match)
    
    def record_consensus(self, node_id: str, matched: bool) -> None:
        """Record consensus participation."""
        self.consensus_history[node_id].append(matched)
    
    def get_trust_score(self, node_id: str) -> float:
        """Get trust score for a node."""
        rep = self.reputations.get(node_id)
        return rep.trust_score if rep else 0.5
    
    def get_top_trusted_nodes(self, limit: int = 10) -> List[NodeReputation]:
        """Get top trusted nodes."""
        sorted_reps = sorted(
            self.reputations.values(),
            key=lambda r: r.trust_score,
            reverse=True,
        )
        return sorted_reps[:limit]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "reputations": {
                node_id: rep.to_dict()
                for node_id, rep in self.reputations.items()
            },
        }
