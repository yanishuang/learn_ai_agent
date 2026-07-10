# AI Agent Course Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the repository into a current, executable, dual-track AI Agent course with fifteen complete chapters, deterministic offline labs, optional live OpenAI integration, instructor materials, assessments, and automated validation.

**Architecture:** The Markdown course remains the source of truth, while one `reference-implementation/` application supplies reusable code for chapter labs. The application uses explicit interfaces for model access, tools, Agent runs, RAG, Workflow, evaluation, and tracing so Fake and live providers share the same teaching contracts. Course validation checks chapter structure, local links, maturity labels, JSONL data, and the relationship between promised labs and actual files.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, OpenAI Responses API, OpenAI Agents SDK, MCP Python SDK, pytest, optional PostgreSQL/pgvector, Markdown, JSONL, GitHub Actions.

## Global Constraints

- Python `>=3.12` is required by the reference implementation.
- Core tests must run without network access, credentials, Docker, PostgreSQL, or a paid model call.
- Live OpenAI behavior must require both `OPENAI_API_KEY` and `AGENT_COURSE_LIVE_TESTS=1`.
- `OPENAI_MODEL` must be explicitly configured in live mode; there is no hardcoded course default.
- User identity, tenant identity, permissions, and approval state come from trusted `RunContext`, never model-generated tool arguments.
- Python is the only required implementation language; Go remains an optional extension.
- MCP `2025-11-25` remains the stable teaching baseline until the repository is deliberately re-verified after the next final specification release.
- A2A remains optional while its published specification is pre-1.0.
- Every chapter has prerequisites, measurable outcomes, a demonstration, a lab, failure injection, verification, assignment, rubric, completion levels, recap, and primary sources.
- Existing illustration assets are preserved unless a replacement materially improves teaching clarity.
- Existing unrelated user changes must not be reverted.

## Execution Order

Execute task briefs in dependency order rather than numeric presentation order:

```text
1 -> 2 -> 8 -> 9 -> 10 -> 4 -> 5 -> 6 -> 7 -> 11 -> 3 -> 12
```

This ensures the reference implementation exists before chapter code is finalized, labs exist before the README and course map link to them, and the final portal describes verified commands rather than planned commands.

---

### Task 1: Add Course Validation Before Structural Changes

**Files:**
- Create: `scripts/validate_course.py`
- Create: `tests/test_validate_course.py`
- Create: `.github/workflows/course-ci.yml`

**Interfaces:**
- Consumes: Markdown files under `README.md`, `chapters/`, `docs/`, `teaching/`, and `labs/` when present.
- Produces: `validate_repository(root: Path, *, require_course_structure: bool = True) -> list[str]` and a CLI that exits `0` with `course validation passed` or exits `1` after printing each error.

- [ ] **Step 1: Write validator tests for the current structural gaps**

```python
from pathlib import Path

from scripts.validate_course import validate_repository


def test_missing_local_markdown_link_is_reported(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("[missing](chapters/99.md)\n", encoding="utf-8")
    assert validate_repository(tmp_path, require_course_structure=False) == [
        "README.md: broken local link chapters/99.md"
    ]


def test_invalid_jsonl_is_reported(tmp_path: Path) -> None:
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / "cases.jsonl").write_text("{not-json}\n", encoding="utf-8")
    assert validate_repository(tmp_path, require_course_structure=False) == [
        "evals/cases.jsonl:1: invalid JSON"
    ]
```

- [ ] **Step 2: Run the tests and verify the validator does not exist**

Run:

```bash
python3 -m pytest tests/test_validate_course.py -q
```

Expected: collection fails because `scripts.validate_course` is missing.

- [ ] **Step 3: Implement the validator**

The implementation must:

- parse Markdown links with `urllib.parse` and `pathlib`, ignoring `http`, `https`, anchors, and fenced code blocks;
- validate every non-empty JSONL line with `json.loads`;
- load `docs/course-manifest.json` when it exists, then require every listed chapter path and exact top-level heading;
- skip manifest structure checks before Task 2 creates the manifest, while still checking links and JSONL;
- require maturity labels in the ecosystem matrix after Task 3;
- expose `validate_repository(root: Path, *, require_course_structure: bool = True) -> list[str]` without terminating the process;
- keep deterministic error ordering.

- [ ] **Step 4: Add CI**

