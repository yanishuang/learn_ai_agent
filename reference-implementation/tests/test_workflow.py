import pytest

from agent_course.core import PermissionDeniedError, RunContext
from agent_course.workflows import (
    ApprovalDecision,
    ApprovalPayloadMismatchError,
    IdempotencyConflictError,
    ResearchWorkflow,
    WorkflowAccessError,
    WorkflowStatus,
)


class ManualClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def make_context(
    *,
    tenant_id: str = "tenant-1",
    user_id: str = "user-1",
    request_id: str = "request-1",
    permissions: frozenset[str] = frozenset(
        {"research:run", "research:approve"}
    ),
) -> RunContext:
    return RunContext(
        user_id=user_id,
        tenant_id=tenant_id,
        request_id=request_id,
        permissions=permissions,
    )


def test_start_creates_versioned_state_waiting_for_content_bound_approval() -> None:
    run = ResearchWorkflow().start("AI safety", make_context())

    assert run.status is WorkflowStatus.WAITING_FOR_APPROVAL
    assert run.workflow_version == "research-v1"
    assert run.state_version == 1
    assert run.approval is not None
    assert len(run.approval.content_hash) == 64
    assert run.approval.run_id == run.run_id
    assert run.approval.tenant_id == run.tenant_id
    assert run.approval.workflow_version == run.workflow_version
    assert run.approval.state_version == run.state_version
    assert run.approval.topic == "AI safety"


def test_approval_hash_cannot_be_replayed_across_same_topic_runs() -> None:
    workflow = ResearchWorkflow()
    first_context = make_context(request_id="request-1")
    second_context = make_context(request_id="request-2")
    first = workflow.start("AI safety", first_context)
    second = workflow.start("AI safety", second_context)

    assert first.approval.content_hash != second.approval.content_hash
    with pytest.raises(ApprovalPayloadMismatchError):
        workflow.approve(
            second.run_id,
            ApprovalDecision(
                approved=True,
                payload_hash=first.approval.content_hash,
                idempotency_key="approval-replay",
            ),
            second_context,
        )

    assert workflow.get(second.run_id, second_context) == second


def test_approval_rejects_a_mismatched_payload_hash() -> None:
    workflow = ResearchWorkflow()
    context = make_context()
    run = workflow.start("AI safety", context)

    with pytest.raises(ApprovalPayloadMismatchError):
        workflow.approve(
            run.run_id,
            ApprovalDecision(
                approved=True,
                payload_hash="0" * 64,
                idempotency_key="approval-1",
            ),
            context,
        )

    assert workflow.get(run.run_id, context).status is WorkflowStatus.WAITING_FOR_APPROVAL


def test_resume_waits_until_approved_then_completes_without_repeating_work() -> None:
    workflow = ResearchWorkflow()
    context = make_context()
    waiting = workflow.start("AI safety", context)

    assert workflow.resume(waiting.run_id, context) == waiting

    approved = workflow.approve(
        waiting.run_id,
        ApprovalDecision(
            approved=True,
            payload_hash=waiting.approval.content_hash,
            idempotency_key="approval-1",
        ),
        context,
    )
    completed = workflow.resume(waiting.run_id, context)

    assert approved.status is WorkflowStatus.RUNNING
    assert approved.state_version == 2
    assert completed.status is WorkflowStatus.COMPLETED
    assert completed.state_version == 3
    assert completed.report == "Research report: AI safety."
    assert workflow.resume(waiting.run_id, context) == completed


def test_start_and_approval_idempotency_keys_detect_conflicting_reuse() -> None:
    workflow = ResearchWorkflow()
    context = make_context()
    first = workflow.start("AI safety", context)

    assert workflow.start("AI safety", context) == first
    with pytest.raises(IdempotencyConflictError):
        workflow.start("Different topic", context)

    decision = ApprovalDecision(
        approved=True,
        payload_hash=first.approval.content_hash,
        idempotency_key="approval-1",
    )
    approved = workflow.approve(first.run_id, decision, context)
    assert workflow.approve(first.run_id, decision, context) == approved

    with pytest.raises(IdempotencyConflictError):
        workflow.approve(
            first.run_id,
            decision.model_copy(update={"approved": False}),
            context,
        )


