"""Deterministic offline model fixtures used by course tests and labs."""

from agent_course.core import (
    Message,
    ModelContinuation,
    ModelStep,
    StopReason,
    ToolCall,
    ToolDefinition,
)

PLAIN_ANSWER_FIXTURE = "什么是 Agent？"
ORDER_QUERY_FIXTURE = "查询订单 O1001"
TIMEOUT_FIXTURE = "[fixture:timeout]"
INVALID_OUTPUT_FIXTURE = "[fixture:invalid-output]"
REPEATED_CALL_FIXTURE = "[fixture:repeated-order-call]"

_ORDER_TOOL = "query_order_status"
_ORDER_ID = "O1001"
_PLAIN_ANSWER = "Agent 是在边界内使用模型、工具和状态完成任务的应用程序。"
_ORDER_ANSWER = "订单 O1001 当前状态为 shipped。"


class ModelTimeoutError(TimeoutError):
    """Explicit deterministic model timeout fixture."""


class InvalidModelOutputError(ValueError):
    """Explicit deterministic invalid-output fixture."""


class ToolUnavailableError(ValueError):
    """Raised when a fixture needs a tool the caller did not provide."""


class FakeModelGateway:
    """Select fixed outputs solely from model-visible message text."""

    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
    ) -> ModelStep:
        prompt = self._latest_user_message(messages)

        if prompt == TIMEOUT_FIXTURE:
            raise ModelTimeoutError("deterministic timeout fixture")
        if prompt == INVALID_OUTPUT_FIXTURE:
            raise InvalidModelOutputError("deterministic invalid output fixture")
        if prompt == ORDER_QUERY_FIXTURE and self._has_order_tool_result(messages):
            return ModelStep(content=_ORDER_ANSWER)
        if prompt in {ORDER_QUERY_FIXTURE, REPEATED_CALL_FIXTURE}:
            self._require_tool(_ORDER_TOOL, tools)
            return ModelStep(
                tool_calls=(
                    ToolCall(
                        id="fake-query-order-status-O1001",
                        name=_ORDER_TOOL,
                        arguments={"order_id": _ORDER_ID},
                    ),
                ),
                stop_reason=StopReason.TOOL_CALLS,
            )

        return ModelStep(content=_PLAIN_ANSWER)

    @staticmethod
    def _latest_user_message(messages: list[Message]) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return message.content
        return ""

    @staticmethod
    def _require_tool(name: str, tools: list[ToolDefinition]) -> None:
        if name not in {tool.name for tool in tools}:
            raise ToolUnavailableError(f"required tool is unavailable: {name}")

    @staticmethod
    def _has_order_tool_result(messages: list[Message]) -> bool:
        latest_user_index = max(
            index
            for index, message in enumerate(messages)
            if message.role == "user"
        )
        return any(
            message.role == "tool"
            and message.tool_call_id == "fake-query-order-status-O1001"
            for message in messages[latest_user_index + 1 :]
        )
