"""Tests for P2P Node module."""
import pytest
import time
from ollama_arena.p2p.node import (
    P2PNode,
    NodeDiscovery,
    P2PMessage,
    MessageType,
    NodeInfo,
)


class TestP2PMessage:
    """Test P2P message serialization."""
    
    def test_message_creation(self):
        """Test creating a P2P message."""
        msg = P2PMessage(
            msg_type=MessageType.DISCOVERY,
            sender_id="node123",
            payload={"test": "data"},
        )
        
        assert msg.msg_type == MessageType.DISCOVERY
        assert msg.sender_id == "node123"
        assert msg.payload == {"test": "data"}
        assert msg.message_id is not None
        assert msg.timestamp > 0
    
    def test_message_serialization(self):
        """Test message to_dict/from_dict."""
        msg = P2PMessage(
            msg_type=MessageType.HEARTBEAT,
            sender_id="node456",
            payload={"status": "ok"},
        )
        
        data = msg.to_dict()
        assert "message_id" in data
        assert "msg_type" in data
        assert data["msg_type"] == "heartbeat"
        
        restored = P2PMessage.from_dict(data)
        assert restored.msg_type == msg.msg_type
        assert restored.sender_id == msg.sender_id
        assert restored.payload == msg.payload


class TestNodeInfo:
    """Test NodeInfo dataclass."""
    
    def test_node_info_creation(self):
        """Test creating NodeInfo."""
        info = NodeInfo(
            node_id="node789",
            address="192.168.1.100",
            port=8080,
        )
        
        assert info.node_id == "node789"
        assert info.address == "192.168.1.100"
        assert info.port == 8080
        assert info.reputation_score == 1.0
    
    def test_node_info_endpoint(self):
        """Test NodeInfo endpoint property."""
        info = NodeInfo(
            node_id="node789",
            address="192.168.1.100",
            port=9090,
        )
        
        assert info.endpoint == "192.168.1.100:9090"
    
    def test_node_info_serialization(self):
        """Test NodeInfo to_dict/from_dict."""
        info = NodeInfo(
            node_id="node789",
            address="192.168.1.100",
            port=8080,
            capabilities={"cpu_cores": 8},
        )
        
        data = info.to_dict()
        assert data["node_id"] == "node789"
        assert data["capabilities"]["cpu_cores"] == 8
        
        restored = NodeInfo.from_dict(data)
        assert restored.node_id == info.node_id
        assert restored.capabilities == info.capabilities


class TestNodeDiscovery:
    """Test NodeDiscovery service."""
    
    @pytest.fixture
    def discovery(self):
        """Create a NodeDiscovery instance."""
        return NodeDiscovery(
            bootstrap_nodes=["bootstrap1:8080", "bootstrap2:8080"],
        )
    
    def test_node_id_generation(self, discovery):
        """Test node ID generation."""
        node_id = discovery.local_node_id
        assert isinstance(node_id, str)
        assert len(node_id) == 16
    
    def test_discover_peers_empty(self, discovery):
        """Test peer discovery with no peers."""
        # This is a synchronous test, so we'll just test the method exists
        assert hasattr(discovery, 'discover_local_peers')
        assert hasattr(discovery, 'discover_from_bootstrap')
    
    def test_get_peer_methods(self, discovery):
        """Test peer retrieval methods."""
        # Add a mock peer
        from ollama_arena.p2p.node import NodeInfo
        peer = NodeInfo(
            node_id="peer123",
            address="192.168.1.1",
            port=8080,
        )
        discovery.discovered_peers[peer.node_id] = peer
        
        assert discovery.get_peer("peer123") == peer
        assert discovery.get_peer("nonexistent") is None
        assert len(discovery.get_all_peers()) == 1


class TestP2PNode:
    """Test P2PNode class."""
    
    @pytest.fixture
    def node(self):
        """Create a P2PNode instance."""
        return P2PNode(
            host="127.0.0.1",
            port=8080,
            bootstrap_nodes=["bootstrap:8080"],
        )
    
    def test_node_initialization(self, node):
        """Test node initialization."""
        assert node.host == "127.0.0.1"
        assert node.port == 8080
        assert node.local_node_id is not None
        assert not node.is_running
    
    def test_node_capabilities(self, node):
        """Test node capabilities."""
        caps = node._get_capabilities()
        assert "cpu_cores" in caps
        assert "memory_gb" in caps
        assert "platform" in caps

    def test_node_capabilities_cached_within_ttl(self, node):
        """A second call within the cache TTL must reuse the same dict, not recompute."""
        first = node._get_capabilities()
        second = node._get_capabilities()
        assert first is second

    def test_node_capabilities_falls_back_without_psutil(self, node, monkeypatch):
        """psutil missing must fall back to defaults, not crash (regression: import
        was previously outside the try/except meant to catch it)."""
        import builtins
        real_import = builtins.__import__

        def _no_psutil(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("no psutil")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _no_psutil)
        caps = node._get_capabilities()
        assert caps["cpu_cores"] == 4
        assert caps["memory_gb"] == 16.0

    def test_task_acceptance(self, node):
        """Test task acceptance logic."""
        simple_task = {
            "task_id": "task1",
            "required_memory_gb": 8,
            "required_cpu_cores": 2,
        }
        
        assert node._can_accept_task(simple_task) is True
    
    def test_task_rejection_memory(self, node):
        """Test task rejection due to memory requirements."""
        high_memory_task = {
            "task_id": "task2",
            "required_memory_gb": 100000,  # Unrealistic
            "required_cpu_cores": 1,
        }
        
        assert node._can_accept_task(high_memory_task) is False
    
    def test_get_stats(self, node):
        """Test node statistics."""
        stats = node.get_stats()
        assert "node_id" in stats
        assert "peer_count" in stats
        assert "messages_sent" in stats
        assert "messages_received" in stats
        assert stats["is_running"] is False
    
    def test_message_handlers(self, node):
        """Test message handlers."""
        discovery_msg = P2PMessage(
            msg_type=MessageType.DISCOVERY,
            sender_id="peer1",
            payload={"address": "192.168.1.1", "port": 8080},
        )
        
        response = node._handle_discovery(discovery_msg)
        assert response["node_id"] == node.local_node_id
        assert "port" in response
        
        heartbeat_msg = P2PMessage(
            msg_type=MessageType.HEARTBEAT,
            sender_id="peer2",
            payload={"status": "ok"},
        )
        
        response = node._handle_heartbeat(heartbeat_msg)
        assert response["status"] == "ok"


@pytest.mark.asyncio
class TestP2PNodeAsync:
    """Async tests for P2PNode."""
    
    async def test_node_start_stop(self):
        """Test node start and stop."""
        node = P2PNode(host="127.0.0.1", port=8080)
        
        await node.start()
        assert node.is_running is True
        
        await node.stop()
        assert node.is_running is False
    
    async def test_discovery_during_start(self):
        """Test peer discovery during node start."""
        node = P2PNode(
            host="127.0.0.1",
            port=8080,
            bootstrap_nodes=[],  # No bootstrap for test
        )
        
        await node.start()
        assert node.is_running is True
        
        await node.stop()
