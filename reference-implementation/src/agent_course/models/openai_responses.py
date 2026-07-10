"""Low-level OpenAI Responses adapter for application-owned tool loops."""

import json
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from openai import AsyncOpenAI
from pydantic import BaseModel

from agent_course.core import (
    Message,
    ModelContinuation,
    ModelStep,
    ModelUsage,
    StopReason,
    ToolCall,
    ToolDefinition,
)
from agent_course.models.base import load_live_settings

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)
_CONTINUATION_PROVIDER = "openai_responses"


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
        *,
        continuation: ModelContinuation | None = None,
    ) -> ModelStep:
        request: dict[str, object] = {
            "model": self.model,
            "input": [self._message_input(message) for message in messages],
            "tools": [self._tool_input(tool) for tool in tools],
        }
        if continuation is not None:
            if continuation.provider != _CONTINUATION_PROVIDER:
                raise ValueError(
                    "continuation provider must be "
                    f"{_CONTINUATION_PROVIDER!r}, got {continuation.provider!r}"
                )
            request["previous_response_id"] = continuation.token

        response = await self._client.responses.create(
            **request,
        )

        response_id = getattr(response, "id", None)
        if not isinstance(response_id, str) or not response_id.strip():
            raise ValueError("Responses API returned no usable response id")

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
            continuation=ModelContinuation(
                provider=_CONTINUATION_PROVIDER,
                token=response_id,
            ),
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
        _validate_strict_schema(tool.input_schema)
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


def _validate_strict_schema(schema: dict[str, object], path: str = "$") -> None:
    """Validate the documented strict-tool subset without changing the schema."""

    node_type = schema.get("type")
    object_keywords = {
        "properties",
        "patternProperties",
        "required",
        "additionalProperties",
        "dependentSchemas",
    }
    is_object = path == "$" or node_type == "object" or bool(object_keywords & schema.keys())

    if is_object:
        if node_type != "object":
            raise ValueError(f"strict tool schema {path}.type must be 'object'")

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"strict tool schema {path}.properties must be an object")

        if schema.get("additionalProperties") is not False:
            raise ValueError(
                f"strict tool schema {path}.additionalProperties must be false"
            )

        required = schema.get("required")
        if not isinstance(required, list) or not all(
            isinstance(name, str) for name in required
        ):
            raise ValueError(f"strict tool schema {path}.required must be an array")

        missing = [name for name in properties if name not in required]
        if missing:
            raise ValueError(
                f"strict tool schema {path}.required must include every property; "
                f"missing {missing!r}"
            )

    for keyword in (
        "properties",
        "patternProperties",
        "$defs",
        "definitions",
        "dependentSchemas",
    ):
        _validate_schema_map(schema, keyword, path)

    for keyword in ("anyOf", "oneOf", "allOf", "prefixItems"):
        _validate_schema_list(schema, keyword, path)

    if "items" in schema:
        _validate_schema_node(schema["items"], f"{path}.items")
    elif node_type == "array":
        raise ValueError(f"strict tool schema {path}.items must be an object")

    for keyword in ("not", "if", "then", "else", "contains", "propertyNames"):
        if keyword in schema:
            _validate_schema_node(schema[keyword], f"{path}.{keyword}")


def _validate_schema_map(schema: dict[str, object], keyword: str, path: str) -> None:
    children = schema.get(keyword)
    if children is None:
        return
    if not isinstance(children, dict):
        raise ValueError(f"strict tool schema {path}.{keyword} must be an object")

    for name, child in children.items():
        _validate_schema_node(child, f"{path}.{keyword}.{name}")


def _validate_schema_list(schema: dict[str, object], keyword: str, path: str) -> None:
    children = schema.get(keyword)
    if children is None:
        return
    if not isinstance(children, list):
        raise ValueError(f"strict tool schema {path}.{keyword} must be an array")

    for index, child in enumerate(children):
        _validate_schema_node(child, f"{path}.{keyword}[{index}]")


def _validate_schema_node(node: object, path: str) -> None:
    if not isinstance(node, dict):
        raise ValueError(f"strict tool schema {path} must be an object")
    _validate_strict_schema(node, path)
