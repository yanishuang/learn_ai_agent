from typing import get_type_hints

import pytest
from pydantic import ValidationError

from agent_course.core import (
    Message,
    ModelGateway,
    ModelStep,
    PermissionDeniedError,
    RunContext,
    RunLimits,
    ToolCall,
    ToolDefinition,
    ToolResult,
)


@pytest.mark.parametrize(
    "model",
    [
        Message(role="user", content="hello"),
        ToolDefinition(name="lookup", description="Lookup", input_schema={}),
        ToolCall(id="call-1", name="lookup", arguments={}),
        ModelStep(content="hello"),
        ToolResult(name="lookup", code="OK", success=True, output={}),
        RunLimits(
            max_turns=1,
            max_tool_calls=1,
            max_output_tokens=1,
            timeout_seconds=0.1,
        ),
    ],
)
def test_core_models_are_frozen(model: object) -> None:
    with pytest.raises(ValidationError):
        model.__setattr__(next(iter(model.__class__.model_fields)), "changed")


@pytest.mark.parametrize("field", ["user_id", "tenant_id", "request_id"])
@pytest.mark.parametrize("value", ["", "   "])
def test_run_context_rejects_blank_trusted_identifiers(field: str, value: str) -> None:
    values = {
        "user_id": "user-1",
        "tenant_id": "tenant-1",
        "request_id": "request-1",
        "permissions": frozenset(),
    }
    values[field] = value

    with pytest.raises(ValidationError):
        RunContext(**values)


def test_run_context_allows_present_permission() -> None:
    context = RunContext(
        user_id="user-1",
        tenant_id="tenant-1",
        request_id="request-1",
        permissions=frozenset({"orders:read"}),
    )

    assert context.require("orders:read") is None


def test_run_context_raises_specific_error_for_missing_permission() -> None:
    context = RunContext(
        user_id="user-1",
        tenant_id="tenant-1",
        request_id="request-1",
        permissions=frozenset(),
    )

    with pytest.raises(PermissionDeniedError) as exc_info:
        context.require("orders:read")

    assert exc_info.value.permission == "orders:read"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_turns", 0),
        ("max_tool_calls", -1),
        ("max_output_tokens", 0),
        ("timeout_seconds", 0),
    ],
)
def test_run_limits_require_positive_values(field: str, value: int) -> None:
    values = {
        "max_turns": 1,
        "max_tool_calls": 1,
        "max_output_tokens": 1,
        "timeout_seconds": 0.1,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        RunLimits(**values)


def test_model_gateway_signature_is_async_and_stable() -> None:
    annotations = get_type_hints(ModelGateway.next_step)

    assert annotations["messages"] == list[Message]
    assert annotations["tools"] == list[ToolDefinition]
    assert annotations["return"] is ModelStep
