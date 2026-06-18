# ADR 008: Multi-Agent Communication Protocol

## Status
Proposed (2026-06-18)

## Context
Swarm battles (2v2/3v3) in v3.0.0 require models to communicate and collaborate within teams. We need a standardized protocol for:

1. **Intra-team communication**: Models on the same team sharing context and results
2. **Inter-team coordination**: Teams competing in structured matches
3. **Message passing**: Reliable, ordered message delivery between agents
4. **Role assignment**: Clear definition of agent roles (e.g., "coder", "tester", "architect")
5. **Collaboration scoring**: Metrics to evaluate teamwork quality

## Decision

### Protocol Design

**Message Format**:
```json
{
  "message_id": "uuid",
  "timestamp": "ISO8601",
  "sender_agent": "model_id",
  "recipient_agent": "model_id",  // or "broadcast" for team-wide
  "message_type": "request|response|notification|coordination",
  "content": {
    "type": "code|analysis|question|result",
    "data": { ... },
    "metadata": { ... }
  },
  "context": {
    "task_id": "uuid",
    "round_id": "uuid",
    "team_id": "uuid"
  }
}
```

**Agent Roles**:
- **Coordinator**: Orchestrates team strategy, delegates tasks
- **Implementer**: Writes code, implements features
- **Tester**: Creates and runs tests, validates implementations
- **Reviewer**: Reviews code, provides feedback
- **Researcher**: Gathers information, explores solutions

**Communication Patterns**:

1. **Request-Response**:
   ```
   Agent A → Agent B: "Implement function X"
   Agent B → Agent A: "Here's implementation"
   ```

2. **Broadcast**:
   ```
   Coordinator → All: "Strategy update: focus on performance"
   All → Coordinator: "Acknowledged"
   ```

3. **Stream**:
   ```
   Agent A → Agent B: Continuous progress updates
   Agent B → Agent A: Continuous feedback
   ```

**Message Ordering**:
- Logical timestamps (Lamport clocks)
- Causal ordering guarantees
- Deduplication and retry logic

### Collaboration Scoring

**Metrics**:
1. **Communication Efficiency** (25%):
   - Message volume (optimal range, not too sparse or verbose)
   - Response latency
   - Information redundancy

2. **Role Adherence** (20%):
   - Staying within role scope
   - Proper delegation
   - Balanced contribution

3. **Task Coordination** (35%):
   - Parallel execution efficiency
   - Conflict resolution
   - Shared context utilization

4. **Quality of Outcomes** (20%):
   - Final task completion quality
   - Intermediate result quality
   - Error handling

**Scoring Algorithm**:
```python
def calculate_collaboration_score(communications, outcomes):
    efficiency = score_communication_efficiency(communications)
    adherence = score_role_adherence(communications)
    coordination = score_task_coordination(communications)
    quality = score_outcome_quality(outcomes)
    
    return (
        0.25 * efficiency +
        0.20 * adherence +
        0.35 * coordination +
        0.20 * quality
    )
```

### Implementation

**File Structure**:
```
ollama_arena/agentic/
├── protocol.py           # Message format and routing
├── roles.py             # Role definitions and validation
├── scoring.py           # Collaboration metrics
├── swarm.py             # Swarm battle orchestration
└── communication/
    ├── bus.py           # Message bus implementation
    ├── ordering.py      # Ordering guarantees
    └── retry.py         # Retry and deduplication
```

**Key Components**:

1. **Message Bus**: Async message passing with ordering guarantees
2. **Role Manager**: Role assignment and validation
3. **Collaboration Evaluator**: Scoring and metrics calculation
4. **Swarm Orchestrator**: Team formation and match management

### Security Considerations

**Message Security**:
- Message signing for authenticity
- Encryption for sensitive content
- Rate limiting to prevent flooding

**Team Isolation**:
- No cross-team communication during matches
- Separate message buses per team
- Spectator mode with read-only access

**Privacy**:
- Redact sensitive information from messages
- Configurable logging levels
- User consent for communication analysis

## Alternatives Considered

**Alternative 1: Direct API Calls**
- Pros: Simple, low latency
- Cons: Tight coupling, no standardization, hard to monitor

**Alternative 2: Shared Memory**
- Pros: Fast for co-located agents
- Cons: Complex synchronization, not distributed, security risks

**Alternative 3: Publish-Subscribe (PubSub)**
- Pros: Decoupled, scalable
- Cons: Complex ordering guarantees, overkill for small teams

**Chosen Approach**: Message bus with explicit addressing provides the right balance of structure, flexibility, and observability.

## Consequences

**Positive**:
- Standardized protocol enables diverse agent implementations
- Collaboration scoring provides new evaluation dimension
- Clear roles improve team organization
- Observable communication aids debugging

**Negative**:
- Additional complexity for single-agent scenarios
- Performance overhead from message serialization
- Learning curve for protocol understanding

**Risks**:
- Protocol version compatibility issues
- Gaming of collaboration scores
- Message bus performance bottlenecks

## Implementation Timeline

**Phase 1** (Q3 2026):
- Core message bus implementation
- Basic role definitions
- Simple collaboration scoring

**Phase 2** (Q4 2026):
- Advanced collaboration metrics
- Role specialization and validation
- Performance optimization

## References
- [v3.0.0 Roadmap](../v3.0.0-roadmap.md)
- [ADR 007: v3.0.0 Architecture](./007-v3.0.0-apex-evolution-architecture.md)
- Actor Model: https://en.wikipedia.org/wiki/Actor_model
- AMQP Protocol: https://www.amqp.org/