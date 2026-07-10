# AI Agent Course Redesign Design

Date: 2026-07-10
Status: Approved for implementation

## 1. Objective

Transform the repository from a detailed curriculum outline into a teaching-ready and self-study-ready AI Agent course that is:

- executable without an API key for core exercises;
- capable of switching to real OpenAI APIs for live experiments;
- current with the 2026 Agent ecosystem without turning into a framework catalog;
- organized around observable engineering capabilities rather than product names;
- usable as a 12-week instructor-led course and a 16-20 week self-study course;
- explicit about security, evaluation, failure recovery, protocol maturity, and production boundaries;
- Python-first, with Go limited to optional stable tool and MCP service extensions.

## 2. Audience And Teaching Modes

### 2.1 Shared audience baseline

The learner is expected to:

- read and write basic Python;
- understand HTTP APIs, JSON, databases, and backend service structure;
- use Git and a terminal;
- have no prior Agent framework experience.

Go is not a prerequisite.

### 2.2 Instructor-led mode

- Duration: 12 weeks.
- Target effort: one guided lesson and one lab block per week, plus homework.
- Required outcome: one complete Know-Engine project with a bounded single Agent, RAG, Workflow, MCP, evaluation, and production checklist.
- Advanced RAG, A2A, full multi-Agent collaboration, and the Dodo-Agent project are optional enrichment.

### 2.3 Self-study mode

- Duration: 16-20 weeks.
- Includes prerequisites, expected outputs, troubleshooting, hints, answer explanations, and recovery checkpoints.
- Uses the same core assignments and acceptance criteria as the instructor-led mode.
- Adds time for repeated experiments, live-model comparisons, and optional Go work.

Both modes share one source of truth. Teaching notes extend the chapters rather than duplicating them.

## 3. Technology Positioning

### 3.1 Required mainline

- Python 3.12 or newer.
- `uv` for the reference implementation environment and dependency locking.
- FastAPI and Pydantic for HTTP and data boundaries.
- OpenAI Responses API for model I/O, native structured outputs, and the explicit tool loop.
- OpenAI Agents SDK for managed Agent runs, sessions, guardrails, tracing, approvals, and handoffs.
- pytest for deterministic tests.
- OpenTelemetry-compatible tracing concepts.
- MCP Python SDK for the required MCP lab.

### 3.2 Architectural portability

Application code depends on a small model gateway interface rather than importing a provider client throughout the codebase. Two adapters are required:

1. A deterministic Fake Model used by default.
2. An OpenAI adapter enabled only when credentials and an explicit live-test flag are present.

The course teaches the conceptual boundary between the Responses API, where the application owns the loop, and the Agents SDK, where the SDK owns the run lifecycle.

### 3.3 Optional comparisons

Pydantic AI, LangGraph, Google ADK, Microsoft Agent Framework, Claude Agent SDK, A2A, MCP Apps, Apps SDK, and Go SDKs are comparison or extension topics. Every ecosystem item must include:

- purpose;
- course role;
- maturity label: Stable, Preview, Experimental, or RC;
- verification date;
- reason it is or is not in the mainline.

No optional framework is required to complete the core course.

## 4. Curriculum Architecture

The course contains one unnumbered prerequisite unit and fifteen numbered chapters.

### Prerequisite unit: Course setup

- Repository navigation and learning modes.
- Python and `uv` setup.
- Fake Model versus live mode.
- API key and cost safety.
- Running tests and interpreting failures.
- The teaching project and sample data.

### Chapter 1: Agent overview and solution boundaries

- Chat, structured generation, RAG, tools, Workflow, Agent, and multi-Agent as composable dimensions.
- A decision framework based on knowledge, actions, autonomy, state, and risk.
- Know-Engine and Dodo-Agent scope.

### Chapter 2: Model application foundations

- Responses API and message roles.
- Model selection as a configurable capability and cost decision.
- Native Pydantic structured outputs.
- Streaming, conversation state, usage, error handling, and request logging.

### Chapter 3: Prompt and context engineering

- Instruction design and context assembly.
- Prompt versioning and executable tests.
- Context compaction and caching.
- Direct and indirect prompt injection.
- Treating user, retrieved, web, and tool content as untrusted data.

### Chapter 4: Python AI application architecture

- Provider boundary, settings, domain schemas, API layer, tools, runs, and observability.
- Framework selection as a short decision guide.
- Pydantic versus Pydantic AI distinction.
- Testing and dependency direction.

### Chapter 5: Tool calling and trusted execution context

