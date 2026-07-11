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
        max_output_tokens: int | None = None,
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
        if max_output_tokens is not None:
            if max_output_tokens <= 0:
                raise ValueError("max_output_tokens must be greater than zero")
            request["max_output_tokens"] = max_output_tokens

        response = await self._client.responses.create(
            **request,
        )

        response_id = getattr(response, "id", None)
        if not isinstance(response_id, str) or not response_id.strip():
            raise ValueError("Responses API returned no usable response id")

        terminal_reason = self._non_success_stop_reason(response)
        tool_calls = (
            ()
            if terminal_reason is not None
            else tuple(
                self._tool_call(item)
                for item in response.output
                if getattr(item, "type", None) == "function_call"
            )
        )
        usage = getattr(response, "usage", None)
        model_usage = ModelUsage(
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )
        return ModelStep(
            content=(response.output_text or None) if terminal_reason is None else None,
            tool_calls=tool_calls,
            continuation=ModelContinuation(
                provider=_CONTINUATION_PROVIDER,
                token=response_id,
            ),
            usage=model_usage,
            stop_reason=(
                terminal_reason
                or (StopReason.TOOL_CALLS if tool_calls else StopReason.COMPLETED)
            ),
        )

    @staticmethod
    def _non_success_stop_reason(response: object) -> StopReason | None:
        status = getattr(response, "status", None)
        if status == "completed":
            return None
        if status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None)
            if reason == "max_output_tokens":
                return StopReason.MAX_OUTPUT_TOKENS
            if reason == "content_filter":
                return StopReason.CONTENT_FILTER
            return StopReason.MODEL_INCOMPLETE
        if status == "failed":
            error = getattr(response, "error", None)
            if getattr(error, "code", None) in {
                "bio_policy",
                "image_content_policy_violation",
            }:
                return StopReason.CONTENT_FILTER
            return StopReason.MODEL_ERROR
        if status == "cancelled":
            return StopReason.CANCELLED
        if status in {"queued", "in_progress"}:
            return StopReason.MODEL_INCOMPLETE
        return StopReason.MODEL_ERROR

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


_SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "type",
        "title",
        "description",
        "enum",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "multipleOf",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minItems",
        "maxItems",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "anyOf",
        "$defs",
        "$ref",
    }
)
_SUPPORTED_TYPES = frozenset(
    {"string", "number", "boolean", "integer", "object", "array", "null"}
)
_NULLABLE_SCALAR_TYPES = frozenset(
    {"string", "number", "boolean", "integer", "null"}
)
_OBJECT_KEYWORDS = frozenset({"properties", "required", "additionalProperties"})
_METADATA_KEYWORDS = ("title", "description")
_STRING_CONSTRAINTS = ("minLength", "maxLength", "pattern", "format")
_NUMBER_CONSTRAINTS = (
    "multipleOf",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
)
_ARRAY_CONSTRAINTS = ("minItems", "maxItems")
_DOCUMENTED_FORMATS = frozenset(
    {"date-time", "time", "date", "duration", "email", "hostname", "ipv4", "ipv6", "uuid"}
)


def _validate_strict_schema(schema: dict[str, object], path: str = "$") -> None:
    """Validate the course's documented Structured Outputs schema subset."""

    _validate_schema_node(schema, path, root=True)
    _validate_local_references(schema, path)