The workflow must use Python 3.12 and run:

```bash
python -m pip install pytest
python -m pytest tests/test_validate_course.py -q
python scripts/validate_course.py
```

- [ ] **Step 5: Run tests and the validator**

Expected: unit tests pass and the current repository passes link/JSON validation; manifest structure checks begin in Task 2.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_course.py tests/test_validate_course.py .github/workflows/course-ci.yml
git commit -m "test: add course structure validation"
```

---

### Task 2: Migrate To The Approved Fifteen-Chapter Structure

**Files:**
- Create: `chapters/00-course-setup.md`
- Rename: `chapters/08-agent-basics.md` -> `chapters/06-agent-runtime.md`
- Rename: `chapters/06-rag-basics.md` -> `chapters/07-rag-core.md`
- Rename: `chapters/09-workflow-state-machine.md` -> `chapters/08-workflow-durable-execution.md`
- Create: `chapters/09-agent-evaluation-observability-security.md`
- Keep: `chapters/10-mcp-integration.md`
- Rename: `chapters/07-advanced-rag-and-evaluation.md` -> `chapters/11-advanced-rag-and-data-routing.md`
- Rename: `chapters/11-agent-interoperability.md` -> `chapters/12-agent-interoperability.md`
- Create: `chapters/13-product-experience-and-production.md`
- Create: `chapters/14-know-engine-capstone.md`
- Create: `chapters/15-dodo-agent-capstone.md`
- Create: `docs/course-manifest.json`
- Modify: `chapters/01-ai-agent-overview.md`
- Modify: `chapters/02-llm-application-basics.md`
- Modify: `chapters/03-prompt-and-context-engineering.md`
- Modify: `chapters/04-python-ai-application-stack.md`
- Modify: `chapters/05-tool-calling.md`
- Modify: `chapters/10-mcp-integration.md`
- Modify: `docs/python-go-feasibility.md`

**Interfaces:**
- Consumes: approved curriculum mapping in `docs/superpowers/specs/2026-07-10-agent-course-redesign-design.md`.
- Produces: exactly one setup unit and chapters 1-15, with chapter paths and exact headings declared in `docs/course-manifest.json`.

- [ ] **Step 1: Move existing files with `git mv`**

Use the exact rename map above so Git history remains legible.

- [ ] **Step 2: Add complete chapter shells**

Each new chapter must immediately include these concrete headings so the validator can enforce them:

```markdown
## 本章定位
## 前置知识
## 学习目标
## 核心知识
## 教师演示
## 学员实验
## 失败注入与排错
## 自动验证
## 作业与评分
## Core / Advanced / Production 完成标准
## 本章资料
## 复盘模板
```

The shells must contain the approved scope in full sentences, not placeholders.

- [ ] **Step 3: Add the machine-readable course manifest**

The JSON file contains ordered objects with `number`, `path`, `title`, and `track`. It declares setup as number `0`, chapters 1-10 and 13-14 as `core`, and chapters 11-12 and 15 as `advanced`.

- [ ] **Step 4: Renumber headings, recaps, and cross-references**

Update all moved chapter numbers, including prose such as “第 8 章”, recap headings, paths, and source fixture names. Do not perform a blind global replacement; check each semantic reference.

- [ ] **Step 5: Run structural searches**

```bash
rg -n '第 8 章：Agent|第 6 章：RAG|第 9 章：Workflow|第 7 章：高级 RAG|第 11 章：Agent 互操作' README.md chapters docs
python scripts/validate_course.py
```

Expected: stale heading search returns no obsolete title; validator has no missing-chapter errors.

- [ ] **Step 6: Commit**

```bash
git add chapters docs/course-manifest.json docs/python-go-feasibility.md
git commit -m "docs: restructure agent course chapters"
```

---

### Task 3: Replace README With A Dual-Track Course Portal

**Files:**
- Modify: `README.md`
- Create: `docs/course-map.md`
- Create: `docs/ecosystem-maturity.md`

**Interfaces:**
- Consumes: chapter files from Task 2.
- Produces: a short entry point, a detailed outcome map, and dated ecosystem maturity records.

- [ ] **Step 1: Rewrite README as an entry point**

README must contain:

- course promise and audience;
- Python-first/Go-optional decision;
- quick start with Fake Model and optional live mode;
- 12-week instructor and 16-20 week self-study links;
- chapter table linking setup and all fifteen chapters;
- Core and Advanced route distinction;
- required Know-Engine and optional Dodo-Agent outcomes;
- links to teaching, labs, reference implementation, evals, feasibility, and ecosystem maturity;
- a maintenance note with the last verification date.

README must not duplicate each chapter’s full goals and assignments.

- [ ] **Step 2: Build the outcome map**

`docs/course-map.md` maps every chapter to:

| Chapter | Capability | Lab | Automated check | Portfolio evidence | Required in 12 weeks |
| --- | --- | --- | --- | --- | --- |

Every promised lab path and command must correspond to a file created by Tasks 8-11.

- [ ] **Step 3: Build the ecosystem maturity matrix**

Use columns:

```markdown
| Technology | Role | Maturity | Course status | Verified | Primary source |
```

Include Responses API, Agents SDK, Pydantic AI, LangGraph, MCP stable, MCP RC, MCP Apps, Apps SDK, A2A, Google ADK, Microsoft Agent Framework, and Claude Agent SDK. Label current preview/experimental/RC status explicitly and avoid predicting final behavior.

- [ ] **Step 4: Validate links and size**

```bash
python scripts/validate_course.py
wc -l README.md
```

Expected: validator passes local-link checks; README is no more than 280 lines.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/course-map.md docs/ecosystem-maturity.md
git commit -m "docs: turn readme into dual-track course portal"
```

