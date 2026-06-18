"""Cryptographic Proof of Evaluation system.

This module implements cryptographic signing of evaluation results,
Zero-Knowledge Proofs for verification, and blockchain anchoring
for immutable leaderboard records.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import secrets

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    import base58
    BASE58_AVAILABLE = True
except ImportError:
    BASE58_AVAILABLE = False


@dataclass
class ResultSignature:
    """Cryptographic signature of an evaluation result."""
    node_id: str
    task_id: str
    signature: str
    public_key: str
    timestamp: float
    algorithm: str = "ed25519"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "task_id": self.task_id,
            "signature": self.signature,
            "public_key": self.public_key,
            "timestamp": self.timestamp,
            "algorithm": self.algorithm,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultSignature":
        """Create from dictionary."""
        return cls(
            node_id=data["node_id"],
            task_id=data["task_id"],
            signature=data["signature"],
            public_key=data["public_key"],
            timestamp=data["timestamp"],
            algorithm=data.get("algorithm", "ed25519"),
        )


@dataclass
class HardwareAttestation:
    """Attestation of hardware used for evaluation."""
    cpu_signature: str
    memory_signature: str
    gpu_signature: Optional[str] = None
    platform_info: Dict[str, Any] = field(default_factory=dict)
    network_isolated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cpu_signature": self.cpu_signature,
            "memory_signature": self.memory_signature,
            "gpu_signature": self.gpu_signature,
            "platform_info": self.platform_info,
            "network_isolated": self.network_isolated,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardwareAttestation":
        """Create from dictionary."""
        return cls(
            cpu_signature=data["cpu_signature"],
            memory_signature=data["memory_signature"],
            gpu_signature=data.get("gpu_signature"),
            platform_info=data.get("platform_info", {}),
            network_isolated=data.get("network_isolated", False),
        )


@dataclass
class ZeroKnowledgeProof:
    """Zero-Knowledge Proof for result verification."""
    proof_type: str  # "range_proof", "membership_proof", "execution_proof"
    proof_data: Dict[str, Any]
    verification_key: str
    challenge: str
    response: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proof_type": self.proof_type,
            "proof_data": self.proof_data,
            "verification_key": self.verification_key,
            "challenge": self.challenge,
            "response": self.response,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZeroKnowledgeProof":
        """Create from dictionary."""
        return cls(
            proof_type=data["proof_type"],
            proof_data=data["proof_data"],
            verification_key=data["verification_key"],
            challenge=data["challenge"],
            response=data["response"],
        )


@dataclass
class BlockchainAnchor:
    """Blockchain anchoring for immutable records."""
    transaction_hash: str
    block_height: int
    block_hash: str
    timestamp: float
    network: str = "ethereum"  # or "bitcoin", "custom"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transaction_hash": self.transaction_hash,
            "block_height": self.block_height,
            "block_hash": self.block_hash,
            "timestamp": self.timestamp,
            "network": self.network,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlockchainAnchor":
        """Create from dictionary."""
        return cls(
            transaction_hash=data["transaction_hash"],
            block_height=data["block_height"],
            block_hash=data["block_hash"],
            timestamp=data["timestamp"],
            network=data.get("network", "ethereum"),
        )


class KeyPair:
    """Ed25519 key pair for signing."""
    
    def __init__(self):
        """Generate new key pair."""
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required")
        
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
    
    def get_private_key_bytes(self) -> bytes:
        """Get private key as bytes."""
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def get_public_key_bytes(self) -> bytes:
        """Get public key as bytes."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def get_public_key_hex(self) -> str:
        """Get public key as hex string."""
        return self.get_public_key_bytes().hex()
    
    def get_public_key_base58(self) -> str:
        """Get public key as base58 string."""
        if BASE58_AVAILABLE:
            return base58.b58encode(self.get_public_key_bytes()).decode()
        return self.get_public_key_hex()


