# ADR 010: Cryptographic Proof of Evaluation

## Status
Proposed (2026-06-18)

## Context
The Global P2P Grid in v3.0.0 introduces significant trust challenges:

1. **Result Integrity**: How do we know a P2P node reported honest results?
2. **Privacy Protection**: How do we verify without exposing proprietary prompts?
3. **Vendor Trust**: How do vendors protect against false accusations?
4. **Immutability**: How do we ensure leaderboard can't be manipulated retroactively?
5. **Reproducibility**: How do we prove a model actually ran on specific hardware?

Existing centralized trust model is insufficient for:
- Decentralized P2P networks with unknown participants
- Competitive vendors who may manipulate results
- High-value evaluations requiring strong guarantees

## Decision

### Cryptographic Proof Architecture

**Multi-Layer Verification**:
1. **Result Signing**: Cryptographic signatures of model outputs
2. **Zero-Knowledge Proofs**: Verify execution without revealing inputs
3. **Hardware Attestation**: Prove execution environment constraints
4. **Blockchain Anchoring**: Immutable ledger for all results

### Layer 1: Result Signing

**Digital Signatures**:
- Each result signed by evaluator node's private key
- Includes: model ID, task hash, output hash, timestamp, hardware signature
- Signature verification on result receipt
- Node reputation tied to key identity

**Signature Format**:
```json
{
  "result_id": "uuid",
  "timestamp": "ISO8601",
  "model_id": "llama3.3:70b",
  "task_hash": "SHA256(task_definition)",
  "output_hash": "SHA256(model_output)",
  "hardware_sig": "TPM/Hardware attestation",
  "node_signature": "ECDSA(P-256)"
}
```

### Layer 2: Zero-Knowledge Proofs

**ZK-SNARKs for Execution Verification**:
- Prove: "Model M on task T produced output O in time < S without internet access"
- Without revealing: T, O, or intermediate computations
- Verification time: <1 second
- Proof size: <1KB

**Circuit Design**:
```
Input: (model_hash, task_hash, output_hash, time_bound, network_proof)
Circuit verifies:
1. Model execution completes within time_bound
2. No network packets sent/received (network_proof)
3. Output hash matches model execution on task hash
4. Hardware constraints satisfied
Output: true/false
```

**Privacy Protection**:
- Benchmark owners can verify results without exposing prompts
- Vendors can prove performance without revealing model internals
- Evaluators can prove honesty without revealing proprietary data

### Layer 3: Hardware Attestation

**Trusted Platform Module (TPM)**:
- Attest to hardware configuration
- Prove no internet access during evaluation
- Verify GPU model and driver version
- Measure runtime integrity

**Attestation Flow**:
1. TPM generates attestation certificate
2. Includes: CPUID, GPU signature, network state, memory state
3. Signed by TPM's Endorsement Key
4. Included in ZK proof circuit
5. Verifier checks attestation chain

**Network Isolation Proof**:
- eBPF programs monitor network stack
- Record packet counts (should be 0)
- TPM attests to eBPF program integrity
- Included in execution proof

### Layer 4: Blockchain Anchoring

**Immutable Ledger**:
- All verified results anchored to public blockchain
- Merkle tree structure for efficient verification
- Smart contract for result validation
- Periodic checkpoint commitments

**Blockchain Choice**: Ethereum L2 (Optimism/Arbitrum)
- Low gas fees for frequent operations
- EVM compatibility for smart contracts
- Strong security guarantees
- Decentralized validation

**Smart Contract Interface**:
```solidity
contract ArenaLeaderboard {
    struct Result {
        bytes32 resultHash;
        bytes32 modelHash;
        bytes32 taskHash;
        uint256 score;
        bytes zkProof;
        uint256 timestamp;
        address submitter;
    }
    
    function submitResult(Result calldata result, bytes calldata signature) external;
    function verifyResult(bytes32 resultHash, bytes calldata zkProof) public view returns (bool);
    function getModelScore(bytes32 modelHash) public view returns (uint256);
}
```

### Proof Generation Flow

**Evaluator Node**:
1. Receive task assignment (encrypted)
2. Execute model in isolated sandbox
3. Collect telemetry and hardware attestation
4. Generate ZK proof of execution
5. Sign result with node key
6. Submit to P2P network

**Verifier Node**:
1. Receive result submission
2. Verify node signature
3. Verify ZK proof (circuit verification)
4. Verify hardware attestation
5. Check blockchain for previous results
6. If valid, anchor to blockchain
7. Update local leaderboard state

### Privacy Controls

