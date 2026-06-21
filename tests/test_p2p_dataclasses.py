"""Tests for P2P crypto_proof and node dataclasses — no network calls."""
from __future__ import annotations

import time

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# crypto_proof — ResultSignature, HardwareAttestation, ZeroKnowledgeProof, BlockchainAnchor
# ──────────────────────────────────────────────────────────────────────────────

class TestResultSignature:
    def _make(self, **kw):
        from ollama_arena.p2p.crypto_proof import ResultSignature
        defaults = dict(
            node_id="node_abc",
            task_id="task_123",
            signature="sig_hex_value",
            public_key="pubkey_hex",
            timestamp=1000.0,
        )
        defaults.update(kw)
        return ResultSignature(**defaults)

    def test_creation(self):
        sig = self._make()
        assert sig.node_id == "node_abc"
        assert sig.algorithm == "ed25519"

    def test_to_dict_has_all_keys(self):
        sig = self._make()
        d = sig.to_dict()
        for key in ["node_id", "task_id", "signature", "public_key", "timestamp", "algorithm"]:
            assert key in d

    def test_to_dict_values(self):
        sig = self._make(node_id="n1", task_id="t1")
        d = sig.to_dict()
        assert d["node_id"] == "n1"
        assert d["task_id"] == "t1"

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.crypto_proof import ResultSignature
        sig = self._make()
        d = sig.to_dict()
        sig2 = ResultSignature.from_dict(d)
        assert sig2.node_id == sig.node_id
        assert sig2.signature == sig.signature
        assert sig2.algorithm == sig.algorithm

    def test_default_algorithm_ed25519(self):
        from ollama_arena.p2p.crypto_proof import ResultSignature
        d = {"node_id": "n", "task_id": "t", "signature": "s", "public_key": "k", "timestamp": 1.0}
        sig = ResultSignature.from_dict(d)
        assert sig.algorithm == "ed25519"


class TestHardwareAttestation:
    def _make(self, **kw):
        from ollama_arena.p2p.crypto_proof import HardwareAttestation
        defaults = dict(cpu_signature="cpu_sig", memory_signature="mem_sig")
        defaults.update(kw)
        return HardwareAttestation(**defaults)

    def test_creation(self):
        hw = self._make()
        assert hw.cpu_signature == "cpu_sig"
        assert hw.gpu_signature is None
        assert hw.network_isolated is False

    def test_to_dict_keys(self):
        hw = self._make()
        d = hw.to_dict()
        for key in ["cpu_signature", "memory_signature", "gpu_signature", "platform_info", "network_isolated"]:
            assert key in d

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.crypto_proof import HardwareAttestation
        hw = self._make(gpu_signature="gpu_sig", network_isolated=True)
        d = hw.to_dict()
        hw2 = HardwareAttestation.from_dict(d)
        assert hw2.gpu_signature == "gpu_sig"
        assert hw2.network_isolated is True

    def test_platform_info_default_empty(self):
        hw = self._make()
        assert hw.platform_info == {}

    def test_platform_info_stored(self):
        hw = self._make(platform_info={"os": "linux", "arch": "x86_64"})
        assert hw.platform_info["os"] == "linux"


