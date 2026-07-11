# Final Review Fix Report

Date: 2026-07-11

Branch: `codex/agent-course-redesign`

Review base: `a26755d`

Outcome: all eight Important findings and the Minor finding in
`.superpowers/sdd/final-review-findings.md` are implemented and verified.

## Execution constraints

- All implementation and verification stayed in the requested worktree.
- Default execution remained Fake/local and credential-free.
- Verification removed `OPENAI_API_KEY` and `OPENAI_MODEL`, set
  `AGENT_COURSE_LIVE_TESTS=0`, and used `UV_OFFLINE=1` where dependency or
  reference commands could otherwise consult the network.
- No Live model, remote MCP, network, or paid request was made.
- Nothing was pushed.
- The worktree was clean at the start of this fix wave. Only files required by
  the findings were changed.

## Finding resolution

### 1. Integrated Fake Know-Engine path

- Replaced the default API's empty RAG and unavailable Workflow placeholders
  with `InMemoryRetriever` and `ResearchWorkflow`.
- Added `CourseApplication.run_know_engine_scenario()` and
  `KnowEngineScenarioResult`.
- The scenario performs one causally connected flow: authorized leave-policy
  retrieval -> retrieved answer inserted into the exact Fake prompt -> bounded
  order tool loop -> evaluation of that same `AgentResult` -> approval-bound
  Workflow start/approve/resume.
- The application and runner share one trace ID. The test asserts the exact
  ordered event stream from retrieval through evaluation and Workflow
  completion, not a set of unrelated service calls.
- Added the exact deterministic Know-Engine fixture to `FakeModelGateway`.

### 2. Live output allowance and typed Responses outcomes

- Extended provider-neutral `ModelGateway.next_step()` with the optional,
  keyword-only `max_output_tokens` allowance.
- Kept Fake and test gateways compatible; Fake deliberately ignores the
  allowance while preserving deterministic behavior.
- `BoundedAgentRunner` computes remaining output allowance before every model
  turn, stops before a request when none remains, and sends the remainder on
  each request.
- `OpenAIResponsesGateway` validates and forwards that value to
  `responses.create(max_output_tokens=...)`.
- Added typed `MODEL_INCOMPLETE`, `CONTENT_FILTER`, and `CANCELLED` stop reasons.
  The adapter examines `response.status`, `incomplete_details.reason`, and
  failure policy codes. Non-success responses cannot leak content or tool calls
  into execution.

### 3. False-success removal and API terminal status

- `StructuredTool` now converts handler exceptions into a sanitized
  `ToolResult(code="TOOL_ERROR", error="tool handler failed")`.
- Added typed `TOOL_ERROR` runner termination.
- Added an exhaustive application mapping from every `StopReason` to
  `completed`, `failed`, or `cancelled`.
- Run events now match the persisted terminal state (`run.completed`,
  `run.failed`, or `run.cancelled`).
- API tests cover timeout, model failure, policy denial, permission denial, and
  handler failure, including sanitized result and event assertions.

### 4. Explicit trajectory evaluation and indirect injection

- Replaced optional single-tool expectations with required ordered
  `expected_tool_calls`, each containing exact name and arguments.
- An empty expected trajectory is represented explicitly as `[]`; any
  unexpected call fails tool selection and argument accuracy.
- Updated all agent dataset rows and evaluator aggregation so zero-tool cases
  still participate in trajectory accuracy.
- Moved the indirect document injection case to a `retrieved_agent` target.
  Authorized hostile content is retrieved, inserted into the bounded Agent's
  model-visible input, and induces an `admin_export` attempt.
- Backend permission enforcement returns `PERMISSION_DENIED` before the handler;
  the executable baseline asserts handler execution count `0`, no external
  requests, and one shared retrieval/Agent trace.

### 5. Enforced chapter teaching contract and narrowed Lab 02 promise

- Extended `scripts/validate_course.py` to require every manifested chapter to
  contain prerequisites, measurable outcomes, core knowledge, instructor demo,
  learner lab, failure injection, automated verification, scored assignment,
  distinct Core/Advanced/Production levels, current sources, and recap.
- Added root validator tests for missing sections, explicit scoring, and
  distinct completion levels.
- Completed missing teaching-contract sections across Chapters 1-5, including
  scored assignments and distinct levels in Chapters 2, 4, and 5.
- Narrowed Chapter 2 Core and Lab 02 to the implemented provider contract,
  deterministic Fake, native structured parsing, token allowance, typed status,
  and Live gate. API/structured endpoint/SSE material is explicitly instructor
  demo or Advanced work until endpoint/framing/disconnect tests exist.

### 6. Learner-facing chronology and schedule

- Removed pre-final Task-era/not-created wording and linked the real labs,
  datasets, and reference tests in the affected chapters.
- Removed the duplicate 12-week schedule from `docs/python-go-feasibility.md`;
  the canonical instructor and self-study syllabi are now the only schedule
  sources.
- Kept advanced RAG, multi-Agent, A2A, and Dodo-Agent as enrichment. The final
  feasibility recommendation no longer puts hybrid retrieval into 12-week
  Core.

### 7. MCP stable protocol and contract allowlist

- `McpExchange` now exposes negotiated `protocol_version`, exact discovered
  `tool_names`, schema hashes, and locally validated structured output.
- The client requires protocol `2025-11-25` and an exact one-tool allowlist.
- Input and output schemas are canonicalized together and checked against the
  pinned SHA-256 contract before any call.
- `structuredContent` is validated with a strict local Pydantic model, including
  nonblank fields, no extras, and requested-order ID equality.
- Focused tests cover protocol drift, unexpected/missing/duplicate tools, schema
  drift, invalid output, business error, timeout, and process cleanup.
