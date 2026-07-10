from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from agent_course.agents.openai_agents import OpenAIAgentsRunner
from agent_course.core import (
    Message,
    ModelContinuation,
    StopReason,
    ToolDefinition,
)
from agent_course.models.base import LiveConfigurationError
from agent_course.models.openai_responses import OpenAIResponsesGateway


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
                    ),
                    SimpleNamespace(
                        id="response-complete",
                        output=[],
                        output_text="Order O1001 is shipped.",
                        usage=None,
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
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
            r"\$\.additionalProperties",
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