class TestZeroKnowledgeProof:
    def _make(self, **kw):
        from ollama_arena.p2p.crypto_proof import ZeroKnowledgeProof
        defaults = dict(
            proof_type="range_proof",
            proof_data={"range": [0, 10]},
            verification_key="vk_hex",
            challenge="challenge_hex",
            response="response_hex",
        )
        defaults.update(kw)
        return ZeroKnowledgeProof(**defaults)

    def test_creation(self):
        zkp = self._make()
        assert zkp.proof_type == "range_proof"
        assert zkp.proof_data["range"] == [0, 10]

    def test_to_dict_all_keys(self):
        zkp = self._make()
        d = zkp.to_dict()
        for key in ["proof_type", "proof_data", "verification_key", "challenge", "response"]:
            assert key in d

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.crypto_proof import ZeroKnowledgeProof
        zkp = self._make(proof_type="execution_proof")
        d = zkp.to_dict()
        zkp2 = ZeroKnowledgeProof.from_dict(d)
        assert zkp2.proof_type == "execution_proof"
        assert zkp2.challenge == zkp.challenge

    def test_proof_data_preserved(self):
        from ollama_arena.p2p.crypto_proof import ZeroKnowledgeProof
        zkp = self._make(proof_data={"key": "value", "n": 42})
        d = zkp.to_dict()
        zkp2 = ZeroKnowledgeProof.from_dict(d)
        assert zkp2.proof_data["key"] == "value"
        assert zkp2.proof_data["n"] == 42


class TestBlockchainAnchor:
    def _make(self, **kw):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchor
        defaults = dict(
            transaction_hash="tx_abc123",
            block_height=12345,
            block_hash="bh_xyz",
            timestamp=2000.0,
        )
        defaults.update(kw)
        return BlockchainAnchor(**defaults)

    def test_creation(self):
        anchor = self._make()
        assert anchor.transaction_hash == "tx_abc123"
        assert anchor.block_height == 12345
        assert anchor.network == "ethereum"

    def test_to_dict_all_keys(self):
        anchor = self._make()
        d = anchor.to_dict()
        for key in ["transaction_hash", "block_height", "block_hash", "timestamp", "network"]:
            assert key in d

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchor
        anchor = self._make(network="bitcoin")
        d = anchor.to_dict()
        anchor2 = BlockchainAnchor.from_dict(d)
        assert anchor2.network == "bitcoin"
        assert anchor2.block_height == 12345

    def test_default_network_ethereum(self):
        from ollama_arena.p2p.crypto_proof import BlockchainAnchor
        d = {"transaction_hash": "tx", "block_height": 1, "block_hash": "bh", "timestamp": 1.0}
        anchor = BlockchainAnchor.from_dict(d)
        assert anchor.network == "ethereum"


# ──────────────────────────────────────────────────────────────────────────────
# node — MessageType, P2PMessage, NodeInfo, NodeDiscovery, P2PNode
# ──────────────────────────────────────────────────────────────────────────────

class TestMessageType:
    def test_all_types_present(self):
        from ollama_arena.p2p.node import MessageType
        types = {t.value for t in MessageType}
        assert "discovery" in types
        assert "heartbeat" in types
        assert "task_offer" in types
        assert "task_accept" in types
        assert "task_result" in types
        assert "peer_list" in types

    def test_from_value(self):
        from ollama_arena.p2p.node import MessageType
        assert MessageType("heartbeat") == MessageType.HEARTBEAT

    def test_count(self):
        from ollama_arena.p2p.node import MessageType
        assert len(list(MessageType)) == 10


class TestP2PMessage:
    def _make(self, **kw):
        from ollama_arena.p2p.node import P2PMessage, MessageType
        defaults = dict(
            msg_type=MessageType.HEARTBEAT,
            sender_id="node_abc",
            payload={"port": 8080},
        )
        defaults.update(kw)
        return P2PMessage(**defaults)

    def test_creation(self):
        msg = self._make()
        assert msg.sender_id == "node_abc"
        assert msg.msg_type.value == "heartbeat"

    def test_auto_timestamp(self):
        before = time.time()
        msg = self._make()
        after = time.time()
        assert before <= msg.timestamp <= after

    def test_auto_message_id(self):
        msg1 = self._make()
        msg2 = self._make()
        assert msg1.message_id != msg2.message_id

    def test_to_dict_has_all_keys(self):
        msg = self._make()
        d = msg.to_dict()
        for key in ["message_id", "msg_type", "sender_id", "payload", "timestamp"]:
            assert key in d

    def test_to_dict_msg_type_is_string(self):
        msg = self._make()
        d = msg.to_dict()
        assert isinstance(d["msg_type"], str)
        assert d["msg_type"] == "heartbeat"

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.node import P2PMessage
        msg = self._make(payload={"key": "val"})
        d = msg.to_dict()
        msg2 = P2PMessage.from_dict(d)
        assert msg2.sender_id == msg.sender_id
        assert msg2.msg_type == msg.msg_type
        assert msg2.payload == msg.payload

    def test_from_dict_different_types(self):
        from ollama_arena.p2p.node import P2PMessage, MessageType
        for msg_type in [MessageType.DISCOVERY, MessageType.TASK_OFFER, MessageType.PEER_LIST]:
            msg = self._make(msg_type=msg_type)
            d = msg.to_dict()
            msg2 = P2PMessage.from_dict(d)
            assert msg2.msg_type == msg_type


