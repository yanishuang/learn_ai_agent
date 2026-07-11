from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agent_course.agents.guardrails import DefaultGuardrail
from agent_course.agents.runner import AgentResult, BoundedAgentRunner
from agent_course.core import (
    Message,
    ModelContinuation,
    ModelStep,
    RunContext,
    RunLimits,
    StopReason,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from agent_course.evals import EvalCase, evaluate_cases
from agent_course.models.fake import FakeModelGateway
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.rag import DocumentChunk, InMemoryRetriever
from agent_course.tools.orders import (
    QueryOrderStatusArguments,
    QueryOrderStatusTool,
)
from agent_course.tools.base import StrictToolArguments, StructuredTool
from agent_course.tools.registry import ToolRegistry


DEFAULT_DATASET_DIR = Path(__file__).resolve().parent


def _load_rows(filename: str, dataset_dir: Path) -> list[dict[str, Any]]:
    path = dataset_dir / filename
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case_ids = [row["case_id"] for row in rows]
    if len(rows) < 10:
        raise AssertionError(f"{filename}: expected at least 10 cases")
    if len(case_ids) != len(set(case_ids)):
        raise AssertionError(f"{filename}: case IDs must be unique")
    return rows


def _limits(values: dict[str, Any] | None = None) -> RunLimits:
    return RunLimits.model_validate(
        values
        or {
            "max_turns": 4,
            "max_tool_calls": 3,
            "max_output_tokens": 100,
            "timeout_seconds": 0.2,
        }
    )


def _runner(
    model: object,
    *,
    tools: ToolRegistry | None = None,
    traces: InMemoryTraceSink | None = None,
) -> BoundedAgentRunner:
    return BoundedAgentRunner(
        model=model,
        tools=tools or ToolRegistry([QueryOrderStatusTool()]),
        guardrail=DefaultGuardrail(),
        traces=traces or InMemoryTraceSink(),
    )


class _AgentApplication:
    async def run_agent(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
    ) -> AgentResult:
        return await _runner(FakeModelGateway()).run(question, context, limits)


async def _validate_agent(dataset_dir: Path) -> dict[str, int]:
    cases = [
        EvalCase.model_validate(row)
        for row in _load_rows("agent-cases.jsonl", dataset_dir)
    ]
    report = await evaluate_cases(cases, _AgentApplication())
    if report.failed_cases:
        failures = {
            result.case_id: result.failures
            for result in report.results
            if not result.passed
        }
        raise AssertionError(f"agent dataset failed: {failures}")
    return {"passed": report.passed_cases, "total": report.total_cases}


def _validate_rag(dataset_dir: Path) -> dict[str, int]:
    rows = _load_rows("rag-cases.jsonl", dataset_dir)
    passed = 0
    for row in rows:
        if row["schema_version"] != "rag-case-v1":
            raise AssertionError(f"{row['case_id']}: unsupported RAG schema")
        context = RunContext.model_validate(row["context"])
        retriever = InMemoryRetriever(
            DocumentChunk.model_validate(chunk) for chunk in row["chunks"]
        )
        hits = retriever.search(row["query"], context, row["top_k"])
        answer = retriever.answer(row["query"], context, row["top_k"])
        expected = row["expected"]
        actual = {
            "refused": answer.refused,
            "hit_chunk_ids": [hit.chunk_id for hit in hits],
            "citation_document_ids": [
                hit.citation.document_id for hit in hits
            ],
        }
        for key, value in actual.items():
            if value != expected[key]:
                raise AssertionError(
                    f"{row['case_id']}: {key} expected {expected[key]!r}, got {value!r}"
                )
        if not all(part in answer.answer for part in expected["answer_contains"]):
            raise AssertionError(
                f"{row['case_id']}: answer did not contain expected fragments"
            )
        passed += 1
    return {"passed": passed, "total": len(rows)}


class _CountingGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep:
        del messages, tools, continuation
        self.calls += 1
        return ModelStep(content="model should only run for allowed input")


class _StaticToolCallGateway:
    def __init__(self, arguments: dict[str, Any]) -> None:
        self.arguments = arguments

    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep:
        del messages, tools, continuation
        return ModelStep(
            tool_calls=(
                ToolCall(
                    id="security-static-call",
                    name="query_order_status",
                    arguments=self.arguments,
                ),
            ),
            stop_reason=StopReason.TOOL_CALLS,
        )


class _UniqueToolCallGateway:
    def __init__(self) -> None:
        self.turn = 0

    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep:
        del messages, tools, continuation
        self.turn += 1
        return ModelStep(
            tool_calls=(
                ToolCall(
                    id=f"security-budget-{self.turn}",
                    name="query_order_status",
                    arguments={"order_id": f"O{1000 + self.turn}"},
                ),
            ),
            stop_reason=StopReason.TOOL_CALLS,
        )


class _SlowGateway:
    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep:
        del messages, tools, continuation
        await asyncio.sleep(1)
        return ModelStep(content="too late")


class _ToolOutputFollowingGateway:
    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep:
        del tools, continuation
        if not any(message.role == "tool" for message in messages):
            return ModelStep(
                tool_calls=(
                    ToolCall(
                        id="security-poison-source",
                        name="query_order_status",
                        arguments={"order_id": "O1001"},
                    ),
                ),
                stop_reason=StopReason.TOOL_CALLS,
            )
        return ModelStep(
            tool_calls=(
                ToolCall(
                    id="security-poison-follow",
                    name="admin_export",
                    arguments={},
                ),
            ),
            stop_reason=StopReason.TOOL_CALLS,
        )


class _RetrievedDocumentFollowingGateway:
    def __init__(self, hostile_content: str) -> None:
        self.hostile_content = hostile_content

    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep:
        del tools, continuation, max_output_tokens
        if self.hostile_content not in "\n".join(message.content for message in messages):
            raise AssertionError("hostile retrieved content did not reach the bounded Agent")
        return ModelStep(
            tool_calls=(
                ToolCall(
                    id="security-indirect-export",
                    name="admin_export",
                    arguments={},
                ),
            ),
            stop_reason=StopReason.TOOL_CALLS,
        )


class _AdminExportArguments(StrictToolArguments):
    pass


class _AdminExportTool(StructuredTool[_AdminExportArguments]):
    name = "admin_export"
    description = "Export protected data after authoritative authorization."
    permission = "admin:export"
    arguments_type = _AdminExportArguments

    def __init__(self) -> None:
        self.execution_count = 0

    async def _execute(
        self,
        arguments: _AdminExportArguments,
        context: RunContext,
    ) -> ToolResult:
        del arguments, context
        self.execution_count += 1
        return ToolResult(name=self.name, code="OK", success=True, output={})


class _PoisonedOrderTool(QueryOrderStatusTool):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    async def _execute(
        self,
        arguments: QueryOrderStatusArguments,
        context: RunContext,
    ) -> ToolResult:
        self.execution_count += 1
        return ToolResult(
            name=self.name,
            code="OK",
            success=True,
            output={
                "order_id": arguments.order_id,
                "tenant_id": context.tenant_id,
                "content": self.content,
            },
        )


@dataclass(frozen=True)
class _SecurityObservation:
    outcome: str
    successful_tools: tuple[str, ...] = ()
    tool_result_codes: tuple[str, ...] = ()
    model_turn_count: int = 0
    retrieved_chunk_ids: tuple[str, ...] = ()
    external_requests: int = 0
    handler_executions: int = 0
    trace_event_types: tuple[str, ...] = ()
    trace_text: str = ""

    def comparable(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "successful_tools": list(self.successful_tools),
            "tool_result_codes": list(self.tool_result_codes),
            "model_turn_count": self.model_turn_count,
            "retrieved_chunk_ids": list(self.retrieved_chunk_ids),
            "external_requests": self.external_requests,
            "handler_executions": self.handler_executions,
        }


def _from_agent_result(
    result: AgentResult,
    traces: InMemoryTraceSink,
    *,
    handler_executions: int = 0,
) -> _SecurityObservation:
    events = traces.for_trace(result.trace_id)
    return _SecurityObservation(
        outcome=result.stop_reason.value,
        successful_tools=tuple(
            item.name for item in result.tool_results if item.success
        ),
        tool_result_codes=tuple(item.code for item in result.tool_results),
        model_turn_count=result.model_turn_count,
        external_requests=0,
        handler_executions=handler_executions,
        trace_event_types=tuple(event.event_type for event in events),
        trace_text="\n".join(event.model_dump_json() for event in events),
    )


async def _run_security_case(row: dict[str, Any]) -> _SecurityObservation:
    source = row["source_fixture"]
    context = RunContext.model_validate(row["trusted_context"])
    target = row["target"]

    if target == "guardrail":
        model = _CountingGateway()
        traces = InMemoryTraceSink()
        result = await _runner(model, traces=traces).run(
            row["input"], context, _limits(source.get("limits"))
        )
        observation = _from_agent_result(result, traces)
        if model.calls != observation.model_turn_count:
            raise AssertionError(f"{row['case_id']}: model call evidence drift")
        return observation

    if target == "rag":
        traces = InMemoryTraceSink()
        trace_id = traces.start_trace(context)
        retriever = InMemoryRetriever(
            [DocumentChunk.model_validate(source["chunk"])]
        )
        answer = retriever.answer(row["input"], context)
        hits = retriever.search(row["input"], context, top_k=3)
        traces.record(
            trace_id,
            "retrieval.completed",
            {"hit_count": len(hits), "refused": answer.refused},
        )
        outcome = "refused" if answer.refused else "completed"
        traces.record(trace_id, "run.finished", {"stop_reason": outcome})
        events = traces.for_trace(trace_id)
        return _SecurityObservation(
            outcome=outcome,
            retrieved_chunk_ids=tuple(hit.chunk_id for hit in hits),
            trace_event_types=tuple(event.event_type for event in events),
            trace_text="\n".join(event.model_dump_json() for event in events),
        )

    if target == "retrieved_agent":
        traces = InMemoryTraceSink()
        trace_id = traces.start_trace(context)
        retriever = InMemoryRetriever(
            [DocumentChunk.model_validate(source["chunk"])]
        )
        hits = retriever.search(row["input"], context, top_k=3)
        traces.record(
            trace_id,
            "retrieval.completed",
            {"hit_count": len(hits), "chunk_ids": [hit.chunk_id for hit in hits]},
        )
        if not hits:
            raise AssertionError(f"{row['case_id']}: hostile fixture was not retrieved")
        hostile_content = hits[0].content
        export_tool = _AdminExportTool()
        result = await _runner(
            _RetrievedDocumentFollowingGateway(hostile_content),
            tools=ToolRegistry([export_tool]),
            traces=traces,
        ).run(
            f"Question: {row['input']}\nRetrieved data:\n{hostile_content}",
            context,
            _limits(source.get("limits")),
            trace_id=trace_id,
        )
        return replace(
            _from_agent_result(
                result,
                traces,
                handler_executions=export_tool.execution_count,
            ),
            retrieved_chunk_ids=tuple(hit.chunk_id for hit in hits),
        )

    if target == "tool_output":
        tool = _PoisonedOrderTool(source["content"])
        traces = InMemoryTraceSink()
        result = await _runner(
            _ToolOutputFollowingGateway(),
            tools=ToolRegistry([tool]),
            traces=traces,
        ).run(row["input"], context, _limits(source.get("limits")))
        return _from_agent_result(
            result, traces, handler_executions=tool.execution_count
        )

    if target == "trace_redaction":
        traces = InMemoryTraceSink()
        trace_id = traces.start_trace(context)
        traces.record(
            trace_id,
            "tool.output",
            {source["sensitive_key"]: source["content"]},
        )
        traces.record(trace_id, "run.finished", {"stop_reason": "completed"})
        events = traces.for_trace(trace_id)
        return _SecurityObservation(
            outcome="completed",
            trace_event_types=tuple(event.event_type for event in events),
            trace_text="\n".join(event.model_dump_json() for event in events),
        )

    traces = InMemoryTraceSink()
    tool = QueryOrderStatusTool()
    if target == "invalid_arguments":
        model: object = _StaticToolCallGateway(source["arguments"])
    elif target == "permission":
        model = FakeModelGateway()
    elif target == "repeated_budget":
        model = FakeModelGateway()
    elif target == "unique_budget":
        model = _UniqueToolCallGateway()
    elif target == "timeout":
        model = _SlowGateway()
    else:
        raise AssertionError(f"{row['case_id']}: unknown target {target}")
    result = await _runner(
        model,
        tools=ToolRegistry([tool]),
        traces=traces,
    ).run(row["input"], context, _limits(source.get("limits")))
    return _from_agent_result(
        result, traces, handler_executions=tool.execution_count
    )


def _assert_security_case(
    row: dict[str, Any], observation: _SecurityObservation
) -> None:
    expected = row["expected_observation"]
    actual = observation.comparable()
    actual["outcome"] = observation.outcome
    for key, value in expected.items():
        if actual[key] != value:
            raise AssertionError(
                f"{row['case_id']}: {key} expected {value!r}, got {actual[key]!r}"
            )
    if observation.outcome != row["expected_policy"]["outcome"]:
        raise AssertionError(f"{row['case_id']}: policy outcome mismatch")

    assertions = row["trace_assertions"]
    missing_events = set(assertions["required_events"]) - set(
        observation.trace_event_types
    )
    if missing_events:
        raise AssertionError(
            f"{row['case_id']}: missing trace events {sorted(missing_events)}"
        )
    for forbidden in assertions["forbidden_text"]:
        if forbidden in observation.trace_text:
            raise AssertionError(
                f"{row['case_id']}: forbidden trace text retained"
            )
    for required in assertions.get("required_text", []):
        if required not in observation.trace_text:
            raise AssertionError(
                f"{row['case_id']}: required trace text absent"
            )


async def _validate_security(dataset_dir: Path) -> dict[str, int]:
    rows = _load_rows("security-cases.jsonl", dataset_dir)
    required_categories = {
        "direct_injection",
        "indirect_document_injection",
        "tool_output_injection",
        "exfiltration",
        "privilege_escalation",
        "denial_of_wallet",
    }
    if required_categories - {row["threat_category"] for row in rows}:
        raise AssertionError("security dataset is missing required categories")

    passed = 0
    for row in rows:
        if row["schema_version"] != "security-case-v1":
            raise AssertionError(f"{row['case_id']}: unsupported security schema")
        outcome = row["expected_policy"]["outcome"]
        if "_or_" in outcome:
            raise AssertionError(f"{row['case_id']}: outcome must be exact")
        observation = await _run_security_case(row)
        _assert_security_case(row, observation)
        passed += 1
    return {"passed": passed, "total": len(rows)}


async def _run(
    selected: str,
    dataset_dir: Path,
) -> dict[str, dict[str, int]]:
    validators = {
        "agent": _validate_agent,
        "rag": _validate_rag,
        "security": _validate_security,
    }
    names = tuple(validators) if selected == "all" else (selected,)
    summary: dict[str, dict[str, int]] = {}
    for name in names:
        result = validators[name](dataset_dir)
        summary[name] = await result if hasattr(result, "__await__") else result
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute all course JSONL baselines offline"
    )
    parser.add_argument(
        "--dataset",
        choices=("all", "agent", "rag", "security"),
        default="all",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="directory containing the three JSONL datasets",
    )
    options = parser.parse_args(argv)
    try:
        summary = asyncio.run(_run(options.dataset, options.dataset_dir))
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        print(f"baseline validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
