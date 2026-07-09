# 第 11 章：Agent 互操作与多 Agent 架构设计

更新时间：2026-07-09
建议学习时间：5-7 天
适合阶段：已经完成单 Agent、Workflow、MCP，准备设计平台化 Agent 系统
本章产出：一个 BaseAgent 抽象、一个 Agent Registry、一个任务路由器、一份 Agent 框架与协议选型说明

![Agent 互操作生态](../assets/agent-ecosystem-illustrations/03-agent-interop.png)

## 11.1 本章学习目标

学完本章后，你应该能做到：

1. 区分单 Agent、Workflow、多 Agent、Agent 平台。
2. 设计 BaseAgent、Agent Registry、Task Router 和 Agent Run 记录。
3. 说明 MCP、A2A、Apps SDK / MCP Apps 分别解决哪一层问题。
4. 比较 OpenAI Agents SDK、Pydantic AI、LangGraph、Google ADK、Microsoft Agent Framework、Claude Agent SDK 的适用边界。
5. 知道什么时候应该拆成多个 Agent，什么时候不应该。
6. 为 Dodo-Agent 设计一个可落地的多 Agent MVP。

本章重点不是“让很多 Agent 聊天”，而是设计一个可控、可观测、可扩展的 Agent 平台。

## 11.2 不要过早多 Agent

多 Agent 不是 Agent 能力的起点，而是平台化后的结果。

不建议拆多 Agent 的情况：

- 任务仍然可以由一个 Agent + 几个工具完成。
- 工具边界还没稳定。
- 没有 trace、评估、权限和失败恢复。
- 每个 Agent 只是换了一段 prompt，没有独立职责。

适合拆多 Agent 的情况：

- 不同 Agent 有明显不同的工具集和权限。
- 不同 Agent 需要不同评估集。
- 任务天然分工，例如研究、检索、分析、报告、文件处理。
- 平台需要按团队、场景、版本注册和治理 Agent。

判断原则：**拆 Agent 是为了降低复杂度，不是为了显得智能。**

## 11.3 最小多 Agent 架构

```text
用户任务
  -> Task Router
  -> Agent Registry
  -> 选择一个或多个 Agent
  -> Agent 调用工具 / RAG / MCP
  -> 汇总结构化结果
  -> 返回最终答案或进入 Workflow
```

推荐先实现 3 个 Agent：

| Agent | 职责 | 工具 |
| --- | --- | --- |
| KnowledgeAgent | 企业知识库问答 | RAG 检索、引用生成 |
| ResearchAgent | 外部资料研究 | Web search、资料摘要、来源检查 |
| ReportAgent | 报告生成 | 大纲生成、章节写作、引用检查 |

每个 Agent 都应该有：

- 名称和版本。
- instructions。
- 输入输出 schema。
- 可用工具列表。
- 风险等级。
- 评估集。
- trace 和运行日志。

## 11.4 BaseAgent 抽象

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field


class AgentInput(BaseModel):
    user_id: str
    tenant_id: str
    task: str
    context: dict = Field(default_factory=dict)