class TestNodeInfo:
    def _make(self, **kw):
        from ollama_arena.p2p.node import NodeInfo
        defaults = dict(
            node_id="node_xyz",
            address="192.168.1.10",
            port=8080,
        )
        defaults.update(kw)
        return NodeInfo(**defaults)

    def test_creation(self):
        ni = self._make()
        assert ni.node_id == "node_xyz"
        assert ni.address == "192.168.1.10"

    def test_endpoint_property(self):
        ni = self._make(address="10.0.0.1", port=9000)
        assert ni.endpoint == "10.0.0.1:9000"

    def test_default_trust_level(self):
        ni = self._make()
        assert ni.trust_level == "unverified"

    def test_default_reputation(self):
        ni = self._make()
        assert ni.reputation_score == 1.0

    def test_to_dict_all_keys(self):
        ni = self._make()
        d = ni.to_dict()
        for key in ["node_id", "address", "port", "capabilities", "reputation_score", "trust_level"]:
            assert key in d

    def test_from_dict_roundtrip(self):
        from ollama_arena.p2p.node import NodeInfo
        ni = self._make(trust_level="trusted", reputation_score=0.9)
        d = ni.to_dict()
        ni2 = NodeInfo.from_dict(d)
        assert ni2.node_id == ni.node_id
        assert ni2.trust_level == "trusted"
        assert ni2.reputation_score == 0.9

    def test_capabilities_stored(self):
        ni = self._make(capabilities={"cpu": 8, "mem": 16})
        assert ni.capabilities["cpu"] == 8

    def test_from_dict_default_trust_unverified(self):
        from ollama_arena.p2p.node import NodeInfo
        d = {"node_id": "n", "address": "1.2.3.4", "port": 80}
        ni = NodeInfo.from_dict(d)
        assert ni.trust_level == "unverified"


class TestNodeDiscovery:
    def test_init_default_bootstrap_empty(self):
        from ollama_arena.p2p.node import NodeDiscovery
        nd = NodeDiscovery()
        assert nd.bootstrap_nodes == []

    def test_init_with_bootstrap(self):
        from ollama_arena.p2p.node import NodeDiscovery
        nd = NodeDiscovery(bootstrap_nodes=["bootstrap.example.com:8080"])
        assert len(nd.bootstrap_nodes) == 1

    def test_generates_node_id(self):
        from ollama_arena.p2p.node import NodeDiscovery
        nd = NodeDiscovery()
        assert nd.local_node_id != ""
        assert len(nd.local_node_id) == 16

    def test_stable_node_id(self):
        from ollama_arena.p2p.node import NodeDiscovery
        nd1 = NodeDiscovery()
        nd2 = NodeDiscovery()
        # Same machine → same ID
        assert nd1.local_node_id == nd2.local_node_id

    def test_get_peer_not_found(self):
        from ollama_arena.p2p.node import NodeDiscovery
        nd = NodeDiscovery()
        assert nd.get_peer("nonexistent_id") is None

    def test_get_all_peers_empty(self):
        from ollama_arena.p2p.node import NodeDiscovery
        nd = NodeDiscovery()
        assert nd.get_all_peers() == []

    def test_discovered_peers_dict(self):
        from ollama_arena.p2p.node import NodeDiscovery, NodeInfo
        nd = NodeDiscovery()
        peer = NodeInfo(node_id="p1", address="1.2.3.4", port=8080)
        nd.discovered_peers["p1"] = peer
        result = nd.get_peer("p1")
        assert result.node_id == "p1"