def test_workflow_checks_permission_tenant_and_owner_boundaries() -> None:
    workflow = ResearchWorkflow()
    owner = make_context()
    run = workflow.start("AI safety", owner)

    with pytest.raises(PermissionDeniedError):
        workflow.resume(
            run.run_id,
            make_context(permissions=frozenset(), request_id="no-permission"),
        )
    with pytest.raises(WorkflowAccessError):
        workflow.get(
            run.run_id,
            make_context(tenant_id="tenant-2", request_id="wrong-tenant"),
        )
    with pytest.raises(WorkflowAccessError):
        workflow.get(
            run.run_id,
            make_context(user_id="user-2", request_id="wrong-owner-get"),
        )
    with pytest.raises(WorkflowAccessError):
        workflow.resume(
            run.run_id,
            make_context(user_id="user-2", request_id="wrong-owner"),
        )


def test_waiting_run_times_out_using_an_injected_clock() -> None:
    clock = ManualClock()
    workflow = ResearchWorkflow(timeout_seconds=10, clock=clock)
    context = make_context()
    run = workflow.start("AI safety", context)

    clock.advance(11)
    timed_out = workflow.resume(run.run_id, context)

    assert timed_out.status is WorkflowStatus.TIMED_OUT
    assert timed_out.error_code == "WORKFLOW_TIMEOUT"
    assert timed_out.state_version == 2


def test_approval_after_deadline_materializes_timeout() -> None:
    clock = ManualClock()
    workflow = ResearchWorkflow(timeout_seconds=10, clock=clock)
    context = make_context()
    run = workflow.start("AI safety", context)

    clock.advance(10)
    timed_out = workflow.approve(
        run.run_id,
        ApprovalDecision(
            approved=True,
            payload_hash=run.approval.content_hash,
            idempotency_key="late-approval",
        ),
        context,
    )

    assert timed_out.status is WorkflowStatus.TIMED_OUT
    assert timed_out.error_code == "WORKFLOW_TIMEOUT"
    assert timed_out.approved_by is None
    assert timed_out.state_version == 2
    assert workflow.approve(
        run.run_id,
        ApprovalDecision(
            approved=True,
            payload_hash=run.approval.content_hash,
            idempotency_key="late-approval-retry",
        ),
        context,
    ) == timed_out


def test_cancel_after_deadline_materializes_timeout_from_running_state() -> None:
    clock = ManualClock()
    workflow = ResearchWorkflow(timeout_seconds=10, clock=clock)
    context = make_context()
    run = workflow.start("AI safety", context)
    running = workflow.approve(
        run.run_id,
        ApprovalDecision(
            approved=True,
            payload_hash=run.approval.content_hash,
            idempotency_key="approval-1",
        ),
        context,
    )

    clock.advance(10)
    timed_out = workflow.cancel(run.run_id, context)

    assert running.status is WorkflowStatus.RUNNING
    assert timed_out.status is WorkflowStatus.TIMED_OUT
    assert timed_out.error_code == "WORKFLOW_TIMEOUT"
    assert timed_out.cancelled_by is None
    assert timed_out.state_version == 3
    assert workflow.cancel(run.run_id, context) == timed_out


def test_owner_can_cancel_and_cancel_is_idempotent() -> None:
    workflow = ResearchWorkflow()
    context = make_context()
    run = workflow.start("AI safety", context)

    cancelled = workflow.cancel(run.run_id, context)

    assert cancelled.status is WorkflowStatus.CANCELLED
    assert cancelled.cancelled_by == context.user_id
    assert cancelled.state_version == 2
    assert workflow.cancel(run.run_id, context) == cancelled
