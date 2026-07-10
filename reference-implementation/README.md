# Agent Course Reference Implementation

This compact scaffold supplies provider-neutral contracts, a deterministic
Fake Model, and two explicitly gated OpenAI execution paths. Python 3.12 or
newer and `uv` are required.

## Offline setup and tests

Run these exact commands from `reference-implementation/`:

```bash
uv sync --group dev --extra live
uv run --group dev --extra live pytest -q
uv run --group dev --extra live ruff check .
```

These tests make no model network requests and require no API key. The live
extra is installed so the default suite can verify that both live adapters
remain locked when configuration is absent. The Fake Model itself does not
import or require either OpenAI package.

## Deterministic fixtures

`FakeModelGateway` chooses behavior only from the latest user message. It does
not use time, randomness, environment state, or the network.

| Exact fixture phrase | Deterministic behavior |
| --- | --- |
| `什么是 Agent？` | Returns the fixed plain answer. |
| `查询订单 O1001` | Calls `query_order_status` with only `{"order_id": "O1001"}`. |
| `[fixture:timeout]` | Raises `ModelTimeoutError`. |
| `[fixture:invalid-output]` | Raises `InvalidModelOutputError`. |
| `[fixture:repeated-order-call]` | Emits the same order tool call on every invocation. |

Order and repeated-call fixtures raise `ToolUnavailableError` unless the
caller supplied `query_order_status`. Permission denial is exercised through
`RunContext.require`, where trusted identity and permissions remain outside
model-visible tool arguments.

## Optional paid live runs

Live runs can incur API charges. Set spend limits in your OpenAI account,
choose a model intentionally, and never commit real credentials. Start from
`.env.example`, then provide all three variables in the process environment:

```bash
export AGENT_COURSE_LIVE_TESTS=1
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="your-explicit-model"
```

Only the exact flag value `1` enables construction. Whitespace-only keys and
model values are rejected. Neither adapter has a default model, and
`from_environment()` only validates configuration and constructs local client
objects; it does not make a request.

## Execution ownership

`OpenAIResponsesGateway` uses the low-level Responses API. Application code
owns the loop: send messages and tool definitions, execute returned tool calls,
append structured tool results, enforce limits, and request the next step. Its
`parse_structured()` path calls `AsyncOpenAI.responses.parse()` with a Pydantic
`text_format` and rejects a response without `output_parsed`.

`OpenAIAgentsRunner` uses the OpenAI Agents SDK. The SDK owns the run lifecycle
through `Agent` and `Runner.run`; the reference wrapper selects the configured
model and disables sensitive trace data by default.
