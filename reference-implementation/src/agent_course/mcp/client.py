"""Small MCP v1 stdio client with bounded lifecycle and structured results."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Sequence

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ConfigDict, ValidationError, field_validator

from agent_course.core import FrozenModel, JsonValue


MCP_PROTOCOL_VERSION = "2025-11-25"
_EXPECTED_TOOL_SCHEMA_HASHES = {
    "query_order_status": (
        "7a448988ed2170c6a8f029bd6cc2e5113676bc65ecee91ca9eb3d75a1888fdb2"
    )
}


class McpClientError(RuntimeError):
    """Raised when the MCP exchange is invalid or reports a tool failure."""


class McpClientTimeoutError(McpClientError):
    """Raised when server startup or an MCP request exceeds its deadline."""


class McpExchange(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: str
    tool_names: tuple[str, ...]
    tool_schema_hashes: dict[str, str]
    structured_result: dict[str, JsonValue]


class McpOrderStatusResult(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: str
    status: str
    tenant_id: str
    requested_by: str

    @field_validator("order_id", "status", "tenant_id", "requested_by")
    @classmethod
    def values_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("MCP order result values must be nonblank")
        return value


def validate_server_contract(
    initialized: object,
    tools: Sequence[object],
) -> dict[str, str]:
    """Reject protocol, allowlist, or schema drift before a tool can execute."""

    protocol_version = getattr(initialized, "protocolVersion", None)
    if protocol_version != MCP_PROTOCOL_VERSION:
        raise McpClientError(
            "MCP protocol must negotiate "
            f"{MCP_PROTOCOL_VERSION}, got {protocol_version!r}"
        )

    tool_names = tuple(getattr(tool, "name", None) for tool in tools)
    expected_names = frozenset(_EXPECTED_TOOL_SCHEMA_HASHES)
    if (
        any(not isinstance(name, str) for name in tool_names)
        or len(tool_names) != len(set(tool_names))
        or frozenset(tool_names) != expected_names
    ):
        raise McpClientError(
            "MCP tool set must match the exact allowlist: "
            f"{sorted(expected_names)!r}"
        )

    schema_hashes: dict[str, str] = {}
    for tool in tools:
        name = tool.name
        try:
            schema_hash = _schema_hash(tool.inputSchema, tool.outputSchema)
        except (AttributeError, TypeError, ValueError) as error:
            raise McpClientError(
                f"MCP tool {name!r} has an invalid schema contract"
            ) from error
        expected_hash = _EXPECTED_TOOL_SCHEMA_HASHES[name]
        if schema_hash != expected_hash:
            raise McpClientError(
                f"MCP tool {name!r} schema hash does not match the allowlist"
            )
        schema_hashes[name] = schema_hash
    return schema_hashes


def validate_order_status_result(
    value: object,
    *,
    expected_order_id: str,
) -> dict[str, JsonValue]:
    """Apply the caller's local output contract to untrusted MCP content."""

    try:
        result = McpOrderStatusResult.model_validate(value)
    except ValidationError as error:
        raise McpClientError(
            "MCP structured output failed local schema validation"
        ) from error
    if result.order_id != expected_order_id:
        raise McpClientError(
            "MCP structured output order_id does not match the requested order"
        )
    return result.model_dump(mode="json")


def _schema_hash(input_schema: object, output_schema: object) -> str:
    canonical = json.dumps(
        {"input_schema": input_schema, "output_schema": output_schema},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
            protocol_version: str | None = None
            tool_names: tuple[str, ...] = ()
            tool_schema_hashes: dict[str, str] = {}
            structured_result: dict[str, JsonValue] | None = None
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:
                    initialized = await session.initialize()
                    protocol_version = str(initialized.protocolVersion)
                    listed = await session.list_tools()
                    tool_names = tuple(tool.name for tool in listed.tools)
                    try:
                        tool_schema_hashes = validate_server_contract(
                            initialized,
                            listed.tools,
                        )
                    except McpClientError as error:
                        failure = str(error)
                    if failure is None:
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
                            try:
                                structured_result = validate_order_status_result(
                                    called.structuredContent,
                                    expected_order_id=order_id,
                                )
                            except McpClientError as error:
                                failure = str(error)

            if failure is not None:
                raise McpClientError(failure)
            if structured_result is None:
                raise McpClientError("MCP exchange ended without a result")
            if protocol_version is None:
                raise McpClientError("MCP exchange ended without a protocol version")
            return McpExchange(
                protocol_version=protocol_version,
                tool_names=tool_names,
                tool_schema_hashes=tool_schema_hashes,
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
    "McpOrderStatusResult",
    "MCP_PROTOCOL_VERSION",
    "main",
    "query_order_status_via_stdio",
    "validate_order_status_result",
    "validate_server_contract",
]
