from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from agent_course.agents.openai_agents import OpenAIAgentsRunner
from agent_course.agents.guardrails import DefaultGuardrail
from agent_course.agents.runner import BoundedAgentRunner
from agent_course.core import (
    Message,
    ModelContinuation,
    RunContext,
    RunLimits,
    StopReason,
    ToolDefinition,
)
from agent_course.models.base import LiveConfigurationError
from agent_course.models.openai_responses import OpenAIResponsesGateway
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.tools.orders import QueryOrderStatusTool
from agent_course.tools.registry import ToolRegistry


LIVE_ENVIRONMENT = {
    "AGENT_COURSE_LIVE_TESTS": "1",
    "OPENAI_API_KEY": "test-key",
    "OPENAI_MODEL": "test-model",
}

ORDER_TOOL = ToolDefinition(
    name="query_order_status",
    description="Query an order",
    input_schema={
        "type": "object",
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"],
        "additionalProperties": False,
    },
)

ORDER_TOOL_INPUT = {
    "type": "function",
    "name": "query_order_status",
    "description": "Query an order",
    "parameters": ORDER_TOOL.input_schema,
    "strict": True,
}


class NoNetworkResponses:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.parse_calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.create_calls.append(kwargs)
        return SimpleNamespace(
            id="response-1",
            status="completed",
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call-1",
                    name="query_order_status",
                    arguments='{"order_id":"O1001"}',
                )
            ],
            output_text="",
            usage=SimpleNamespace(
                input_tokens=11,
                output_tokens=7,
                total_tokens=18,
            ),
            incomplete_details=None,
            error=None,
        )

    async def parse(self, **kwargs: object) -> SimpleNamespace:
        self.parse_calls.append(kwargs)
        return SimpleNamespace(output_parsed=StructuredAnswer(answer="bounded"))


class NoNetworkClient:
    def __init__(self) -> None:
        self.responses = NoNetworkResponses()


class StructuredAnswer(BaseModel):
    answer: str


def set_live_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in LIVE_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize(
    "adapter",
    [OpenAIResponsesGateway, OpenAIAgentsRunner],
)
@pytest.mark.parametrize(
    ("environment", "missing_name"),
    [
        ({}, "AGENT_COURSE_LIVE_TESTS=1"),
        (
            {
                "AGENT_COURSE_LIVE_TESTS": "true",
                "OPENAI_API_KEY": "test-key",
                "OPENAI_MODEL": "test-model",
            },
            "AGENT_COURSE_LIVE_TESTS=1",
        ),
        (
            {
                "AGENT_COURSE_LIVE_TESTS": " 1 ",
                "OPENAI_API_KEY": "test-key",
                "OPENAI_MODEL": "test-model",
            },
            "AGENT_COURSE_LIVE_TESTS=1",
        ),
        (
            {
                "AGENT_COURSE_LIVE_TESTS": "1",
                "OPENAI_API_KEY": "   ",
                "OPENAI_MODEL": "test-model",
            },
            "OPENAI_API_KEY",
        ),
        (
            {
                "AGENT_COURSE_LIVE_TESTS": "1",
                "OPENAI_API_KEY": "test-key",
                "OPENAI_MODEL": "\t",
            },
            "OPENAI_MODEL",
        ),
    ],
)
def test_live_adapters_share_a_strict_environment_gate(
    monkeypatch: pytest.MonkeyPatch,
    adapter: type[OpenAIResponsesGateway] | type[OpenAIAgentsRunner],
    environment: dict[str, str],
    missing_name: str,
) -> None:
    for name in LIVE_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(LiveConfigurationError, match=missing_name):
        adapter.from_environment()


def test_successful_live_gate_construction_makes_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()

    gateway = OpenAIResponsesGateway.from_environment(client=client)
    runner = OpenAIAgentsRunner.from_environment()

    assert gateway.model == "test-model"
    assert runner.model == "test-model"
    assert client.responses.create_calls == []
    assert client.responses.parse_calls == []


