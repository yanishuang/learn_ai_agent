import os
import sys
from pathlib import Path

import pytest

from agent_course.mcp.client import (
    McpClientTimeoutError,
    query_order_status_via_stdio,
)


@pytest.mark.asyncio
async def test_stdio_server_lists_and_calls_order_tool_with_structured_result() -> None:
    exchange = await query_order_status_via_stdio(
        "O1001",
        command=sys.executable,
        args=("-m", "agent_course.mcp.server"),
        timeout_seconds=5.0,
    )

    assert "query_order_status" in exchange.tool_names
    assert exchange.structured_result == {
        "order_id": "O1001",
        "status": "shipped",
        "tenant_id": "tenant-1",
        "requested_by": "mcp-user",
    }


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
