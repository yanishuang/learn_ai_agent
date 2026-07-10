import pytest

from agent_course.core import Message, StopReason, ToolDefinition
from agent_course.models.fake import (
    INVALID_OUTPUT_FIXTURE,
    PLAIN_ANSWER_FIXTURE,
    REPEATED_CALL_FIXTURE,
    TIMEOUT_FIXTURE,
    FakeModelGateway,
    InvalidModelOutputError,
    ModelTimeoutError,
    ToolUnavailableError,
)


ORDER_TOOL = ToolDefinition(
    name="query_order_status",
    description="Query order status",
    input_schema={
        "type": "object",
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"],
        "additionalProperties": False,
    },
)


@pytest.mark.asyncio
async def test_fake_model_emits_deterministic_order_tool_call() -> None:
    model = FakeModelGateway()

    first = await model.next_step(
        messages=[Message(role="user", content="查询订单 O1001")],
        tools=[ORDER_TOOL],
    )
    second = await model.next_step(
        messages=[Message(role="user", content="查询订单 O1001")],
        tools=[ORDER_TOOL],
    )

    assert first == second
    assert first.stop_reason is StopReason.TOOL_CALLS
    assert len(first.tool_calls) == 1
    assert first.tool_calls[0].name == "query_order_status"
    assert first.tool_calls[0].arguments == {"order_id": "O1001"}


@pytest.mark.asyncio
async def test_fake_model_returns_deterministic_plain_answer() -> None:
    model = FakeModelGateway()

    first = await model.next_step(
        messages=[Message(role="user", content=PLAIN_ANSWER_FIXTURE)],
        tools=[],
    )
    second = await model.next_step(
        messages=[Message(role="user", content=PLAIN_ANSWER_FIXTURE)],
        tools=[],
    )

    assert first == second
    assert first.stop_reason is StopReason.COMPLETED
    assert first.tool_calls == ()
    assert first.content == "Agent 是在边界内使用模型、工具和状态完成任务的应用程序。"


@pytest.mark.asyncio
async def test_fake_model_injects_timeout_explicitly() -> None:
    model = FakeModelGateway()

    with pytest.raises(ModelTimeoutError, match="deterministic timeout"):
        await model.next_step(
            messages=[Message(role="user", content=TIMEOUT_FIXTURE)],
            tools=[],
        )


@pytest.mark.asyncio
async def test_fake_model_injects_invalid_output_explicitly() -> None:
    model = FakeModelGateway()

    with pytest.raises(InvalidModelOutputError, match="deterministic invalid output"):
        await model.next_step(
            messages=[Message(role="user", content=INVALID_OUTPUT_FIXTURE)],
            tools=[],
        )


@pytest.mark.asyncio
async def test_fake_model_injects_repeated_call_without_state_or_randomness() -> None:
    model = FakeModelGateway()
    messages = [Message(role="user", content=REPEATED_CALL_FIXTURE)]

    first = await model.next_step(messages=messages, tools=[ORDER_TOOL])
    second = await model.next_step(messages=messages, tools=[ORDER_TOOL])

    assert first.tool_calls == second.tool_calls
    assert first.tool_calls[0].arguments == {"order_id": "O1001"}


@pytest.mark.asyncio
async def test_fake_model_refuses_to_emit_an_unavailable_tool() -> None:
    model = FakeModelGateway()

    with pytest.raises(ToolUnavailableError, match="query_order_status"):
        await model.next_step(
            messages=[Message(role="user", content="查询订单 O1001")],
            tools=[],
        )
