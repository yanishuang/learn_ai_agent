import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_course.mcp import client as mcp_client
from agent_course.mcp.client import (
    McpClientError,
    McpClientTimeoutError,
    query_order_status_via_stdio,
)


EXPECTED_INPUT_SCHEMA = {
    "properties": {"order_id": {"title": "Order Id", "type": "string"}},
    "required": ["order_id"],
    "title": "query_order_statusArguments",
    "type": "object",
}
EXPECTED_OUTPUT_SCHEMA = {
    "additionalProperties": {"type": "string"},
    "title": "query_order_statusDictOutput",
    "type": "object",
}
EXPECTED_SCHEMA_HASH = "7a448988ed2170c6a8f029bd6cc2e5113676bc65ecee91ca9eb3d75a1888fdb2"


def contract_tool(
    *,
    name: str = "query_order_status",
    input_schema: dict[str, object] | None = None,
    output_schema: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        inputSchema=input_schema or EXPECTED_INPUT_SCHEMA,
        outputSchema=output_schema or EXPECTED_OUTPUT_SCHEMA,
    )


@pytest.mark.asyncio
async def test_stdio_server_lists_and_calls_order_tool_with_structured_result() -> None:
    exchange = await query_order_status_via_stdio(
        "O1001",
        command=sys.executable,
        args=("-m", "agent_course.mcp.server"),
        timeout_seconds=5.0,
    )

    assert exchange.protocol_version == "2025-11-25"
    assert exchange.tool_names == ("query_order_status",)
    assert exchange.tool_schema_hashes == {
        "query_order_status": EXPECTED_SCHEMA_HASH
    }
    assert exchange.structured_result == {
        "order_id": "O1001",
        "status": "shipped",
        "tenant_id": "tenant-1",
        "requested_by": "mcp-user",
    }


def test_client_rejects_nonbaseline_protocol_before_tool_call() -> None:
    with pytest.raises(McpClientError, match="protocol.*2025-11-25"):
        mcp_client.validate_server_contract(
            SimpleNamespace(protocolVersion="2025-06-18"),
            [contract_tool()],
        )


def test_client_rejects_unexpected_tool_set() -> None:
    with pytest.raises(McpClientError, match="exact allowlist"):
        mcp_client.validate_server_contract(
            SimpleNamespace(protocolVersion="2025-11-25"),
            [contract_tool(), contract_tool(name="admin_export")],
        )


def test_client_rejects_allowlisted_tool_schema_drift() -> None:
    drifted_input = {
        **EXPECTED_INPUT_SCHEMA,
        "properties": {
            **EXPECTED_INPUT_SCHEMA["properties"],
            "tenant_id": {"type": "string"},
        },
        "required": ["order_id", "tenant_id"],
    }

    with pytest.raises(McpClientError, match="schema hash"):
        mcp_client.validate_server_contract(
            SimpleNamespace(protocolVersion="2025-11-25"),
            [contract_tool(input_schema=drifted_input)],
        )


@pytest.mark.parametrize(
    "structured_result",
    [
        {"order_id": "O1001", "status": "shipped", "tenant_id": "tenant-1"},
        {
            "order_id": "O1001",
            "status": "shipped",
            "tenant_id": "tenant-1",
            "requested_by": "mcp-user",
            "secret": "must-not-pass",
        },
        {
            "order_id": "O9999",
            "status": "shipped",
            "tenant_id": "tenant-1",
            "requested_by": "mcp-user",
        },
    ],
)
def test_client_validates_structured_output_locally(
    structured_result: dict[str, str],
) -> None:
    with pytest.raises(McpClientError, match="structured output"):
        mcp_client.validate_order_status_result(
            structured_result,
            expected_order_id="O1001",
        )


@pytest.mark.asyncio
async def test_stdio_client_reports_server_tool_errors_and_cleans_up() -> None:
    with pytest.raises(RuntimeError, match="order was not found"):
        await query_order_status_via_stdio(
            "missing",
            command=sys.executable,
            args=("-m", "agent_course.mcp.server"),
            timeout_seconds=5.0,
        )


@pytest.mark.asyncio
async def test_stdio_client_times_out_and_reaps_unresponsive_subprocess(
    tmp_path: Path,
) -> None:
    pid_path = tmp_path / "server.pid"
    script = (
        "import os,time; from pathlib import Path; "
        f"Path({str(pid_path)!r}).write_text(str(os.getpid())); "
        "time.sleep(10)"
    )

    with pytest.raises(McpClientTimeoutError, match="timed out after 0.1 seconds"):
        await query_order_status_via_stdio(
            "O1001",
            command=sys.executable,
            args=("-c", script),
            timeout_seconds=0.1,
        )

    pid = int(pid_path.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
