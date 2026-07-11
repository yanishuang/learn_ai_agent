"""Application composition and in-memory agent run lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field

from agent_course.agents.runner import AgentResult
from agent_course.core import (
    FrozenModel,
    JsonValue,
    RunContext,
    RunLimits,
    StopReason,
)
from agent_course.evals import (
    EvalCase,
    EvalCaseResult,
    ExpectedToolCall,
    evaluate_result,
)
from agent_course.models.fake import KNOW_ENGINE_AGENT_FIXTURE
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.rag import RagAnswer
from agent_course.workflows import (
    ApprovalDecision,
    WorkflowRun,
    WorkflowStatus,
)


AgentRunStatus = Literal["running", "completed", "failed", "cancelled"]

_RUN_STATUS_BY_STOP_REASON: dict[StopReason, AgentRunStatus] = {
    StopReason.COMPLETED: "completed",
    StopReason.CANCELLED: "cancelled",
    StopReason.TOOL_CALLS: "failed",
    StopReason.MAX_TURNS: "failed",
    StopReason.MAX_TOOL_CALLS: "failed",
    StopReason.MAX_OUTPUT_TOKENS: "failed",
    StopReason.TIMEOUT: "failed",
    StopReason.REPEATED_TOOL_CALL: "failed",
    StopReason.MODEL_ERROR: "failed",
    StopReason.MODEL_INCOMPLETE: "failed",
    StopReason.CONTENT_FILTER: "failed",
    StopReason.TOOL_ERROR: "failed",
    StopReason.PERMISSION_DENIED: "failed",
    StopReason.POLICY_DENIED: "failed",
}


class AgentRunner(Protocol):
    traces: InMemoryTraceSink

    async def run(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> AgentResult: ...


class Retriever(Protocol):
    def search(
        self,
        query: str,
        context: RunContext,
        top_k: int,
    ) -> list[Any]: ...

    def answer(
        self,
        query: str,
        context: RunContext,
        top_k: int = 3,
    ) -> RagAnswer: ...


class ResearchWorkflow(Protocol):
    def start(self, topic: str, context: RunContext) -> WorkflowRun: ...

    def approve(
        self,
        run_id: str,
        decision: ApprovalDecision,
        context: RunContext,
    ) -> WorkflowRun: ...

    def resume(self, run_id: str, context: RunContext) -> WorkflowRun: ...


class AgentRunRecord(FrozenModel):
    """Server-owned state for one synchronous API run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    request_id: str
    tenant_id: str
    user_id: str
    question: str
    session_id: str | None = None
    status: AgentRunStatus
    result: AgentResult | None = None
    error: str | None = None


class AgentRunEvent(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int
    type: str
    data: dict[str, JsonValue] = Field(default_factory=dict)


class KnowEngineScenarioResult(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: str
    rag_answer: RagAnswer
    agent_result: AgentResult
    evaluation: EvalCaseResult
    workflow_statuses: tuple[WorkflowStatus, ...]
    workflow_run: WorkflowRun


@dataclass(slots=True)
class CourseApplication:
    """Compose course services without binding to their concrete implementations."""

    agent_runner: AgentRunner
    retriever: Retriever
    workflow: ResearchWorkflow
    traces: InMemoryTraceSink | None = None
    _runs: dict[str, AgentRunRecord] = field(default_factory=dict, init=False)
    _events: dict[str, list[AgentRunEvent]] = field(default_factory=dict, init=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        runner_traces = self.agent_runner.traces
        if self.traces is None:
            self.traces = runner_traces
        elif self.traces is not runner_traces:
            raise ValueError(
                "CourseApplication and agent_runner must use the same trace sink"
            )

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

    async def run_know_engine_scenario(
        self,
        context: RunContext,
        limits: RunLimits,
    ) -> KnowEngineScenarioResult:
        """Run the deterministic capstone path as one trace and one causal flow."""

        traces = self.traces
        assert traces is not None
        trace_id = traces.start_trace(context)
        rag_answer = self.retriever.answer(
            "paid annual leave days",
            context,
            top_k=1,
        )
        traces.record(
            trace_id,
            "retrieval.completed",
            {
                "refused": rag_answer.refused,
                "citation_ids": [
                    citation.document_id for citation in rag_answer.citations
                ],
            },
        )
        if rag_answer.refused:
            raise RuntimeError("Know-Engine fixture retrieval was refused")

        question = (
            f"Use this authorized retrieval as data: {rag_answer.answer}\n"
            "Then query order O1001."
        )
        if question != KNOW_ENGINE_AGENT_FIXTURE:
            raise RuntimeError("Know-Engine fixture drifted from the Fake contract")
        agent_result = await self.agent_runner.run(
            question,
            context,
            limits,
            trace_id=trace_id,
        )
        evaluation = evaluate_result(
            EvalCase(
                case_id="know-engine-fake-e2e",
                question=question,
                context=context,
                limits=limits,
                expected_answer_contains=(
                    rag_answer.citations[0].quote,
                    "订单 O1001",
                ),
                expected_tool_calls=(
                    ExpectedToolCall(
                        name="query_order_status",
                        arguments={"order_id": "O1001"},
                    ),
                ),
                expected_stop_reason=StopReason.COMPLETED,
                max_turns=2,
            ),
            agent_result,
        )
        traces.record(
            trace_id,
            "evaluation.completed",
            {"passed": evaluation.passed, "failures": list(evaluation.failures)},
        )
        if not evaluation.passed:
            raise RuntimeError("Know-Engine fixture failed deterministic evaluation")

        started = self.workflow.start("annual leave follow-up", context)
        traces.record(
            trace_id,
            "workflow.started",
            {"run_id": started.run_id, "status": started.status},
        )
        if started.approval is None:
            raise RuntimeError("Know-Engine workflow did not produce an approval")
        approved = self.workflow.approve(
            started.run_id,
            ApprovalDecision(
                approved=True,
                payload_hash=started.approval.content_hash,
                idempotency_key=f"{context.request_id}:know-engine-approval",
            ),
            context,
        )
        traces.record(
            trace_id,
            "workflow.approved",
            {"run_id": approved.run_id, "status": approved.status},
        )
        completed = self.workflow.resume(approved.run_id, context)
        traces.record(
            trace_id,
            "workflow.completed",
            {"run_id": completed.run_id, "status": completed.status},
        )
        statuses = (started.status, approved.status, completed.status)
        traces.record(
            trace_id,
            "know_engine.completed",
            {"workflow_statuses": [status.value for status in statuses]},
        )
        return KnowEngineScenarioResult(
            trace_id=trace_id,
            rag_answer=rag_answer,
            agent_result=agent_result,
            evaluation=evaluation,
            workflow_statuses=statuses,
            workflow_run=completed,
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

        run_status = _RUN_STATUS_BY_STOP_REASON[result.stop_reason]
        terminal = running.model_copy(update={"status": run_status, "result": result})
        with self._lock:
            self._runs[run_id] = terminal
            self._append_event(
                run_id,
                f"run.{run_status}",
                {"stop_reason": result.stop_reason.value},
            )
        return terminal

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
    "KnowEngineScenarioResult",
    "ResearchWorkflow",
    "Retriever",
]