class AgentOutput(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    next_actions: list[str] = Field(default_factory=list)


class BaseAgent(ABC):
    name: str
    version: str

    @abstractmethod
    async def run(self, payload: AgentInput) -> AgentOutput:
        raise NotImplementedError
```

这个抽象不要设计得太早、太大。先让 2-3 个 Agent 真实跑起来，再提炼公共接口。

## 11.5 Agent Registry

Agent Registry 用来管理 Agent 元数据：

```sql
create table agents (
  id text primary key,
  name text not null,
  version text not null,
  description text not null,
  risk_level text not null,
  enabled boolean not null default true,
  config_json jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

工具绑定：

```sql
create table agent_tools (
  agent_id text not null references agents(id),
  tool_name text not null,
  risk_level text not null,
  enabled boolean not null default true,
  primary key (agent_id, tool_name)
);
```

生产系统里，不建议让 Agent 动态获得所有工具。Agent 能用哪些工具，应该由 Registry、权限和风险等级共同控制。

## 11.6 Task Router

路由器负责决定任务交给谁。

先用规则：

| 规则 | 路由 |
| --- | --- |
| 用户问公司制度、项目文档 | KnowledgeAgent |
| 用户要求调研行业、竞品、资料 | ResearchAgent |
| 用户要求生成报告、周报、总结 | ReportAgent |
| 用户要求执行高风险动作 | Workflow + 人工确认 |

再用模型做辅助分类：

```python
from typing import Literal
from pydantic import BaseModel


class RouteDecision(BaseModel):
    route: Literal["knowledge", "research", "report", "workflow", "clarify"]
    reason: str
    confidence: Literal["high", "medium", "low"]
```

低置信度时不要乱路由，应该追问用户。

## 11.7 MCP、A2A、Apps 的边界

| 协议 / SDK | 解决什么 | 不解决什么 |
| --- | --- | --- |
| MCP | Agent / Host 如何标准化接入工具、资源、提示词 | 不决定 Agent 如何规划，也不替代业务权限 |
| A2A | 不同 Agent 如何跨系统发现、通信、协作 | 不替代工具协议，也不保证任务质量 |
| Apps SDK / MCP Apps | 工具结果如何渲染成交互式 UI | 不替代工具 schema、权限、审计 |

推荐理解：

```text
Agent runtime 决定怎么思考和行动
MCP 决定怎么接工具和上下文
A2A 决定怎么和其他 Agent 协作
Apps 决定怎么把结果展示给用户操作
```

这些能力可以组合，但不要混为一谈。

## 11.8 框架选型表

| 框架 | 强项 | 适合主线吗 |
| --- | --- | --- |
| OpenAI Agents SDK | Agent、tools、handoff、trace、guardrails | 是，本课程 Agent 主线 |
| Pydantic AI | 类型安全、结构化输出、evals、Logfire、durable execution | 是，作为 Python 工程补强 |
| LangGraph | 状态图、human-in-the-loop、可恢复 workflow | 是，第 9 章重点 |
| Google ADK | 多语言 Agent、A2A、Google 生态集成 | 进阶比较 |
| Microsoft Agent Framework | .NET / Python、多 Agent workflow、MCP/A2A 互操作 | 进阶比较 |
| Claude Agent SDK | Claude Code 式 agent loop、编码代理能力 | 进阶参考 |

课程建议：前 10 周不要同时深入所有框架。主线保持 OpenAI SDK / Agents SDK + Pydantic + LangGraph + MCP，其他框架用于做选型报告。

## 11.9 Dodo-Agent MVP

MVP 功能：

1. 用户提交任务。
2. Task Router 选择 Agent。
3. Agent 调用工具、RAG 或 MCP。
4. 系统记录 run、step、tool_call。
5. 前端展示最终答案、引用、工具轨迹和失败原因。

暂不做：

- 完整 A2A 协议实现。
- 所有框架统一 runtime。
- 自动生成和上线新 Agent。
- 高风险工具自动执行。
- 复杂企业 IM 全量集成。

MVP 验收：

| 能力 | 验收 |
| --- | --- |
| 路由 | 10 个测试问题中至少 8 个路由正确 |
| 工具 | 每个 Agent 只能调用授权工具 |
| Trace | 能看到 Agent run、step、tool_call |
| 失败处理 | 工具失败有结构化错误 |
| 评估 | 每个 Agent 至少 10 条基础评估用例 |

## 11.10 常见误区

- 多 Agent 只是多个 prompt 名字。
- Agent 之间传递整段自由文本，导致不可控。
- 没有 Registry，工具权限散落在代码里。
- 为了追新协议而忽略 RAG、工具、Workflow 基础。
- 把 A2A 当成 MCP 的替代品。
- 把交互式 UI 当成 Agent 智能本身。

## 11.11 本章学习资料

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK - Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/getting-started/intro)
- [MCP Apps](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)
- [OpenAI Apps SDK](https://developers.openai.com/apps-sdk)
- [Google Agent Development Kit](https://adk.dev/)
- [Google A2A Protocol](https://adk.dev/a2a/)
- [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)
- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

## 11.12 本章复盘模板

```markdown
# 第 11 章复盘

## 我设计了哪些 Agent

## 每个 Agent 的职责和工具是什么

## Task Router 如何做决策

## 哪些任务必须进入 Workflow

## MCP、A2A、Apps SDK 在我的系统里分别负责什么

## 我为什么没有过早引入某些框架

## 我的 Agent Registry 记录哪些字段

## 我如何评估每个 Agent 的效果
```
