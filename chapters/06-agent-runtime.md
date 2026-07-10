# 第 6 章：单 Agent Runtime：执行循环、工具、记忆与 Trace

更新时间：2026-07-09
建议学习时间：5-7 天  
适合阶段：已经完成 Tool Calling，并能使用第 5 章的模拟知识库工具，准备让系统从“一次问答”升级为“多步任务执行”
本章产出：一个受控单 Agent，可调用天气、订单、知识库检索工具，具备停止条件、失败处理和运行轨迹记录

## 6.1 本章学习目标

学完本章后，你应该能做到：

1. 解释 Agent 与普通 Tool Calling 的区别。
2. 实现一个受控的 Agent 执行循环。
3. 为 Agent 注册只读工具和模拟知识库工具，并为第 7 章接入真实 RAG 保留边界。
4. 设置最大轮数、最大工具次数、超时、token 限制等停止条件。
5. 记录 Agent run、每轮 step、工具调用和最终状态。
6. 设计短期记忆和摘要记忆，不滥用长期记忆。
7. 用测试问题验证 Agent 是否真的基于工具结果回答。
8. 了解 Sessions、human-in-the-loop、background mode 等现代 Agent runtime 能力。

本章重点是“可控 Agent”，不是追求模型看起来多聪明。

## 6.2 Agent 适用边界

适合 Agent 的任务：

- 步骤不完全固定。
- 可能需要选择不同工具。
- 需要根据工具结果决定下一步。
- 用户目标较开放。

不适合 Agent 的任务：

- 审批、退款、转账等高风险操作。
- 步骤稳定且失败成本高的流程。
- 只需要一次检索或一次 SQL 查询的问题。
- 权限和合规边界不清的问题。

判断原则：能用普通函数和 Workflow 稳定解决的，不要强行 Agent 化。

## 6.3 基本执行循环

```text
用户目标
  -> Agent 理解任务
  -> 判断是否需要工具
  -> 生成工具调用参数
  -> 后端校验并执行工具
  -> Agent 观察工具结果
  -> 判断是否完成
  -> 未完成则继续下一轮
  -> 输出最终答案
```

受控 Agent 必须有停止条件：

| 条件 | 建议 |
| --- | --- |
| 最大轮数 | 3-5 轮起步 |
| 最大工具次数 | 3-8 次 |
| 最大运行时间 | 30-120 秒 |
| 最大 token | 按模型和成本设置 |
| 高风险工具 | 必须人工确认 |
| 连续失败 | 失败 2 次后退出或追问 |

## 6.4 推荐项目结构

```text
app/
  agents/
    schemas.py
    base.py
    course_assistant.py
    runner.py
    memory.py
    trace_repository.py
  tools/
    registry.py
    weather.py
    order.py
    knowledge.py
  rag/
    retriever.py
tests/
  agents/
    test_course_assistant.py
```

## 6.5 Agent Run 数据结构

```python
from enum import StrEnum
from pydantic import BaseModel, Field


class AgentRunStatus(StrEnum):
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class AgentRun(BaseModel):
    id: str
    user_id: str
    tenant_id: str
    input: str
    status: AgentRunStatus
    final_output: str | None = None
    error_code: str | None = None
```

Step 结构：

```python
class AgentStep(BaseModel):
    run_id: str
    step_index: int
    action_type: str
    tool_name: str | None = None
    tool_arguments: dict = Field(default_factory=dict)
    observation: str | None = None
    status: str
```

Trace 不是装饰品。没有 trace，就无法解释 Agent 为什么做出某个动作。

## 6.6 使用 OpenAI Agents SDK

下面示例展示核心思路，具体 API 以当前 SDK 文档为准。

```python
from agents import Agent, Runner, function_tool


@function_tool
async def search_course_knowledge(query: str) -> str:
    """搜索课程知识库。仅用于回答 AI Agent、RAG、MCP、Workflow 等课程问题。"""
    result = await rag_search(query=query, top_k=5)
    return result.model_dump_json()


course_agent = Agent(
    name="course_assistant",
    instructions="""
你是 AI Agent 课程助教。
如果问题涉及课程资料，请优先调用 search_course_knowledge。
不要编造工具结果。
如果工具结果不足以回答，请说明资料不足。
""".strip(),
    tools=[search_course_knowledge],
)


async def run_course_agent(question: str) -> str:
    result = await Runner.run(course_agent, question)
    return result.final_output
```

注意：

- 工具内部仍然要做权限校验。
- Agent instructions 不能替代后端规则。
- 工具返回要结构化，避免模型误读。

## 6.7 现代 Agent Runtime 能力

Agent 不只是“模型 + 工具循环”。进入真实产品后，还需要 runtime 能力：

| 能力 | 解决的问题 | 学习阶段如何处理 |
| --- | --- | --- |
| Sessions / 会话状态 | 多轮上下文、短期记忆、任务连续性 | 第 6 章先做会话历史和摘要 |
| Human-in-the-loop | 高风险工具、审批、纠错 | 第 8 章放入 Workflow 节点 |
| Trace / Tracing | 解释每一步为什么发生 | 第 6 章记录 run / step / tool_call |
| Background mode | 深度研究、长报告、复杂工具链路 | 第 8 章作为异步任务处理 |
| Realtime agent | 语音、低延迟交互、多模态实时输入 | 不进入 12 周主线，可做扩展 |