class CryptoProofGenerator:
    """Generator for cryptographic proofs of evaluation."""
    
    def __init__(self, node_id: str):
        """
        Initialize proof generator.
        
        Args:
            node_id: Node identifier
        """
        self.node_id = node_id
        self.key_pair = KeyPair()
        self.hardware_attestation = self._generate_hardware_attestation()
    
    def _generate_hardware_attestation(self) -> HardwareAttestation:
        """Generate hardware attestation signature."""
        import platform
        
        # Create signature based on system info
        system_info = {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
        
        cpu_sig = hashlib.sha256(
            json.dumps(system_info, sort_keys=True).encode()
        ).hexdigest()[:32]
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_sig = hashlib.sha256(
                f"{memory.total}-{memory.available}".encode()
            ).hexdigest()[:32]
        except ImportError:
            memory_sig = hashlib.sha256(b"unknown_memory").hexdigest()[:32]
        
        # GPU signature (if available)
        gpu_sig = None
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_info = f"{gpus[0].name}-{gpus[0].memoryTotal}"
                gpu_sig = hashlib.sha256(gpu_info.encode()).hexdigest()[:32]
        except ImportError:
            pass
        
        return HardwareAttestation(
            cpu_signature=cpu_sig,
            memory_signature=memory_sig,
            gpu_signature=gpu_sig,
            platform_info=system_info,
        )
    
    def sign_result(self, task_id: str, result: Dict[str, Any]) -> ResultSignature:
        """
        Cryptographically sign an evaluation result.
        
        Args:
            task_id: Task identifier
            result: Result data to sign
        
        Returns:
            Result signature
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required")
        
        # Create canonical hash of result
        result_hash = self._hash_result(result)
        
        # Sign the hash
        signature = self.key_pair.private_key.sign(result_hash)
        
        return ResultSignature(
            node_id=self.node_id,
            task_id=task_id,
            signature=signature.hex(),
            public_key=self.key_pair.get_public_key_hex(),
            timestamp=time.time(),
        )
    
    def _hash_result(self, result: Dict[str, Any]) -> bytes:
        """Create cryptographic hash of result."""
        canonical = json.dumps(result, sort_keys=True)
        return hashlib.sha256(canonical.encode()).digest()
    
    def verify_signature(
        self,
        signature: ResultSignature,
        result: Dict[str, Any],
    ) -> bool:
        """
        Verify a result signature.
        
        Args:
            signature: Result signature to verify
            result: Result data
        
        Returns:
            True if signature is valid
        """
        if not CRYPTO_AVAILABLE:
            return False
        
        try:
            # Recreate result hash
            result_hash = self._hash_result(result)
            
            # Reconstruct public key
            pub_key = ed25519.Ed25519PublicKey.from_bytes(
                bytes.fromhex(signature.public_key)
            )
            
            # Verify signature
            pub_key.verify(
                bytes.fromhex(signature.signature),
                result_hash
            )
            
            return True
        except Exception:
            return False
    
    def generate_execution_proof(
        self,
        task_id: str,
        execution_trace: List[Dict[str, Any]],
    ) -> ZeroKnowledgeProof:
        """
        Generate Zero-Knowledge Proof of execution.
        
        This is a simplified implementation. In production, use
        a proper ZK system like zk-SNARKs or Bulletproofs.
        
        Args:
            task_id: Task identifier
            execution_trace: Trace of execution steps
        
        Returns:
            ZK proof of execution
        """
        # Create challenge
        challenge = secrets.token_hex(32)
        
        # Create proof data (simplified)
        trace_hash = hashlib.sha256(
            json.dumps(execution_trace, sort_keys=True).encode()
        ).hexdigest()
        
        proof_data = {
            "task_id": task_id,
            "trace_hash": trace_hash,
            "step_count": len(execution_trace),
            "hardware_attestation": self.hardware_attestation.to_dict(),
        }
        
        # Create response (simplified commitment)
        commitment = hashlib.sha256(
            f"{challenge}-{trace_hash}".encode()
        ).hexdigest()
        
        return ZeroKnowledgeProof(
            proof_type="execution_proof",
            proof_data=proof_data,
            verification_key=self.key_pair.get_public_key_hex(),
            challenge=challenge,
            response=commitment,
        )
    
    def verify_execution_proof(self, proof: ZeroKnowledgeProof) -> bool:
        """
        Verify a Zero-Knowledge Proof of execution.
        
        Args:
            proof: ZK proof to verify
        
        Returns:
            True if proof is valid
        """
        # Recompute commitment
        trace_hash = proof.proof_data.get("trace_hash", "")
        expected_commitment = hashlib.sha256(
            f"{proof.challenge}-{trace_hash}".encode()
        ).hexdigest()
        
        return proof.response == expected_commitment
    
    def create_proof_bundle(
        self,
        task_id: str,
        result: Dict[str, Any],
        execution_trace: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a complete proof bundle for a result.
        
        Args:
            task_id: Task identifier
            result: Result data
            execution_trace: Optional execution trace
        
        Returns:
            Complete proof bundle
        """
        signature = self.sign_result(task_id, result)
        
        zk_proof = None
        if execution_trace:
            zk_proof = self.generate_execution_proof(task_id, execution_trace)
        
        bundle = {
            "task_id": task_id,
            "result": result,
            "signature": signature.to_dict(),
            "hardware_attestation": self.hardware_attestation.to_dict(),
            "timestamp": time.time(),
        }
        
        if zk_proof:
            bundle["zk_proof"] = zk_proof.to_dict()
        
        return bundle
    
    def verify_proof_bundle(self, bundle: Dict[str, Any]) -> tuple[bool, str]:
        """
        Verify a complete proof bundle.
        
        Args:
            bundle: Proof bundle to verify
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check signature
        signature_data = bundle.get("signature", {})
        if not signature_data:
            return False, "missing_signature"
        
        signature = ResultSignature.from_dict(signature_data)
        result = bundle.get("result", {})
        
        if not self.verify_signature(signature, result):
            return False, "invalid_signature"
        
        # Check node ID match
        if signature.node_id != self.node_id:
            return False, "node_id_mismatch"
        
        # Verify ZK proof if present
        zk_proof_data = bundle.get("zk_proof")
        if zk_proof_data:
            zk_proof = ZeroKnowledgeProof.from_dict(zk_proof_data)
            if not self.verify_execution_proof(zk_proof):
                return False, "invalid_zk_proof"
        
        return True, "valid"


class BlockchainAnchorer:
    """Blockchain anchoring for immutable record keeping."""
    
    def __init__(self, network: str = "ethereum"):
        """
        Initialize blockchain anchorer.
        
        Args:
            network: Blockchain network to use
        """
        self.network = network
        self.pending_anchors: List[Dict[str, Any]] = []
    
    def create_anchor_hash(
        self,
        record: Dict[str, Any],
    ) -> str:
        """
        Create hash for blockchain anchoring.
        
        Args:
            record: Record to anchor
        
        Returns:
            Anchor hash
        """
        canonical = json.dumps(record, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def anchor_to_blockchain(
        self,
        proof_bundle: Dict[str, Any],
    ) -> Optional[BlockchainAnchor]:
        """
        Anchor a proof bundle to blockchain.
        
        This is a simplified implementation. In production, integrate
        with actual blockchain infrastructure (Ethereum, Bitcoin, etc.)
        
        Args:
            proof_bundle: Proof bundle to anchor
        
        Returns:
            Blockchain anchor or None if failed
        """
        # Create anchor hash
        anchor_hash = self.create_anchor_hash(proof_bundle)
        
        # In production, submit transaction to actual blockchain
        # For now, simulate anchoring
        simulated_tx_hash = hashlib.sha256(
            f"{anchor_hash}-{time.time()}".encode()
        ).hexdigest()
        
        anchor = BlockchainAnchor(
            transaction_hash=simulated_tx_hash,
            block_height=0,  # Would be actual block height
            block_hash="0000000000000000000000000000000000000000000000000000000000000000",
            timestamp=time.time(),
            network=self.network,
        )
        
        return anchor
    
    def verify_anchor(
        self,
        proof_bundle: Dict[str, Any],
        anchor: BlockchainAnchor,
    ) -> bool:
        """
        Verify blockchain anchor.
        
        Args:
            proof_bundle: Original proof bundle
            anchor: Blockchain anchor to verify
        
        Returns:
            True if anchor is valid
        """
        # Recreate anchor hash
        expected_hash = self.create_anchor_hash(proof_bundle)
        
        # In production, verify against actual blockchain
        # For simulation, just check format
        return len(anchor.transaction_hash) == 64
    
    def get_anchor_status(self, tx_hash: str) -> str:
        """
        Get status of blockchain transaction.
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            Status string (pending, confirmed, failed)
        """
        # In production, query blockchain for actual status
        return "simulated"


class ProofValidator:
    """Validator for cryptographic proofs."""
    
    def __init__(self):
        """Initialize proof validator."""
        self.known_public_keys: Dict[str, str] = {}  # node_id -> public_key
    
    def register_public_key(self, node_id: str, public_key: str) -> None:
        """Register a node's public key."""
        self.known_public_keys[node_id] = public_key
    
    def validate_proof_bundle(self, bundle: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a complete proof bundle.
        
        Args:
            bundle: Proof bundle to validate
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        required_fields = ["task_id", "result", "signature", "hardware_attestation"]
        for field in required_fields:
            if field not in bundle:
                errors.append(f"missing_field_{field}")
        
        if errors:
            return False, errors
        
        # Validate signature
        signature_data = bundle["signature"]
        if not isinstance(signature_data, dict):
            errors.append("invalid_signature_format")
            return False, errors
        
        # Check if public key is registered
        node_id = signature_data.get("node_id")
        public_key = signature_data.get("public_key")
        
        if node_id in self.known_public_keys:
            if self.known_public_keys[node_id] != public_key:
                errors.append("public_key_mismatch")
        
        # Validate hardware attestation
        hw_attestation = bundle.get("hardware_attestation", {})
        if not hw_attestation.get("cpu_signature"):
            errors.append("missing_cpu_signature")
        
        # Check timestamp is recent
        timestamp = bundle.get("timestamp", 0)
        if time.time() - timestamp > 3600:  # 1 hour old
            errors.append("timestamp_too_old")
        
        return len(errors) == 0, errors
