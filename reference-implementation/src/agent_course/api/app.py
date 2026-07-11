"""Credential-free FastAPI composition for bounded agent runs."""

from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from agent_course.agents.guardrails import DefaultGuardrail
from agent_course.agents.runner import BoundedAgentRunner
from agent_course.agents.sessions import InMemorySessionStore
from agent_course.application import AgentRunEvent, AgentRunRecord, CourseApplication
from agent_course.core import RunContext, RunLimits
from agent_course.models.fake import FakeModelGateway
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.rag import DocumentChunk, InMemoryRetriever
from agent_course.tools.orders import QueryOrderStatusTool
from agent_course.tools.registry import ToolRegistry
from agent_course.workflows import ResearchWorkflow
from agent_course.models.fake import KNOW_ENGINE_POLICY_QUOTE


class AgentRunLimitsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_turns: int = Field(default=4, ge=1, le=10)
    max_tool_calls: int = Field(default=3, ge=1, le=20)
    max_output_tokens: int = Field(default=1_000, ge=1, le=10_000)
    timeout_seconds: float = Field(default=5.0, gt=0, le=30.0)

    def to_run_limits(self) -> RunLimits:
        return RunLimits(**self.model_dump())


class CreateAgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4_000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    limits: AgentRunLimitsRequest = Field(default_factory=AgentRunLimitsRequest)


class AgentRunEventsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[AgentRunEvent, ...]


def build_offline_course_application() -> CourseApplication:
    """Build the runnable API path entirely from deterministic local components."""

    traces = InMemoryTraceSink()
    runner = BoundedAgentRunner(
        model=FakeModelGateway(),
        tools=ToolRegistry([QueryOrderStatusTool()]),
        guardrail=DefaultGuardrail(),
        sessions=InMemorySessionStore(),
        traces=traces,
    )
    return CourseApplication(
        agent_runner=runner,
        retriever=InMemoryRetriever(
            [
                DocumentChunk(
                    chunk_id="hr-policy-annual-leave",
                    document_id="hr-policy",
                    tenant_id="tenant-1",
                    title="HR Policy - Annual Leave",
                    content=KNOW_ENGINE_POLICY_QUOTE,
                    required_permissions=frozenset({"knowledge:read"}),
                )
            ]
        ),
        workflow=ResearchWorkflow(),
        traces=traces,
    )


def default_run_context() -> RunContext:
    """Fail closed until the host injects a trusted request identity provider.

    This dependency is deliberately not an authentication implementation. A host must
    derive ``RunContext`` from its authenticated, request-scoped server identity and
    pass that provider to ``create_app``.
    """

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="trusted identity provider is not configured",
    )


def create_app(
    course_application: CourseApplication | None = None,
    context_provider: Callable[[], RunContext] | None = None,
) -> FastAPI:
    course_application = course_application or build_offline_course_application()
    context_dependency = context_provider or default_run_context
    api = FastAPI(title="Agent Course Reference API", version="1.0.0")

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post(
        "/v1/agent/runs",
        response_model=AgentRunRecord,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_agent_run(
        request: CreateAgentRunRequest,
        context: RunContext = Depends(context_dependency),
    ) -> AgentRunRecord:
        return await course_application.create_agent_run(
            request.question,
            context,
            request.limits.to_run_limits(),
            session_id=request.session_id,
        )

    @api.get("/v1/agent/runs/{run_id}", response_model=AgentRunRecord)
    async def get_agent_run(
        run_id: str,
        context: RunContext = Depends(context_dependency),
    ) -> AgentRunRecord:
        run = course_application.get_agent_run(run_id, context)
        if run is None:
            raise HTTPException(status_code=404, detail="agent run not found")
        return run

    @api.get(
        "/v1/agent/runs/{run_id}/events",
        response_model=AgentRunEventsResponse,
    )
    async def get_agent_run_events(
        run_id: str,
        context: RunContext = Depends(context_dependency),
    ) -> AgentRunEventsResponse:
        events = course_application.get_agent_run_events(run_id, context)
        if events is None:
            raise HTTPException(status_code=404, detail="agent run not found")
        return AgentRunEventsResponse(items=events)

    return api


app = create_app()


__all__ = [
    "AgentRunLimitsRequest",
    "AgentRunEventsResponse",
    "CreateAgentRunRequest",
    "app",
    "build_offline_course_application",
    "create_app",
    "default_run_context",
]
