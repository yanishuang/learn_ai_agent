"""Minimal traces with sanitization enforced at the storage boundary."""

import re
from collections.abc import Mapping
from uuid import uuid4

from pydantic import ConfigDict, JsonValue

from agent_course.core import FrozenModel, RunContext

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "args",
        "arguments",
        "authorization",
        "cookie",
        "password",
        "secret",
        "token",
        "tool_args",
        "tool_arguments",
    }
)
_SENSITIVE_KEY_SUFFIXES = tuple(f"_{key}" for key in _SENSITIVE_KEYS)
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~-]+"),
)


class TraceEvent(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: str
    event_type: str
    attributes: dict[str, JsonValue]


class InMemoryTraceSink:
    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def start_trace(self, context: RunContext) -> str:
        trace_id = uuid4().hex
        self.record(
            trace_id,
            "run.started",
            {
                "request_id": context.request_id,
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
            },
        )
        return trace_id

    def record(
        self,
        trace_id: str,
        event_type: str,
        attributes: Mapping[str, object] | None = None,
    ) -> None:
        sanitized = _sanitize_mapping(attributes or {})
        self._events.append(
            TraceEvent(
                trace_id=trace_id,
                event_type=event_type,
                attributes=sanitized,
            )
        )

    def for_trace(self, trace_id: str) -> tuple[TraceEvent, ...]:
        return tuple(event for event in self._events if event.trace_id == trace_id)


def _sanitize_mapping(values: Mapping[str, object]) -> dict[str, JsonValue]:
    sanitized: dict[str, JsonValue] = {}
    for key, value in values.items():
        normalized = _normalize_key(key)
        if normalized in _SENSITIVE_KEYS or normalized.endswith(
            _SENSITIVE_KEY_SUFFIXES
        ):
            sanitized[key] = _REDACTED
        else:
            sanitized[key] = _sanitize_value(value)
    return sanitized


def _normalize_key(key: str) -> str:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    return re.sub(r"[^a-z0-9]+", "_", separated.casefold()).strip("_")


def _sanitize_value(value: object) -> JsonValue:
    if isinstance(value, Mapping):
        return _sanitize_mapping({str(key): item for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        sanitized = value
        for pattern in _SECRET_PATTERNS:
            sanitized = pattern.sub(_REDACTED, sanitized)
        return sanitized
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


__all__ = ["InMemoryTraceSink", "TraceEvent"]
