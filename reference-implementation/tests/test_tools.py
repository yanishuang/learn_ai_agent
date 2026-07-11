from inspect import Parameter, signature
from typing import get_type_hints

import pytest

from agent_course.core import RunContext, ToolResult
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.tools.base import StrictToolArguments
from agent_course.tools.orders import QueryOrderStatusArguments, QueryOrderStatusTool
from agent_course.tools.registry import ToolRegistry


@pytest.fixture
def context() -> RunContext:
    return RunContext(
        user_id="user-1",
        tenant_id="tenant-1",
        request_id="request-1",
        permissions=frozenset({"orders:read"}),
    )


@pytest.fixture
def context_without_permissions() -> RunContext:
    return RunContext(
        user_id="user-1",
        tenant_id="tenant-1",
        request_id="request-2",
        permissions=frozenset(),
    )


@pytest.fixture
def order_tool() -> QueryOrderStatusTool:
    return QueryOrderStatusTool()


def test_tool_registry_execute_signature_is_stable() -> None:
    annotations = get_type_hints(ToolRegistry.execute)
    parameters = signature(ToolRegistry.execute).parameters

    assert annotations["name"] is str
    assert annotations["arguments"] is dict
    assert annotations["context"] is RunContext
    assert annotations["return"] is ToolResult
    assert parameters["context"].kind is Parameter.POSITIONAL_OR_KEYWORD


def test_tool_arguments_are_strict_pydantic_models() -> None:
    assert issubclass(QueryOrderStatusArguments, StrictToolArguments)
    assert QueryOrderStatusArguments.model_config["extra"] == "forbid"


@pytest.mark.asyncio
async def test_model_cannot_override_tenant(
    order_tool: QueryOrderStatusTool,
    context: RunContext,
) -> None:
    result = await order_tool.execute(
        {"order_id": "O1001", "tenant_id": "attacker"},
        context=context,
    )

    assert result.code == "INVALID_ARGUMENTS"
    assert result.success is False


@pytest.mark.asyncio
async def test_model_cannot_override_user(
    order_tool: QueryOrderStatusTool,
    context: RunContext,
) -> None:
    result = await order_tool.execute(
        {"order_id": "O1001", "user_id": "attacker"},
        context=context,
    )

    assert result.code == "INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_missing_permission_is_blocked(
    order_tool: QueryOrderStatusTool,
    context_without_permissions: RunContext,
) -> None:
    result = await order_tool.execute(
        {"order_id": "O1001"},
        context=context_without_permissions,
    )

    assert result.code == "PERMISSION_DENIED"
    assert result.success is False


@pytest.mark.asyncio
async def test_order_lookup_uses_trusted_context_identity(
    order_tool: QueryOrderStatusTool,
    context: RunContext,
) -> None:
    result = await order_tool.execute({"order_id": "O1001"}, context=context)

    assert result == ToolResult(
        name="query_order_status",
        code="OK",
        success=True,
        output={
            "order_id": "O1001",
            "status": "shipped",
            "tenant_id": "tenant-1",
            "requested_by": "user-1",
        },
    )


@pytest.mark.asyncio
async def test_registry_rejects_unknown_fields_before_handler(
    context: RunContext,
) -> None:
    tool = QueryOrderStatusTool()
    registry = ToolRegistry([tool])

    result = await registry.execute(
        "query_order_status",
        {"order_id": "O1001", "api_key": "sk-raw-secret"},
        context,
    )

    assert result.code == "INVALID_ARGUMENTS"
    assert tool.execution_count == 0


@pytest.mark.asyncio
async def test_registry_returns_structured_unknown_tool_error(
    context: RunContext,
) -> None:
    result = await ToolRegistry().execute("missing", {}, context)

    assert result == ToolResult(
        name="missing",
        code="UNKNOWN_TOOL",
        success=False,
        error="tool is not registered",
    )


@pytest.mark.asyncio
async def test_tool_handler_exception_becomes_sanitized_structured_result(
    context: RunContext,
) -> None:
    class ExplodingOrderTool(QueryOrderStatusTool):
        async def _execute(
            self,
            arguments: QueryOrderStatusArguments,
            context: RunContext,
        ) -> ToolResult:
            del arguments, context
            raise RuntimeError("database failed with sk-handler-secret")

    result = await ToolRegistry([ExplodingOrderTool()]).execute(
        "query_order_status",
        {"order_id": "O1001"},
        context,
    )

    assert result == ToolResult(
        name="query_order_status",
        code="TOOL_ERROR",
        success=False,
        error="tool handler failed",
    )
    assert "sk-handler-secret" not in result.model_dump_json()


def test_registry_exposes_strict_tool_definition() -> None:
    definitions = ToolRegistry([QueryOrderStatusTool()]).definitions()

    assert len(definitions) == 1
    assert definitions[0].name == "query_order_status"
    assert definitions[0].input_schema["additionalProperties"] is False
    assert definitions[0].input_schema["required"] == ["order_id"]


def test_trace_sink_redacts_normalized_sensitive_key_variants() -> None:
    traces = InMemoryTraceSink()
    traces.record(
        "trace-1",
        "secret.probe",
        {
            "X-API-Key": "x-api-key-secret",
            "access_token": "access-token-secret",
            "request_id": "request-1",
        },
    )

    attributes = traces.events[0].attributes

    assert attributes == {
        "X-API-Key": "[REDACTED]",
        "access_token": "[REDACTED]",
        "request_id": "request-1",
    }
    serialized = traces.events[0].model_dump_json()
    assert "x-api-key-secret" not in serialized
    assert "access-token-secret" not in serialized
