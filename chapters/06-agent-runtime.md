# 第 6 章：单 Agent Runtime：执行循环、工具、记忆与 Trace

更新时间：2026-07-10
建议学习时间：5-7 天  
本章产出：一个有显式预算、可信身份边界、会话隔离、停止原因和脱敏轨迹的单 Agent；以及一份把高风险动作交给可恢复审批流程的设计说明。

## 本章定位

第 5 章解决了“一次模型输出怎样变成一次受控工具调用”。本章把它扩展成运行时：模型可能连续请求工具，应用必须决定何时继续、何时停止、哪些状态可以保存、哪些数据不能进入 trace。重点不是让 Agent 显得更自主，而是让每次运行都可终止、可解释、可测试。

参考实现提供两条刻意分开的 Live 路径：

| 路径 | 谁拥有循环 | 参考实现入口 | 本章结论 |
| --- | --- | --- | --- |
| Responses-owned step，应用拥有 loop | `BoundedAgentRunner` 调用 `OpenAIResponsesGateway.next_step()`，应用执行工具并继续 | `agent_course.agents.runner`、`agent_course.models.openai_responses` | 适合教学预算、权限、停止原因和轨迹断言 |
| SDK-owned run | OpenAI Agents SDK 的 `Runner.run()` 拥有 run lifecycle | `agent_course.agents.openai_agents.OpenAIAgentsRunner` | 适合采用 SDK 的运行语义；不能假装自动继承本地 `RunLimits` |

两条路径不是嵌套关系，也不要在同一次 run 中让两个 runtime 同时拥有循环。默认离线实验使用 Fake Model 和应用拥有的有界循环，不需要 API Key。

## 前置知识

- 已完成第 5 章，理解 strict tool schema、后端参数校验、可信 `RunContext` 和 `ToolResult`。
- 能阅读异步 Python、Pydantic 模型、pytest 断言和结构化事件。
- 已按 `reference-implementation/README.md` 同步环境；本章所有 `uv run` 命令都从 `reference-implementation/` 执行。

## 学习目标

完成本章后，你应该能够：

1. 区分应用拥有的 Responses 循环与 Agents SDK 拥有的 run。
2. 用 `RunLimits` 实际设置轮数、工具次数、输出 token 和总超时，而不只把限制写在文档里。
3. 解释 `RunContext`、guardrail、tool permission 和 approval 各自负责什么。
4. 读取 `AgentResult` 和全部 `StopReason`，不把“停止”都误判为“完成”。
5. 使用按租户、用户、会话三元组隔离的 session，并说明当前内存实现的保留限制。
6. 保存 provider continuation，并在 Responses 续跑时只发送新产生的 tool result。
7. 验证 trace 在写入边界脱敏，同时保留可评分的工具轨迹证据。
8. 把需要人工确认的副作用交给第 8 章的可恢复 Workflow，而不是在 Agent 内用一句提示词模拟审批。

## 核心知识

### 6.1 运行时边界

一个受控循环可以简化为：

```text
可信请求上下文 + 用户问题 + RunLimits
  -> 输入 guardrail
  -> model.next_step(messages, tools, continuation)
  -> 检查累计输出 token
  -> 若有工具调用：去重、检查工具预算、后端校验与授权、执行
  -> 保存 ToolResult，并用 continuation 或完整历史继续
  -> 若无工具调用：按模型 stop_reason 结束
  -> 保存 session 增量和脱敏 trace
  -> 返回 AgentResult
```

控制面必须在应用后端，而不是 prompt 内：

- `RunContext` 由认证层提供 `user_id`、`tenant_id`、`request_id` 和权限集合。模型不能提交或覆盖这些值。
- `DefaultGuardrail` 是一个确定性的输入策略，只阻断参考实现中列出的高风险模式。它不是完整内容安全系统，也没有实现输出 guardrail。
- 工具仍通过 `context.require(...)` 和 strict 参数模型执行权限与参数校验。guardrail 通过不代表工具有权执行。
- 人工审批必须绑定实际 payload 并持久化暂停状态。当前 `BoundedAgentRunner` 自身不提供暂停审批；可恢复审批由 `ResearchWorkflow` 演示。

