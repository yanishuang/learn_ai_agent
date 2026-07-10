"""Application composition and in-memory agent run lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field

from agent_course.agents.runner import AgentResult
from agent_course.core import FrozenModel, JsonValue, RunContext, RunLimits


class AgentRunner(Protocol):
    async def run(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
        *,
        session_id: str | None = None,
    ) -> AgentResult: ...


class Retriever(Protocol):
    def search(
        self,
        query: str,
        context: RunContext,
        top_k: int,
    ) -> list[Any]: ...


class ResearchWorkflow(Protocol):
    def start(self, topic: str, context: RunContext) -> Any: ...

    def approve(
        self,
        run_id: str,
        decision: Any,
        context: RunContext,
    ) -> Any: ...

    def resume(self, run_id: str, context: RunContext) -> Any: ...


class AgentRunRecord(FrozenModel):
    """Server-owned state for one synchronous API run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    request_id: str
    tenant_id: str
    user_id: str
    question: str
    session_id: str | None = None
    status: Literal["running", "completed", "failed"]
    result: AgentResult | None = None
    error: str | None = None


class AgentRunEvent(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int
    type: str
    data: dict[str, JsonValue] = Field(default_factory=dict)


@dataclass(slots=True)
class CourseApplication:
    """Compose course services without binding to their concrete implementations."""

    agent_runner: AgentRunner
    retriever: Retriever
    workflow: ResearchWorkflow
    _runs: dict[str, AgentRunRecord] = field(default_factory=dict, init=False)
    _events: dict[str, list[AgentRunEvent]] = field(default_factory=dict, init=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    async def run_agent(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
        *,
        session_id: str | None = None,
    ) -> AgentResult:
        return await self.agent_runner.run(
            question,
            context,
            limits,
            session_id=session_id,
        )

    async def create_agent_run(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
        *,
        session_id: str | None = None,
    ) -> AgentRunRecord:
        run_id = uuid4().hex
        running = AgentRunRecord(
            run_id=run_id,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            question=question,
            session_id=session_id,
            status="running",
        )
        with self._lock:
            self._runs[run_id] = running
            self._events[run_id] = [
                AgentRunEvent(sequence=1, type="run.created"),
                AgentRunEvent(sequence=2, type="run.started"),
            ]

        try:
            result = await self.run_agent(
                question,
                context,
                limits,
                session_id=session_id,
            )
        except Exception as error:
            failed = running.model_copy(
                update={
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            with self._lock:
                self._runs[run_id] = failed
                self._append_event(
                    run_id,
                    "run.failed",
                    {"error_type": type(error).__name__},
                )
            raise

        completed = running.model_copy(update={"status": "completed", "result": result})
        with self._lock:
            self._runs[run_id] = completed
            self._append_event(
                run_id,
                "run.completed",
                {"stop_reason": result.stop_reason.value},
            )
        return completed

    def get_agent_run(
        self,
        run_id: str,
        context: RunContext,
    ) -> AgentRunRecord | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or not self._can_read(run, context):
                return None
            return run

    def get_agent_run_events(
        self,
        run_id: str,
        context: RunContext,
    ) -> tuple[AgentRunEvent, ...] | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or not self._can_read(run, context):
                return None
            return tuple(self._events[run_id])

    def search(
        self,
        query: str,
        context: RunContext,
        top_k: int = 3,
    ) -> list[Any]:
        return self.retriever.search(query, context, top_k)

    def start_research(self, topic: str, context: RunContext) -> Any:
        return self.workflow.start(topic, context)

    def approve_research(
        self,
        run_id: str,
        decision: Any,
        context: RunContext,
    ) -> Any:
        return self.workflow.approve(run_id, decision, context)

    def resume_research(self, run_id: str, context: RunContext) -> Any:
        return self.workflow.resume(run_id, context)

    def _append_event(
        self,
        run_id: str,
        event_type: str,
        data: dict[str, JsonValue],
    ) -> None:
        events = self._events[run_id]
        events.append(
            AgentRunEvent(
                sequence=len(events) + 1,
                type=event_type,
                data=data,
            )
        )

    @staticmethod
    def _can_read(run: AgentRunRecord, context: RunContext) -> bool:
        return run.tenant_id == context.tenant_id and run.user_id == context.user_id


__all__ = [
    "AgentRunEvent",
    "AgentRunRecord",
    "AgentRunner",
    "CourseApplication",
    "ResearchWorkflow",
    "Retriever",
]