def _validate_schema_node(node: object, path: str, *, root: bool = False) -> None:
    if not isinstance(node, dict):
        raise ValueError(f"strict tool schema {path} must be an object")

    unsupported_keywords = sorted(set(node) - _SUPPORTED_SCHEMA_KEYWORDS)
    if unsupported_keywords:
        raise ValueError(
            f"strict tool schema {path}.{unsupported_keywords[0]} is unsupported"
        )

    if root:
        if "anyOf" in node:
            raise ValueError(f"strict tool schema {path}.anyOf is unsupported at root")
        if node.get("type") != "object":
            raise ValueError(f"strict tool schema {path}.type must be 'object'")

    schema_types = _validate_schema_values(node, path)
    if "$ref" in node:
        _validate_reference_node(node, path)
    elif "anyOf" in node:
        _validate_any_of_node(node, path)
    else:
        if schema_types is None:
            raise ValueError(f"strict tool schema {path}.type is required")
        _validate_type_specific_constraints(node, schema_types, path)
        if _OBJECT_KEYWORDS & node.keys() and schema_types != {"object"}:
            raise ValueError(f"strict tool schema {path}.type must be 'object'")
        if schema_types == {"object"}:
            _validate_strict_object(node, path)
        if "items" in node and schema_types != {"array"}:
            raise ValueError(f"strict tool schema {path}.items requires type 'array'")
        if schema_types == {"array"} and "items" not in node:
            raise ValueError(f"strict tool schema {path}.items must be an object")

    _validate_schema_children(node, path)


def _validate_schema_values(
    schema: dict[str, object], path: str
) -> frozenset[str] | None:
    schema_types = None
    if "type" in schema:
        schema_types = _validate_type(schema["type"], path)

    for keyword in (*_METADATA_KEYWORDS, "pattern", "format"):
        if keyword in schema and not isinstance(schema[keyword], str):
            raise ValueError(f"strict tool schema {path}.{keyword} must be a string")

    if "enum" in schema and not isinstance(schema["enum"], list):
        raise ValueError(f"strict tool schema {path}.enum must be an array")
    if "$ref" in schema and not isinstance(schema["$ref"], str):
        raise ValueError(f"strict tool schema {path}.$ref must be a string")

    for keyword in _NUMBER_CONSTRAINTS:
        if keyword in schema and not _is_number(schema[keyword]):
            raise ValueError(f"strict tool schema {path}.{keyword} must be a number")

    for keyword in (*_STRING_CONSTRAINTS[:2], *_ARRAY_CONSTRAINTS):
        if keyword in schema and (
            not isinstance(schema[keyword], int)
            or isinstance(schema[keyword], bool)
            or schema[keyword] < 0
        ):
            raise ValueError(
                f"strict tool schema {path}.{keyword} must be a non-negative integer"
            )

    return schema_types


def _validate_type(value: object, path: str) -> frozenset[str]:
    if isinstance(value, str) and value in _SUPPORTED_TYPES:
        return frozenset({value})
    if (
        isinstance(value, list)
        and len(value) >= 2
        and "null" in value
        and all(isinstance(item, str) and item in _NULLABLE_SCALAR_TYPES for item in value)
    ):
        return frozenset(cast(list[str], value))
    raise ValueError(
        f"strict tool schema {path}.type must be a supported type or nullable scalar "
        "type array"
    )


def _validate_reference_node(schema: dict[str, object], path: str) -> None:
    _validate_exclusive_node_keywords(
        schema, path, "$ref", frozenset({"$ref", *_METADATA_KEYWORDS})
    )


def _validate_any_of_node(schema: dict[str, object], path: str) -> None:
    _validate_exclusive_node_keywords(
        schema, path, "anyOf", frozenset({"anyOf", *_METADATA_KEYWORDS})
    )


def _validate_exclusive_node_keywords(
    schema: dict[str, object], path: str, node_kind: str, allowed: frozenset[str]
) -> None:
    incompatible_keywords = sorted(set(schema) - allowed)
    if incompatible_keywords:
        raise ValueError(
            f"strict tool schema {path}.{incompatible_keywords[0]} cannot be combined "
            f"with {node_kind}"
        )


def _validate_type_specific_constraints(
    schema: dict[str, object], schema_types: frozenset[str], path: str
) -> None:
    _validate_constraint_types(schema, path, schema_types, _STRING_CONSTRAINTS, {"string"})
    _validate_constraint_types(
        schema, path, schema_types, _NUMBER_CONSTRAINTS, {"number", "integer"}
    )
    _validate_constraint_types(schema, path, schema_types, _ARRAY_CONSTRAINTS, {"array"})

    if "format" in schema and schema["format"] not in _DOCUMENTED_FORMATS:
        raise ValueError(
            f"strict tool schema {path}.format must be one of the documented formats"
        )


