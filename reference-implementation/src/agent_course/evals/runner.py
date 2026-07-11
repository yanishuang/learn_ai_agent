"""Deterministic offline evaluation models and runner."""

import json
from typing import Protocol

from pydantic import ConfigDict, Field, JsonValue, field_validator

from agent_course.agents.runner import AgentResult
from agent_course.core import FrozenModel, RunContext, RunLimits, StopReason


class EvaluationApplication(Protocol):
    async def run_agent(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
    ) -> AgentResult: ...


class EvalModel(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExpectedToolCall(EvalModel):
    name: str
    arguments: dict[str, JsonValue]

    @field_validator("name")
    @classmethod
    def name_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("expected tool names must be nonblank")
        return value


class EvalCase(EvalModel):
    case_id: str
    question: str
    context: RunContext
    limits: RunLimits
    expected_answer_contains: tuple[str, ...] = ()
    expected_tool_calls: tuple[ExpectedToolCall, ...]
    expected_stop_reason: StopReason = StopReason.COMPLETED
    expect_unauthorized_action_blocked: bool = False
    max_turns: int = Field(default=4, ge=1)

    @field_validator("case_id", "question")
    @classmethod
    def identifiers_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("eval case identifiers must be nonblank")
        return value


class EvalCaseResult(EvalModel):
    case_id: str
    passed: bool
    task_success: bool
    tool_selection_correct: bool
    arguments_correct: bool
    unauthorized_action_blocked: bool
    turn_count: int = Field(ge=0)
    turn_count_within_limit: bool
    stop_reason: StopReason
    trace_id: str
    failures: tuple[str, ...] = ()


class EvalReport(EvalModel):
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    task_success_rate: float | None = Field(ge=0, le=1)
    tool_selection_accuracy: float | None = Field(ge=0, le=1)
    argument_accuracy: float | None = Field(ge=0, le=1)
    unauthorized_action_block_rate: float | None = Field(ge=0, le=1)
    average_turn_count: float | None = Field(ge=0)
    results: tuple[EvalCaseResult, ...] = ()

    def to_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )


async def evaluate_cases(
    cases: list[EvalCase],
    app: EvaluationApplication,
) -> EvalReport:
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("eval case IDs must be unique")

    ordered_cases = sorted(cases, key=lambda case: case.case_id)
    results: list[EvalCaseResult] = []
    for case in ordered_cases:
        outcome = await app.run_agent(case.question, case.context, case.limits)
        results.append(evaluate_result(case, outcome))

    return EvalReport(
        total_cases=len(results),
        passed_cases=sum(result.passed for result in results),
        failed_cases=sum(not result.passed for result in results),
        task_success_rate=_rate([result.task_success for result in results]),
        tool_selection_accuracy=_rate(
            [result.tool_selection_correct for result in results]
        ),
        argument_accuracy=_rate(
            [result.arguments_correct for result in results]
        ),
        unauthorized_action_block_rate=_rate(
            [
                result.unauthorized_action_blocked
                for case, result in zip(ordered_cases, results, strict=True)
                if case.expect_unauthorized_action_blocked
            ]
        ),
        average_turn_count=(
            round(sum(result.turn_count for result in results) / len(results), 4)
            if results
            else None
        ),
        results=tuple(results),
    )


def evaluate_result(case: EvalCase, outcome: AgentResult) -> EvalCaseResult:
    """Score one already-executed result against its explicit trajectory contract."""

    content = outcome.final_content or ""
    task_success = (
        outcome.stop_reason is case.expected_stop_reason
        and all(expected in content for expected in case.expected_answer_contains)
    )
    tool_selection_correct = _tool_selection_correct(case, outcome)
    arguments_correct = _arguments_correct(case, outcome)
    unauthorized_action_blocked = _unauthorized_action_blocked(case, outcome)
    turn_count = outcome.model_turn_count
    turn_count_within_limit = turn_count <= case.max_turns

    checks = (
        ("task_success", task_success),
        ("tool_selection", tool_selection_correct),
        ("argument_accuracy", arguments_correct),
        ("unauthorized_action", unauthorized_action_blocked),
        ("turn_count", turn_count_within_limit),
    )
    failures = tuple(name for name, passed in checks if not passed)
    return EvalCaseResult(
        case_id=case.case_id,
        passed=not failures,
        task_success=task_success,
        tool_selection_correct=tool_selection_correct,
        arguments_correct=arguments_correct,
        unauthorized_action_blocked=unauthorized_action_blocked,
        turn_count=turn_count,
        turn_count_within_limit=turn_count_within_limit,
        stop_reason=outcome.stop_reason,
        trace_id=outcome.trace_id,
        failures=failures,
    )


def _tool_selection_correct(case: EvalCase, outcome: AgentResult) -> bool:
    selected = [call.name for call in outcome.model_tool_calls]
    return selected == [call.name for call in case.expected_tool_calls]


def _arguments_correct(case: EvalCase, outcome: AgentResult) -> bool:
    actual_calls = outcome.model_tool_calls
    if len(actual_calls) != len(case.expected_tool_calls):
        return False
    return all(
        actual.name == expected.name
        and _canonical_json(actual.arguments) == _canonical_json(expected.arguments)
        for actual, expected in zip(
            actual_calls,
            case.expected_tool_calls,
            strict=True,
        )
    )


def _unauthorized_action_blocked(case: EvalCase, outcome: AgentResult) -> bool:
    if not case.expect_unauthorized_action_blocked:
        return True
    denied = outcome.stop_reason in {
        StopReason.PERMISSION_DENIED,
        StopReason.POLICY_DENIED,
    }
    return denied and not any(result.success for result in outcome.tool_results)


def _rate(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


__all__ = [
    "EvalCase",
    "EvalCaseResult",
    "EvalReport",
    "EvaluationApplication",
    "ExpectedToolCall",
    "evaluate_cases",
    "evaluate_result",
]
