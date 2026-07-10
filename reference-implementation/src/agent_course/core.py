"""Provider-neutral contracts shared by the course implementation."""

from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class FrozenModel(BaseModel):
    """Base class for immutable boundary values."""

    model_config = ConfigDict(frozen=True)


class Message(FrozenModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None


class ToolDefinition(FrozenModel):
    name: str
    description: str
    input_schema: dict[str, JsonValue]


class ToolCall(FrozenModel):
    id: str
    name: str
    arguments: dict[str, JsonValue]


class ModelUsage(FrozenModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class StopReason(StrEnum):
    COMPLETED = "completed"
    TOOL_CALLS = "tool_calls"
    MAX_TURNS = "max_turns"
    MAX_TOOL_CALLS = "max_tool_calls"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    TIMEOUT = "timeout"
    REPEATED_TOOL_CALL = "repeated_tool_call"
    MODEL_ERROR = "model_error"
    PERMISSION_DENIED = "permission_denied"
    POLICY_DENIED = "policy_denied"


class ModelStep(FrozenModel):
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: ModelUsage = Field(default_factory=ModelUsage)
    stop_reason: StopReason = StopReason.COMPLETED


class ToolResult(FrozenModel):
    name: str
    code: str
    success: bool
    output: JsonValue | None = None
    error: str | None = None
    call_id: str | None = None


class RunLimits(FrozenModel):
    max_turns: int = Field(gt=0)
    max_tool_calls: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)


class PermissionDeniedError(Exception):
    """Raised when trusted run context lacks a required permission."""

    def __init__(self, permission: str) -> None:
        self.permission = permission
        super().__init__(f"missing required permission: {permission}")


class RunContext(FrozenModel):
    user_id: str
    tenant_id: str
    request_id: str
    permissions: frozenset[str]

    @field_validator("user_id", "tenant_id", "request_id")
    @classmethod
    def trusted_identifiers_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("trusted identifiers must be nonblank")
        return value

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise PermissionDeniedError(permission)


@runtime_checkable
class ModelGateway(Protocol):
    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelStep: ...