---

### Task 4: Modernize Chapters 1-5

**Files:**
- Modify: `chapters/01-ai-agent-overview.md`
- Modify: `chapters/02-llm-application-basics.md`
- Modify: `chapters/03-prompt-and-context-engineering.md`
- Modify: `chapters/04-python-ai-application-stack.md`
- Modify: `chapters/05-tool-calling.md`

**Interfaces:**
- Consumes: reference application contracts specified in Tasks 8-9.
- Produces: concept and code guidance that exactly matches the runnable labs.

- [ ] **Step 1: Correct Chapter 1 taxonomy**

Replace the mutually exclusive solution tree with a five-axis decision card:

```text
Knowledge: public / private / real-time
Action: none / read / write / irreversible
Path: fixed / branching / open-ended
State: one-shot / session / durable
Risk: low / controlled / high
```

Explain that RAG, tools, Workflow, and Agent are composable layers.

- [ ] **Step 2: Replace Chapter 2 structured-output implementation**

Teach this live adapter contract:

```python
response = await client.responses.parse(
    model=settings.openai_model,
    input=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ],
    text_format=LessonAnswer,
)
return response.output_parsed
```

Keep prompt-only JSON plus `json.loads` in a clearly labeled compatibility note. Remove the `gpt-4.1-mini` default; require `OPENAI_MODEL` in live mode. Correct SSE framing by serializing event payloads as JSON and handling disconnect/cancellation.

- [ ] **Step 3: Expand Chapter 3 threat model**

Add indirect injection from documents, web pages, emails, and tool outputs; taint tracking; context provenance; least privilege; data minimization; compaction; prompt caching; executable prompt tests; and the distinction between instruction precedence and enforceable application policy.

- [ ] **Step 4: Clarify Chapter 4 framework boundaries**

Separate Pydantic validation from Pydantic AI. Make the model gateway and run context the core architecture. Move long framework comparisons to `docs/ecosystem-maturity.md` and keep only selection rules in the chapter.

- [ ] **Step 5: Correct Chapter 5 authorization and tool execution**

Teach the exact signature:

```python
async def query_order_status(
    arguments: OrderStatusArguments,
    context: RunContext,
) -> ToolResult:
    context.require("orders:read")
    return await order_repository.get_for_tenant(
        order_id=arguments.order_id,
        tenant_id=context.tenant_id,
    )
```

The model-visible schema contains only `order_id`. Add effect classes, idempotency, approval, retry policy, tool poisoning, argument accuracy, tool-selection evaluation, and a complete low-level Responses tool loop.

- [ ] **Step 6: Check code references against the planned interfaces**

```bash
rg -n 'gpt-4\.1-mini|user_id: str,.*order_id|只返回 JSON' chapters/0[1-5]-*.md
python scripts/validate_course.py
```

Expected: no hardcoded stale model default or model-visible identity argument remains; prompt-only JSON appears only in the compatibility section.

