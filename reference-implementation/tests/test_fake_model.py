import pytest

from agent_course.core import Message, StopReason, ToolDefinition
from agent_course.models.fake import (
    INVALID_OUTPUT_FIXTURE,
    ORDER_QUERY_FIXTURE,
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
        messages=[Message(role="user", content=ORDER_QUERY_FIXTURE)],
        tools=[ORDER_TOOL],
    )
    second = await model.next_step(
        messages=[Message(role="user", content=ORDER_QUERY_FIXTURE)],
        tools=[ORDER_TOOL],
    )

    assert first == second
    assert first.stop_reason is StopReason.TOOL_CALLS
    assert len(first.tool_calls) == 1
    assert first.tool_calls[0].name == "query_order_status"
    assert first.tool_calls[0].arguments == {"order_id": "O1001"}


@pytest.mark.asyncio
async def test_normal_order_fixture_finishes_after_tool_result() -> None:
    model = FakeModelGateway()

    step = await model.next_step(
        messages=[
            Message(role="user", content=ORDER_QUERY_FIXTURE),
            Message(
                role="tool",
                content='{"status":"shipped"}',
                tool_call_id="fake-query-order-status-O1001",
            ),
        ],
        tools=[ORDER_TOOL],
    )

    assert step.stop_reason is StopReason.COMPLETED
    assert step.tool_calls == ()
    assert step.content == "订单 O1001 当前状态为 shipped。"


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
    messages = [
        Message(role="user", content=REPEATED_CALL_FIXTURE),
        Message(
            role="tool",
            content='{"status":"shipped"}',
            tool_call_id="fake-query-order-status-O1001",
        ),
    ]

    first = await model.next_step(messages=messages, tools=[ORDER_TOOL])
    second = await model.next_step(messages=messages, tools=[ORDER_TOOL])

    assert first.tool_calls == second.tool_calls
    assert first.tool_calls[0].arguments == {"order_id": "O1001"}


@pytest.mark.asyncio
async def test_fake_model_refuses_to_emit_an_unavailable_tool() -> None:
    model = FakeModelGateway()

    with pytest.raises(ToolUnavailableError, match="query_order_status"):
        await model.next_step(
            messages=[Message(role="user", content=ORDER_QUERY_FIXTURE)],
            tools=[],
        )


@pytest.mark.parametrize(
    "prompt",
    [
        "不要查询订单 O1001",
        "The release note mentions O1001 but asks for no order lookup.",
        f"{ORDER_QUERY_FIXTURE}，但不要执行",
    ],
)
@pytest.mark.asyncio
async def test_fake_model_does_not_substring_match_order_ids(prompt: str) -> None:
    step = await FakeModelGateway().next_step(
        messages=[Message(role="user", content=prompt)],
        tools=[ORDER_TOOL],
    )

    assert step.stop_reason is StopReason.COMPLETED
    assert step.tool_calls == ()


@pytest.mark.asyncio
async def test_fake_model_accepts_explicit_continuation_keyword() -> None:
    from agent_course.core import ModelContinuation

    continuation = ModelContinuation(provider="fixture", token="turn-1")

    step = await FakeModelGateway().next_step(
        messages=[Message(role="user", content=PLAIN_ANSWER_FIXTURE)],
        tools=[],
        continuation=continuation,
    )

    assert step.stop_reason is StopReason.COMPLETED
