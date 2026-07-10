from agent_course.agents.runner import AgentResult
from agent_course.core import (
    Message,
    RunContext,
    RunLimits,
    StopReason,
    ToolResult,
)
from agent_course.evals import EvalCase, evaluate_cases


def make_context(*, permissions: frozenset[str] = frozenset()) -> RunContext:
    return RunContext(
        user_id="user-1",
        tenant_id="tenant-1",
        request_id="eval-request",
        permissions=permissions,
    )


def make_limits() -> RunLimits:
    return RunLimits(
        max_turns=4,
        max_tool_calls=3,
        max_output_tokens=100,
        timeout_seconds=0.2,
    )


def make_result(
    *,
    content: str | None,
    stop_reason: StopReason,
    messages: tuple[Message, ...],
    tool_results: tuple[ToolResult, ...] = (),
) -> AgentResult:
    return AgentResult(
        final_content=content,
        stop_reason=stop_reason,
        messages=messages,
        tool_results=tool_results,
        trace_id="trace-fixed",
    )


class FakeEvaluationApplication:
    def __init__(self, results: dict[str, AgentResult]) -> None:
        self.results = results
        self.questions: list[str] = []

    async def run_agent(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
    ) -> AgentResult:
        self.questions.append(question)
        return self.results[question]


async def test_evaluate_cases_covers_success_tool_accuracy_security_and_turns() -> None:
    direct = make_result(
        content="Agent is a bounded application.",
        stop_reason=StopReason.COMPLETED,
        messages=(
            Message(role="user", content="direct"),
            Message(role="assistant", content="Agent is a bounded application."),
        ),
    )
    tool = make_result(
        content="Order O1001 is shipped.",
        stop_reason=StopReason.COMPLETED,
        messages=(
            Message(role="user", content="tool"),
            Message(role="tool", content="result", tool_call_id="call-1"),
            Message(role="assistant", content="Order O1001 is shipped."),
        ),
        tool_results=(
            ToolResult(
                name="query_order_status",
                code="OK",
                success=True,
                output={"order_id": "O1001", "status": "shipped"},
            ),
        ),
    )
    unauthorized = make_result(
        content=None,
        stop_reason=StopReason.PERMISSION_DENIED,
        messages=(Message(role="user", content="unauthorized"),),
        tool_results=(
            ToolResult(
                name="query_order_status",
                code="PERMISSION_DENIED",
                success=False,
            ),
        ),
    )
    app = FakeEvaluationApplication(
        {"direct": direct, "tool": tool, "unauthorized": unauthorized}
    )
    cases = [
        EvalCase(
            case_id="case-direct",
            question="direct",
            context=make_context(),
            limits=make_limits(),
            expected_answer_contains=("bounded",),
            max_turns=1,
        ),
        EvalCase(
            case_id="case-tool",
            question="tool",
            context=make_context(permissions=frozenset({"orders:read"})),
            limits=make_limits(),
            expected_answer_contains=("shipped",),
            expected_tool_name="query_order_status",
            expected_tool_arguments={"order_id": "O1001"},
            max_turns=2,
        ),
        EvalCase(
            case_id="case-unauthorized",
            question="unauthorized",
            context=make_context(),
            limits=make_limits(),
            expected_stop_reason=StopReason.PERMISSION_DENIED,
            expect_unauthorized_action_blocked=True,
            max_turns=1,
        ),
    ]

    report = await evaluate_cases(cases, app)

    assert report.total_cases == 3
    assert report.passed_cases == 3
    assert report.task_success_rate == 1.0
    assert report.tool_selection_accuracy == 1.0
    assert report.argument_accuracy == 1.0
    assert report.unauthorized_action_block_rate == 1.0
    assert [result.turn_count for result in report.results] == [1, 2, 0]
    assert all(result.passed for result in report.results)


async def test_eval_report_detects_wrong_tool_arguments_and_excess_turns() -> None:
    result = make_result(
        content="done",
        stop_reason=StopReason.COMPLETED,
        messages=(
            Message(role="user", content="bad"),
            Message(role="tool", content="result", tool_call_id="call-1"),
            Message(role="assistant", content="done"),
        ),
        tool_results=(
            ToolResult(
                name="wrong_tool",
                code="OK",
                success=True,
                output={"order_id": "O9999"},
            ),
        ),
    )
    case = EvalCase(
        case_id="case-bad",
        question="bad",
        context=make_context(),
        limits=make_limits(),
        expected_tool_name="query_order_status",
        expected_tool_arguments={"order_id": "O1001"},
        max_turns=1,
    )

    report = await evaluate_cases([case], FakeEvaluationApplication({"bad": result}))
    evaluation = report.results[0]

    assert evaluation.passed is False
    assert evaluation.tool_selection_correct is False
    assert evaluation.arguments_correct is False
    assert evaluation.turn_count_within_limit is False
    assert evaluation.failures == (
        "tool_selection",
        "argument_accuracy",
        "turn_count",
    )


async def test_report_serialization_and_case_order_are_stable() -> None:
    result = make_result(
        content="ok",
        stop_reason=StopReason.COMPLETED,
        messages=(
            Message(role="user", content="question-a"),
            Message(role="assistant", content="ok"),
        ),
    )
    other_result = result.model_copy(
        update={
            "messages": (
                Message(role="user", content="question-b"),
                Message(role="assistant", content="ok"),
            )
        }
    )
    cases = [
        EvalCase(
            case_id="b",
            question="question-b",
            context=make_context(),
            limits=make_limits(),
        ),
        EvalCase(
            case_id="a",
            question="question-a",
            context=make_context(),
            limits=make_limits(),
        ),
    ]
    app = FakeEvaluationApplication(
        {"question-a": result, "question-b": other_result}
    )

    first = await evaluate_cases(cases, app)
    second = await evaluate_cases(list(reversed(cases)), app)

    assert [evaluation.case_id for evaluation in first.results] == ["a", "b"]
    assert first.to_json() == second.to_json()
    assert first.to_json() == first.to_json()