def _validate_constraint_types(
    schema: dict[str, object],
    path: str,
    schema_types: frozenset[str],
    constraints: tuple[str, ...],
    allowed_types: set[str],
) -> None:
    for keyword in constraints:
        if keyword in schema and not schema_types & allowed_types:
            type_names = "/".join(sorted(allowed_types))
            raise ValueError(
                f"strict tool schema {path}.{keyword} requires type {type_names!r}"
            )


def _validate_strict_object(schema: dict[str, object], path: str) -> None:
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

    missing = sorted(name for name in properties if name not in required)
    if missing:
        raise ValueError(
            f"strict tool schema {path}.required must include every property; "
            f"missing {missing!r}"
        )


def _validate_schema_children(schema: dict[str, object], path: str) -> None:
    if "properties" in schema:
        _validate_schema_map(schema["properties"], f"{path}.properties")
    if "items" in schema:
        _validate_schema_node(schema["items"], f"{path}.items")
    if "anyOf" in schema:
        _validate_schema_list(schema["anyOf"], f"{path}.anyOf")
    if "$defs" in schema:
        _validate_schema_map(schema["$defs"], f"{path}.$defs")


def _validate_local_references(schema: dict[str, object], path: str) -> None:
    definitions = schema.get("$defs", {})
    if not isinstance(definitions, dict):
        return
    _validate_schema_references(schema, path, frozenset(definitions))


def _validate_schema_references(
    schema: dict[str, object], path: str, definition_names: frozenset[str]
) -> None:
    if "$ref" in schema:
        reference = cast(str, schema["$ref"])
        _validate_local_reference(reference, path, definition_names)
    if "properties" in schema:
        _validate_schema_map_references(
            cast(dict[str, object], schema["properties"]),
            f"{path}.properties",
            definition_names,
        )
    if "items" in schema:
        _validate_schema_references(
            cast(dict[str, object], schema["items"]),
            f"{path}.items",
            definition_names,
        )
    if "anyOf" in schema:
        for index, child in enumerate(cast(list[dict[str, object]], schema["anyOf"])):
            _validate_schema_references(
                child, f"{path}.anyOf[{index}]", definition_names
            )
    if "$defs" in schema:
        _validate_schema_map_references(
            cast(dict[str, object], schema["$defs"]),
            f"{path}.$defs",
            definition_names,
        )


def _validate_local_reference(
    reference: str, path: str, definition_names: frozenset[str]
) -> None:
    prefix = "#/$defs/"
    if not reference.startswith(prefix):
        raise ValueError(
            f"strict tool schema {path}.$ref must use a local #/$defs/<name> reference"
        )

    definition_name = reference.removeprefix(prefix)
    if not definition_name or "/" in definition_name or definition_name not in definition_names:
        raise ValueError(
            f"strict tool schema {path}.$ref references an unknown local definition "
            f"{definition_name!r}"
        )


def _validate_schema_map_references(
    children: dict[str, object], path: str, definition_names: frozenset[str]
) -> None:
    for name in sorted(children):
        _validate_schema_references(
            cast(dict[str, object], children[name]),
            f"{path}.{name}",
            definition_names,
        )


def _validate_schema_map(children: object, path: str) -> None:
    if not isinstance(children, dict):
        raise ValueError(f"strict tool schema {path} must be an object")
    if not all(isinstance(name, str) for name in children):
        raise ValueError(f"strict tool schema {path} must use string names")
    for name in sorted(children):
        _validate_schema_node(children[name], f"{path}.{name}")


def _validate_schema_list(children: object, path: str) -> None:
    if not isinstance(children, list):
        raise ValueError(f"strict tool schema {path} must be an array")
    if not children:
        raise ValueError(f"strict tool schema {path} must contain at least one schema")
    for index, child in enumerate(children):
        _validate_schema_node(child, f"{path}[{index}]")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
