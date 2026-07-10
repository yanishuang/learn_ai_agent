"""Low-level OpenAI Responses adapter for application-owned tool loops."""

import json
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from openai import AsyncOpenAI
from pydantic import BaseModel

from agent_course.core import (
    Message,
    ModelStep,
    ModelUsage,
    StopReason,
    ToolCall,
    ToolDefinition,
)
from agent_course.models.base import load_live_settings

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class OpenAIResponsesGateway:
    """Translate course contracts to the public async Responses API."""

    model: str
    _client: Any

    @classmethod
    def from_environment(
        cls,
        *,
        client: AsyncOpenAI | Any | None = None,
    ) -> "OpenAIResponsesGateway":
        settings = load_live_settings()
        configured_client = client or AsyncOpenAI(api_key=settings.api_key)
        return cls(model=settings.model, _client=configured_client)

    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelStep:
        response = await self._client.responses.create(
            model=self.model,
            input=[self._message_input(message) for message in messages],
            tools=[self._tool_input(tool) for tool in tools],
        )

        tool_calls = tuple(
            self._tool_call(item)
            for item in response.output
            if getattr(item, "type", None) == "function_call"
        )
        usage = getattr(response, "usage", None)
        model_usage = ModelUsage(
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )
        return ModelStep(
            content=response.output_text or None,
            tool_calls=tool_calls,
            usage=model_usage,
            stop_reason=(StopReason.TOOL_CALLS if tool_calls else StopReason.COMPLETED),
        )

    async def parse_structured(
        self,
        messages: list[Message],
        text_format: type[StructuredOutput],
    ) -> StructuredOutput:
        """Use native Pydantic parsing and return the validated output."""

        response = await self._client.responses.parse(
            model=self.model,
            input=[self._message_input(message) for message in messages],
            text_format=text_format,
        )
        if response.output_parsed is None:
            raise ValueError("Responses API returned no parsed output")
        return cast(StructuredOutput, response.output_parsed)

    @staticmethod
    def _message_input(message: Message) -> dict[str, object]:
        if message.role == "tool":
            if not message.tool_call_id:
                raise ValueError("tool messages require tool_call_id")
            return {
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": message.content,
            }
        return {"role": message.role, "content": message.content}

    @staticmethod
    def _tool_input(tool: ToolDefinition) -> dict[str, object]:
        return {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
            "strict": True,
        }

    @staticmethod
    def _tool_call(item: object) -> ToolCall:
        try:
            arguments = json.loads(item.arguments)
        except (AttributeError, json.JSONDecodeError) as error:
            raise ValueError("Responses API returned invalid tool arguments") from error
        if not isinstance(arguments, dict):
            raise ValueError("Responses API tool arguments must be a JSON object")
        return ToolCall(
            id=item.call_id,
            name=item.name,
            arguments=arguments,
        )