@pytest.mark.asyncio
async def test_responses_gateway_converts_low_level_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)

    step = await gateway.next_step(
        messages=[Message(role="user", content="Order O1001")],
        tools=[ORDER_TOOL],
    )

    assert step.stop_reason is StopReason.TOOL_CALLS
    assert step.tool_calls[0].name == "query_order_status"
    assert step.tool_calls[0].arguments == {"order_id": "O1001"}
    assert step.continuation == ModelContinuation(
        provider="openai_responses",
        token="response-1",
    )
    assert step.usage.total_tokens == 18
    assert client.responses.create_calls == [
        {
            "model": "test-model",
            "input": [{"role": "user", "content": "Order O1001"}],
            "tools": [ORDER_TOOL_INPUT],
        }
    ]


@pytest.mark.asyncio
async def test_responses_gateway_runs_injected_two_turn_tool_exchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)

    class TwoTurnResponses:
        def __init__(self) -> None:
            self.create_calls: list[dict[str, object]] = []
            self.responses = iter(
                [
                    SimpleNamespace(
                        id="response-tool-call",
                        status="completed",
                        output=[
                            SimpleNamespace(
                                type="function_call",
                                call_id="call-order-1",
                                name="query_order_status",
                                arguments='{"order_id":"O1001"}',
                            )
                        ],
                        output_text="",
                        usage=None,
                        incomplete_details=None,
                        error=None,
                    ),
                    SimpleNamespace(
                        id="response-complete",
                        status="completed",
                        output=[],
                        output_text="Order O1001 is shipped.",
                        usage=None,
                        incomplete_details=None,
                        error=None,
                    ),
                ]
            )

        async def create(self, **kwargs: object) -> SimpleNamespace:
            self.create_calls.append(kwargs)
            return next(self.responses)

    responses = TwoTurnResponses()
    client = SimpleNamespace(responses=responses)
    gateway = OpenAIResponsesGateway.from_environment(client=client)

    first = await gateway.next_step(
        messages=[Message(role="user", content="Order O1001")],
        tools=[ORDER_TOOL],
    )

    def query_order_status(order_id: object) -> str:
        assert order_id == "O1001"
        return '{"order_id":"O1001","status":"shipped"}'

    tool_output = Message(
        role="tool",
        tool_call_id=first.tool_calls[0].id,
        content=query_order_status(**first.tool_calls[0].arguments),
    )
    second = await gateway.next_step(
        messages=[tool_output],
        tools=[ORDER_TOOL],
        continuation=first.continuation,
    )

    assert second.content == "Order O1001 is shipped."
    assert second.stop_reason is StopReason.COMPLETED
    assert second.continuation == ModelContinuation(
        provider="openai_responses",
        token="response-complete",
    )
    assert responses.create_calls == [
        {
            "model": "test-model",
            "input": [{"role": "user", "content": "Order O1001"}],
            "tools": [ORDER_TOOL_INPUT],
        },
        {
            "model": "test-model",
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "call-order-1",
                    "output": '{"order_id":"O1001","status":"shipped"}',
                }
            ],
            "tools": [ORDER_TOOL_INPUT],
            "previous_response_id": "response-tool-call",
        },
    ]