### 6.2 `RunLimits` 是执行合同

参考实现的限制全部为正数：

```python
class RunLimits(FrozenModel):
    max_turns: int = Field(gt=0)
    max_tool_calls: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)
```

四个限制的语义不同：

| 字段 | 计数边界 | 超限结果 |
| --- | --- | --- |
| `max_turns` | 每次 `model.next_step()` 计一轮 | `max_turns` |
| `max_tool_calls` | 真正执行工具前检查；预算耗尽时不执行下一次 | `max_tool_calls` |
| `max_output_tokens` | 累加每个 `ModelStep.usage.output_tokens`；超限内容不返回也不写入 session | `max_output_tokens` |
| `timeout_seconds` | `asyncio.timeout()` 包住整个 loop，包括模型和工具时间 | `timeout` |

`max_output_tokens` 依赖 gateway 返回的 usage。它不是账户级消费上限；Live 模式仍需平台预算和线上费用监控。

### 6.3 主示例：真正设置限制

下面代码与参考实现接口一致，使用确定性 Fake Model。`RunLimits(...)` 是 run 的必填参数，而不是注释里的愿望。

```python
import asyncio

from agent_course.agents.guardrails import DefaultGuardrail
from agent_course.agents.runner import BoundedAgentRunner
from agent_course.core import RunContext, RunLimits
from agent_course.models.fake import FakeModelGateway
from agent_course.observability.traces import InMemoryTraceSink
from agent_course.tools.orders import QueryOrderStatusTool
from agent_course.tools.registry import ToolRegistry


async def main() -> None:
    traces = InMemoryTraceSink()
    runner = BoundedAgentRunner(
        model=FakeModelGateway(),
        tools=ToolRegistry([QueryOrderStatusTool()]),
        guardrail=DefaultGuardrail(),
        traces=traces,
    )
    context = RunContext(
        user_id="user-1",
        tenant_id="tenant-1",
        request_id="chapter-06-demo",
        permissions=frozenset({"orders:read"}),
    )
    limits = RunLimits(
        max_turns=4,
        max_tool_calls=3,
        max_output_tokens=100,
        timeout_seconds=0.2,
    )

    result = await runner.run(
        "查询订单 O1001",
        context,
        limits,
        session_id="lesson-session",
    )

    assert result.stop_reason.value == "completed"
    assert result.final_content == "订单 O1001 当前状态为 shipped。"
    assert result.model_turn_count == 2
    assert [call.name for call in result.model_tool_calls] == [
        "query_order_status"
    ]
    assert [item.code for item in result.tool_results] == ["OK"]
    assert traces.for_trace(result.trace_id)[-1].event_type == "run.finished"


asyncio.run(main())
```

工具调用参数证据来自 `AgentResult.model_tool_calls`，不是工具输出的自述。`ToolCall.arguments` 进入结果后深层不可变，因此后续工具或评分代码不能悄悄改写历史证据。

### 6.4 结果与停止原因

`AgentResult` 的当前字段是：

| 字段 | 语义 |
| --- | --- |
| `final_content` | 最后一个被预算接受的 assistant 文本；停止时可能为 `None` |
| `stop_reason` | 终止分类，必须由调用方显式处理 |
| `messages` | 本次模型可见历史加上新消息的快照 |
| `model_tool_calls` | 模型实际提出的工具调用轨迹 |
| `model_turn_count` | 模型 step 次数 |
| `tool_results` | 后端实际执行后的结果 |
| `trace_id` | 关联脱敏事件的标识 |
| `continuation` | provider continuation；可能为 `None` |

当前 `StopReason` 全集如下：