- [ ] **Step 7: Commit**

```bash
git add chapters/01-* chapters/02-* chapters/03-* chapters/04-* chapters/05-*
git commit -m "docs: modernize model context and tool foundations"
```

---

### Task 5: Build The Core Agent, RAG, Workflow, And Evaluation Chapters

**Files:**
- Modify: `chapters/06-agent-runtime.md`
- Modify: `chapters/07-rag-core.md`
- Modify: `chapters/08-workflow-durable-execution.md`
- Modify: `chapters/09-agent-evaluation-observability-security.md`

**Interfaces:**
- Consumes: runner, retriever, workflow, trace, and evaluator interfaces from Tasks 9-10.
- Produces: teaching content aligned with executable tests and datasets.

- [ ] **Step 1: Expand Chapter 6 into the central Agent chapter**

Cover Responses-owned loop versus SDK-owned run, `RunLimits`, sessions, guardrails, results, resumable approval, stop reasons, memory retention, trace redaction, and trajectory evaluation. The primary example must set actual limits rather than only listing them.

- [ ] **Step 2: Correct Chapter 7 data and permission models**

Document fields for `document_version`, `content_hash`, `embedding_model`, `embedding_dimensions`, `chunker_version`, `page_number`, `source_offset`, and `access_scope`. Retrieval examples must apply tenant and user-access filters in the query itself. Present HNSW and IVFFlat trade-offs instead of treating IVFFlat as a universal default.

- [ ] **Step 3: Complete Chapter 8 durability semantics**

Add `workflow_version`, `waiting_for_input`, `retrying`, `timed_out`, and `cancelled` states; unique idempotency constraints; approval payload hashes and expiry; side-effect placement; deterministic resume boundaries; and model-output snapshotting.

- [ ] **Step 4: Write Chapter 9 in full**

The chapter must implement and explain:

- deterministic assertions before LLM judges;
- task, tool, argument, trajectory, policy, latency, and cost metrics;
- trace grading and dataset regression;
- calibration and repeated runs for stochastic behavior;
- offline versus online evaluation;
- red-team datasets and response procedures;
- why self-reported confidence is not a safety control.

- [ ] **Step 5: Validate chapter labs and rubrics**

Every chapter must reference the exact lab directory and default pytest command created later. No chapter may claim a production feature without either runnable code or an explicitly labeled design exercise.

- [ ] **Step 6: Commit**

```bash
git add chapters/06-* chapters/07-* chapters/08-* chapters/09-*
git commit -m "docs: establish agent runtime durability and eval core"
```

---

### Task 6: Complete MCP, Advanced RAG, And Multi-Agent Chapters

**Files:**
- Modify: `chapters/10-mcp-integration.md`
- Modify: `chapters/11-advanced-rag-and-data-routing.md`
- Modify: `chapters/12-agent-interoperability.md`

**Interfaces:**
- Consumes: MCP example, RRF function, and Agent contracts from Tasks 9-10.
- Produces: advanced chapters with explicit maturity and trust boundaries.

- [ ] **Step 1: Add a runnable MCP client path to Chapter 10**

Document both the stdio server command and client command. Add authorization versus business permission, token audience, consent, server allowlist, schema drift, output schema, protocol version, timeouts, and untrusted tool descriptions. Remove “Go server required for production”; make Go an optional extension.

- [ ] **Step 2: Correct hybrid retrieval in Chapter 11**

Use RRF as the default implementation:

```python
def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.__getitem__, reverse=True)
```

Weighted score fusion must state that scores require normalization and validation. Expand Text2SQL controls to AST parsing, read-only credentials, statement timeout, row limit, tenant enforcement, and audit.

- [ ] **Step 3: Add maturity gates to Chapter 12**

Keep A2A optional and pre-1.0. Teach agents-as-tools and handoffs before remote interoperability. Label Microsoft Agent Framework preview status and Google ADK A2A support maturity from primary docs. Do not make framework-specific APIs required work.

- [ ] **Step 4: Commit**

```bash
git add chapters/10-* chapters/11-* chapters/12-*
git commit -m "docs: complete protocol retrieval and interoperability tracks"
```

---

### Task 7: Write Productization And Both Capstones