@pytest.mark.asyncio
async def test_bounded_runner_sends_remaining_allowance_to_every_responses_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)

    class BudgetedResponses:
        def __init__(self) -> None:
            self.create_calls: list[dict[str, object]] = []
            self.responses = iter(
                [
                    SimpleNamespace(
                        id="response-budget-tool",
                        status="completed",
                        output=[
                            SimpleNamespace(
                                type="function_call",
                                call_id="call-budget-order",
                                name="query_order_status",
                                arguments='{"order_id":"O1001"}',
                            )
                        ],
                        output_text="",
                        usage=SimpleNamespace(
                            input_tokens=5,
                            output_tokens=7,
                            total_tokens=12,
                        ),
                        incomplete_details=None,
                        error=None,
                    ),
                    SimpleNamespace(
                        id="response-budget-complete",
                        status="completed",
                        output=[],
                        output_text="Order O1001 is shipped.",
                        usage=SimpleNamespace(
                            input_tokens=8,
                            output_tokens=3,
                            total_tokens=11,
                        ),
                        incomplete_details=None,
                        error=None,
                    ),
                ]
            )

        async def create(self, **kwargs: object) -> SimpleNamespace:
            self.create_calls.append(kwargs)
            return next(self.responses)

    responses = BudgetedResponses()
    runner = BoundedAgentRunner(
        model=OpenAIResponsesGateway.from_environment(
            client=SimpleNamespace(responses=responses)
        ),
        tools=ToolRegistry([QueryOrderStatusTool()]),
        guardrail=DefaultGuardrail(),
        traces=InMemoryTraceSink(),
    )

    result = await runner.run(
        "Order O1001",
        RunContext(
            user_id="live-test-user",
            tenant_id="tenant-1",
            request_id="live-budget-request",
            permissions=frozenset({"orders:read"}),
        ),
        RunLimits(
            max_turns=3,
            max_tool_calls=2,
            max_output_tokens=10,
            timeout_seconds=1,
        ),
    )

    assert result.stop_reason is StopReason.COMPLETED
    assert [call["max_output_tokens"] for call in responses.create_calls] == [10, 3]


@pytest.mark.parametrize(
    ("response_status", "incomplete_reason", "error_code", "expected_reason"),
    [
        ("incomplete", "max_output_tokens", None, "max_output_tokens"),
        ("incomplete", "content_filter", None, "content_filter"),
        ("incomplete", None, None, "model_incomplete"),
        ("failed", None, "server_error", "model_error"),
        ("failed", None, "bio_policy", "content_filter"),
        ("cancelled", None, None, "cancelled"),
        ("in_progress", None, None, "model_incomplete"),
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_maps_non_success_statuses_to_typed_stop_reasons(
    monkeypatch: pytest.MonkeyPatch,
    response_status: str,
    incomplete_reason: str | None,
    error_code: str | None,
    expected_reason: str,
) -> None:
    set_live_environment(monkeypatch)
    response = SimpleNamespace(
        id="response-terminal-status",
        status=response_status,
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="must-not-execute",
                name="query_order_status",
                arguments='{"order_id":"O1001"}',
            )
        ],
        output_text="partial output",
        usage=None,
        incomplete_details=(
            SimpleNamespace(reason=incomplete_reason)
            if response_status == "incomplete"
            else None
        ),
        error=(
            SimpleNamespace(code=error_code, message="sanitized by boundary")
            if error_code is not None
            else None
        ),
    )

    async def create(**kwargs: object) -> SimpleNamespace:
        del kwargs
        return response

    gateway = OpenAIResponsesGateway.from_environment(
        client=SimpleNamespace(responses=SimpleNamespace(create=create))
    )

    step = await gateway.next_step(
        messages=[Message(role="user", content="Order O1001")],
        tools=[ORDER_TOOL],
    )

    assert isinstance(step.stop_reason, StopReason)
    assert step.stop_reason.value == expected_reason
    assert step.tool_calls == ()


@pytest.mark.asyncio
async def test_responses_gateway_rejects_wrong_continuation_provider_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)

    with pytest.raises(ValueError, match="continuation provider.*openai_responses"):
        await gateway.next_step(
            messages=[Message(role="tool", content="{}", tool_call_id="call-1")],
            tools=[ORDER_TOOL],
            continuation=ModelContinuation(provider="other", token="response-1"),
        )

    assert client.responses.create_calls == []