- Low-level Responses function-calling loop.
- Typed schemas and structured tool results.
- User and tenant identity injected through trusted run context, never model arguments.
- Read/write effect classification, idempotency, retries, approvals, audit, and tool-selection evaluation.
- Built-in tools, remote MCP, tool search, and programmatic tool calling as advanced entries.

### Chapter 6: Single Agent runtime

- Bounded loop, stop reasons, time, turn, tool, and token budgets.
- Agents SDK run lifecycle, sessions, results, guardrails, tracing, and resumable approval.
- Memory taxonomy, retention, privacy, and compaction.
- Task success and trajectory evaluation.

### Chapter 7: RAG core

- Ingestion, parsing, chunking, embedding, indexing, retrieval, context assembly, answers, and citations.
- Document and index versioning, source locations, access control, and retrieval logging.
- Deterministic offline retrieval for the default lab and pgvector as the production extension.
- Minimal retrieval and answer evaluation.

### Chapter 8: Workflow and durable execution

- Workflow versus Agent.
- State models, versioning, checkpoints, retries, cancellation, and recovery.
- Human-in-the-loop with payload hashes and authoritative server-side approval checks.
- Database state machine first; LangGraph, Temporal, and Pydantic AI durable execution as comparisons.
- Background API execution is not presented as a substitute for durable application state.

### Chapter 9: Agent evaluation, observability, and security

- Datasets, cases, deterministic assertions, model graders, and human calibration.
- Task success, tool selection, argument accuracy, trajectory efficiency, policy compliance, latency, and cost.
- Trace-based debugging and grading.
- Red-team cases for prompt injection, indirect injection, data exfiltration, privilege escalation, tool poisoning, runaway loops, and denial of wallet.
- Online failure feedback into offline regression suites.

### Chapter 10: MCP integration and trust governance

- Host, client, server, tools, resources, and prompts.
- Runnable stdio server, Inspector workflow, and runnable client integration.
- Streamable HTTP, remote MCP, authorization, business permissions, consent, and trusted server policy.
- Registry metadata, protocol and schema versions, ownership, risk, and audit.
- Stable specification baseline and clearly separated RC observation notes.

### Chapter 11: Advanced RAG and governed data routing

- Query rewriting with original-query fallback.
- Hybrid retrieval using RRF by default; weighted scores require normalization.
- Reranking, tables, and structured data routing.
- Text2SQL and graph querying through templates, parsers, read-only roles, limits, and audit.
- Optional modern retrieval techniques, selected by measured need rather than novelty.

### Chapter 12: Multi-Agent design and interoperability

- Agents-as-tools, handoffs, ownership, routing, and structured contracts.
- Evaluation by specialist and end-to-end workflow.
- MCP versus A2A versus interactive app surfaces.
- A2A remains optional while pre-1.0.
- Framework maturity and ecosystem comparison.

### Chapter 13: Product experience, enterprise integration, and production governance

- Task creation plus SSE/WebSocket progress streams.
- Citation, tool activity, approval, retry, cancellation, and failure user experience.
- Enterprise IM boundaries.
- Deployment, secrets, tenant isolation, rate limits, quotas, cost budgets, data retention, incident response, and CI gates.
- Apps SDK and MCP Apps as optional interactive result surfaces.

### Chapter 14: Know-Engine capstone

- Required graduation project.
- Delivered through milestones that reuse chapter labs.
- Includes document ingestion, retrieval, citations, permissions, a bounded Agent, Workflow, MCP, evals, observability, and a production-readiness report.
- Has Core, Advanced, and Production acceptance levels.

### Chapter 15: Dodo-Agent capstone

- Optional advanced project.
- Begins with one router and two specialists, not a general-purpose platform.
- Adds structured contracts, handoff or agents-as-tools, a registry, trace evaluation, and optional A2A research.
- Does not require automatic Agent generation, arbitrary code execution, or a universal framework abstraction.

## 5. Reference Implementation

The repository gains one evolving application under `reference-implementation/`.

```text
reference-implementation/
  pyproject.toml
  uv.lock
  .env.example
  README.md
  src/agent_course/
    api/
    models/
    tools/
    agents/
    rag/
    workflows/
    evals/
    observability/
  tests/
  sample-data/
  compose.yaml
```

### 5.1 Required execution modes

Fake mode is the default and must:

- require no network and no API key;
- return deterministic structured outputs;
- emit deterministic tool calls for course fixtures;
- support failure injection for timeout, invalid output, permission denial, and repeated calls;
- run all core tests.

Live mode must:

- require an explicit environment switch;
- load the API key only from the environment;
- require an explicit model value rather than a stale hardcoded default;
- keep live tests excluded from the default test command;
- record usage and latency without recording secrets or raw sensitive data.

