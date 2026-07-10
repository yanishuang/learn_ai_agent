"""Application-owned agent loop with explicit budgets and continuation state."""

import asyncio
import json
from dataclasses import dataclass, field

from pydantic import ConfigDict, Field

from agent_course.agents.guardrails import DefaultGuardrail, Guardrail
from agent_course.agents.sessions import InMemorySessionStore, SessionKey
from agent_course.core import (
    FrozenModel,
    Message,
    ModelContinuation,
    ModelGateway,
    RunContext,
    RunLimits,
    StopReason,
    ToolCall,
    ToolResult,
)
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.tools.registry import ToolRegistry


class AgentResult(FrozenModel):
    """Complete, typed outcome of a bounded agent run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    final_content: str | None = None
    stop_reason: StopReason
    messages: tuple[Message, ...]
    model_tool_calls: tuple[ToolCall, ...]
    model_turn_count: int = Field(ge=0)
    tool_results: tuple[ToolResult, ...]
    trace_id: str
    continuation: ModelContinuation | None = None


@dataclass(slots=True)
class _RunState:
    messages: list[Message]
    new_messages: list[Message]
    model_tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    seen_tool_calls: set[str] = field(default_factory=set)
    continuation: ModelContinuation | None = None
    final_content: str | None = None
    output_tokens: int = 0
    model_turn_count: int = 0
    executed_tool_calls: int = 0


@dataclass(slots=True)
class BoundedAgentRunner:
    """Run a model/tool loop while retaining control of every boundary."""

    model: ModelGateway
    tools: ToolRegistry
    guardrail: Guardrail = field(default_factory=DefaultGuardrail)
    sessions: InMemorySessionStore = field(default_factory=InMemorySessionStore)
    traces: InMemoryTraceSink = field(default_factory=InMemoryTraceSink)

    async def run(
        self,
        question: str,
        context: RunContext,
        limits: RunLimits,
        *,
        session_id: str | None = None,
    ) -> AgentResult:
        trace_id = self.traces.start_trace(context)
        decision = self.guardrail.check_input(question, context)
        self.traces.record(
            trace_id,
            "guardrail.checked",
            {"allowed": decision.allowed, "code": decision.code},
        )
        if not decision.allowed:
            return self._finish(
                trace_id,
                _RunState(messages=[], new_messages=[]),
                StopReason.POLICY_DENIED,
            )

        session_key = (
            SessionKey.from_context(context, session_id)
            if session_id is not None
            else None
        )
        history = self.sessions.load(session_key) if session_key is not None else []
        user_message = Message(role="user", content=question)
        state = _RunState(
            messages=[*history, user_message],
            new_messages=[user_message],
        )

        try:
            async with asyncio.timeout(limits.timeout_seconds):
                stop_reason = await self._run_loop(
                    state,
                    context,
                    limits,
                    trace_id,
                )
        except TimeoutError:
            stop_reason = StopReason.TIMEOUT
            self.traces.record(trace_id, "run.timeout")
        except Exception as error:
            stop_reason = StopReason.MODEL_ERROR
            self.traces.record(
                trace_id,
                "run.error",
                {"error_type": type(error).__name__},
            )

        if session_key is not None:
            self.sessions.append(session_key, state.new_messages)
        return self._finish(trace_id, state, stop_reason)

    async def _run_loop(
        self,
        state: _RunState,
        context: RunContext,
        limits: RunLimits,
        trace_id: str,
    ) -> StopReason:
        model_input = list(state.messages)
        for turn in range(1, limits.max_turns + 1):
            state.model_turn_count += 1
            step = await self.model.next_step(
                model_input,
                self.tools.definitions(),
                continuation=state.continuation,
            )
            state.continuation = step.continuation
            state.model_tool_calls.extend(
                call.model_copy(deep=True) for call in step.tool_calls
            )
            state.output_tokens += step.usage.output_tokens
            self.traces.record(
                trace_id,
                "model.step",
                {
                    "turn": turn,
                    "tool_call_count": len(step.tool_calls),
                    "output_tokens": step.usage.output_tokens,
                    "stop_reason": step.stop_reason,
                },
            )

            if state.output_tokens > limits.max_output_tokens:
                return StopReason.MAX_OUTPUT_TOKENS

            if step.content is not None:
                assistant_message = Message(role="assistant", content=step.content)
                state.messages.append(assistant_message)
                state.new_messages.append(assistant_message)
                state.final_content = step.content

            if not step.tool_calls:
                if step.stop_reason is StopReason.TOOL_CALLS:
                    return StopReason.MODEL_ERROR
                return step.stop_reason

            tool_messages: list[Message] = []
            for call in step.tool_calls:
                stop_reason = await self._execute_tool_call(
                    call,
                    state,
                    context,
                    limits,
                    trace_id,
                    tool_messages,
                )
                if stop_reason is not None:
                    return stop_reason

            model_input = (
                tool_messages if state.continuation is not None else list(state.messages)
            )

        return StopReason.MAX_TURNS

    async def _execute_tool_call(
        self,
        call: ToolCall,
        state: _RunState,
        context: RunContext,
        limits: RunLimits,
        trace_id: str,
        tool_messages: list[Message],
    ) -> StopReason | None:
        fingerprint = json.dumps(
            [call.name, call.arguments],
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.traces.record(
            trace_id,
            "tool.called",
            {"name": call.name, "arguments": call.arguments},
        )
        if fingerprint in state.seen_tool_calls:
            return StopReason.REPEATED_TOOL_CALL
        if state.executed_tool_calls >= limits.max_tool_calls:
            return StopReason.MAX_TOOL_CALLS

        state.seen_tool_calls.add(fingerprint)
        state.executed_tool_calls += 1
        result = await self.tools.execute(call.name, call.arguments, context)
        result = result.model_copy(update={"call_id": call.id})
        state.tool_results.append(result)
        tool_message = Message(
            role="tool",
            content=result.model_dump_json(),
            tool_call_id=call.id,
        )
        state.messages.append(tool_message)
        state.new_messages.append(tool_message)
        tool_messages.append(tool_message)
        self.traces.record(
            trace_id,
            "tool.result",
            {
                "name": result.name,
                "code": result.code,
                "success": result.success,
            },
        )

        if result.success:
            return None
        if result.code == "PERMISSION_DENIED":
            return StopReason.PERMISSION_DENIED
        if result.code == "POLICY_DENIED":
            return StopReason.POLICY_DENIED
        return StopReason.MODEL_ERROR

    def _finish(
        self,
        trace_id: str,
        state: _RunState,
        stop_reason: StopReason,
    ) -> AgentResult:
        self.traces.record(
            trace_id,
            "run.finished",
            {
                "stop_reason": stop_reason,
                "message_count": len(state.messages),
                "tool_result_count": len(state.tool_results),
            },
        )
        return AgentResult(
            final_content=state.final_content,
            stop_reason=stop_reason,
            messages=tuple(state.messages),
            model_tool_calls=tuple(state.model_tool_calls),
            model_turn_count=state.model_turn_count,
            tool_results=tuple(state.tool_results),
            trace_id=trace_id,
            continuation=state.continuation,
        )


__all__ = ["AgentResult", "BoundedAgentRunner"]
