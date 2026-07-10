from collections.abc import Callable

from fastapi.testclient import TestClient

from agent_course.agents.guardrails import DefaultGuardrail
from agent_course.agents.runner import BoundedAgentRunner
from agent_course.agents.sessions import InMemorySessionStore
from agent_course.api.app import create_app
from agent_course.application import CourseApplication
from agent_course.core import RunContext
from agent_course.models.fake import ORDER_QUERY_FIXTURE, FakeModelGateway
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.tools.orders import QueryOrderStatusTool
from agent_course.tools.registry import ToolRegistry


class CompatibleRetriever:
    def search(
        self,
        query: str,
        context: RunContext,
        top_k: int,
    ) -> list[object]:
        return []


class CompatibleWorkflow:
    def start(self, topic: str, context: RunContext) -> object:
        raise NotImplementedError

    def approve(
        self,
        run_id: str,
        decision: object,
        context: RunContext,
    ) -> object:
        raise NotImplementedError

    def resume(self, run_id: str, context: RunContext) -> object:
        raise NotImplementedError


def make_context(
    *,
    tenant_id: str = "tenant-1",
    user_id: str = "api-user",
) -> RunContext:
    return RunContext(
        user_id=user_id,
        tenant_id=tenant_id,
        request_id=f"api-{tenant_id}-{user_id}",
        permissions=frozenset({"orders:read"}),
    )


def make_course_application() -> CourseApplication:
    runner = BoundedAgentRunner(
        model=FakeModelGateway(),
        tools=ToolRegistry([QueryOrderStatusTool()]),
        guardrail=DefaultGuardrail(),
        sessions=InMemorySessionStore(),
        traces=InMemoryTraceSink(),
    )
    return CourseApplication(
        agent_runner=runner,
        retriever=CompatibleRetriever(),
        workflow=CompatibleWorkflow(),
    )


def make_client(
    context_provider: Callable[[], RunContext],
) -> TestClient:
    return TestClient(
        create_app(
            course_application=make_course_application(),
            context_provider=context_provider,
        )
    )


def test_health_does_not_require_credentials_or_network() -> None:
    with make_client(make_context) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_default_api_composition_uses_the_offline_fake_path() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/agent/runs",
            json={"question": ORDER_QUERY_FIXTURE},
        )

    assert response.status_code == 201
    output = response.json()["result"]["tool_results"][0]["output"]
    assert output["tenant_id"] == "tenant-1"
    assert output["requested_by"] == "api-demo-user"


def test_create_get_and_events_use_fake_model_and_trusted_context() -> None:
    with make_client(make_context) as client:
        created = client.post(
            "/v1/agent/runs",
            json={"question": ORDER_QUERY_FIXTURE, "session_id": "api-session"},
        )

        assert created.status_code == 201
        payload = created.json()
        assert payload["status"] == "completed"
        assert payload["result"]["final_content"] == "订单 O1001 当前状态为 shipped。"
        assert payload["result"]["tool_results"][0]["output"] == {
            "order_id": "O1001",
            "status": "shipped",
            "tenant_id": "tenant-1",
            "requested_by": "api-user",
        }

        fetched = client.get(f"/v1/agent/runs/{payload['run_id']}")
        events = client.get(f"/v1/agent/runs/{payload['run_id']}/events")

    assert fetched.status_code == 200
    assert fetched.json() == payload
    assert events.status_code == 200
    assert [event["type"] for event in events.json()["items"]] == [
        "run.created",
        "run.started",
        "run.completed",
    ]
    assert events.json()["items"][-1]["data"]["stop_reason"] == "completed"


def test_request_body_cannot_supply_trusted_context() -> None:
    with make_client(make_context) as client:
        response = client.post(
            "/v1/agent/runs",
            json={
                "question": ORDER_QUERY_FIXTURE,
                "tenant_id": "tenant-2",
                "user_id": "attacker",
                "permissions": ["orders:read"],
            },
        )

    assert response.status_code == 422


def test_request_cannot_raise_server_owned_run_budgets() -> None:
    with make_client(make_context) as client:
        response = client.post(
            "/v1/agent/runs",
            json={
                "question": "什么是 Agent？",
                "limits": {
                    "max_turns": 1_000,
                    "max_tool_calls": 1_000,
                    "max_output_tokens": 1_000_000,
                    "timeout_seconds": 3_600,
                },
            },
        )

    assert response.status_code == 422


def test_run_lookup_is_isolated_by_trusted_tenant_and_user() -> None:
    active_context = {"value": make_context()}

    def context_provider() -> RunContext:
        return active_context["value"]

    with make_client(context_provider) as client:
        created = client.post(
            "/v1/agent/runs",
            json={"question": "什么是 Agent？"},
        )
        run_id = created.json()["run_id"]

        active_context["value"] = make_context(user_id="other-user")
        hidden = client.get(f"/v1/agent/runs/{run_id}")
        hidden_events = client.get(f"/v1/agent/runs/{run_id}/events")

    assert hidden.status_code == 404
    assert hidden_events.status_code == 404