| 值 | 解释 | 调用方应做什么 |
| --- | --- | --- |
| `completed` | 正常完成 | 展示被接受的结果 |
| `tool_calls` | gateway step 表示还需工具；若没有实际 tool call 则被 runner 转成 `model_error` | 不作为最终成功状态 |
| `max_turns` | 模型轮数耗尽 | 返回受控失败并检查轨迹 |
| `max_tool_calls` | 工具预算耗尽 | 不执行超预算调用 |
| `max_output_tokens` | 累计输出 token 超限 | 不返回或保留超限文本 |
| `timeout` | 整个 run 超时 | 可由上层决定是否创建新 run；不要盲目重放副作用 |
| `repeated_tool_call` | 同一 run 中工具名和规范化参数重复 | 停止循环 |
| `model_error` | gateway 异常、无效 step 或一般工具失败 | 查看 trace 和结构化工具错误 |
| `permission_denied` | 工具缺少可信权限 | 不重试，不把权限交给模型猜测 |
| `policy_denied` | 输入策略或工具策略拒绝 | 返回安全的拒绝结果 |

`repeated_tool_call` 的指纹由工具名与规范化 JSON 参数组成，去重集合只活在一次 run 内。同一 session 的下一次合法请求可以再次调用同一工具。

### 6.5 Responses continuation 与 SDK-owned run

应用拥有 loop 时，`OpenAIResponsesGateway` 把公开的 Responses response ID 包装成：

```python
ModelContinuation(provider="openai_responses", token="response-1")
```

下一轮把这个 continuation 传给 `next_step(..., continuation=...)`，并只发送上一响应之后的新 tool 消息。gateway 会把它转换为 `function_call_output`，同时设置 `previous_response_id`。不要同时重发旧 transcript，否则上下文会重复。gateway 无状态，不替调用方保存 response ID。

SDK-owned 路径的当前 wrapper 只有模型选择、instructions 和敏感 trace 开关：

```python
from agent_course.agents.openai_agents import OpenAIAgentsRunner


async def run_sdk_owned() -> object:
    runner = OpenAIAgentsRunner.from_environment()
    return await runner.run(
        "解释受控 Agent 的停止条件",
        instructions="Complete the task within the configured boundaries.",
    )
```

这段是可解析的 Live 示例，但只有在精确设置 `AGENT_COURSE_LIVE_TESTS=1`、`OPENAI_API_KEY` 和 `OPENAI_MODEL` 后才能构造 adapter。当前 wrapper 没有接收课程的 `RunLimits`、tools、session 或本地 guardrail，所以不得用它声称已经验证了同一组本地边界。

### 6.6 Session 与记忆保留

`InMemorySessionStore` 使用 `(tenant_id, user_id, session_id)` 组成的 `SessionKey`：相同字符串 session ID 不会跨租户或跨用户共享。runner 在 run 开始时加载历史，在结束时只追加本次 `new_messages`。

当前实现明确做到：

- 保存用户消息、成功进入状态的 tool 消息和 assistant 消息。
- 即使 run 因超时或错误结束，也保存已经形成的本次增量。
- 输出 token 超限时，只保存先前已接受的消息；超限 assistant 文本不会进入 `final_content` 或 session。
- 不把一次 run 的重复调用指纹带到下一次 run。

当前实现明确没有做到：持久化、TTL、删除 API、摘要、token compaction、长期用户画像、加密或跨进程恢复。把它们写成“已支持记忆系统”是不准确的。

**设计练习：生产记忆保留。** 为 session 增加 `retention_policy`、消息来源、写入时间、删除时间和摘要版本；先按租户/用户授权查询，再做 compaction。长期偏好必须有用途、同意、可纠正和删除机制，不能从聊天中无条件抽取。

### 6.7 Guardrail、权限与可恢复审批

安全边界按执行顺序分层：