- The real current local server under the pinned MCP SDK 1.x completed a stdio
  exchange successfully.

### 8. Frozen CI lock enforcement

- CI now runs `uv lock --check` before sync.
- Sync uses `uv sync --frozen --group dev --extra live`.
- Test and Ruff steps use `uv run --frozen --no-sync --group dev --extra live`.
- The reference README documents the same reproducible command sequence.

### 9. Markdown whitespace

- Removed the reviewed trailing-space hard breaks from Chapters 6, 7, and 8.
- Working-tree and full base-to-commit diff checks pass.

## TDD evidence

Runtime, evaluator, MCP, and validator work followed red/green cycles before
the full matrix:

| Slice | Red evidence | Green evidence |
| --- | --- | --- |
| Provider allowance, Responses statuses, tool/API errors | New focused assertions initially produced 15 expected failures | Core/runner/tool/live/API focused suite passed; final combined focused suite: 176 passed |
| Integrated Know-Engine and explicit trajectory/security | New application/evaluator/dataset assertions initially produced 4 expected failures | Application/evaluator/dataset slice: 16 passed; exact API/application final check: 14 passed |
| MCP protocol/allowlist/schema/output | New client contract tests initially produced 7 expected failures with 2 existing cleanup tests passing | `tests/test_mcp.py`: 9 passed; adjacent MCP/tool/runner slice: 38 passed |
| Chapter contract validator | New missing-contract/scoring tests initially produced 2 expected failures | Root validator suite: 25 passed; repository validator passed |

The implementation was added only after each corresponding red assertion was
observed. Adjacent suites were then run before the complete offline suite.

## Final command evidence

All commands below completed on 2026-07-11. `REF` means the
`reference-implementation/` directory; commands shown with the offline prefix
ran with credentials removed, `AGENT_COURSE_LIVE_TESTS=0`, and `UV_OFFLINE=1`.

### Frozen environment and repository gates

| Working directory | Command | Result |
| --- | --- | --- |
| REF | `uv lock --check` | exit 0; resolved 52 packages |
| REF | `uv sync --frozen --group dev --extra live` (offline) | exit 0; checked 50 packages |
| repository root | `python3 -m pytest tests/test_validate_course.py -q` | 25 passed |
| repository root | `python3 scripts/validate_course.py` | `course validation passed` |
| REF | `uv run --frozen --no-sync --group dev --extra live ruff check .` (offline) | `All checks passed!` |
| REF | `uv run --frozen --no-sync --group dev --extra live pytest -q -m 'not live'` (offline) | 208 passed, 1 warning |
| REF | `AGENT_COURSE_LIVE_TESTS=0 uv run --frozen --no-sync --group dev --extra live pytest -q` (offline) | 208 passed, 1 warning; no Live request |

The sole warning is an installed FastAPI/Starlette `TestClient` deprecation
about the future `httpx2` package. It is unrelated to these findings and does
not affect behavior or pass status.

### Focused runtime, API, evaluation, and security

| Command | Result |
| --- | --- |
| `pytest -q tests/test_core.py tests/test_agent_runner.py tests/test_tools.py tests/test_live_gates.py tests/test_api.py tests/test_application.py tests/test_evals.py tests/test_course_datasets.py tests/test_mcp.py` (frozen/offline) | 176 passed, 1 warning |
| `pytest -q tests/test_api.py tests/test_application.py` (frozen/offline) | 14 passed, 1 warning |
| `uv run --frozen --no-sync python ../evals/run_baseline.py --dataset agent` | agent 12/12 |
| `uv run --frozen --no-sync python ../evals/run_baseline.py --dataset rag` | RAG 12/12 |
| `uv run --frozen --no-sync python ../evals/run_baseline.py --dataset security` | security 12/12 |
| `uv run --frozen --no-sync python ../evals/run_baseline.py --dataset all` | agent, RAG, security each 12/12 |

### Exact affected Lab verification commands

| Lab | Documented default command result |
| --- | --- |
| 02 | Core/Fake/live-gate command: 121 passed, 1 deselected |
| 05 | Tool/permission/validation command: 20 passed, 9 deselected |
| 06 | Runner/evaluator command: 29 passed |
| 07 | RAG/API filter command: 9 passed, 12 deselected, 1 warning |
| 08 | Workflow/API command: 10 passed, 13 deselected, 1 warning |
| 09 | Validator passed; all baselines 12/12; dependency command 58 passed; dataset/evaluator command 15 passed; targeted argument/turn command 2 passed, 9 deselected |
| 10 | MCP/tool/runner command: 38 passed; cleanup/timeout command: 2 passed, 7 deselected |

### Exact local MCP checks

`uv run python -m agent_course.mcp.client O1001 --timeout 5` exited 0 and
returned:

```json
{"protocol_version":"2025-11-25","tool_names":["query_order_status"],"tool_schema_hashes":{"query_order_status":"7a448988ed2170c6a8f029bd6cc2e5113676bc65ecee91ca9eb3d75a1888fdb2"},"structured_result":{"order_id":"O1001","status":"shipped","tenant_id":"tenant-1","requested_by":"mcp-user"}}
```

`uv run python -m agent_course.mcp.client O9999 --timeout 5` exited 1 as
required and reported:

```text
error: Error executing tool query_order_status: order was not found in the caller's tenant
```

No remote MCP endpoint was contacted.

### Diff integrity

- `git diff --check`: exit 0 before commit.
- `git diff --check a26755d`: exit 0 for the complete base-to-working-tree
  patch before commit.
- `git diff --check a26755d..HEAD`: exit 0 after the focused commit.

## Residual concerns

- No blocking or behavioral concern remains from the final-review findings.
- The one non-blocking Starlette/httpx deprecation warning is recorded above;
  changing dependency strategy was outside this focused fix wave.
