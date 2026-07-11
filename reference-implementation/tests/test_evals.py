import json

from agent_course.agents.runner import AgentResult
from agent_course.core import (
    Message,
    RunContext,
    RunLimits,
    StopReason,
    ToolCall,
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
    model_turn_count: int,
    model_tool_calls: tuple[ToolCall, ...] = (),
    tool_results: tuple[ToolResult, ...] = (),
) -> AgentResult:
    return AgentResult(
        final_content=content,
        stop_reason=stop_reason,
        messages=messages,
        model_tool_calls=model_tool_calls,
        model_turn_count=model_turn_count,
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
        model_turn_count=1,
    )
    tool = make_result(
        content="Order O1001 is shipped.",
        stop_reason=StopReason.COMPLETED,
        messages=(
            Message(role="user", content="tool"),
            Message(role="tool", content="result", tool_call_id="call-1"),
            Message(role="assistant", content="Order O1001 is shipped."),
        ),
        model_tool_calls=(
            ToolCall(
                id="call-1",
                name="query_order_status",
                arguments={"order_id": "O1001"},
            ),
        ),
        model_turn_count=2,
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
        model_tool_calls=(
            ToolCall(
                id="call-denied",
                name="query_order_status",
                arguments={"order_id": "O1001"},
            ),
        ),
        model_turn_count=1,
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
            expected_tool_calls=(),
            max_turns=1,
        ),
        EvalCase(
            case_id="case-tool",
            question="tool",
            context=make_context(permissions=frozenset({"orders:read"})),
            limits=make_limits(),
            expected_answer_contains=("shipped",),
            expected_tool_calls=(
                {
                    "name": "query_order_status",
                    "arguments": {"order_id": "O1001"},
                },
            ),
            max_turns=2,
        ),
        EvalCase(
            case_id="case-unauthorized",
            question="unauthorized",
            context=make_context(),
            limits=make_limits(),
            expected_tool_calls=(
                {
                    "name": "query_order_status",
                    "arguments": {"order_id": "O1001"},
                },
            ),
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
    assert [result.turn_count for result in report.results] == [1, 2, 1]
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
        model_tool_calls=(
            ToolCall(
                id="call-1",
                name="wrong_tool",
                arguments={"order_id": "O9999"},
            ),
        ),
        model_turn_count=2,
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
        expected_tool_calls=(
            {"name": "query_order_status", "arguments": {"order_id": "O1001"}},
        ),
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


async def test_eval_argument_accuracy_rejects_unexpected_arguments() -> None:
    result = make_result(
        content="done",
        stop_reason=StopReason.COMPLETED,
        messages=(Message(role="user", content="extra-arguments"),),
        model_tool_calls=(
            ToolCall(
                id="call-1",
                name="query_order_status",
                arguments={
                    "order_id": "O1001",
                    "tenant_id": "attacker",
                },
            ),
        ),
        model_turn_count=1,
    )
    case = EvalCase(
        case_id="extra-arguments",
        question="extra-arguments",
        context=make_context(),
        limits=make_limits(),
        expected_tool_calls=(
            {"name": "query_order_status", "arguments": {"order_id": "O1001"}},
        ),
        max_turns=1,
    )

    report = await evaluate_cases(
        [case], FakeEvaluationApplication({"extra-arguments": result})
    )

    assert report.results[0].tool_selection_correct is True
    assert report.results[0].arguments_correct is False
    assert report.results[0].failures == ("argument_accuracy",)


async def test_explicit_empty_tool_trajectory_rejects_an_unexpected_call() -> None:
    result = make_result(
        content="done",
        stop_reason=StopReason.COMPLETED,
        messages=(Message(role="user", content="unexpected-tool"),),
        model_tool_calls=(
            ToolCall(
                id="unexpected-call",
                name="query_order_status",
                arguments={"order_id": "O1001"},
            ),
        ),
        model_turn_count=1,
    )
    case = EvalCase(
        case_id="unexpected-tool",
        question="unexpected-tool",
        context=make_context(),
        limits=make_limits(),
        expected_tool_calls=(),
        max_turns=1,
    )

    report = await evaluate_cases(
        [case], FakeEvaluationApplication({"unexpected-tool": result})
    )

    assert report.results[0].tool_selection_correct is False
    assert report.results[0].arguments_correct is False
    assert report.results[0].failures == ("tool_selection", "argument_accuracy")


async def test_tool_trajectory_requires_exact_call_order_and_arguments() -> None:
    result = make_result(
        content="done",
        stop_reason=StopReason.COMPLETED,
        messages=(Message(role="user", content="ordered-tools"),),
        model_tool_calls=(
            ToolCall(id="call-a", name="search", arguments={"query": "leave"}),
            ToolCall(
                id="call-b",
                name="query_order_status",
                arguments={"order_id": "O1001"},
            ),
        ),
        model_turn_count=2,
    )
    case = EvalCase(
        case_id="ordered-tools",
        question="ordered-tools",
        context=make_context(),
        limits=make_limits(),
        expected_tool_calls=(
            {"name": "query_order_status", "arguments": {"order_id": "O1001"}},
            {"name": "search", "arguments": {"query": "leave"}},
        ),
        max_turns=2,
    )

    report = await evaluate_cases(
        [case], FakeEvaluationApplication({"ordered-tools": result})
    )

    assert report.results[0].tool_selection_correct is False
    assert report.results[0].arguments_correct is False


async def test_eval_argument_accuracy_requires_canonical_nested_json() -> None:
    result = make_result(
        content="done",
        stop_reason=StopReason.COMPLETED,
        messages=(Message(role="user", content="canonical-arguments"),),
        model_tool_calls=(
            ToolCall(
                id="call-1",
                name="query_order_status",
                arguments={
                    "filters": {"include_archived": 1, "order_ids": ["O1001"]},
                },
            ),
        ),
        model_turn_count=1,
    )
    case = EvalCase(
        case_id="canonical-arguments",
        question="canonical-arguments",
        context=make_context(),
        limits=make_limits(),
        expected_tool_calls=(
            {
                "name": "query_order_status",
                "arguments": {
                    "filters": {
                        "include_archived": True,
                        "order_ids": ["O1001"],
                    },
                },
            },
        ),
        max_turns=1,
    )

    report = await evaluate_cases(
        [case], FakeEvaluationApplication({"canonical-arguments": result})
    )

    assert report.results[0].arguments_correct is False


async def test_report_serialization_and_case_order_are_stable() -> None:
    result = make_result(
        content="ok",
        stop_reason=StopReason.COMPLETED,
        messages=(
            Message(role="user", content="question-a"),
            Message(role="assistant", content="ok"),
        ),
        model_turn_count=1,
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
            expected_tool_calls=(),
        ),
        EvalCase(
            case_id="a",
            question="question-a",
            context=make_context(),
            limits=make_limits(),
            expected_tool_calls=(),
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


async def test_claimed_tool_result_without_model_call_evidence_cannot_pass() -> None:
    claimed = make_result(
        content="done",
        stop_reason=StopReason.COMPLETED,
        messages=(Message(role="user", content="claimed"),),
        model_turn_count=1,
        tool_results=(
            ToolResult(
                name="query_order_status",
                code="OK",
                success=True,
                output={"order_id": "O1001"},
            ),
        ),
    )
    case = EvalCase(
        case_id="claimed",
        question="claimed",
        context=make_context(),
        limits=make_limits(),
        expected_tool_calls=(
            {"name": "query_order_status", "arguments": {"order_id": "O1001"}},
        ),
    )

    report = await evaluate_cases(
        [case], FakeEvaluationApplication({"claimed": claimed})
    )

    assert report.results[0].tool_selection_correct is False
    assert report.results[0].arguments_correct is False


async def test_non_echoing_tool_result_scores_from_model_call_evidence() -> None:
    result = make_result(
        content="done",
        stop_reason=StopReason.COMPLETED,
        messages=(Message(role="user", content="non-echoing"),),
        model_tool_calls=(
            ToolCall(
                id="call-1",
                name="query_order_status",
                arguments={"order_id": "O1001"},
            ),
        ),
        model_turn_count=1,
        tool_results=(
            ToolResult(
                name="query_order_status",
                code="OK",
                success=True,
                output={"status": "shipped"},
            ),
        ),
    )
    case = EvalCase(
        case_id="non-echoing",
        question="non-echoing",
        context=make_context(),
        limits=make_limits(),
        expected_tool_calls=(
            {"name": "query_order_status", "arguments": {"order_id": "O1001"}},
        ),
        max_turns=1,
    )

    report = await evaluate_cases(
        [case], FakeEvaluationApplication({"non-echoing": result})
    )

    assert report.results[0].passed is True
    assert report.tool_selection_accuracy == 1.0
    assert report.argument_accuracy == 1.0


async def test_explicit_empty_trajectory_is_scored_and_optional_security_is_null() -> None:
    result = make_result(
        content="ok",
        stop_reason=StopReason.COMPLETED,
        messages=(Message(role="user", content="plain"),),
        model_turn_count=3,
    )
    case = EvalCase(
        case_id="plain",
        question="plain",
        context=make_context(),
        limits=make_limits(),
        expected_tool_calls=(),
        max_turns=3,
    )

    report = await evaluate_cases([case], FakeEvaluationApplication({"plain": result}))
    payload = json.loads(report.to_json())

    assert report.task_success_rate == 1.0
    assert report.tool_selection_accuracy == 1.0
    assert report.argument_accuracy == 1.0
    assert report.unauthorized_action_block_rate is None
    assert report.average_turn_count == 3.0
    assert payload["tool_selection_accuracy"] == 1.0
    assert payload["argument_accuracy"] == 1.0
    assert payload["unauthorized_action_block_rate"] is None


async def test_report_with_no_cases_has_only_not_applicable_aggregates() -> None:
    report = await evaluate_cases([], FakeEvaluationApplication({}))

    assert report.task_success_rate is None
    assert report.tool_selection_accuracy is None
    assert report.argument_accuracy is None
    assert report.unauthorized_action_block_rate is None
    assert report.average_turn_count is None
