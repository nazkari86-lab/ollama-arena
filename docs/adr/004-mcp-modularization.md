# ADR 004: MCP System Modularization

## Status
Accepted

## Context
The MCP (Model Context Protocol) system in ollama-arena was already well-organized with a registry and orchestrator, but it lacked a proper transport layer abstraction. Different communication methods (stdio, HTTP, in-memory) were not abstracted, making it difficult to support external MCP servers or alternative transport mechanisms.

## Decision
Implemented a comprehensive transport layer abstraction to modularize the MCP system:

1. **Transport Abstraction:** Created `MCPTransport` base class with pluggable implementations
2. **Multiple Transport Types:** Implemented stdio, HTTP, and in-memory transports
3. **Factory Pattern:** Added `create_transport()` for flexible transport instantiation
4. **Error Handling:** Consistent error handling across all transport types
5. **Lifecycle Management:** Proper connection lifecycle with cleanup

### Changes Made

**File:** `ollama_arena/mcp/transport.py`

1. Created `MCPTransport` abstract base class
2. Implemented `StdioTransport` for subprocess-based MCP servers
3. Implemented `HTTPTransport` for HTTP-based MCP servers
4. Implemented `InMemoryTransport` for local tool execution
5. Added `create_transport()` factory function
6. Proper async/await patterns for all operations
7. Connection health checking with `is_alive()` method

**File:** `tests/test_mcp_transport.py`

1. Created comprehensive test suite with 17 test cases
2. Tests for each transport type
3. Tests for factory function
4. Tests for error handling and edge cases
5. Tests for lifecycle management

## Consequences

### Positive
- **Extensibility:** Easy to add new transport types (WebSocket, gRPC, etc.)
- **Flexibility:** Support for external MCP servers via different protocols
- **Testing:** In-memory transport simplifies testing without external dependencies
- **Maintainability:** Clear separation between transport and orchestration logic
- **Performance:** In-memory transport for local tools avoids IPC overhead

### Negative
- **Complexity:** Additional abstraction layer increases code complexity
- **Dependency:** HTTP transport requires aiohttp (optional dependency)
- **Testing Overhead:** More test cases needed for transport implementations
- **Async Requirements:** All operations must be async (potential learning curve)

## Integration Impact

The transport layer is designed to integrate seamlessly with the existing MCP orchestrator:

**Current Integration:**
- Existing `MCPOrchestrator` can use `InMemoryTransport` for local tools
- External MCP servers can use `StdioTransport` or `HTTPTransport`
- Backward compatibility maintained through existing registry system

**Future Integration:**
- Can replace direct tool calls with transport-based communication
- Support for remote MCP servers becomes straightforward
- Enables distributed agent execution across multiple machines

## Performance Characteristics

**In-Memory Transport:**
- Latency: ~0.1ms (direct function call)
- Throughput: High (limited by Python execution speed)
- Use case: Local tools, testing, development

**Stdio Transport:**
- Latency: ~5-15ms (subprocess overhead + serialization)
- Throughput: Medium (limited by IPC)
- Use case: External MCP servers, language servers

**HTTP Transport:**
- Latency: ~10-50ms (network overhead + serialization)
- Throughput: Medium (limited by network)
- Use case: Remote MCP servers, web-based tools

## Alternatives Considered

1. **Single Transport Implementation:** Rejected due to need for multiple communication methods
2. **External Library:** Rejected to maintain control over implementation and dependencies
3. **Synchronous API:** Rejected in favor of async for better performance
4. **No Abstraction:** Rejected to enable future extensibility and maintainability

## References
- Transport implementation in `ollama_arena/mcp/transport.py`
- Test suite in `tests/test_mcp_transport.py`
- MCP protocol specification
- Existing MCP orchestrator in `ollama_arena/mcp/orchestrator.py`
- Existing MCP registry in `ollama_arena/mcp/registry.py`