**Files:**
- Modify: `chapters/13-product-experience-and-production.md`
- Modify: `chapters/14-know-engine-capstone.md`
- Modify: `chapters/15-dodo-agent-capstone.md`

**Interfaces:**
- Consumes: all core chapter outputs and reference application commands.
- Produces: a complete production chapter, one required capstone, and one bounded optional capstone.

- [ ] **Step 1: Write Chapter 13**

Cover task creation, SSE/WebSocket progress, cancellation, retries, citations, tool activity, approvals, enterprise IM boundaries, deployment, secrets, work identity, rate limits, quotas, tenant isolation, retention, incident handling, CI release gates, and production review. Include an explicit UX state machine for queued, running, waiting, completed, failed, and cancelled runs.

- [ ] **Step 2: Write Chapter 14 as a milestone-driven required project**

Milestones must be independently demonstrable:

1. Reproducible setup and sample documents.
2. Ingestion and citations.
3. Permission-aware retrieval.
4. Bounded single Agent and Workflow.
5. MCP integration.
6. Evaluation and red-team report.
7. Production-readiness review and final demonstration.

Provide Core, Advanced, and Production rubrics and explicitly exclude unnecessary graph and multi-Agent work from Core.

- [ ] **Step 3: Write Chapter 15 as an optional bounded project**

Require one router, KnowledgeAgent, and ReportAgent first. Add ResearchAgent, handoffs, registry, and A2A only in Advanced. Explicitly exclude automatic Agent generation, arbitrary code execution, universal runtime abstraction, and automatic high-risk actions.

- [ ] **Step 4: Commit**

```bash
git add chapters/13-* chapters/14-* chapters/15-*
git commit -m "docs: add production and capstone teaching chapters"
```

---

### Task 8: Scaffold The Deterministic Reference Implementation

**Files:**
- Create: `reference-implementation/pyproject.toml`
- Create: `reference-implementation/.env.example`
- Create: `reference-implementation/README.md`
- Create: `reference-implementation/src/agent_course/__init__.py`
- Create: `reference-implementation/src/agent_course/core.py`
- Create: `reference-implementation/src/agent_course/models/__init__.py`
- Create: `reference-implementation/src/agent_course/models/base.py`
- Create: `reference-implementation/src/agent_course/models/fake.py`
- Create: `reference-implementation/src/agent_course/models/openai_responses.py`
- Create: `reference-implementation/src/agent_course/agents/__init__.py`
- Create: `reference-implementation/src/agent_course/agents/openai_agents.py`
- Create: `reference-implementation/tests/test_fake_model.py`
- Create: `reference-implementation/tests/test_live_gates.py`
- Generate: `reference-implementation/uv.lock`

**Interfaces:**
- Produces:
  - `RunContext.require(permission: str) -> None`
  - `RunContext(user_id: str, tenant_id: str, request_id: str, permissions: frozenset[str])`
  - `RunLimits(max_turns: int, max_tool_calls: int, max_output_tokens: int, timeout_seconds: float)`
  - `ModelGateway.next_step(messages: list[Message], tools: list[ToolDefinition]) -> ModelStep`
  - `FakeModelGateway` and `OpenAIResponsesGateway`.
  - `OpenAIAgentsRunner.from_environment()` for the SDK-managed live path.

- [ ] **Step 1: Write failing Fake Model tests**

```python
import pytest

from agent_course.core import Message, ToolDefinition
from agent_course.models.fake import FakeModelGateway


@pytest.mark.asyncio
async def test_fake_model_emits_order_tool_call() -> None:
    model = FakeModelGateway()
    step = await model.next_step(
        messages=[Message(role="user", content="查询订单 O1001")],
        tools=[
            ToolDefinition(
                name="query_order_status",
                description="查询订单状态",
                input_schema={"type": "object"},
            )
        ],
    )
    assert step.tool_calls[0].name == "query_order_status"
    assert step.tool_calls[0].arguments == {"order_id": "O1001"}
```

- [ ] **Step 2: Run the test and verify failure**

Run from `reference-implementation/`:

