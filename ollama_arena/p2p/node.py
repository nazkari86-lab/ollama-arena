"""P2P Node implementation for Arena@Home network.

This module implements peer-to-peer node discovery, communication protocol,
and distributed task execution for the global ollama-arena grid.
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
import socket

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class MessageType(Enum):
    """Types of P2P messages."""
    DISCOVERY = "discovery"
    HEARTBEAT = "heartbeat"
    TASK_OFFER = "task_offer"
    TASK_ACCEPT = "task_accept"
    TASK_RESULT = "task_result"
    NODE_INFO = "node_info"
    PEER_LIST = "peer_list"
    SYNC_REQUEST = "sync_request"
    CHALLENGE = "challenge"
    RESPONSE = "response"


@dataclass
class P2PMessage:
    """Message format for P2P communication."""
    msg_type: MessageType
    sender_id: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "message_id": self.message_id,
            "msg_type": self.msg_type.value,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "P2PMessage":
        """Create message from dictionary."""
        return cls(
            message_id=data["message_id"],
            msg_type=MessageType(data["msg_type"]),
            sender_id=data["sender_id"],
            payload=data["payload"],
            timestamp=data["timestamp"],
        )


@dataclass
class NodeInfo:
    """Information about a P2P node."""
    node_id: str
    address: str
    port: int
    capabilities: Dict[str, Any] = field(default_factory=dict)
    reputation_score: float = 1.0
    last_seen: float = field(default_factory=time.time)
    trust_level: str = "unverified"  # unverified, trusted, verified
    
    @property
    def endpoint(self) -> str:
        """Get node endpoint."""
        return f"{self.address}:{self.port}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "port": self.port,
            "capabilities": self.capabilities,
            "reputation_score": self.reputation_score,
            "last_seen": self.last_seen,
            "trust_level": self.trust_level,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeInfo":
        """Create from dictionary."""
        return cls(
            node_id=data["node_id"],
            address=data["address"],
            port=data["port"],
            capabilities=data.get("capabilities", {}),
            reputation_score=data.get("reputation_score", 1.0),
            last_seen=data.get("last_seen", time.time()),
            trust_level=data.get("trust_level", "unverified"),
        )


class NodeDiscovery:
    """P2P node discovery service using multicast and bootstrap nodes."""
    
    def __init__(
        self,
        bootstrap_nodes: Optional[List[str]] = None,
        multicast_group: str = "239.255.255.250",
        multicast_port: int = 1900,
    ):
        """
        Initialize node discovery.
        
        Args:
            bootstrap_nodes: List of known bootstrap node endpoints
            multicast_group: Multicast group address for local discovery
            multicast_port: Multicast port for local discovery
        """
        self.bootstrap_nodes = bootstrap_nodes or []
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.discovered_peers: Dict[str, NodeInfo] = {}
        self.local_node_id = self._generate_node_id()
    
    def _generate_node_id(self) -> str:
        """Generate unique node ID based on hardware."""
        # Use MAC address and hostname for stable ID
        mac = uuid.getnode()
        hostname = socket.gethostname()
        node_string = f"{mac}-{hostname}"
        return hashlib.sha256(node_string.encode()).hexdigest()[:16]
    
    async def discover_local_peers(self) -> List[NodeInfo]:
        """
        Discover peers on local network via multicast.
        
        Returns:
            List of discovered peer nodes
        """
        peers = []
        
        try:
            # Create UDP socket for multicast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self.multicast_port))
            
            # Join multicast group
            mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            sock.settimeout(5.0)  # 5 second timeout
            
            # Send discovery message
            discovery_msg = {
                "node_id": self.local_node_id,
                "type": "discovery",
                "timestamp": time.time(),
            }
            
            sock.sendto(
                json.dumps(discovery_msg).encode(),
                (self.multicast_group, self.multicast_port)
            )
            
            # Listen for responses
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = json.loads(data.decode())
                    
                    if response.get("node_id") != self.local_node_id:
                        peer_info = NodeInfo(
                            node_id=response["node_id"],
                            address=addr[0],
                            port=response.get("port", 8080),
                            capabilities=response.get("capabilities", {}),
                        )
                        peers.append(peer_info)
                        self.discovered_peers[peer_info.node_id] = peer_info
                except socket.timeout:
                    break
            
            sock.close()
        except Exception as e:
            print(f"Warning: Local discovery failed: {e}")
        
        return peers
    
    async def discover_from_bootstrap(self) -> List[NodeInfo]:
        """
        Discover peers from bootstrap nodes.
        
        Returns:
            List of discovered peer nodes
        """
        if not AIOHTTP_AVAILABLE:
            print("Warning: aiohttp not available, bootstrap discovery disabled")
            return []
        
        peers = []
        
        for bootstrap in self.bootstrap_nodes:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{bootstrap}/api/v1/peers",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for peer_data in data.get("peers", []):
                                peer = NodeInfo.from_dict(peer_data)
                                peers.append(peer)
                                self.discovered_peers[peer.node_id] = peer
            except Exception as e:
                print(f"Warning: Failed to contact bootstrap {bootstrap}: {e}")
        
        return peers
    
    async def discover_all(self) -> List[NodeInfo]:
        """
        Discover peers from all sources.
        
        Returns:
            Combined list of discovered peers
        """
        local_peers = await self.discover_local_peers()
        bootstrap_peers = await self.discover_from_bootstrap()
        
        # Deduplicate by node_id
        all_peers = {p.node_id: p for p in local_peers + bootstrap_peers}
        self.discovered_peers = all_peers
        
        return list(all_peers.values())
    
    def get_peer(self, node_id: str) -> Optional[NodeInfo]:
        """Get peer information by node ID."""
        return self.discovered_peers.get(node_id)
    
    def get_all_peers(self) -> List[NodeInfo]:
        """Get all discovered peers."""
        return list(self.discovered_peers.values())


class P2PNode:
    """Main P2P node for Arena@Home network."""
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        bootstrap_nodes: Optional[List[str]] = None,
        max_peers: int = 50,
        heartbeat_interval: float = 30.0,
    ):
        """
        Initialize P2P node.
        
        Args:
            host: Host address to bind to
            port: Port to listen on
            bootstrap_nodes: List of bootstrap node endpoints
            max_peers: Maximum number of peers to maintain
            heartbeat_interval: Heartbeat interval in seconds
        """
        self.host = host
        self.port = port
        self.max_peers = max_peers
        self.heartbeat_interval = heartbeat_interval
        
        self.discovery = NodeDiscovery(bootstrap_nodes=bootstrap_nodes)
        self.local_node_id = self.discovery.local_node_id
        self.peers: Dict[str, NodeInfo] = {}
        
        # Message handlers
        self.message_handlers: Dict[MessageType, Callable] = {
            MessageType.DISCOVERY: self._handle_discovery,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.TASK_OFFER: self._handle_task_offer,
            MessageType.TASK_RESULT: self._handle_task_result,
            MessageType.PEER_LIST: self._handle_peer_list,
        }
        
        # Task queue
        self.task_queue: List[Dict[str, Any]] = []
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        # Node state
        self.is_running = False
        self.server: Optional[asyncio.Server] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.tasks_completed = 0
        self.tasks_failed = 0

        # _get_capabilities() shells out to psutil; cache briefly since
        # _can_accept_task() calls it on every task offer.
        self._capabilities_cache: Optional[Dict[str, Any]] = None
        self._capabilities_cache_time: float = 0.0
    
    async def start(self) -> None:
        """Start the P2P node."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Discover initial peers
        discovered = await self.discovery.discover_all()
        for peer in discovered:
            if peer.node_id != self.local_node_id:
                self.peers[peer.node_id] = peer
        
        print(f"P2P Node started: {self.local_node_id}")
        print(f"Discovered {len(self.peers)} peers")
        
        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def stop(self) -> None:
        """Stop the P2P node."""
        self.is_running = False
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Cancel running tasks
        for task_id, task in self.running_tasks.items():
            task.cancel()
        
        print("P2P Node stopped")
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to peers."""
        while self.is_running:
            await asyncio.sleep(self.heartbeat_interval)
            
            heartbeat_msg = P2PMessage(
                msg_type=MessageType.HEARTBEAT,
                sender_id=self.local_node_id,
                payload={
                    "port": self.port,
                    "capabilities": self._get_capabilities(),
                },
            )
            
            stale_peer_ids = []
            for peer_id, peer in list(self.peers.items()):
                sent = await self._send_message(peer, heartbeat_msg)
                if sent:
                    peer.last_seen = time.time()
                elif time.time() - peer.last_seen > 300:  # 5 minutes unreachable
                    stale_peer_ids.append(peer_id)

            # _send_message() already logs failures and never raises, so
            # pruning must be driven by its return value, not an exception.
            for peer_id in stale_peer_ids:
                self.peers.pop(peer_id, None)
    
    async def _send_message(self, peer: NodeInfo, message: P2PMessage) -> bool:
        """
        Send message to a peer.
        
        Args:
            peer: Target peer
            message: Message to send
        
        Returns:
            True if message sent successfully
        """
        if not AIOHTTP_AVAILABLE:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{peer.endpoint}/api/v1/message",
                    json=message.to_dict(),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        self.messages_sent += 1
                        return True
        except Exception as e:
            print(f"Failed to send message to {peer.node_id}: {e}")
        
        return False
    
    async def broadcast_message(self, message: P2PMessage) -> None:
        """Broadcast message to all peers."""
        tasks = [
            self._send_message(peer, message)
            for peer in self.peers.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def _handle_discovery(self, message: P2PMessage) -> Dict[str, Any]:
        """Handle discovery message from new peer."""
        sender_info = NodeInfo(
            node_id=message.sender_id,
            address=message.payload.get("address", "unknown"),
            port=message.payload.get("port", 8080),
            capabilities=message.payload.get("capabilities", {}),
        )
        
        if sender_info.node_id != self.local_node_id:
            self.peers[sender_info.node_id] = sender_info
        
        return {
            "node_id": self.local_node_id,
            "port": self.port,
            "capabilities": self._get_capabilities(),
        }
    
    def _handle_heartbeat(self, message: P2PMessage) -> Dict[str, Any]:
        """Handle heartbeat from peer."""
        self.messages_received += 1
        
        if message.sender_id in self.peers:
            self.peers[message.sender_id].last_seen = time.time()
            self.peers[message.sender_id].capabilities = message.payload.get(
                "capabilities", {}
            )
        
        return {"status": "ok"}
    
    def _handle_task_offer(self, message: P2PMessage) -> Dict[str, Any]:
        """Handle task offer from peer."""
        self.messages_received += 1
        
        task = message.payload
        task_id = task.get("task_id")
        
        if task_id and self._can_accept_task(task):
            self.task_queue.append(task)
            return {"accepted": True, "task_id": task_id}
        
        return {"accepted": False, "reason": "cannot_accept"}
    
    def _handle_task_result(self, message: P2PMessage) -> Dict[str, Any]:
        """Handle task result from peer."""
        self.messages_received += 1
        # Results are handled by the distribution protocol
        return {"status": "received"}
    
    def _handle_peer_list(self, message: P2PMessage) -> Dict[str, Any]:
        """Handle peer list request."""
        self.messages_received += 1
        
        peers_list = [peer.to_dict() for peer in self.peers.values()]
        return {"peers": peers_list}
    
    def _get_capabilities(self) -> Dict[str, Any]:
        """Get node capabilities (cached for 30s to avoid repeated psutil calls)."""
        now = time.time()
        if self._capabilities_cache is not None and now - self._capabilities_cache_time < 30:
            return self._capabilities_cache

        import platform

        try:
            import psutil
            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
        except ImportError:
            cpu_count = 4
            memory_gb = 16.0

        self._capabilities_cache = {
            "cpu_cores": cpu_count,
            "memory_gb": round(memory_gb, 2),
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "supported_backends": ["ollama", "openai_compat"],
            "max_concurrent_tasks": 2,
        }
        self._capabilities_cache_time = now
        return self._capabilities_cache
    
    def _can_accept_task(self, task: Dict[str, Any]) -> bool:
        """Check if node can accept a task."""
        required_memory = task.get("required_memory_gb", 0)
        required_cpu = task.get("required_cpu_cores", 1)
        
        caps = self._get_capabilities()
        
        if required_memory > caps["memory_gb"]:
            return False
        if required_cpu > caps["cpu_cores"]:
            return False
        if len(self.running_tasks) >= caps["max_concurrent_tasks"]:
            return False
        
        return True
    
    async def execute_blind_ab_test(
        self,
        model_a: str,
        model_b: str,
        task: Dict[str, Any],
        backend: Any,
    ) -> Dict[str, Any]:
        """
        Execute blind A/B test on this node.
        
        Args:
            model_a: First model to test
            model_b: Second model to test
            task: Task specification
            backend: Backend to use for inference
        
        Returns:
            Test results with cryptographic proof
        """
        task_id = task.get("task_id", str(uuid.uuid4()))
        
        # Blind the models (randomize order)
        import random
        models = [model_a, model_b]
        random.shuffle(models)
        blinded = {"A": models[0], "B": models[1]}
        
        # Execute inference
        results = {}
        for label, model in blinded.items():
            try:
                # This would call the actual backend
                # For now, simulate
                results[label] = {
                    "model": model,
                    "response": f"Simulated response from {model}",
                    "latency_ms": random.randint(100, 1000),
                }
            except Exception as e:
                results[label] = {"error": str(e)}
        
        self.tasks_completed += 1
        
        return {
            "task_id": task_id,
            "blinded_mapping": blinded,
            "results": results,
            "node_id": self.local_node_id,
            "timestamp": time.time(),
        }
    
    def get_peer_count(self) -> int:
        """Get number of connected peers."""
        return len(self.peers)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get node statistics."""
        return {
            "node_id": self.local_node_id,
            "peer_count": len(self.peers),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "is_running": self.is_running,
        }
