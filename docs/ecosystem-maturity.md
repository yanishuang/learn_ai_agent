# AI Agent Ecosystem Maturity Matrix

Verified: 2026-07-11

This is a dated course-maintenance record, not a ranking or a compatibility guarantee.
`Stable` means the cited primary source describes the **named artifact or path** as
released or production-ready. `Preview` covers an explicit upstream preview or Beta
package line; `Experimental` and `RC` preserve those upstream designations (or, for
the Claude Agent SDK row, a pre-1.0 release line with no upstream GA declaration as of
this verification date). A row never grants one umbrella status to every package,
language implementation, or integration in a product family. Recheck the source before
upgrading, especially where stable and prerelease artifacts coexist.

| Technology | Role | Maturity | Course status | Verified | Primary source |
| --- | --- | --- | --- | --- | --- |
| OpenAI Responses API | Low-level model, tool, and structured-output API | Stable | Core: use behind `ModelGateway`; the course owns tool dispatch and state. | 2026-07-10 | [OpenAI recommends Responses for new projects](https://help.openai.com/en/articles/8550641-assistants-api-v2-faq) |
| OpenAI Agents SDK | Python agent runtime for managed turns, tools, handoffs, and tracing | Stable | Optional Live comparison in Chapter 4; exclude beta feature areas from course contracts. | 2026-07-10 | [SDK overview calls the core runtime production-ready](https://openai.github.io/openai-agents-python/) and [its release policy documents the evolving `0.Y.Z` line](https://openai.github.io/openai-agents-python/release/) |
| Pydantic AI 1.x | Typed Python agent framework | Stable | Optional: evaluate only after the course `ModelGateway` and `RunContext` boundaries are in place. | 2026-07-10 | [v1.104.0 is the latest non-prerelease release](https://github.com/pydantic/pydantic-ai/releases); [v2.0.0b4 is explicitly a prerelease](https://github.com/pydantic/pydantic-ai/releases) |
| LangGraph 1.x | Stateful graph/workflow runtime | Stable | Advanced workflow option after durable state, recovery, and approval requirements are clear. | 2026-07-10 | [LangGraph 1.0 LTS policy](https://docs.langchain.com/oss/python/release-policy) |
| MCP specification `2025-11-25` | Stable model-to-tool/context protocol baseline | Stable | Core interoperability baseline for Chapters 10-13; pin implementation behavior to the released specification. | 2026-07-10 | [November 2025 specification release](https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/) |
| MCP specification `2026-07-28` | Next stateless protocol revision | RC | Do not make it a course contract before final publication; validate migrations separately because the RC has breaking changes. | 2026-07-10 | [MCP release-candidate announcement](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) |
| MCP Apps (SEP-1865 in the `2026-07-28` revision) | Interactive server-rendered UI extension | RC | Exploration only; it is part of the cited RC and must not be presented as final behavior. | 2026-07-10 | [MCP RC announcement: Apps ships in the RC and final is scheduled for 2026-07-28](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) |
| OpenAI Apps SDK | ChatGPT-native app logic and UI SDK built on MCP | Preview | Optional product-experience extension; do not depend on directory, policy, or monetization behavior in required labs. | 2026-07-10 | [OpenAI Help: Apps SDK is available in preview](https://help.openai.com/en/articles/12515353-build-with-the-apps-sdk.iso) |
| A2A Protocol 1.0 | Agent-to-agent interoperability protocol | Stable | Optional Chapter 12 extension; use beside MCP, not as a replacement for tool/context integration. | 2026-07-10 | [A2A 1.0 announcement](https://a2a-protocol.org/latest/announcing-1.0/) and [latest released specification](https://a2a-protocol.org/dev/specification/) |
| Google ADK Python 1.0 | Google Python agent-development framework; A2A support is documented separately for Python, Go, and Java | Stable | Optional framework evaluation. A2A remains an optional course extension; current docs provide exposing/consuming quickstarts, but this record does not assign the ADK A2A integration a separate upstream maturity designation. | 2026-07-11 | [Google announcement of Python ADK v1.0.0 stable](https://developers.googleblog.com/en/agents-adk-agent-engine-a2a-enhancements-google-io/) and [ADK A2A support and language quickstarts](https://adk.dev/a2a/) |
| Microsoft Agent Framework Python 1.0 released packages: `agent-framework`, `agent-framework-core`, `agent-framework-openai`, `agent-framework-foundry` | Python meta/core packages plus OpenAI and Foundry providers | Stable | Optional package-level evaluation; preserve course contracts and do not infer this status for other integrations or languages. | 2026-07-11 | [Microsoft's Python guide distinguishes released packages from preview connectors](https://github.com/microsoft/agent-framework/blob/main/python/README.md); PyPI 1.0 metadata marks [meta](https://pypi.org/project/agent-framework/1.0.0/), [core](https://pypi.org/project/agent-framework-core/1.0.0/), [OpenAI](https://pypi.org/project/agent-framework-openai/1.0.0/), and [Foundry](https://pypi.org/project/agent-framework-foundry/1.0.0/) as Production/Stable. |
| Microsoft Agent Framework Python beta integrations, including `agent-framework-a2a`, `agent-framework-mem0`, `agent-framework-copilotstudio` `1.0.0b*` | Optional A2A, memory, and Copilot Studio connectors | Preview | Optional isolated evaluation only; pin the named beta package and verify its classifier before adoption. | 2026-07-11 | Microsoft package metadata labels [A2A](https://github.com/microsoft/agent-framework/blob/main/python/packages/a2a/pyproject.toml), [Mem0](https://github.com/microsoft/agent-framework/blob/main/python/packages/mem0/pyproject.toml), and [Copilot Studio](https://github.com/microsoft/agent-framework/blob/main/python/packages/copilotstudio/pyproject.toml) `Development Status :: 4 - Beta`. |
| Microsoft Agent Framework for Go | Go agent implementation with a smaller current feature surface | Preview | Optional comparison only; do not require it for labs or assume parity with Python packages. | 2026-07-11 | [Microsoft Learn explicitly labels the Go implementation public preview and lists unavailable capabilities](https://learn.microsoft.com/en-us/agent-framework/overview/). |
| Claude Agent SDK 0.2.x | In-process Python/TypeScript agent loop with Claude Code tools | Preview | Optional sandboxed experiment; do not add it to the default reference implementation or use it without isolation and approval controls. | 2026-07-10 | [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview), [0.2.x Python releases](https://github.com/anthropics/claude-agent-sdk-python), and [production hosting guidance](https://code.claude.com/docs/en/agent-sdk/hosting) |

## Review Procedure

For a framework-selection exercise, cite the exact matrix row and its primary source in
the decision record. Re-verify a row when its source changes status, a major version is
released, or a proposed feature becomes required by a lab. A maturity label does not
replace architecture review: keep identity in `RunContext`, preserve provider-neutral
contracts, and use the deterministic Fake path for default regression tests.
