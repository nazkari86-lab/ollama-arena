"""Tests for P2P Distribution module."""
import pytest
import time
from ollama_arena.p2p.distribution import (
    DistributedTask,
    TaskState,
    TaskGossipProtocol,
    TaskDistributor,
    ResultAggregator,
    ReputationDatabase,
    NodeReputation,
)


class TestDistributedTask:
    """Test DistributedTask dataclass."""
    
    def test_task_creation(self):
        """Test creating a distributed task."""
        task = DistributedTask(
            task_id="task123",
            task_type="ab_test",
            payload={"model_a": "llama2", "model_b": "mistral"},
        )
        
        assert task.task_id == "task123"
        assert task.task_type == "ab_test"
        assert task.state == TaskState.PENDING
        assert task.gossip_count == 0
    
    def test_task_serialization(self):
        """Test task to_dict/from_dict."""
        task = DistributedTask(
            task_id="task456",
            task_type="benchmark",
            payload={"category": "coding"},
            state=TaskState.RUNNING,
        )
        
        data = task.to_dict()
        assert data["task_id"] == "task456"
        assert data["state"] == "running"
        
        restored = DistributedTask.from_dict(data)
        assert restored.task_id == task.task_id
        assert restored.state == task.state


class TestNodeReputation:
    """Test NodeReputation tracking."""
    
    def test_reputation_initialization(self):
        """Test reputation initialization."""
        rep = NodeReputation(node_id="node123")
        
        assert rep.node_id == "node123"
        assert rep.trust_score == 1.0
        assert rep.successful_tasks == 0
        assert rep.failed_tasks == 0
    
    def test_reputation_update_success(self):
        """Test reputation update on success."""
        rep = NodeReputation(node_id="node123")
        
        rep.update_score(success=True, consensus_match=True)
        
        assert rep.successful_tasks == 1
        assert rep.total_tasks == 1
        assert rep.trust_score > 1.0  # Should increase
    
    def test_reputation_update_failure(self):
        """Test reputation update on failure."""
        rep = NodeReputation(node_id="node123")
        
        rep.update_score(success=False, consensus_match=True)
        
        assert rep.failed_tasks == 1
        assert rep.total_tasks == 1
        assert rep.trust_score < 1.0  # Should decrease
    
    def test_reputation_consensus_violation(self):
        """Test reputation update on consensus violation."""
        rep = NodeReputation(node_id="node123")
        
        rep.update_score(success=True, consensus_match=False)
        
        assert rep.consensus_violations == 1
        assert rep.trust_score < 1.0  # Should decrease more
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        rep = NodeReputation(node_id="node123")
        
        assert rep.success_rate == 1.0
        
        rep.update_score(success=True)
        rep.update_score(success=True)
        rep.update_score(success=False)
        
        assert rep.success_rate == 2/3


class TestReputationDatabase:
    """Test ReputationDatabase."""
    
    @pytest.fixture
    def db(self):
        """Create a ReputationDatabase instance."""
        return ReputationDatabase()
    
    def test_database_initialization(self, db):
        """Test database initialization."""
        assert len(db.reputations) == 0
    
    def test_get_nonexistent_reputation(self, db):
        """Test getting reputation for nonexistent node."""
        rep = db.get_node_reputation("nonexistent")
        assert rep is None
    
    def test_update_and_get_reputation(self, db):
        """Test updating and getting reputation."""
        db.update_node_reputation("node1", success=True)
        
        rep = db.get_node_reputation("node1")
        assert rep is not None
        assert rep.node_id == "node1"
        assert rep.successful_tasks == 1
    
    def test_trust_score_retrieval(self, db):
        """Test trust score retrieval."""
        assert db.get_trust_score("nonexistent") == 0.5
        
        db.update_node_reputation("node1", success=True)
        assert db.get_trust_score("node1") >= 0.5
    
    def test_top_trusted_nodes(self, db):
        """Test getting top trusted nodes."""
        db.update_node_reputation("node1", success=True)
        db.update_node_reputation("node2", success=False)
        db.update_node_reputation("node3", success=True)
        
        top = db.get_top_trusted_nodes(limit=2)
        assert len(top) <= 2


