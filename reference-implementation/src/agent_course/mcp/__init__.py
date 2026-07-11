"""MCP stdio server and client helpers."""

from importlib import import_module
from typing import Any

_CLIENT_EXPORTS = {
    "McpClientError",
    "McpClientTimeoutError",
    "McpExchange",
    "query_order_status_via_stdio",
}
_SERVER_EXPORTS = {"create_server", "default_mcp_context"}

__all__ = sorted(_CLIENT_EXPORTS | _SERVER_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _CLIENT_EXPORTS:
        module = import_module("agent_course.mcp.client")
        return getattr(module, name)
    if name in _SERVER_EXPORTS:
        module = import_module("agent_course.mcp.server")
        return getattr(module, name)
    raise AttributeError(name)
