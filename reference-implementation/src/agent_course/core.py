"""Provider-neutral contracts shared by the course implementation."""

from enum import StrEnum
from typing import Literal, NoReturn, Protocol, runtime_checkable

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


class _FrozenJsonDict(dict[str, JsonValue]):
    """JSON object that cannot be changed after crossing an agent boundary."""

    def __init__(self, values: dict[str, JsonValue]) -> None:
        dict.__init__(self, values)

    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> NoReturn:
        raise TypeError("JSON argument values are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class _FrozenJsonList(list[JsonValue]):
    """JSON array that cannot be changed after crossing an agent boundary."""

    def __init__(self, values: list[JsonValue]) -> None:
        list.__init__(self, values)

    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> NoReturn:
        raise TypeError("JSON argument values are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable


def _freeze_json_value(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return _FrozenJsonDict(
            {key: _freeze_json_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return _FrozenJsonList([_freeze_json_value(item) for item in value])
    return value


class ToolCall(FrozenModel):
    id: str
    name: str
    arguments: dict[str, JsonValue]

    @field_validator("arguments")
    @classmethod
    def arguments_are_deeply_immutable(
        cls, value: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        return _FrozenJsonDict(
            {key: _freeze_json_value(item) for key, item in value.items()}
        )


class ModelContinuation(FrozenModel):
    provider: str
    token: str

    @field_validator("provider", "token")
    @classmethod
    def values_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("continuation values must be nonblank")
        return value


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
    MODEL_INCOMPLETE = "model_incomplete"
    CONTENT_FILTER = "content_filter"
    CANCELLED = "cancelled"
    TOOL_ERROR = "tool_error"
    PERMISSION_DENIED = "permission_denied"
    POLICY_DENIED = "policy_denied"


class ModelStep(FrozenModel):
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    continuation: ModelContinuation | None = None
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
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep: ...
