"""Identity-scoped in-memory conversation sessions."""

from pydantic import ConfigDict, field_validator

from agent_course.core import FrozenModel, Message, RunContext


class SessionKey(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    user_id: str
    session_id: str

    @field_validator("tenant_id", "user_id", "session_id")
    @classmethod
    def values_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("session key values must be nonblank")
        return value

    @classmethod
    def from_context(cls, context: RunContext, session_id: str) -> "SessionKey":
        return cls(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            session_id=session_id,
        )


class InMemorySessionStore:
    def __init__(self) -> None:
        self._messages: dict[SessionKey, list[Message]] = {}

    def load(self, key: SessionKey) -> list[Message]:
        return list(self._messages.get(key, ()))

    def append(self, key: SessionKey, messages: list[Message]) -> None:
        self._messages.setdefault(key, []).extend(messages)


__all__ = ["InMemorySessionStore", "SessionKey"]
