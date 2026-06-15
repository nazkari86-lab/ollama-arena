"""
Planning Benchmarks — 20 architectural/design tasks.
Scored by: LLM-as-judge (A6 Judge) on a rubric 0–10.
Rubric: completeness (0-3), feasibility (0-3), clarity (0-2), edge cases (0-2).
"""

PLANNING_RUBRIC = {
    "completeness": {"max": 3, "desc": "All required components/steps present"},
    "feasibility":  {"max": 3, "desc": "Plan is technically realistic and correct"},
    "clarity":      {"max": 2, "desc": "Plan is well-structured and unambiguous"},
    "edge_cases":   {"max": 2, "desc": "Addresses failure modes and edge cases"},
}

PLANNING_TASKS = [
    # System Design (8)
    {
        "id": "plan_001", "difficulty": "medium", "role": "planner",
        "instruction": "Design a URL shortener service (like bit.ly) that handles 10,000 requests/sec. Describe: data model, hash generation strategy, caching layer, database choice, and API endpoints.",
        "key_components": ["hash generation", "database", "cache", "API", "collision handling"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_002", "difficulty": "medium", "role": "planner",
        "instruction": "Design a real-time collaborative document editor (like Google Docs) for 100 concurrent users on the same document. Describe: conflict resolution strategy, synchronization protocol, data structure for document state.",
        "key_components": ["OT or CRDT", "WebSocket", "document model", "conflict resolution"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_003", "difficulty": "hard", "role": "planner",
        "instruction": "Design a distributed task queue system (like Celery + Redis) that supports: priority queues, task retry with exponential backoff, dead letter queue, and at-least-once delivery guarantees.",
        "key_components": ["priority queue", "retry backoff", "dead letter queue", "delivery guarantee"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_004", "difficulty": "medium", "role": "planner",
        "instruction": "Design a multi-tenant SaaS authentication system supporting: OAuth 2.0 social login, MFA, session management, and rate limiting per tenant. Describe the token lifecycle.",
        "key_components": ["OAuth", "MFA", "session management", "rate limiting", "token lifecycle"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_005", "difficulty": "hard", "role": "planner",
        "instruction": "Design a distributed cache (like Redis Cluster) with: consistent hashing for sharding, replication with failover, and cache invalidation strategies. How do you handle network partitions?",
        "key_components": ["consistent hashing", "replication", "failover", "CAP theorem", "invalidation"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_006", "difficulty": "medium", "role": "planner",
        "instruction": "Design an event-driven microservices architecture for an e-commerce order processing system. Show the sequence of events from order placement to fulfillment with appropriate services and message queues.",
        "key_components": ["event sourcing", "services decomposition", "message queue", "saga pattern"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_007", "difficulty": "hard", "role": "planner",
        "instruction": "Design a real-time ML feature store that serves features to models with < 10ms P99 latency. It must support both batch (historical) and streaming (real-time) feature computation.",
        "key_components": ["online store", "offline store", "feature pipeline", "latency SLA", "consistency"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_008", "difficulty": "medium", "role": "planner",
        "instruction": "Design a CI/CD pipeline for a Python monorepo with 20 services. Include: test strategy (unit/integration/e2e), deployment strategy (canary/blue-green), rollback mechanism, and secret management.",
        "key_components": ["test pyramid", "deployment strategy", "rollback", "secrets", "monorepo tooling"],
        "rubric": PLANNING_RUBRIC,
    },
    # Algorithm/Approach Design (7)
    {
        "id": "plan_009", "difficulty": "medium", "role": "planner",
        "instruction": "You have a dataset of 100M user clickstream events per day. Design an approach to compute top-100 most clicked products in real-time (< 1 minute delay) and batch (daily). Include data structures and algorithms.",
        "key_components": ["streaming aggregation", "top-k algorithm", "batch vs streaming", "data structure"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_010", "difficulty": "hard", "role": "planner",
        "instruction": "Design a plagiarism detection system for code submissions. It should detect: exact copies, renamed variables, restructured code, and cross-language copying (Python vs Java). Describe the similarity algorithm.",
        "key_components": ["AST normalization", "fingerprinting", "similarity metric", "cross-language"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_011", "difficulty": "medium", "role": "planner",
        "instruction": "Design a recommendation engine for a music streaming service with 50M songs and 10M users. Support both collaborative filtering and content-based recommendations. How do you handle cold-start?",
        "key_components": ["collaborative filtering", "content-based", "cold start", "embedding", "online updates"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_012", "difficulty": "medium", "role": "planner",
        "instruction": "Design the data model and query strategy for a social network's news feed (like Twitter/X). Support: chronological feed, algorithmic ranking, real-time updates, and pagination for 100M users.",
        "key_components": ["fan-out strategy", "feed ranking", "pagination", "real-time", "storage model"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_013", "difficulty": "hard", "role": "planner",
        "instruction": "Design a system that detects anomalies in server metrics (CPU, memory, network) across 10,000 servers in real-time. It must minimize false positives while catching true incidents within 30 seconds.",
        "key_components": ["anomaly algorithm", "baseline", "false positive control", "latency SLA", "alerting"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_014", "difficulty": "medium", "role": "planner",
        "instruction": "Design a database migration strategy for moving a 500GB PostgreSQL database to a new schema with zero downtime. The migration requires renaming columns and adding new indexes.",
        "key_components": ["zero downtime", "dual write", "backfill", "cutover", "rollback plan"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_015", "difficulty": "hard", "role": "planner",
        "instruction": "Design a distributed rate limiter that works across 50 API server instances. Support: per-user, per-IP, and per-endpoint limits with different windows (1s, 1m, 1h). Latency must be < 1ms.",
        "key_components": ["token bucket vs sliding window", "distributed coordination", "latency SLA", "atomicity"],
        "rubric": PLANNING_RUBRIC,
    },
    # Code Architecture (5)
    {
        "id": "plan_016", "difficulty": "medium", "role": "planner",
        "instruction": "You're refactoring a 50,000-line Python monolith into microservices. Describe your strangler fig pattern approach: how to identify boundaries, the migration sequence, and how to maintain data consistency during migration.",
        "key_components": ["strangler fig", "service boundaries", "migration sequence", "data consistency"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_017", "difficulty": "easy", "role": "planner",
        "instruction": "Design the class hierarchy for a plugin system where third-party developers can add new capabilities to an application without modifying core code. Include: plugin discovery, lifecycle hooks, and error isolation.",
        "key_components": ["plugin interface", "discovery mechanism", "lifecycle hooks", "error isolation"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_018", "difficulty": "medium", "role": "planner",
        "instruction": "Design the architecture for an LLM agent that needs to: use tools (search, code exec, file I/O), maintain conversation context across 10K tokens, and gracefully handle tool failures with fallback strategies.",
        "key_components": ["tool use loop", "context management", "failure handling", "fallback strategy"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_019", "difficulty": "medium", "role": "planner",
        "instruction": "Design a configuration management system for a distributed application where config changes must: propagate to all instances within 5 seconds, support A/B testing (10% rollout), and be rollback-safe.",
        "key_components": ["propagation mechanism", "A/B rollout", "rollback", "consistency model"],
        "rubric": PLANNING_RUBRIC,
    },
    {
        "id": "plan_020", "difficulty": "hard", "role": "planner",
        "instruction": "Design a self-healing Kubernetes operator that monitors a stateful application and automatically: scales based on custom metrics, restores from backup on data corruption, and rotates secrets without downtime.",
        "key_components": ["custom controller", "custom metrics", "backup/restore", "secret rotation", "reconciliation loop"],
        "rubric": PLANNING_RUBRIC,
    },
]
