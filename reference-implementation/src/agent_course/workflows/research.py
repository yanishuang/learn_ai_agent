"""In-memory durable-state teaching workflow with explicit approval boundaries."""

import hashlib
import json
import time
from collections.abc import Callable
from enum import StrEnum

from pydantic import ConfigDict, Field, field_validator, model_validator

from agent_course.core import FrozenModel, RunContext


class WorkflowStatus(StrEnum):
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class WorkflowError(RuntimeError):
    """Base error for invalid workflow operations."""


class WorkflowNotFoundError(WorkflowError):
    pass


class WorkflowAccessError(WorkflowError):
    pass


class WorkflowStateError(WorkflowError):
    pass


class ApprovalPayloadMismatchError(WorkflowError):
    pass


class IdempotencyConflictError(WorkflowError):
    pass


def _payload_hash(
    *,
    run_id: str,
    tenant_id: str,
    workflow_version: str,
    state_version: int,
    action: str,
    topic: str,
    summary: str,
) -> str:
    canonical = json.dumps(
        {
            "action": action,
            "run_id": run_id,
            "state_version": state_version,
            "summary": summary,
            "tenant_id": tenant_id,
            "topic": topic,
            "workflow_version": workflow_version,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class WorkflowModel(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ApprovalPayload(WorkflowModel):
    run_id: str
    tenant_id: str
    workflow_version: str
    state_version: int = Field(ge=1)
    action: str
    topic: str
    summary: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def content_hash_must_match_payload(self) -> "ApprovalPayload":
        expected = _payload_hash(
            run_id=self.run_id,
            tenant_id=self.tenant_id,
            workflow_version=self.workflow_version,
            state_version=self.state_version,
            action=self.action,
            topic=self.topic,
            summary=self.summary,
        )
        if self.content_hash != expected:
            raise ValueError("content_hash does not match approval payload")
        return self


class ApprovalDecision(WorkflowModel):
    approved: bool
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_key_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("idempotency_key must be nonblank")
        return value


class WorkflowRun(WorkflowModel):
    run_id: str
    workflow_version: str
    state_version: int = Field(ge=1)
    status: WorkflowStatus
    tenant_id: str
    user_id: str
    topic: str
    approval: ApprovalPayload | None = None
    approved_by: str | None = None
    cancelled_by: str | None = None
    report: str | None = None
    error_code: str | None = None


class ResearchWorkflow:
    """Persist workflow checkpoints in memory for deterministic offline labs."""

    workflow_version = "research-v1"

    def __init__(
        self,
        *,
        timeout_seconds: float = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._runs: dict[str, WorkflowRun] = {}
        self._deadlines: dict[str, float] = {}
        self._start_keys: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._approval_keys: dict[tuple[str, str], tuple[str, bool, str]] = {}

    def start(self, topic: str, context: RunContext) -> WorkflowRun:
        context.require("research:run")
        normalized_topic = topic.strip()
        if not normalized_topic:
            raise ValueError("topic must be nonblank")

        key = (context.tenant_id, context.user_id, context.request_id)
        previous = self._start_keys.get(key)
        if previous is not None:
            previous_topic, run_id = previous
            if previous_topic != normalized_topic:
                raise IdempotencyConflictError(
                    "start idempotency key was reused with a different topic"
                )
            return self._runs[run_id]

        run_id = self._run_id(context)
        state_version = 1
        summary = f"Approve the deterministic research report for: {normalized_topic}"
        approval = ApprovalPayload(
            run_id=run_id,
            tenant_id=context.tenant_id,
            workflow_version=self.workflow_version,
            state_version=state_version,
            action="publish_research_report",
            topic=normalized_topic,
            summary=summary,
            content_hash=_payload_hash(
                run_id=run_id,
                tenant_id=context.tenant_id,
                workflow_version=self.workflow_version,
                state_version=state_version,
                action="publish_research_report",
                topic=normalized_topic,
                summary=summary,
            ),
        )
        run = WorkflowRun(
            run_id=run_id,
            workflow_version=self.workflow_version,
            state_version=state_version,
            status=WorkflowStatus.WAITING_FOR_APPROVAL,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            topic=normalized_topic,
            approval=approval,
        )
        self._runs[run_id] = run
        self._deadlines[run_id] = self._clock() + self._timeout_seconds
        self._start_keys[key] = (normalized_topic, run_id)
        return run

    def get(self, run_id: str, context: RunContext) -> WorkflowRun:
        context.require("research:run")
        run = self._load(run_id)
        self._require_tenant(run, context)
        self._require_owner(run, context)
        return run

    def approve(
        self,
        run_id: str,
        decision: ApprovalDecision,
        context: RunContext,
    ) -> WorkflowRun:
        context.require("research:approve")
        run = self._load(run_id)
        self._require_tenant(run, context)
        run = self._materialize_timeout(run)

        key = (context.tenant_id, decision.idempotency_key)
        fingerprint = (run_id, decision.approved, decision.payload_hash)
        previous = self._approval_keys.get(key)
        if previous is not None:
            if previous != fingerprint:
                raise IdempotencyConflictError(
                    "approval idempotency key was reused with different content"
                )
            return run

        if run.approval is None or decision.payload_hash != run.approval.content_hash:
            raise ApprovalPayloadMismatchError(
                "approval decision does not match the persisted payload"
            )
        if run.status is WorkflowStatus.TIMED_OUT:
            return run
        if run.status is not WorkflowStatus.WAITING_FOR_APPROVAL:
            raise WorkflowStateError("workflow is not waiting for approval")

        if decision.approved:
            updated = run.model_copy(
                update={
                    "status": WorkflowStatus.RUNNING,
                    "state_version": run.state_version + 1,
                    "approved_by": context.user_id,
                }
            )
        else:
            updated = run.model_copy(
                update={
                    "status": WorkflowStatus.CANCELLED,
                    "state_version": run.state_version + 1,
                    "cancelled_by": context.user_id,
                }
            )
        self._runs[run_id] = updated
        self._approval_keys[key] = fingerprint
        return updated

    def resume(self, run_id: str, context: RunContext) -> WorkflowRun:
        context.require("research:run")
        run = self._load(run_id)
        self._require_tenant(run, context)
        self._require_owner(run, context)
        run = self._materialize_timeout(run)

        if run.status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.TIMED_OUT,
        }:
            return run
        if run.status is WorkflowStatus.WAITING_FOR_APPROVAL:
            return run
        if run.status is not WorkflowStatus.RUNNING:
            raise WorkflowStateError("workflow cannot resume from its current state")
        return self._update(
            run,
            status=WorkflowStatus.COMPLETED,
            report=f"Research report: {run.topic}.",
        )

    def cancel(self, run_id: str, context: RunContext) -> WorkflowRun:
        context.require("research:run")
        run = self._load(run_id)
        self._require_tenant(run, context)
        self._require_owner(run, context)
        run = self._materialize_timeout(run)
        if run.status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.TIMED_OUT,
        }:
            return run
        return self._update(
            run,
            status=WorkflowStatus.CANCELLED,
            cancelled_by=context.user_id,
        )

    def _load(self, run_id: str) -> WorkflowRun:
        try:
            return self._runs[run_id]
        except KeyError as error:
            raise WorkflowNotFoundError("workflow run was not found") from error

    def _update(self, run: WorkflowRun, **changes: object) -> WorkflowRun:
        updated = run.model_copy(
            update={"state_version": run.state_version + 1, **changes}
        )
        self._runs[run.run_id] = updated
        return updated

    def _materialize_timeout(self, run: WorkflowRun) -> WorkflowRun:
        if run.status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.TIMED_OUT,
        }:
            return run
        if self._clock() < self._deadlines[run.run_id]:
            return run
        return self._update(
            run,
            status=WorkflowStatus.TIMED_OUT,
            error_code="WORKFLOW_TIMEOUT",
        )

    @staticmethod
    def _require_tenant(run: WorkflowRun, context: RunContext) -> None:
        if run.tenant_id != context.tenant_id:
            raise WorkflowAccessError("workflow run belongs to another tenant")

    @staticmethod
    def _require_owner(run: WorkflowRun, context: RunContext) -> None:
        if run.user_id != context.user_id:
            raise WorkflowAccessError("workflow run belongs to another user")

    @staticmethod
    def _run_id(context: RunContext) -> str:
        canonical = ":".join(
            (context.tenant_id, context.user_id, context.request_id)
        ).encode("utf-8")
        return "run-" + hashlib.sha256(canonical).hexdigest()[:20]


__all__ = [
    "ApprovalDecision",
    "ApprovalPayload",
    "ApprovalPayloadMismatchError",
    "IdempotencyConflictError",
    "ResearchWorkflow",
    "WorkflowAccessError",
    "WorkflowError",
    "WorkflowNotFoundError",
    "WorkflowRun",
    "WorkflowStateError",
    "WorkflowStatus",
]