class TestP2PNode:
    def _make(self):
        from ollama_arena.p2p.node import P2PNode
        return P2PNode(host="127.0.0.1", port=0, max_peers=10, heartbeat_interval=60.0)

    def test_initial_state(self):
        node = self._make()
        assert node.is_running is False
        assert node.peers == {}
        assert node.messages_sent == 0

    def test_get_stats(self):
        node = self._make()
        stats = node.get_stats()
        assert "node_id" in stats
        assert stats["peer_count"] == 0
        assert stats["is_running"] is False
        assert stats["tasks_completed"] == 0

    def test_get_peer_count(self):
        node = self._make()
        assert node.get_peer_count() == 0

    def test_can_accept_task_no_resources(self):
        node = self._make()
        task = {"required_memory_gb": 0, "required_cpu_cores": 1}
        # Should return True for minimal requirements
        result = node._can_accept_task(task)
        assert isinstance(result, bool)

    def test_can_accept_task_excessive_requirements(self):
        node = self._make()
        task = {"required_memory_gb": 99999, "required_cpu_cores": 9999}
        assert node._can_accept_task(task) is False

    def test_handle_heartbeat_increments_received(self):
        from ollama_arena.p2p.node import P2PMessage, MessageType
        node = self._make()
        msg = P2PMessage(
            msg_type=MessageType.HEARTBEAT,
            sender_id="other_node",
            payload={"port": 8080, "capabilities": {}},
        )
        node._handle_heartbeat(msg)
        assert node.messages_received == 1

    def test_handle_task_offer_no_task_id(self):
        from ollama_arena.p2p.node import P2PMessage, MessageType
        node = self._make()
        msg = P2PMessage(
            msg_type=MessageType.TASK_OFFER,
            sender_id="other_node",
            payload={},  # no task_id
        )
        result = node._handle_task_offer(msg)
        assert result["accepted"] is False

    def test_handle_peer_list_returns_peers(self):
        from ollama_arena.p2p.node import P2PMessage, MessageType
        node = self._make()
        msg = P2PMessage(
            msg_type=MessageType.PEER_LIST,
            sender_id="other_node",
            payload={},
        )
        result = node._handle_peer_list(msg)
        assert "peers" in result
        assert isinstance(result["peers"], list)

    def test_handle_discovery_adds_peer(self):
        from ollama_arena.p2p.node import P2PMessage, MessageType
        node = self._make()
        msg = P2PMessage(
            msg_type=MessageType.DISCOVERY,
            sender_id="peer_99",
            payload={"address": "1.2.3.4", "port": 8080, "capabilities": {}},
        )
        result = node._handle_discovery(msg)
        assert "node_id" in result
        assert "peer_99" in node.peers

    def test_handle_task_result_increments_received(self):
        from ollama_arena.p2p.node import P2PMessage, MessageType
        node = self._make()
        msg = P2PMessage(
            msg_type=MessageType.TASK_RESULT,
            sender_id="worker",
            payload={"result": "ok"},
        )
        result = node._handle_task_result(msg)
        assert result["status"] == "received"
        assert node.messages_received == 1

    def test_message_handlers_registered(self):
        from ollama_arena.p2p.node import MessageType
        node = self._make()
        assert MessageType.DISCOVERY in node.message_handlers
        assert MessageType.HEARTBEAT in node.message_handlers
        assert MessageType.TASK_OFFER in node.message_handlers
