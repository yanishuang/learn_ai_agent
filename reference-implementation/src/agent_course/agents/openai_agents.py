"""OpenAI Agents SDK-managed live run path."""

from dataclasses import dataclass
from typing import Any

from agents import Agent, RunConfig, Runner

from agent_course.models.base import load_live_settings


@dataclass(frozen=True, slots=True)
class OpenAIAgentsRunner:
    """Keep the Agents SDK in charge of the run lifecycle."""

    model: str
    _runner: Any = Runner
    trace_include_sensitive_data: bool = False

    @classmethod
    def from_environment(
        cls,
        *,
        runner: Any = Runner,
    ) -> "OpenAIAgentsRunner":
        settings = load_live_settings()
        return cls(model=settings.model, _runner=runner)

    async def run(
        self,
        prompt: str,
        *,
        instructions: str = "Complete the task within the configured boundaries.",
    ) -> Any:
        agent = Agent(
            name="Agent Course Reference",
            instructions=instructions,
            model=self.model,
        )
        run_config = RunConfig(
            trace_include_sensitive_data=self.trace_include_sensitive_data
        )
        return await self._runner.run(agent, prompt, run_config=run_config)