长任务不要卡在一个 HTTP 请求里等待模型慢慢跑完。更稳的做法是：

1. API 创建任务并返回 `run_id`。
2. 后台 worker 执行 Agent / Workflow。
3. 前端通过 SSE / WebSocket / 轮询查看进度。
4. 每一步写入 trace 和状态表。
5. 失败后允许从最近 checkpoint 恢复或重新运行。

## 6.8 工具注册策略

本章建议只注册低风险工具：

| 工具 | 风险等级 | 是否自动执行 |
| --- | --- | --- |
| `get_current_weather` | low | 是 |
| `query_order_status` | medium | 只读且有权限时 |
| `search_course_knowledge` | low | 是 |

不要注册：

- 删除文档。
- 发送邮件。
- 创建退款。
- 修改权限。
- 执行任意代码。

如果要支持这些工具，必须放到第 8 章 Workflow 的人工确认节点里。

## 6.9 记忆设计

记忆分三类：

| 类型 | 用途 | 本章建议 |
| --- | --- | --- |
| 会话历史 | 当前对话上下文 | 保留最近几轮 |
| 摘要记忆 | 长对话压缩 | 超过上下文后摘要 |
| 长期记忆 | 用户偏好、长期事实 | 暂不做或非常谨慎 |

不要把所有历史都塞进 prompt。记忆也要有权限、来源和过期策略。

会话摘要示例：

```json
{
  "conversation_id": "conv_001",
  "summary": "用户正在学习 RAG 和 Tool Calling，已完成基础模型调用。",
  "updated_at": "2026-07-09T10:00:00Z"
}
```

## 6.10 失败处理

常见失败：

| 失败 | 处理 |
| --- | --- |
| 工具参数缺失 | 追问用户 |
| 工具权限不足 | 明确说明无权访问 |
| 工具超时 | 有限重试后失败退出 |
| 检索无结果 | 回答资料不足 |
| 循环调用 | 达到最大轮数后停止 |
| 模型输出异常 | 记录错误并返回友好提示 |

失败结果要进入 trace，而不是只返回“系统繁忙”。

## 6.11 测试场景

至少准备 10 个 Agent 测试用例：

| 类型 | 示例 | 预期 |
| --- | --- | --- |
| 直接回答 | 什么是 Agent？ | 可直接解释或查知识库 |
| RAG 工具 | 第 7 章 RAG MVP 要做什么？ | 调用知识库工具 |
| 订单工具 | 订单 O1001 到哪里了？ | 调用订单工具 |
| 参数缺失 | 我的订单到哪里了？ | 追问订单号 |
| 无权限 | 查别人的订单 | 拒绝 |
| 无资料 | 课程里有没有量子计算章节？ | 说明资料不足 |
| 工具失败 | 上游超时 | 有限重试或失败 |
| 多意图 | 查天气并解释 RAG | 分别处理或澄清 |
| 高风险请求 | 删除文档 | 拒绝或转人工确认 |
| 循环风险 | 一直继续查 | 达到停止条件 |

## 6.12 MVP / 进阶 / 生产化验收

### MVP

- 一个 Agent 能调用 3 个只读工具。
- 有最大轮数和超时。
- 工具调用有日志。
- 10 个测试用例能人工验收。

### 进阶

- Agent run 和 step 写入数据库。
- 支持会话摘要。
- 支持结构化 final output。
- 支持失败分类。

### 生产化

- Trace 可视化。
- Agent 测试进入 CI。
- 线上失败样本回流测试集。
- 工具风险等级和人工确认策略可配置。
- 成本和 token 超限自动停止。
- 长任务走后台任务或 durable workflow，不阻塞单个请求。

## 6.13 常见误区

- 把 Agent 当万能自动化。
- 不设最大轮数。
- 把高风险工具直接交给 Agent。
- 不记录工具调用参数。
- 让模型自己判断权限。
- 把长期记忆当数据库。
- 用同步 HTTP 请求承载深度研究、报告生成等长任务。

## 6.14 本章学习资料

- [OpenAI Agents SDK - Agents](https://openai.github.io/openai-agents-python/agents/)
- [OpenAI Agents SDK - Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Agents SDK - Tracing](https://openai.github.io/openai-agents-python/tracing/)
- [OpenAI Background Mode](https://developers.openai.com/api/docs/guides/background)
- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

## 6.15 本章复盘模板

```markdown
# 第 6 章复盘

## 我的 Agent 能调用哪些工具

## 我设置了哪些停止条件

## 我的 Agent run / step 如何记录

## 哪些测试用例失败了

## Agent 什么时候应该追问用户

## Agent 什么时候应该拒绝执行

## 哪些能力应该放到 Workflow 而不是 Agent
```