```bash
python3.12 -m pytest tests/test_fake_model.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement core types and Fake Model**

Use frozen Pydantic models for messages, tool calls, model steps, tool results, and run limits. Fake behavior must be deterministic and selected by explicit fixture phrases, not random generation.

- [ ] **Step 4: Define and lock dependency groups**

Core dependencies are `fastapi`, `mcp`, `pydantic`, `pydantic-settings`, and `uvicorn`. The `live` extra contains `openai` and `openai-agents`. The `dev` extra contains `httpx`, `pytest`, `pytest-asyncio`, and `ruff`. `uv.lock` pins the resolved versions used by the course.

- [ ] **Step 5: Implement both live adapter gates**

`OpenAIResponsesGateway.from_environment()` must raise a clear configuration error unless all three values exist:

```text
AGENT_COURSE_LIVE_TESTS=1
OPENAI_API_KEY must be non-empty
OPENAI_MODEL must be non-empty
```

It must use native Responses structured outputs where a structured result is requested.

`OpenAIAgentsRunner.from_environment()` uses the same gate and provides the SDK-managed path used by Chapter 6. Default tests assert that both live adapters refuse to initialize when the gate is absent; they do not call the network.

- [ ] **Step 6: Create and lock the environment**

Install `uv` in a project-local or user-local tool location if absent, then run:

```bash
uv sync --extra dev --extra live
uv run pytest tests/test_fake_model.py -q
```

Expected: pass without a live API call.

- [ ] **Step 7: Commit**

```bash
git add reference-implementation
git commit -m "feat: add deterministic course model gateway"
```

---

### Task 9: Implement Secure Tools And A Bounded Agent Runner

**Files:**
- Create: `reference-implementation/src/agent_course/tools/base.py`
- Create: `reference-implementation/src/agent_course/tools/__init__.py`
- Create: `reference-implementation/src/agent_course/tools/orders.py`
- Create: `reference-implementation/src/agent_course/tools/registry.py`
- Create: `reference-implementation/src/agent_course/agents/guardrails.py`
- Create: `reference-implementation/src/agent_course/agents/runner.py`
- Create: `reference-implementation/src/agent_course/agents/sessions.py`
- Create: `reference-implementation/src/agent_course/observability/__init__.py`
- Create: `reference-implementation/src/agent_course/observability/traces.py`
- Create: `reference-implementation/tests/test_tools.py`
- Create: `reference-implementation/tests/test_agent_runner.py`

**Interfaces:**
- Consumes: `ModelGateway`, `RunContext`, and `RunLimits` from Task 8.
- Produces:
  - `ToolRegistry.execute(name: str, arguments: dict, context: RunContext) -> ToolResult`
  - `BoundedAgentRunner.run(question: str, context: RunContext, limits: RunLimits) -> AgentResult`
  - `InMemorySessionStore.append(session_id: str, messages: list[Message]) -> None`
  - `Guardrail.check_input(question: str, context: RunContext) -> GuardrailDecision`
  - `InMemoryTraceSink` with redacted events.

- [ ] **Step 1: Write authorization and identity tests**

```python
@pytest.mark.asyncio
async def test_model_cannot_override_tenant(order_tool, context) -> None:
    result = await order_tool.execute(
        {"order_id": "O1001", "tenant_id": "attacker"},
        context=context,
    )
    assert result.code == "INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_missing_permission_is_blocked(order_tool, context_without_permissions) -> None:
    result = await order_tool.execute(
        {"order_id": "O1001"},
        context=context_without_permissions,
    )
    assert result.code == "PERMISSION_DENIED"
```

- [ ] **Step 2: Write bounded-run tests**

Test correct tool use, repeated-call stop, max-turn stop, timeout, structured permission failure, blocked high-risk input, session continuation, and redacted trace arguments.

- [ ] **Step 3: Implement tools and runner**

The registry rejects unknown fields before calling a handler. The runner applies input guardrails, loads and appends session messages, records each model step and tool result, increments budgets, and returns a typed stop reason. It never retries permission, policy, or validation failures.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_tools.py tests/test_agent_runner.py -q
```

Expected: all tests pass with Fake Model.

- [ ] **Step 5: Commit**

```bash
git add reference-implementation/src/agent_course/tools reference-implementation/src/agent_course/agents reference-implementation/src/agent_course/observability reference-implementation/tests
git commit -m "feat: add secure tools and bounded agent runner"
```

---

### Task 10: Implement Offline RAG, Durable Workflow, Evals, API, And MCP

