"""Shared model gateway contracts and live-environment gate."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from agent_course.core import ModelGateway


class LiveConfigurationError(RuntimeError):
    """Raised before constructing a live adapter with unsafe configuration."""


@dataclass(frozen=True, slots=True)
class LiveSettings:
    api_key: str
    model: str


def load_live_settings(
    environment: Mapping[str, str] | None = None,
) -> LiveSettings:
    """Require an exact opt-in plus nonblank key and model values."""

    values = os.environ if environment is None else environment
    missing: list[str] = []

    if values.get("AGENT_COURSE_LIVE_TESTS") != "1":
        missing.append("AGENT_COURSE_LIVE_TESTS=1")

    api_key = values.get("OPENAI_API_KEY", "")
    if not api_key.strip():
        missing.append("OPENAI_API_KEY must be non-empty")

    model = values.get("OPENAI_MODEL", "")
    if not model.strip():
        missing.append("OPENAI_MODEL must be non-empty")

    if missing:
        raise LiveConfigurationError(
            "live adapters are disabled; required configuration: " + ", ".join(missing)
        )

    return LiveSettings(api_key=api_key.strip(), model=model.strip())


__all__ = [
    "LiveConfigurationError",
    "LiveSettings",
    "ModelGateway",
    "load_live_settings",
]
