"""Example: register a custom MCP handler on MCPOrchestrator."""
import asyncio
from ollama_arena.mcp_client import MCPOrchestrator


def hello_handler(args: dict) -> str:
    name = args.get("name", "world")
    return f"Hello, {name}!"


async def main():
    mcp = MCPOrchestrator()
    mcp.register_handler("hello", hello_handler)
    mcp._handlers["hello"] = hello_handler
    print(await mcp.execute_tool("hello", {"name": "arena"}))


if __name__ == "__main__":
    asyncio.run(main())