1. 输入 guardrail 在模型调用前拦截参考实现定义的高风险模式。
2. strict tool schema 拒绝额外或无效参数。
3. 工具从可信 `RunContext` 检查权限；模型只提供业务参数。
4. trace sink 在存储边界脱敏。
5. 高风险副作用进入可恢复 Workflow，审批通过后才允许执行。

当前 `BoundedAgentRunner` 没有“暂停等待审批”的 stop reason，也不应把高风险工具直接注册后让模型询问“你确认吗”。参考实现的可恢复审批合同是：`ResearchWorkflow.start()` 返回 `waiting_for_approval`；审批决定携带已持久化 payload 的 SHA-256 hash 和 idempotency key；`approve()` 后状态为 `running` 或 `cancelled`；所有者再调用 `resume()` 完成。第 8 章会完整实现和测试这条路径。

### 6.8 Trace 脱敏与轨迹评分

`InMemoryTraceSink.record()` 在事件进入存储前递归清洗属性：

- `arguments`、`tool_args`、`api_key`、`authorization`、`cookie`、`password`、`secret`、`token` 等键及其下划线后缀整体替换为 `[REDACTED]`。
- 字符串中的 `sk-...` 和 Bearer token 也被替换。
- `tool.called` 因此记录工具名，但不会保留原始参数。

脱敏 trace 与可评分轨迹不是矛盾关系。`AgentResult.model_tool_calls` 是本次进程内的不可变评分证据；trace 只保留生产诊断所需的低敏摘要。若生产系统确实需要参数级审计，应使用单独的加密、最小访问权限和保留策略，不能关闭默认脱敏来图省事。

第 9 章的 trajectory evaluation 至少检查：

- 工具名称序列是否符合预期；
- 参数的规范 JSON 是否精确匹配；
- 未授权动作是否在无成功副作用的情况下终止；
- `model_turn_count` 是否在 case 的上限内；
- `stop_reason` 是否是预期的完成、预算停止或拒绝类型。

## 教师演示

1. 运行 6.3 主示例，展示两轮模型 step、一次工具执行和 `completed`。
2. 把 `max_tool_calls` 改为 `1`，注入两个工具调用，展示第二个调用没有执行且结果为 `max_tool_calls`。
3. 使用 `[fixture:repeated-order-call]` 展示相同工具名和参数在第二次执行前被停止。
4. 用同一个 `session_id` 分别配合两个用户上下文，展示历史不会跨用户读取。
5. 向 trace 手工写入 `arguments` 和 `api_key`，序列化事件后确认订单号和密钥均不存在。
6. 对比应用拥有 loop 的 `AgentResult` 与 SDK-owned wrapper，指出后者当前没有课程 `RunLimits` 接口。

## 学员实验

Task 11 计划创建本章实验目录 `labs/chapter-06/`；该目录在本次 Task 5 提交中尚未创建，因此这里记录的是准确的后续路径，不宣称当前已经可以从该目录运行 README。

实验任务：

1. 用 Fake Model 完成一个有 `RunLimits` 的订单查询 run。
2. 分别制造 `max_turns`、`max_tool_calls`、`max_output_tokens`、`timeout` 和 `repeated_tool_call`。
3. 验证无权限和高风险输入不会产生成功工具结果。
4. 验证 session 的租户/用户隔离和超预算内容不保留。
5. 从 `model_tool_calls` 评分工具轨迹，并证明 trace 不含原始参数。
6. 写一段设计说明，把一个发送邮件动作移到第 8 章的审批 Workflow。

默认离线验证命令与参考实现 README 完全一致：

```bash
cd reference-implementation
uv run --group dev --extra live pytest -q
```

本章聚焦命令：

```bash
uv run --group dev --extra live pytest tests/test_agent_runner.py tests/test_evals.py -q
```

## 失败注入与排错

