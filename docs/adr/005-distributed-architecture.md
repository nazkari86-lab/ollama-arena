# ADR 005: Distributed Architecture for Multi-Node Execution

## Status
Accepted

## Context
Ollama Arena originally operated as a single-node system, which limited scalability for large-scale evaluation and benchmarking. As the number of models and tasks grew, the single-node architecture became a bottleneck. The system needed to support:
- Horizontal scaling across multiple compute nodes
- Load balancing to distribute work efficiently
- Fault tolerance for node failures
- Health monitoring and automatic failover

## Decision
Implemented a comprehensive distributed architecture with the following components:

### 1. Node Management
- **Node Class**: Represents individual compute nodes with capabilities, state, and performance tracking
- **NodePool Class**: Thread-safe pool for node registration, health checking, and selection
- **Health Monitoring**: Automatic heartbeat-based health checks with state transitions

### 2. Load Balancing
- **Multiple Strategies**: Round-robin, least-loaded, random, affinity, and weighted balancing
- **Strategy Selection**: Pluggable strategy pattern for easy extension
- **Model-Aware Selection**: Nodes can declare supported models for affinity routing

### 3. Task Execution
- **DistributedExecutor**: Coordinates task distribution across nodes
- **Parallel Execution**: Thread pool-based parallel task execution
- **Fault Tolerance**: Automatic retry with node exclusion on failures
- **Result Collection**: Aggregation of results from multiple nodes

### Changes Made

**File:** `ollama_arena/distributed/__init__.py`
- Package initialization with public API exports

**File:** `ollama_arena/distributed/node.py`
- `Node` dataclass with capabilities, state, and performance tracking
- `NodeState` enum for node health states
- `NodeCapabilities` dataclass for compute resources
- Thread-safe operations with validation

**File:** `ollama_arena/distributed/pool.py`
- `NodePool` class for managing multiple nodes
- Node registration and unregistration
- Health checking with configurable intervals
- Statistics and utilization tracking
- Thread-safe operations with locking

**File:** `ollama_arena/distributed/balancer.py`
- `LoadBalancer` class with strategy delegation
- Five balancing strategies: RoundRobin, LeastLoaded, Random, Affinity, Weighted
- `BalancingResult` for decision metadata
- Extensible strategy pattern

**File:** `ollama_arena/distributed/executor.py`
- `DistributedExecutor` for task coordination
- `Task` and `TaskResult` dataclasses
- Parallel execution with configurable workers
- Retry logic with node exclusion
- Performance statistics tracking

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Arena / CLI                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              DistributedExecutor                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  LoadBalancer (Strategy: LeastLoaded)            │  │
│  │  - RoundRobin                                     │  │
│  │  - LeastLoaded                                    │  │
│  │  - Random                                         │  │
│  │  - Affinity (model-aware)                         │  │
│  │  - Weighted (capacity-based)                     │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    NodePool                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Node 1  │ │  Node 2  │ │  Node 3  │ │  Node N  │  │
│  │ ONLINE   │ │ BUSY     │ │ ONLINE   │ │ OFFLINE  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Consequences

### Positive
- **Scalability**: Horizontal scaling across unlimited compute nodes
- **Performance**: Parallel execution reduces total evaluation time
- **Fault Tolerance**: Automatic retry and node exclusion on failures
- **Flexibility**: Multiple load balancing strategies for different workloads
- **Resource Efficiency**: Model-aware routing reduces cold starts
- **Monitoring**: Comprehensive health checks and performance metrics

### Negative
- **Complexity**: Additional architectural layers increase system complexity
- **Network Dependency**: Requires reliable network between nodes
- **Synchronization Overhead**: Node pool operations require locking
- **Configuration Complexity**: Need to configure and manage multiple nodes
- **Testing Overhead**: More test scenarios needed for distributed behavior

## Integration Impact

### Backward Compatibility
The distributed architecture is opt-in. Single-node mode remains the default:
- `Arena` class works without distributed components
- Distributed execution requires explicit initialization of `NodePool` and `DistributedExecutor`
- No breaking changes to existing APIs

### Future Enhancements
- Add WebSocket support for real-time node communication
- Implement automatic node discovery via multicast/DNS
- Add support for Kubernetes deployment
- Implement result caching across nodes
- Add node authentication and TLS encryption

## Performance Characteristics

### Load Balancing Strategies

**Round-Robin:**
- Distribution: Even across nodes
- Overhead: Minimal (O(1) selection)
- Best for: Homogeneous nodes, equal task complexity

**Least-Loaded:**
- Distribution: Based on current utilization
- Overhead: Low (O(n) for n nodes)
- Best for: Heterogeneous nodes, varying task complexity

**Random:**
- Distribution: Probabilistic
- Overhead: Minimal (O(1) selection)
- Best for: Large node pools, avoiding synchronization

**Affinity:**
- Distribution: Model-specific with cache
- Overhead: Low (O(1) with cache hit)
- Best for: Model inference with warm-up cost

**Weighted:**
- Distribution: Based on node capacity
- Overhead: Medium (O(n) weight calculation)
- Best for: Nodes with different capabilities

### Scaling Characteristics
- Linear scalability with node count for embarrassingly parallel tasks
- Network latency adds ~10-50ms per task (depending on distance)
- Node pool operations: O(1) for registration, O(n) for health checks
- Thread pool overhead: ~1-2ms per task for context switching

## Usage Example

```python
from ollama_arena.distributed import Node, NodePool, LoadBalancer, DistributedExecutor, BalancingStrategy

# Create node pool
pool = NodePool()

# Register nodes
pool.register_node(Node(
    node_id="node-1",
    address="192.168.1.10",
    port=8080,
))

pool.register_node(Node(
    node_id="node-2",
    address="192.168.1.11",
    port=8080,
))

# Create load balancer
balancer = LoadBalancer(pool, strategy=BalancingStrategy.LEAST_LOADED)

# Create executor
executor = DistributedExecutor(pool, balancer)

# Execute tasks
tasks = [Task(task_id=str(i), model="llama3", ...) for i in range(100)]
results = executor.execute_tasks_parallel(tasks, max_workers=10)
```

## Alternatives Considered

1. **Single Node Scaling**: Rejected due to hardware limitations
2. **External Orchestrator (Kubernetes)**: Rejected due to complexity and dependencies
3. **Message Queue (RabbitMQ/Kafka)**: Rejected due to over-engineering for this use case
4. **gRPC instead of HTTP**: Rejected for simplicity and broader compatibility
5. **No Load Balancing**: Rejected due to inefficient resource utilization

## References
- Distributed architecture implementation in `ollama_arena/distributed/`
- Test suite in `tests/test_distributed/`
- Distributed systems design patterns
- Load balancing algorithms research