### 5.2 Core application flow

```text
HTTP request
  -> validated request and trusted RunContext
  -> model gateway or Agent runtime
  -> tool / RAG / Workflow boundary
  -> structured result
  -> redacted trace and metrics
  -> response or durable run status
  -> offline evaluation dataset
```

### 5.3 Error model

Errors are classified as validation, permission, policy, transient dependency, budget, model output, not found, conflict, cancellation, and internal errors.

- Only transient dependency errors are automatically retried.
- Retries have limits and backoff.
- Permission and policy failures are never retried by the model.
- Tool exceptions are converted to structured results before entering model context.
- Sensitive values are redacted before logs or traces.
- Side effects require idempotency and, when risky, an authoritative approval record.

## 6. Teaching Artifacts

The repository adds:

```text
teaching/
  12-week-syllabus.md
  instructor-guide.md
  assessment-rubrics.md
  answer-key.md
labs/
  README.md
  chapter-02/
  chapter-05/
  chapter-06/
  chapter-07/
  chapter-08/
  chapter-09/
  chapter-10/
evals/
  agent-cases.jsonl
  rag-cases.jsonl
  security-cases.jsonl
```

Every chapter follows this teaching structure:

1. Prerequisites.
2. Measurable learning outcomes.
3. Core concepts and engineering boundaries.
4. Instructor demonstration.
5. Learner lab.
6. Failure injection and debugging.
7. Automated verification.
8. Assignment and rubric.
9. Core, Advanced, and Production completion levels.
10. Recap and current primary sources.

## 7. Assessment Model

### 7.1 Chapter checks

- deterministic unit tests;
- scenario classification;
- trace inspection;
- short written engineering decisions;
- one failure analysis per major lab.

### 7.2 Agent metrics

- end-to-end task success;
- tool selection accuracy;
- tool argument accuracy;
- unauthorized action block rate;
- average and maximum turns;
- unnecessary tool-call rate;
- latency and token/cost budget compliance;
- final-output schema validity.

Model-reported confidence is never used as a security or authorization control. Any confidence field is treated as explanatory metadata unless calibrated against an evaluation dataset.

### 7.3 RAG metrics

- hit@k;
- context precision and recall where ground truth exists;
- citation support;
- answer faithfulness and correctness;
- correct refusal;
- permission isolation;
- latency and cost.

### 7.4 Graduation

Know-Engine is the required capstone. Passing requires:

- all Core acceptance checks;
- a reproducible setup;
- passing offline tests;
- a documented live evaluation when credentials are available;
- a threat model and production-readiness report;
- an architecture explanation and failure postmortem.

Dodo-Agent is optional and graded separately.

## 8. Migration From Existing Material

- Keep valid explanations, exercises, diagrams, and references.
- Move the existing Agent basics chapter from 8 to 6.
- Move existing RAG basics from 6 to 7.
- Move existing Workflow from 9 to 8.
- Add the new evaluation, observability, and security chapter at 9.
- Keep MCP at 10.
- Move advanced RAG from 7 to 11.
- Move interoperability and multi-Agent from 11 to 12.
- Write complete chapters 13, 14, and 15.
- Shorten the README into a navigable course portal.
- Update every chapter number, local link, recap template, and cross-reference.
- Preserve existing illustration assets where they clarify the new structure.

## 9. Verification And Completion Criteria

The redesign is complete only when:

1. All prerequisite and chapter files exist and are linked from the README.
2. No stale chapter numbers or broken local links remain.
3. The reference implementation installs from a clean environment.
4. The default test command passes without network access or credentials.
5. Live tests are explicitly opt-in.
6. At least one end-to-end Fake Model scenario covers model output, tool use, RAG, Workflow state, trace, and evaluation.
7. MCP server and client examples are runnable.
8. Each chapter contains a lab, verification command, assignment, and completion rubric.
9. The 12-week and 16-20 week paths map to the same chapter outcomes.
10. Framework and protocol maturity labels are dated and supported by primary documentation.
11. Markdown structure, code blocks, local links, and JSONL datasets pass automated validation.
12. The repository contains no API keys, secrets, or live-test defaults that can incur accidental cost.

## 10. Explicit Non-Goals

- Supporting Java as a course implementation language.
- Requiring Go for core completion.
- Teaching every Agent framework API.
- Building a universal multi-Agent platform in the core course.
- Treating model self-reported confidence as calibrated certainty.
- Allowing arbitrary SQL, arbitrary code execution, or untrusted MCP servers in core labs.
- Claiming that background API execution alone provides durable application workflows.
- Making live paid API calls part of the default CI or test path.
