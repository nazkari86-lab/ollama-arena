# ADR 009: VM Sandbox Security Isolation

## Status
Proposed (2026-06-18)

## Context
Deep agentic evaluation in v3.0.0 requires executing untrusted AI-generated code for long-duration tasks (1-8 hours). This introduces significant security risks:

1. **Code Execution**: Models may generate malicious code
2. **Network Access**: Code may attempt external connections
3. **Resource Exhaustion**: Unbounded resource consumption
4. **Data Exfiltration**: Sensitive data may leak through side channels
5. **Persistence**: Malware may attempt to survive sandbox termination

Existing Docker container isolation (v2.5.0) is insufficient for:
- Long-running tasks with higher attack surface
- Untrusted model outputs requiring stronger isolation
- Multi-tenant P2P environments requiring strict boundaries

## Decision

### Technology Choice: KubeVirt + Firecracker

**KubeVirt**: Kubernetes API for managing VMs
- Seamless integration with existing K8s infrastructure
- Declarative VM management
- Scalable orchestration

**Firecracker**: Lightweight microVMs from AWS
- <125ms startup time
- Minimal resource overhead
- Strong isolation via Linux KVM

### Isolation Layers

**Layer 1: Hardware Virtualization (KVM)**
- CPU virtualization with separate virtual CPUs
- Memory isolation via EPT/NPT
- I/O device emulation and passthrough

**Layer 2: MicroVM Isolation (Firecracker)**
- Separate kernel per sandbox
- Minimal attack surface (only necessary devices)
- No shell or network by default

**Layer 3: Network Isolation**
- Default deny all network traffic
- Whitelist-based outbound rules (if needed)
- Separate bridge per tenant
- DNS filtering

**Layer 4: Resource Constraints**
- CPU quotas and limits
- Memory limits with OOM handling
- Disk quotas and IOPS limits
- GPU access control (if applicable)

**Layer 5: Filesystem Isolation**
- Separate filesystem per sandbox
- No host filesystem access
- Ephemeral storage (wiped on termination)
- Read-only base image with writable overlay

**Layer 6: Time Limitation**
- Hard timeout enforcement
- CPU time accounting
- Wall-clock time limits
- Pre-kill checkpointing

### Security Controls

**Code Execution Controls**:
```yaml
execution_policy:
  allowed_languages: ["python", "javascript", "rust"]
  max_processes: 100
  max_threads: 1000
  forbidden_syscalls: ["ptrace", "process_vm_readv"]
  network_access: false
  filesystem_access: "ephemeral_only"
```

**Network Controls**:
```yaml
network_policy:
  outbound:
    - allowed: false
    - exceptions:
        - domain: "pypi.org"
          purpose: "package_installation"
          rate_limit: "10 req/min"
  inbound: false
  dns:
    - filter: "malicious_domains.txt"
```

**Resource Limits**:
```yaml
resources:
  cpu:
    limit: "4"
    request: "1"
  memory:
    limit: "16Gi"
    request: "2Gi"
  disk:
    limit: "100Gi"
    iops: 1000
  timeout:
    wall: "8h"
    cpu: "24h"
```

### Checkpoint/Resume

**Snapshots**:
- Periodic checkpointing (every 15 minutes)
- Pre-kill checkpoint on timeout
- Incremental snapshot storage
- Compression for space efficiency

**Resume Process**:
1. Load latest snapshot
2. Restore memory state
3. Restart processes from checkpoint
4. Continue evaluation from resume point

### Monitoring and Auditing

**Security Events**:
- Syscall violations
- Network access attempts
- Resource limit violations
- Filesystem access violations
- Unexpected process creation

**Audit Logging**:
```json
{
  "event_type": "security_violation",
  "timestamp": "ISO8601",
  "sandbox_id": "uuid",
  "violation_type": "syscall_denied",
  "details": {
    "syscall": "ptrace",
    "pid": 12345,
    "arguments": [...]
  }
}
```

### Implementation

**File Structure**:
```
ollama_arena/agentic/
├── sandbox.py           # Main sandbox manager
├── firecracker.py       # Firecracker integration
├── kubevirt.py          # KubeVirt orchestration
├── security.py          # Security policy engine
├── monitoring.py        # Event monitoring
└── policies/
    ├── default.yaml     # Default security policy
    ├── strict.yaml      # High-security policy
    └── permissive.yaml  # Development policy
```

**Key Components**:

1. **SandboxManager**: Lifecycle management (create, start, stop, snapshot)
2. **SecurityPolicy**: Policy definition and enforcement
3. **FirecrackerBackend**: MicroVM creation and management
4. **KubeVirtOrchestrator**: Kubernetes integration
5. **SecurityMonitor**: Real-time threat detection

### P2P Considerations

**Untrusted Environments**:
- Assume P2P nodes may be malicious
- Verify sandbox integrity before accepting results
- Rate limit sandbox creation per node
- Reputation system for sandbox reliability

**Result Verification**:
- Cryptographic proof of sandbox execution
- Attestation of security policy compliance
- Reproducibility checks for critical results

## Alternatives Considered

**Alternative 1: Enhanced Docker**
- Pros: Simpler, faster, familiar
- Cons: Weaker isolation, shared kernel, cgroup escape vectors

**Alternative 2: gVisor**
- Pros: Stronger than Docker, faster than VMs
- Cons: Limited syscall coverage, compatibility issues

**Alternative 3: Full VMs (QEMU/KVM)**
- Pros: Strong isolation, full OS support
- Cons: Heavy resource usage, slow startup (>1 minute)

**Alternative 4: AWS Lambda Functions**
- Pros: Managed, scalable
- Cons: Vendor lock-in, limited control, cold starts

**Chosen Approach**: KubeVirt + Firecracker provides the best balance of isolation, performance, and manageability for our use case.

## Consequences

**Positive**:
- Strong isolation suitable for untrusted code
- Fast startup for agile evaluation
- Scalable orchestration via Kubernetes
- Checkpoint/resume for long tasks

**Negative**:
- Significant infrastructure complexity
- Requires K8s expertise for deployment
- Resource overhead per sandbox
- Storage requirements for snapshots

**Risks**:
- KubeVirt learning curve
- Firecracker platform compatibility
- Snapshot storage growth
- P2P node resource requirements

## Security Considerations

**Remaining Attack Vectors**:
- Side-channel attacks (timing, cache)
- Speculative execution vulnerabilities
- Hardware bugs (Spectre, Meltdown variants)
- Host kernel exploits

**Mitigations**:
- Regular host kernel updates
- CPU microcode updates
- Side-channel resistant algorithms
- Hardware vulnerability scanning

## Implementation Timeline

**Phase 1** (Q3 2026):
- Basic Firecracker integration
- Core security policies
- Simple lifecycle management

**Phase 2** (Q4 2026):
- KubeVirt orchestration
- Advanced security controls
- Checkpoint/resume implementation

**Phase 3** (Q1 2027):
- P2P integration
- Result verification
- Security hardening

## References
- [v3.0.0 Roadmap](../v3.0.0-roadmap.md)
- [ADR 007: v3.0.0 Architecture](./007-v3.0.0-apex-evolution-architecture.md)
- KubeVirt: https://kubevirt.io/
- Firecracker: https://firecracker-microvm.github.io/
- seccomp: https://man7.org/linux/man-pages/man2/seccomp.2.html