**Files:**
- Create: `reference-implementation/src/agent_course/rag/models.py`
- Create: `reference-implementation/src/agent_course/rag/__init__.py`
- Create: `reference-implementation/src/agent_course/rag/retriever.py`
- Create: `reference-implementation/src/agent_course/workflows/__init__.py`
- Create: `reference-implementation/src/agent_course/workflows/research.py`
- Create: `reference-implementation/src/agent_course/evals/__init__.py`
- Create: `reference-implementation/src/agent_course/evals/runner.py`
- Create: `reference-implementation/src/agent_course/application.py`
- Create: `reference-implementation/src/agent_course/api/__init__.py`
- Create: `reference-implementation/src/agent_course/api/app.py`
- Create: `reference-implementation/src/agent_course/mcp/__init__.py`
- Create: `reference-implementation/src/agent_course/mcp/server.py`
- Create: `reference-implementation/src/agent_course/mcp/client.py`
- Create: `reference-implementation/tests/test_rag.py`
- Create: `reference-implementation/tests/test_workflow.py`
- Create: `reference-implementation/tests/test_evals.py`
- Create: `reference-implementation/tests/test_api.py`
- Create: `reference-implementation/tests/test_mcp.py`
- Create: `reference-implementation/sample-data/hr-policy.md`
- Create: `reference-implementation/compose.yaml`

**Interfaces:**
- Consumes: core, tools, runner, and trace interfaces from Tasks 8-9.
- Produces:
  - `InMemoryRetriever.search(query: str, context: RunContext, top_k: int) -> list[RetrievalHit]`
  - `ResearchWorkflow.start(topic: str, context: RunContext) -> WorkflowRun`
  - `ResearchWorkflow.approve(run_id: str, decision: ApprovalDecision, context: RunContext) -> WorkflowRun`
  - `ResearchWorkflow.resume(run_id: str, context: RunContext) -> WorkflowRun`
  - `evaluate_cases(cases: list[EvalCase], app: CourseApplication) -> EvalReport`
  - `CourseApplication(agent_runner: BoundedAgentRunner, retriever: InMemoryRetriever, workflow: ResearchWorkflow)`
  - FastAPI endpoints `/health`, `/v1/agent/runs`, `/v1/agent/runs/{run_id}`, and `/v1/agent/runs/{run_id}/events`.
  - runnable MCP server and client commands.

- [ ] **Step 1: Write offline RAG tests**

Cover retrieval hit, real citation quote, tenant isolation, inaccessible document exclusion, and correct refusal.

- [ ] **Step 2: Write Workflow tests**

Cover versioned state, waiting for approval, mismatched approval payload hash, resume, duplicate idempotency key, timeout, and cancellation.

- [ ] **Step 3: Write eval tests**

Cover task success, tool selection, argument accuracy, blocked unauthorized action, turn count, and deterministic report serialization.

- [ ] **Step 4: Write API and MCP smoke tests**

API tests use FastAPI `TestClient` and Fake Model. MCP tests start a stdio subprocess, list tools, call `query_order_status`, and assert the structured result. They must not require live credentials.

- [ ] **Step 5: Implement the minimum passing behavior**

Offline retrieval uses normalized token overlap so results remain deterministic and dependency-light. `compose.yaml` provides PostgreSQL/pgvector only as an optional extension and is not started by default tests.

- [ ] **Step 6: Run the entire reference suite**

```bash
uv run pytest -q -m "not live"
```

Expected: pass without network access or credentials.

- [ ] **Step 7: Commit**

```bash
git add reference-implementation
git commit -m "feat: complete offline agent course reference app"
```

---

### Task 11: Add Dual-Track Teaching, Labs, Rubrics, And Datasets

**Files:**
- Create: `teaching/12-week-syllabus.md`
- Create: `teaching/16-20-week-self-study.md`
- Create: `teaching/instructor-guide.md`
- Create: `teaching/assessment-rubrics.md`
- Create: `teaching/answer-key.md`
- Create: `labs/README.md`
- Create: `labs/chapter-02/README.md`
- Create: `labs/chapter-05/README.md`
- Create: `labs/chapter-06/README.md`
- Create: `labs/chapter-07/README.md`
- Create: `labs/chapter-08/README.md`
- Create: `labs/chapter-09/README.md`
- Create: `labs/chapter-10/README.md`
- Create: `evals/agent-cases.jsonl`
- Create: `evals/rag-cases.jsonl`
- Create: `evals/security-cases.jsonl`

