import pytest

from agent_course.api.app import build_offline_course_application
from agent_course.application import CourseApplication, _RUN_STATUS_BY_STOP_REASON
from agent_course.core import RunContext, RunLimits, StopReason
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.workflows import WorkflowStatus


def test_direct_construction_adopts_runner_trace_sink_when_omitted() -> None:
    factory_app = build_offline_course_application()

    direct_app = CourseApplication(
        agent_runner=factory_app.agent_runner,
        retriever=factory_app.retriever,
        workflow=factory_app.workflow,
    )

    assert direct_app.traces is factory_app.agent_runner.traces


def test_direct_construction_rejects_inconsistent_trace_sinks() -> None:
    factory_app = build_offline_course_application()

    with pytest.raises(ValueError, match="same trace sink"):
        CourseApplication(
            agent_runner=factory_app.agent_runner,
            retriever=factory_app.retriever,
            workflow=factory_app.workflow,
            traces=InMemoryTraceSink(),
        )


def test_agent_run_status_mapping_covers_every_stop_reason() -> None:
    assert set(_RUN_STATUS_BY_STOP_REASON) == set(StopReason)


async def test_fake_know_engine_runs_one_grounded_traced_evaluated_flow() -> None:
    app = build_offline_course_application()
    assert app.traces is app.agent_runner.traces
    context = RunContext(
        user_id="capstone-user",
        tenant_id="tenant-1",
        request_id="know-engine-e2e",
        permissions=frozenset(
            {"knowledge:read", "orders:read", "research:run", "research:approve"}
        ),
    )

    outcome = await app.run_know_engine_scenario(
        context,
        RunLimits(
            max_turns=4,
            max_tool_calls=2,
            max_output_tokens=100,
            timeout_seconds=1,
        ),
    )

    assert outcome.rag_answer.refused is False
    assert outcome.rag_answer.citations[0].document_id == "hr-policy"
    assert outcome.rag_answer.citations[0].quote in outcome.agent_result.final_content
    assert outcome.agent_result.stop_reason is StopReason.COMPLETED
    assert [call.name for call in outcome.agent_result.model_tool_calls] == [
        "query_order_status"
    ]
    assert outcome.evaluation.passed is True
    assert outcome.workflow_statuses == (
        WorkflowStatus.WAITING_FOR_APPROVAL,
        WorkflowStatus.RUNNING,
        WorkflowStatus.COMPLETED,
    )
    assert outcome.workflow_run.status is WorkflowStatus.COMPLETED
    assert outcome.trace_id == outcome.agent_result.trace_id

    event_types = [event.event_type for event in app.traces.for_trace(outcome.trace_id)]
    assert event_types == [
        "run.started",
        "retrieval.completed",
        "guardrail.checked",
        "model.step",
        "tool.called",
        "tool.result",
        "model.step",
        "run.finished",
        "evaluation.completed",
        "workflow.started",
        "workflow.approved",
        "workflow.completed",
        "know_engine.completed",
    ]