class TestTaskGossipProtocol:
    """Test TaskGossipProtocol."""
    
    @pytest.fixture
    def node(self):
        """Create a mock P2P node."""
        from ollama_arena.p2p.node import P2PNode
        return P2PNode(host="127.0.0.1", port=8080)
    
    @pytest.fixture
    def gossip(self, node):
        """Create a TaskGossipProtocol instance."""
        return TaskGossipProtocol(node=node)
    
    def test_gossip_initialization(self, gossip):
        """Test gossip protocol initialization."""
        assert gossip.node is not None
        assert gossip.gossip_interval > 0
        assert gossip.gossip_fanout > 0
    
    def test_receive_task(self, gossip):
        """Test receiving a task."""
        task_data = {
            "task_id": "task123",
            "task_type": "ab_test",
            "payload": {},
            "state": "pending",
            "ttl": 10,
        }
        
        assert gossip.receive_task(task_data) is True
        assert "task123" in gossip.seen_task_ids
    
    def test_receive_duplicate_task(self, gossip):
        """Test receiving duplicate task."""
        task_data = {
            "task_id": "task123",
            "task_type": "ab_test",
            "payload": {},
            "state": "pending",
            "ttl": 10,
        }
        
        gossip.receive_task(task_data)
        assert gossip.receive_task(task_data) is False  # Duplicate
    
    def test_receive_expired_task(self, gossip):
        """Test receiving expired task."""
        task_data = {
            "task_id": "task123",
            "task_type": "ab_test",
            "payload": {},
            "state": "pending",
            "ttl": 0,  # Expired
        }
        
        assert gossip.receive_task(task_data) is False
    
    def test_get_task_status(self, gossip):
        """Test getting task status."""
        task_data = {
            "task_id": "task123",
            "task_type": "ab_test",
            "payload": {},
            "state": "pending",
            "ttl": 10,
        }
        
        gossip.receive_task(task_data)
        
        status = gossip.get_task_status("task123")
        assert status is not None
        assert status.task_id == "task123"


class TestResultAggregator:
    """Test ResultAggregator."""
    
    @pytest.fixture
    def reputation_db(self):
        """Create a reputation database."""
        return ReputationDatabase()
    
    @pytest.fixture
    def aggregator(self, reputation_db):
        """Create a ResultAggregator instance."""
        return ResultAggregator(reputation_db)
    
    @pytest.mark.asyncio
    async def test_collect_result(self, aggregator):
        """Test collecting a result."""
        result = {
            "task_id": "task123",
            "node_id": "node1",
            "score": 0.85,
        }
        
        await aggregator.collect_result("task123", result)
        
        assert len(aggregator.task_results["task123"]) == 1
    
    @pytest.mark.asyncio
    async def test_compute_consensus_single(self, aggregator):
        """Test consensus with single result."""
        result = {
            "task_id": "task123",
            "node_id": "node1",
            "score": 0.85,
        }
        
        await aggregator.collect_result("task123", result)
        
        consensus = aggregator.compute_consensus("task123")
        assert consensus is not None
        assert consensus["result_count"] == 1
    
    @pytest.mark.asyncio
    async def test_compute_consensus_multiple(self, aggregator):
        """Test consensus with multiple results."""
        for i in range(3):
            result = {
                "task_id": "task123",
                "node_id": f"node{i}",
                "score": 0.85 + (i * 0.01),
            }
            await aggregator.collect_result("task123", result)
        
        consensus = aggregator.compute_consensus("task123")
        assert consensus is not None
        assert consensus["result_count"] == 3
    
    def test_detect_fraud_insufficient_data(self, aggregator):
        """Test fraud detection with insufficient data."""
        result = {"task_id": "task123", "node_id": "node1"}
        
        is_fraud, reason = aggregator.detect_fraud("task123", result)
        assert is_fraud is False
        assert reason == "insufficient_data"


class TestTaskDistributor:
    """Test TaskDistributor."""
    
    @pytest.fixture
    def node(self):
        """Create a mock P2P node."""
        from ollama_arena.p2p.node import P2PNode
        return P2PNode(host="127.0.0.1", port=8080)
    
    @pytest.fixture
    def reputation_db(self):
        """Create a reputation database."""
        return ReputationDatabase()
    
    @pytest.fixture
    def gossip(self, node):
        """Create a gossip protocol."""
        return TaskGossipProtocol(node=node)
    
    @pytest.fixture
    def distributor(self, node, gossip, reputation_db):
        """Create a TaskDistributor instance."""
        return TaskDistributor(node, gossip, reputation_db)
    
    @pytest.mark.asyncio
    async def test_distribute_ab_test(self, distributor):
        """Test distributing an A/B test."""
        task_id = await distributor.distribute_ab_test(
            model_a="llama2",
            model_b="mistral",
            task_spec={"category": "coding"},
            required_nodes=3,
        )
        
        assert task_id is not None
        assert task_id in distributor.active_tasks
    
    def test_select_best_node_no_peers(self, distributor):
        """Test selecting best node with no peers."""
        task = DistributedTask(
            task_id="task123",
            task_type="ab_test",
            payload={},
        )
        
        best = distributor.select_best_node(task)
        assert best is None
