"""Example: autonomous issue resolution with MCP tools."""
from ollama_arena.agent_loop import run_agent_sync
from ollama_arena.backends.ollama import OllamaBackend
from ollama_arena.mcp_client import MCPOrchestrator


def main():
    backend = OllamaBackend()
    mcp = MCPOrchestrator()
    result = run_agent_sync(
        backend,
        model="qwen2.5-coder:7b",
        instruction="List files in the workspace and summarize what you find.",
        mcp=mcp,
        max_steps=5,
    )
    print(result.text)
    if result.agent_trace:
        print(f"Steps: {len(result.agent_trace)}")


if __name__ == "__main__":
    main()