| 注入 | 预期证据 | 常见误判 |
| --- | --- | --- |
| 删除 `orders:read` | `permission_denied`，一个失败 `ToolResult`，无成功副作用 | 让模型换一种参数重试 |
| 超过输出 token | `max_output_tokens`，超限文本不在 result/session | 只截断显示文本但仍保存全文 |
| gateway 睡眠超过总超时 | `timeout` 和 `run.timeout` | 只给单个 HTTP 调用设置超时 |
| 重复相同工具与参数 | 只执行一次，随后 `repeated_tool_call` | 只按 call ID 去重 |
| `tool_calls` stop reason 却没有调用 | `model_error` | 把不完整 step 当完成 |
| trace 属性含 `arguments` | 值为 `[REDACTED]` | 在 logger 外先记录原始参数 |

排错顺序固定为：case 输入与可信 context -> 实际 `stop_reason` -> `model_tool_calls` -> `tool_results` -> 同一 `trace_id` 的事件 -> session 增量。不要从最终文本反推整个执行过程。

## 自动验证

现有参考测试已经覆盖：runner 类型签名、正常工具循环、重复调用、轮数/工具/token/时间预算、权限失败、参数失败、输入 guardrail、Responses continuation、session 隔离、trace 脱敏以及工具轨迹不可变。

本章提交的自动验收还应确认：

- 所有 Python fence 能被 `ast.parse` 解析；
- `StopReason` 拼写与 `core.py` 一致；
- 主示例构造了真实 `RunLimits`；
- 未把 SDK-owned wrapper 描述成支持本地 `RunLimits`；
- `labs/chapter-06/` 只作为 Task 11 计划路径出现，没有失效 Markdown 链接。

## 作业与评分

| 维度 | 分值 | 满分证据 |
| --- | ---: | --- |
| 有界循环 | 25 | 四个 `RunLimits` 都实际传入，预算停止有测试 |
| 权限与 guardrail | 20 | 可信 identity 不进入模型参数，拒绝无成功副作用 |
| session 与保留 | 15 | 跨租户/用户隔离，能准确说明当前不支持的保留能力 |
| trace 与轨迹 | 20 | trace 脱敏，轨迹从不可变模型调用证据评分 |
| runtime 取舍 | 10 | 清楚区分 Responses-owned loop 与 SDK-owned run |
| 审批设计 | 10 | 高风险动作交给 hash 绑定、可恢复、幂等的 Workflow |

任何只在 prompt 中写“最多调用三次”却没有 `RunLimits` 的提交，有界循环项不得分；任何让模型提供 `tenant_id` 或权限的提交，安全项不得分。

## Core / Advanced / Production 完成标准

- **Core**：Fake Model 下的 runner 有实际预算、结构化停止原因、可信权限、session 隔离和脱敏 trace。
- **Advanced**：能够对 Responses continuation 做 delta 续跑，并用确定性轨迹断言比较运行结果。
- **Production（设计与外部基础设施要求）**：持久化 run/session、TTL 与删除、加密审计、后台 worker、费用告警和可恢复审批均有独立实现及测试。当前内存参考实现不宣称达到这一层。

## 本章资料

- [参考实现 README](../reference-implementation/README.md)
- [OpenAI Agents SDK - Running agents](https://openai.github.io/openai-agents-python/running_agents/)
- [OpenAI Agents SDK - Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK - Guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [OpenAI Agents SDK - Tracing](https://openai.github.io/openai-agents-python/tracing/)
- [OpenAI Background Mode](https://developers.openai.com/api/docs/guides/background)
- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

## 复盘模板

```markdown
# 第 6 章复盘

## 谁拥有我的执行循环，为什么

## 我实际设置了哪些 RunLimits

## 每个 StopReason 如何进入产品状态

## session 的身份键和保留策略是什么

## 哪些证据进入 AgentResult，哪些进入脱敏 trace

## 哪些动作必须移交可恢复审批

## 我用哪条轨迹断言发现了最终答案之外的问题
```
