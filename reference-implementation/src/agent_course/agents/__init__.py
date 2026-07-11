"""Agent runtime adapters."""

from typing import Any

__all__ = ["OpenAIAgentsRunner"]


def __getattr__(name: str) -> Any:
    if name == "OpenAIAgentsRunner":
        from agent_course.agents.openai_agents import OpenAIAgentsRunner

        return OpenAIAgentsRunner
    raise AttributeError(name)
