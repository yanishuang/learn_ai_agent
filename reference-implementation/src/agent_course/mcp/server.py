"""Deterministic order-status MCP server over stdio."""

from mcp.server.fastmcp import FastMCP

from agent_course.core import RunContext
from agent_course.tools.orders import QueryOrderStatusTool


def default_mcp_context() -> RunContext:
    """Server-owned identity used by the credential-free course subprocess."""

    return RunContext(
        user_id="mcp-user",
        tenant_id="tenant-1",
        request_id="mcp-stdio-request",
        permissions=frozenset({"orders:read"}),
    )


def create_server(context: RunContext | None = None) -> FastMCP:
    trusted_context = context or default_mcp_context()
    order_tool = QueryOrderStatusTool()
    server = FastMCP(
        "agent-course-orders",
        instructions="Read-only deterministic order tools for the agent course.",
        log_level="WARNING",
    )

    @server.tool(
        name="query_order_status",
        description="Query an order status in the server-authorized tenant.",
        structured_output=True,
    )
    async def query_order_status(order_id: str) -> dict[str, str]:
        result = await order_tool.execute(
            {"order_id": order_id},
            context=trusted_context,
        )
        if not result.success:
            raise RuntimeError(result.error or result.code)
        if not isinstance(result.output, dict):
            raise RuntimeError("order tool returned an invalid structured result")
        return {str(key): str(value) for key, value in result.output.items()}

    return server


mcp = create_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


__all__ = ["create_server", "default_mcp_context", "main", "mcp"]