@pytest.mark.asyncio
async def test_responses_gateway_rejects_missing_response_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)

    async def create_without_id(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(id="", output=[], output_text="complete", usage=None)

    client.responses.create = create_without_id

    with pytest.raises(ValueError, match="response id"):
        await gateway.next_step(
            messages=[Message(role="user", content="Hello")],
            tools=[],
        )


@pytest.mark.parametrize(
    ("schema", "error_path"),
    [
        (
            {
                "type": "array",
                "items": {"type": "string"},
            },
            r"\$\.type",
        ),
        (
            {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
            r"\$\.additionalProperties",
        ),
        (
            {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            },
            r"\$\.required",
        ),
        (
            {
                "type": "object",
                "properties": {
                    "delivery": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": [],
                        "additionalProperties": False,
                    }
                },
                "required": ["delivery"],
                "additionalProperties": False,
            },
            r"\$\.properties\.delivery\.required",
        ),
        (
            {
                "type": "object",
                "properties": {
                    "destinations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": [],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["destinations"],
                "additionalProperties": False,
            },
            r"\$\.properties\.destinations\.items\.required",
        ),
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_rejects_non_strict_tool_schema_before_request(
    monkeypatch: pytest.MonkeyPatch,
    schema: dict[str, object],
    error_path: str,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)
    tool = ToolDefinition(
        name="query_order_status",
        description="Query an order",
        input_schema=schema,
    )

    with pytest.raises(ValueError, match=error_path):
        await gateway.next_step(
            messages=[Message(role="user", content="Order O1001")],
            tools=[tool],
        )

    assert client.responses.create_calls == []


def strict_tool_schema(property_schema: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {"value": property_schema},
        "required": ["value"],
        "additionalProperties": False,
    }


async def assert_schema_rejected_before_request(
    monkeypatch: pytest.MonkeyPatch,
    schema: dict[str, object],
    error_path: str,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)
    tool = ToolDefinition(
        name="query_order_status",
        description="Query an order",
        input_schema=schema,
    )

    with pytest.raises(ValueError, match=error_path):
        await gateway.next_step(
            messages=[Message(role="user", content="Order O1001")],
            tools=[tool],
        )

    assert client.responses.create_calls == []


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("allOf", [{"type": "string"}]),
        ("oneOf", [{"type": "string"}]),
        ("not", {"type": "string"}),
        ("dependentRequired", {"value": ["other"]}),
        ("dependentSchemas", {"value": {"type": "string"}}),
        ("if", {"type": "string"}),
        ("then", {"type": "string"}),
        ("else", {"type": "string"}),
        ("definitions", {}),
        ("patternProperties", {}),
        ("prefixItems", [{"type": "string"}]),
        ("contains", {"type": "string"}),
        ("propertyNames", {"type": "string"}),
        ("unevaluatedProperties", False),
        ("unevaluatedItems", False),
        ("contentSchema", {"type": "string"}),
        ("default", "value"),
        ("examples", ["value"]),
        ("const", "value"),
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_rejects_explicitly_unsupported_schema_keywords(
    monkeypatch: pytest.MonkeyPatch,
    keyword: str,
    value: object,
) -> None:
    await assert_schema_rejected_before_request(
        monkeypatch,
        strict_tool_schema({keyword: value}),
        rf"\$\.properties\.value\.{keyword}",
    )


@pytest.mark.asyncio
async def test_responses_gateway_rejects_unknown_schema_keyword_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await assert_schema_rejected_before_request(
        monkeypatch,
        strict_tool_schema({"x-course-extension": True}),
        r"\$\.properties\.value\.x-course-extension",
    )


@pytest.mark.parametrize(
    ("schema", "error_path"),
    [
        (
            strict_tool_schema({"anyOf": [{"default": "value"}]}),
            r"\$\.properties\.value\.anyOf\[0\]\.default",
        ),
        (
            {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
                "$defs": {"Address": {"default": "value"}},
            },
            r"\$\.\$defs\.Address\.default",
        ),
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_reports_indexed_and_named_schema_paths(
    monkeypatch: pytest.MonkeyPatch,
    schema: dict[str, object],
    error_path: str,
) -> None:
    await assert_schema_rejected_before_request(monkeypatch, schema, error_path)


@pytest.mark.parametrize(
    ("schema", "error_path"),
    [
        (
            {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
                "anyOf": [],
            },
            r"\$\.anyOf",
        ),
        (strict_tool_schema({"type": "array", "items": []}), r"\.items"),
        (strict_tool_schema({"anyOf": {}}), r"\.anyOf"),
        (
            {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
                "$defs": [],
            },
            r"\$\.\$defs",
        ),
        (strict_tool_schema({"$ref": 1}), r"\.\$ref"),
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_rejects_invalid_schema_container_shapes(
    monkeypatch: pytest.MonkeyPatch,
    schema: dict[str, object],
    error_path: str,
) -> None:
    await assert_schema_rejected_before_request(monkeypatch, schema, error_path)


@pytest.mark.parametrize(
    ("property_schema", "error_path"),
    [
        ({"type": "string", "format": "uri"}, r"\.format"),
        ({"type": "boolean", "format": "date"}, r"\.format"),
        ({"type": "boolean", "pattern": "true|false"}, r"\.pattern"),
        ({"type": "string", "minimum": 0}, r"\.minimum"),
        (
            {
                "type": "array",
                "items": {"type": "string"},
                "maxLength": 3,
            },
            r"\.maxLength",
        ),
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_rejects_invalid_formats_and_type_constraints(
    monkeypatch: pytest.MonkeyPatch,
    property_schema: dict[str, object],
    error_path: str,
) -> None:
    await assert_schema_rejected_before_request(
        monkeypatch,
        strict_tool_schema(property_schema),
        rf"\$\.properties\.value{error_path}",
    )


@pytest.mark.parametrize(
    "format_name",
    ["date-time", "time", "date", "duration", "email", "hostname", "ipv4", "ipv6", "uuid"],
)
@pytest.mark.asyncio
async def test_responses_gateway_accepts_documented_string_formats(
    monkeypatch: pytest.MonkeyPatch,
    format_name: str,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)
    tool = ToolDefinition(
        name="query_order_status",
        description="Query an order",
        input_schema=strict_tool_schema({"type": "string", "format": format_name}),
    )

    await gateway.next_step(
        messages=[Message(role="user", content="Order O1001")], tools=[tool]
    )

    assert len(client.responses.create_calls) == 1


@pytest.mark.parametrize(
    "property_schema",
    [
        {"type": "string", "minLength": 1, "maxLength": 80, "pattern": ".+"},
        {
            "type": "number",
            "multipleOf": 0.5,
            "minimum": 0,
            "maximum": 10,
            "exclusiveMinimum": -1,
            "exclusiveMaximum": 11,
        },
        {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string"}},
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_accepts_documented_type_constraints(
    monkeypatch: pytest.MonkeyPatch,
    property_schema: dict[str, object],
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)
    tool = ToolDefinition(
        name="query_order_status",
        description="Query an order",
        input_schema=strict_tool_schema(property_schema),
    )

    await gateway.next_step(
        messages=[Message(role="user", content="Order O1001")], tools=[tool]
    )

    assert len(client.responses.create_calls) == 1


@pytest.mark.parametrize(
    "reference",
    ["#/$defs/Missing", "#/definitions/Address", "https://example.com/Address"],
)
@pytest.mark.asyncio
async def test_responses_gateway_rejects_unresolved_or_unsupported_refs(
    monkeypatch: pytest.MonkeyPatch,
    reference: str,
) -> None:
    await assert_schema_rejected_before_request(
        monkeypatch,
        strict_tool_schema({"$ref": reference}),
        r"\$\.properties\.value\.\$ref",
    )


@pytest.mark.asyncio
async def test_responses_gateway_rejects_empty_any_of_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await assert_schema_rejected_before_request(
        monkeypatch,
        strict_tool_schema({"anyOf": []}),
        r"\$\.properties\.value\.anyOf",
    )


@pytest.mark.asyncio
async def test_responses_gateway_accepts_recursive_local_defs_and_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)
    tool = ToolDefinition(
        name="query_order_status",
        description="Query an order",
        input_schema={
            "type": "object",
            "properties": {"node": {"$ref": "#/$defs/Node"}},
            "required": ["node"],
            "additionalProperties": False,
            "$defs": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "next": {
                            "anyOf": [
                                {"type": "null"},
                                {"$ref": "#/$defs/Node"},
                            ]
                        },
                    },
                    "required": ["value", "next"],
                    "additionalProperties": False,
                }
            },
        },
    )

    await gateway.next_step(
        messages=[Message(role="user", content="Order O1001")], tools=[tool]
    )

    assert len(client.responses.create_calls) == 1


@pytest.mark.parametrize(
    "schema",
    [
        {
            "type": "object",
            "title": "Order delivery",
            "description": "A strict nested object and array.",
            "properties": {
                "destinations": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": ["string", "null"],
                                "minLength": 1,
                                "maxLength": 80,
                                "pattern": ".+",
                                "format": "hostname",
                            },
                            "priority": {
                                "type": "number",
                                "multipleOf": 0.5,
                                "minimum": 0,
                                "maximum": 10,
                                "exclusiveMinimum": -1,
                                "exclusiveMaximum": 11,
                            },
                        },
                        "required": ["city", "priority"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["destinations"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "delivery": {
                    "anyOf": [
                        {"type": "string", "enum": ["collect"]},
                        {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                            "additionalProperties": False,
                        },
                    ]
                }
            },
            "required": ["delivery"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {"address": {"$ref": "#/$defs/Address"}},
            "required": ["address"],
            "additionalProperties": False,
            "$defs": {
                "Address": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                    "additionalProperties": False,
                }
            },
        },
    ],
)
@pytest.mark.asyncio
async def test_responses_gateway_accepts_course_supported_strict_schemas(
    monkeypatch: pytest.MonkeyPatch,
    schema: dict[str, object],
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)
    tool = ToolDefinition(
        name="query_order_status",
        description="Query an order",
        input_schema=schema,
    )

    await gateway.next_step(
        messages=[Message(role="user", content="Order O1001")], tools=[tool]
    )

    assert len(client.responses.create_calls) == 1


@pytest.mark.asyncio
async def test_responses_gateway_uses_native_structured_output_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)

    result = await gateway.parse_structured(
        messages=[Message(role="user", content="Return a bounded answer")],
        text_format=StructuredAnswer,
    )

    assert result == StructuredAnswer(answer="bounded")
    assert client.responses.parse_calls == [
        {
            "model": "test-model",
            "input": [{"role": "user", "content": "Return a bounded answer"}],
            "text_format": StructuredAnswer,
        }
    ]


@pytest.mark.asyncio
async def test_responses_gateway_fails_when_parsed_output_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    client = NoNetworkClient()
    gateway = OpenAIResponsesGateway.from_environment(client=client)

    async def parse_without_output(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(output_parsed=None)

    client.responses.parse = parse_without_output

    with pytest.raises(ValueError, match="parsed output"):
        await gateway.parse_structured(
            messages=[Message(role="user", content="Return a bounded answer")],
            text_format=StructuredAnswer,
        )


@pytest.mark.asyncio
async def test_agents_runner_uses_sdk_run_with_sensitive_tracing_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_live_environment(monkeypatch)
    calls: dict[str, object] = {}

    class FakeRunner:
        @staticmethod
        async def run(agent: object, prompt: str, *, run_config: object) -> str:
            calls.update(agent=agent, prompt=prompt, run_config=run_config)
            return "result"

    runner = OpenAIAgentsRunner.from_environment(runner=FakeRunner)
    result = await runner.run("Hello", instructions="Stay bounded")

    assert result == "result"
    assert calls["prompt"] == "Hello"
    assert calls["agent"].model == "test-model"
    assert calls["agent"].instructions == "Stay bounded"
    assert calls["run_config"].trace_include_sensitive_data is False