**Data Classification**:
- **Public**: Model IDs, scores, timestamps
- **Protected**: Task definitions, model outputs (protected by ZK)
- **Private**: Evaluator identities (optional anonymity)

**Anonymous Submission**:
- Nodes can submit via mixnet
- ZK proofs hide task/output specifics
- Only aggregate statistics visible publicly

**Benchmark Protection**:
- Benchmark owners control decryption keys
- Results verifiable without prompt exposure
- Selective disclosure for audit

### Implementation

**File Structure**:
```
ollama_arena/p2p/
├── crypto_proof.py       # Main proof orchestration
├── signing.py            # Digital signature operations
├── zk_proof.py           # ZK-SNARK circuit operations
├── attestation.py        # TPM/hardware attestation
├── blockchain.py         # Blockchain integration
└── circuits/
    ├── execution.circom  # ZK circuit definition
    └── verification.sol  # Solidity verifier contract
```

**Key Components**:

1. **ProofGenerator**: Creates ZK proofs from execution traces
2. **ProofVerifier**: Validates submitted proofs
3. **AttestationCollector**: Gathers hardware attestations
4. **BlockchainAnchor**: Manages blockchain interactions
5. **SignatureManager**: Handles key management and signing

**Dependencies**:
- circom: ZK circuit compiler
- snarkjs: ZK proof generation/verification
- libtpm: TPM interface
- web3.py: Ethereum blockchain interaction

### Performance Considerations

**Proof Generation Time**:
- Target: <30 seconds for typical evaluation
- Optimization: Pre-computed setup parameters
- Parallelization: Multi-threaded witness computation

**Proof Verification Time**:
- Target: <1 second per result
- Optimization: On-chain verifier for batch verification
- Caching: Verification results for repeated checks

**Storage Requirements**:
- ZK proofs: ~1KB per result
- Attestations: ~5KB per result
- Blockchain cost: ~$0.01 per result (L2)

## Alternatives Considered

**Alternative 1: Simple Cryptographic Signatures**
- Pros: Simple, fast, low overhead
- Cons: No privacy protection, no execution verification, easy to fake

**Alternative 2: Trusted Execution Environments (TEE)**
- Pros: Strong hardware-based isolation
- Cons: Hardware dependencies, limited availability, potential vulnerabilities

**Alternative 3: Full Transparency**
- Pros: Simple verification, maximum accountability
- Cons: Leaks proprietary prompts and models, privacy concerns

**Alternative 4: Proof-of-Work**
- Pros: Decentralized, no cryptography expertise needed
- Cons: Wasteful, slow, doesn't prove execution correctness

**Chosen Approach**: ZK-SNARKs + blockchain provides strong verification with privacy protection and reasonable performance.

## Consequences

**Positive**:
- Strong cryptographic guarantees prevent fraud
- Privacy protection for benchmarks and models
- Immutable blockchain prevents manipulation
- Vendor protection against false accusations
- Enables trustless P2P evaluation

**Negative**:
- Significant implementation complexity
- ZK proof generation computational overhead
- Blockchain transaction costs (even on L2)
- Requires cryptographic expertise
- TPM hardware requirements

**Risks**:
- ZK circuit vulnerabilities
- TPM compatibility issues
- Blockchain dependency and costs
- Regulatory concerns (blockchain in some jurisdictions)
- Performance bottlenecks in proof generation

## Security Considerations

**ZK Circuit Security**:
- Formal verification of circuit correctness
- Regular audits by cryptography experts
- Bug bounty program for vulnerability discovery
- Backup verification mechanisms

**Key Management**:
- Secure key generation and storage
- Key rotation policies
- Recovery mechanisms for lost keys
- HSM integration for production use

**Blockchain Security**:
- Smart contract audits
- Upgradeable contract patterns
- Multisig control for contract upgrades
- Insurance for smart contract failures

## Implementation Timeline

**Phase 1** (Q3 2026):
- Basic result signing implementation
- Simple ZK circuit for execution
- Hardware attestation prototype

**Phase 2** (Q4 2026):
- Complete ZK proof system
- Blockchain smart contract
- Privacy controls implementation

**Phase 3** (Q1 2027):
- P2P network integration
- Performance optimization
- Production hardening

## References
- [v3.0.0 Roadmap](../v3.0.0-roadmap.md)
- [ADR 007: v3.0.0 Architecture](./007-v3.0.0-apex-evolution-architecture.md)
- ZK-SNARKs: https://zkp.science/
- circom: https://docs.circom.io/
- TPM 2.0 Specification: https://trustedcomputinggroup.org/