**Interfaces:**
- Consumes: commands and behavior from the completed reference implementation.
- Produces: one teachable 12-week route, one self-study route, lab instructions, answer explanations, rubrics, and machine-readable baseline cases.

- [ ] **Step 1: Write both schedules against the shared course map**

The 12-week route must finish Know-Engine Core and mark Chapters 11, 12, and 15 as enrichment. The self-study route must provide weekly checkpoints and recovery weeks without changing acceptance criteria.

- [ ] **Step 2: Write the instructor guide**

For every week include:

- preparation;
- 15-minute concept opener;
- live demonstration command;
- learner lab block;
- expected failure injection;
- discussion question;
- exit ticket;
- homework and grading reference.

- [ ] **Step 3: Write lab instructions**

Every lab must contain exact commands, expected output shape, one intentional failure, debugging steps, default offline verification, optional live extension, and submission evidence.

- [ ] **Step 4: Write rubrics and answer key**

Rubrics score correctness, security boundary, evaluation evidence, observability, failure handling, code quality, and explanation. The answer key explains reasoning and common wrong approaches rather than only presenting final output.

- [ ] **Step 5: Add at least ten cases per JSONL dataset**

Agent cases cover direct response, correct tool, missing argument, multi-intent, stop budget, and unauthorized request. RAG cases cover answerable, unanswerable, synonyms, citations, and tenant isolation. Security cases cover direct injection, indirect document injection, tool-output injection, exfiltration, privilege escalation, and denial-of-wallet loops.

- [ ] **Step 6: Validate data and links**

```bash
python scripts/validate_course.py
```

Expected: all JSONL lines parse and every lab/reference link exists.

- [ ] **Step 7: Commit**

```bash
git add teaching labs evals
git commit -m "docs: add dual-track teaching labs and assessments"
```

---

### Task 12: Final Logic, Currency, Security, And Reproducibility Audit

**Files:**
- Audit and modify only when a listed check fails: `README.md`, `chapters/*.md`, `docs/*.md`, `teaching/*.md`, `labs/**/*.md`, `reference-implementation/**`, `scripts/validate_course.py`

**Interfaces:**
- Consumes: all previous deliverables.
- Produces: a clean, coherent, testable repository ready for user review.

- [ ] **Step 1: Run deterministic repository validation**

```bash
python scripts/validate_course.py
git diff --check
```

Expected: both pass.

- [ ] **Step 2: Run reference implementation quality checks**

```bash
cd reference-implementation
uv sync --frozen --extra dev --extra live
uv run ruff check .
uv run pytest -q -m "not live"
```

Expected: all pass without credentials or network calls during tests.

- [ ] **Step 3: Verify live-test isolation**

```bash
env -u OPENAI_API_KEY -u OPENAI_MODEL AGENT_COURSE_LIVE_TESTS=0 uv run pytest -q
```

Expected: live tests are skipped and core tests pass.

- [ ] **Step 4: Audit logic and stale concepts**

Search for:

```bash
rg -n 'gpt-4\.1-mini|第 8 章.*Agent|第 6 章.*RAG|先让模型输出 JSON|confidence.*权限|Go 实现至少一个' README.md chapters docs teaching labs
```

Expected: no stale mainline guidance remains. Any compatibility or historical mention must be explicitly labeled.

- [ ] **Step 5: Audit security boundaries**

Confirm tests exist for trusted identity, tenant isolation, permission denial, indirect injection, tool poisoning, approval hash mismatch, idempotency, budget stop, trace redaction, and live-mode gating.

- [ ] **Step 6: Re-read the full course as two learner journeys**

Walk the README links in instructor order and self-study order. Check that every prerequisite appears before use, every promised output has a lab, every lab has a verification command, and optional technologies never become accidental requirements.

- [ ] **Step 7: Run final Git checks**

```bash
git status -sb
git diff --stat HEAD~1
git log --oneline --decorate -12
```

Expected: only intentional course redesign changes are present, with no secret files or generated environment directories.

- [ ] **Step 8: Commit final audit fixes**

```bash
git add README.md chapters docs teaching labs evals reference-implementation scripts tests .github
git commit -m "docs: finalize executable agent teaching course"
```

Do not push until the user explicitly requests a GitHub push.
