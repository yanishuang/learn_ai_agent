"""Small MCP v1 stdio client with bounded lifecycle and structured results."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ConfigDict

from agent_course.core import FrozenModel, JsonValue


class McpClientError(RuntimeError):
    """Raised when the MCP exchange is invalid or reports a tool failure."""


class McpClientTimeoutError(McpClientError):
    """Raised when server startup or an MCP request exceeds its deadline."""


class McpExchange(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_names: tuple[str, ...]
    structured_result: dict[str, JsonValue]


async def query_order_status_via_stdio(
    order_id: str,
    *,
    command: str = sys.executable,
    args: Sequence[str] = ("-m", "agent_course.mcp.server"),
    timeout_seconds: float = 5.0,
) -> McpExchange:
    """Start a server, discover its tools, call one tool, and always close it."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    server = StdioServerParameters(command=command, args=list(args))

    try:
        async with asyncio.timeout(timeout_seconds):
            failure: str | None = None
            structured_result: dict[str, JsonValue] | None = None
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    tool_names = tuple(tool.name for tool in listed.tools)
                    if "query_order_status" not in tool_names:
                        failure = "MCP server does not expose query_order_status"
                    else:
                        called = await session.call_tool(
                            "query_order_status",
                            {"order_id": order_id},
                        )
                        if called.isError:
                            details = " ".join(
                                str(getattr(block, "text", ""))
                                for block in called.content
                            ).strip()
                            failure = details or "MCP tool call failed"
                        elif called.structuredContent is None:
                            failure = "MCP tool did not return structured content"
                        else:
                            structured_result = called.structuredContent

            if failure is not None:
                raise McpClientError(failure)
            if structured_result is None:
                raise McpClientError("MCP exchange ended without a result")
            return McpExchange(
                tool_names=tool_names,
                structured_result=structured_result,
            )
    except TimeoutError as error:
        raise McpClientTimeoutError(
            f"MCP stdio exchange timed out after {timeout_seconds:g} seconds"
        ) from error


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Call the course MCP order tool")
    parser.add_argument("order_id", nargs="?", default="O1001")
    parser.add_argument("--timeout", type=float, default=5.0)
    options = parser.parse_args(argv)

    try:
        result = asyncio.run(
            query_order_status_via_stdio(
                options.order_id,
                timeout_seconds=options.timeout,
            )
        )
    except (McpClientError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(result.model_dump_json())


if __name__ == "__main__":
    main()


__all__ = [
    "McpClientError",
    "McpClientTimeoutError",
    "McpExchange",
    "main",
    "query_order_status_via_stdio",
]
