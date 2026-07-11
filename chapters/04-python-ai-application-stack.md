# 第 4 章：Python AI 应用工程栈

更新时间：2026-07-10
建议学习时间：3-5 天  
适合阶段：已经能调用模型、能写基础 Prompt，希望进入 Python AI 应用工程化  
本章产出：一个 ModelGateway 问答服务、一个 Agents SDK 概念解释 Agent、一份框架选择记录、一套 AI 应用分层设计

## 4.1 本章学习目标

学完本章后，你应该能做到：

1. 区分 Pydantic 数据校验库与 Pydantic AI Agent 框架。
2. 用 `ModelGateway` 隔离模型提供商，并在默认 Fake 与显式 Live 之间切换。
3. 用可信 `RunContext` 传递用户、租户、请求和权限，而不让模型生成身份。
4. 使用 Pydantic 定义输入、输出和工具参数。
5. 设计 Python AI 应用中的 API、Service、Prompt、Tool、Repository、Trace 分层。
6. 根据任务状态、工具、可恢复性和互操作需求选择框架。
7. 避免把框架 API 当作 Agent 能力本身。

本章重点不是“哪个框架最强”，而是学会用 Python 工程方式组织 AI 应用。

## 前置知识

先完成第 2-3 章，能够运行 Fake Model、解释结构化输出合同，并把 Prompt、外部上下文与应用强制策略分开。Go 和任何 Agent 框架都不是前置条件。

## 核心知识

本章核心知识由 4.2-4.11 节组成：以 `ModelGateway` 和可信 `RunContext` 为稳定内核，再按 API、Service、Tool、Repository、Trace 的依赖方向选择最少框架层。

![Agent 框架与互操作生态](../assets/agent-ecosystem-illustrations/03-agent-interop.png)

## 4.2 Python AI 生态里的核心选择

本课程的核心不是某个 Agent 框架，而是两个应用合同：

- `ModelGateway`：把消息和工具定义交给模型，返回类型化的 `ModelStep`；
  Fake 与 Live adapter 实现同一个接口。
- `RunContext`：保存由认证层提供的 `user_id`、`tenant_id`、`request_id` 和
  `permissions`。它不进入模型可见参数，由应用在每个资源边界执行授权。

```python
from typing import Protocol

from agent_course.core import (
    Message,
    ModelContinuation,
    ModelStep,
    RunContext,
    ToolDefinition,
)


class ModelGateway(Protocol):
    async def next_step(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        continuation: ModelContinuation | None = None,
        max_output_tokens: int | None = None,
    ) -> ModelStep: ...


def require_order_read(context: RunContext) -> None:
    context.require("orders:read")
```

`ModelContinuation` 是调用方持有的 provider 状态。Responses Live adapter 返回公开的
response ID；下一轮传回 continuation 时，只发送上一步之后新增的工具结果，不重发
完整历史。gateway 自身保持无状态，运行状态由应用持久化。

### Pydantic 不是 Pydantic AI

| 名称 | 它是什么 | 本课程用途 |
| --- | --- | --- |
| Pydantic | 数据模型与运行时校验库 | DTO、工具参数、结果、配置和持久化边界 |
| Pydantic AI | 建立在 Pydantic 生态上的 Agent 框架 | 可选的 provider、tool、eval 与观测实现 |

只使用 `BaseModel.model_validate()`、`Field` 或 `ConfigDict`，并不等于项目使用了
Pydantic AI。参考实现的核心合同只依赖 Pydantic，因此 Fake、OpenAI Responses、
Agents SDK 或其他 adapter 都能复用相同的业务边界。

OpenAI SDK、OpenAI Agents SDK、Pydantic AI、LangGraph、LlamaIndex 等项目的版本、
成熟度和能力对比统一维护在[生态成熟度矩阵](../docs/ecosystem-maturity.md)；本章不复制
会过期的功能表。

## 4.3 框架对比

这里保留选择规则，不做容易过期的横向排名：

1. 只有一次模型调用或原生结构化输出：实现 `ModelGateway` adapter 即可。
2. 需要 SDK 管理 tool loop、handoff 和 trace：选择 Agent runtime，并把业务权限留在
   `RunContext` 与工具层。
3. 需要显式状态、暂停、审批、恢复：选择 Workflow / graph runtime，持久化版本化状态。
4. 需要大量文档连接器：先固定检索与引用合同，再评估 RAG 框架。
5. 需要跨进程共享工具：稳定工具边界后再使用 MCP。
6. 不论框架如何选择，默认回归测试都使用 Fake；Live 只通过显式门禁做付费对比。

课程主线因此是：

```text
OpenAI SDK 打地基
  -> ModelGateway 隔离 provider
  -> Pydantic 管好数据边界
  -> RunContext 管住身份与权限
  -> Agent runtime 学执行循环
  -> 自研最小 RAG 理解链路
  -> LangGraph 处理复杂工作流
  -> 按需求补 RAG 数据连接器
  -> MCP / A2A / Apps 处理互操作和体验
```

## 4.4 推荐项目分层

无论用哪个框架，都建议按下面方式组织代码：

```text
app/
  api/
    routes.py
  core.py                 # Message / ModelGateway / RunContext / RunLimits
  models/
    fake.py               # 默认离线 adapter
    openai_responses.py   # 显式 Live adapter
  agents/
    runner.py             # 应用拥有的有界循环
    sessions.py
  prompts/
    concept_explainer.md
    knowledge_qa.md
  tools/
    weather.py
    order.py
    knowledge.py
  rag/
    loader.py
    chunker.py
    retriever.py
    generator.py
  repositories/
    conversation_repo.py
    run_log_repo.py
  observability/
    tracing.py
    logging.py
```

### 分层原则

- API 层只处理 HTTP 输入输出。
- API 的身份依赖必须从认证结果构造 `RunContext`；请求体不能提交或覆盖可信身份。
- Application / runner 层负责组织模型调用、工具调用、continuation 和运行预算。
- Model adapter 只翻译 provider 协议，不保存会话或业务权限。
- Prompt 不要散落在 route 或 tool 里。
- Tool 层先校验模型参数，再用 `RunContext` 授权，最后调用 Repository。
- Repository 层按可信 tenant / user 范围查询数据库。
- Observability 层记录 trace、日志、token、耗时和错误，并在存储边界脱敏。

## 4.5 实践一：OpenAI SDK 问答服务

### 目标

先用 provider-neutral 合同实现概念解释服务。默认路径使用 Fake，不加载
`openai` 或 `agents` 包；Live 路径必须显式启用。

```python
from agent_course.core import Message, ModelGateway


async def explain(concept: str, model: ModelGateway) -> str:
    step = await model.next_step(
        messages=[
            Message(
                role="system",
                content="你是 AI Agent 课程助教，请用工程化视角解释概念。",
            ),
            Message(role="user", content=f"请解释：{concept}"),
        ],
        tools=[],
    )
    if step.content is None or step.tool_calls:
        raise ValueError("concept explanation did not return plain content")
    return step.content
```

离线练习注入 `FakeModelGateway()`。只有操作者同时设置
`AGENT_COURSE_LIVE_TESTS=1`、非空 `OPENAI_API_KEY` 和非空
`OPENAI_MODEL` 后，才构造 `OpenAIResponsesGateway.from_environment()`；Live adapter
没有硬编码模型默认值。

### 验收

输入：

```text
RAG
```

结果应该：

- 有一句话定义。
- 有工程例子。
- 提到检索、上下文和引用来源。
- 不把 RAG 说成 Agent。

## 4.6 实践二：Pydantic 结构化输出

这一节使用的是 **Pydantic 校验库**，不是 Pydantic AI。它定义应用数据边界，
不负责 Agent 循环、provider 路由或工具执行。

### DTO

```python
from pydantic import BaseModel, Field


class ConceptExplanation(BaseModel):
    concept: str
    definition: str
    example: str
    common_mistakes: list[str] = Field(min_length=1, max_length=5)
    next_practice: str
```

### 校验边界

即使用了结构化输出能力，也要保留后端校验：

```python
def validate_explanation(payload: dict[str, object]) -> ConceptExplanation:
    return ConceptExplanation.model_validate(payload)
```

### 验收

- `concept` 为 RAG。
- `definition` 不为空。
- `common_mistakes` 是数组。
- 不符合结构时抛出校验错误。

## 4.7 实践三：OpenAI Agents SDK 概念解释 Agent

下面是 SDK 管理运行生命周期的可选 Live 路径。参考实现通过与 Responses adapter
相同的三重环境门禁构造 `OpenAIAgentsRunner`，并默认关闭敏感 trace 数据。

```python
from agent_course.agents.openai_agents import OpenAIAgentsRunner


INSTRUCTIONS = """
你是 AI Agent 课程助教。
请用中文解释概念，并给出 Python / FastAPI 工程例子。
回答必须包含：定义、工程例子、常见误区、下一步练习。
""".strip()


async def explain_with_agent(concept: str) -> str:
    runner = OpenAIAgentsRunner.from_environment()
    result = await runner.run(f"请解释：{concept}", instructions=INSTRUCTIONS)
    return result.final_output
```

### Agents SDK 的价值

相比直接调用模型，Agent 框架更适合：

- 管理 instructions。
- 注册 tools。
- 组织 handoff。
- 查看 trace。
- 控制 Agent run。

如果只是普通问答，不一定需要 Agent 框架。

## 4.8 实践四：同一功能做两套实现

本章最重要的实践是让 Fake、低层 Responses adapter 和可选 Agents SDK 路径遵守
同一个应用输入输出合同，而不是把业务逻辑绑定到某个 SDK。

功能要求：

```json
{
  "concept": "RAG"
}
```

输出要求：

```json
{
  "concept": "RAG",
  "definition": "...",
  "example": "...",
  "common_mistakes": ["...", "..."],
  "next_practice": "..."
}
```

### 对比维度

- 两条 Live 路径是否都拒绝缺少显式门禁或模型名的配置。
- 默认 Fake 测试是否完全离线，并且不导入可选 Live 包。
- adapter 是否隐藏 provider wire format，而不吞掉停止原因和 usage。
- `RunContext` 是否始终由应用注入，不出现在模型可见 schema 中。
- 切换实现后，应用 DTO、权限测试和评估用例是否保持不变。

## 4.9 如何选择框架

只按当前问题选择一层：

- 普通问答、结构化输出、Embedding：低层模型 SDK adapter。
- 希望 SDK 管理 tool loop、handoff、guardrail 和 trace：Agent runtime。
- 希望 Python 类型贯穿 Agent、工具和评估：评估 Pydantic AI，但不要与 Pydantic
  校验库混为一谈。
- 有版本化状态、暂停、审批和恢复：Workflow / graph runtime。
- 主要复杂度是文档摄取与检索连接器：RAG 框架。
- 工具要被多个进程或产品复用：边界稳定后采用 MCP。

具体产品的版本、成熟度、验证日期和来源只在[生态成熟度矩阵](../docs/ecosystem-maturity.md)
更新。
本章的选择规则不随某一版本的功能清单变化。

## 4.10 常见工程误区

### 误区 1：框架等于能力

用了 Agents SDK 或 LangGraph，不代表你的应用就是可控 Agent。Agent 需要工具、上下文、执行循环、停止条件和观测。

### 误区 2：Prompt 到处散落

把 prompt 写在 route、service、tool 里，会很快失控。应该集中管理。

### 误区 3：没有 DTO 边界

直接把模型返回传给前端或数据库，会导致格式漂移、字段缺失和安全风险。

### 误区 4：过早多框架混用

初学阶段同时混用 Agents SDK、LangGraph、LlamaIndex、Pydantic AI，容易把问题归因到框架。先用一条主线跑通，再按痛点引入组件。

### 误区 5：没有错误处理

模型超时、限流、输出非法、工具失败都应该有统一处理。

## 4.11 Python 主线与 Go 扩展

本课程第 4 章开始正式确认工程边界：

| 模块 | 首选 | 可选 Go 化时机 |
| --- | --- | --- |
| Agent 编排 | Python | 不建议早期 Go 化 |
| RAG 实验 | Python | 不建议早期 Go 化 |
| Prompt 测试 | Python | 不需要 Go 化 |
| 只读工具服务 | Python 起步 | 接口稳定后可用 Go 重写 |
| MCP Server | Python 起步 | 企业系统集成时可用 Go 实现 |
| API 网关 | Python 起步 | 高并发或统一网关时可用 Go |
| 后台 worker | Python 起步 | CPU/并发压力明确后可用 Go |

判断标准：

1. 业务边界是否稳定。
2. 输入输出 schema 是否清晰。
3. 是否真的遇到性能、部署或团队维护问题。
4. Go 化后是否减少复杂度，而不是增加双栈成本。

## 教师演示

1. 展示 `ModelGateway.next_step()` 的 provider-neutral 签名，以及 runner 如何在每一轮传入剩余 `max_output_tokens`。
2. 用同一问题切换 Fake adapter 与被三重门禁锁住的 OpenAI adapter，证明业务层不读取 Key。
3. 从认证请求构造 `RunContext`，展示模型 arguments 无法覆盖 tenant/user/permissions。
4. 对比低层 Responses-owned loop 与 Agents SDK-owned run，说明两者的状态和预算责任不同。
5. 打开生态成熟度矩阵，只按当前任务需要选择最少层，不复制易过期的框架排名。

## 学员实验

本章实验直接复用参考实现的 core/model/live-gate 文件，不新增平行脚手架。任务 1 和任务 3 属于 Core；任务 2 的真实 SDK run 属于显式 Live 的 Advanced 扩展。

### 任务 1：ModelGateway 概念解释服务

要求：

- 使用 Python。
- Service 只依赖 `ModelGateway`，默认注入 `FakeModelGateway`。
- Prompt 不写在 API route 里。
- 输出能解释 RAG、Agent、Workflow、MCP。

验收：

- 每个概念都有定义、例子、误区。
- 不确定时不编造。
- 默认测试离线、无密钥，不导入可选 Live 包。

### 任务 2：Agents SDK 概念解释 Agent

要求：

- 使用 Agent instructions。
- 与 `ModelGateway` 版本输出字段一致。
- 只在三重 Live 门禁满足时构造 SDK runner。
- 能观察运行结果和错误。

验收：

- 同一个概念，两种实现都能回答。
- 能解释 Agent 框架带来的额外价值。

### 任务 3：框架选择记录

先查阅[生态成熟度矩阵](../docs/ecosystem-maturity.md)的当前版本、成熟度、验证日期和
来源；在记录中写出你实际参考的矩阵行和来源链接。再只按本章选择规则记录决策，不在
作业中复制一份新的生态功能表：

```markdown
# Python AI 应用框架选择记录

## 当前任务与约束

## 参考的成熟度矩阵行与来源

## 必需能力：模型 / 工具 / 状态 / 恢复 / 互操作

## 选择的最小层

## ModelGateway 与 RunContext 如何保持稳定

## 默认 Fake 验证

## 可选 Live 门禁

## 重新评估触发条件

## 我的结论
```

## 失败注入与排错

| 注入 | 预期 | 首查边界 |
| --- | --- | --- |
| Service 直接 import OpenAI client | 架构评审失败 | 依赖是否只指向 `ModelGateway` |
| 模型 arguments 加 tenant/user | strict validation 失败 | `RunContext` 是否来自认证层 |
| Live 缺 flag/key/model | 构造前失败 | `load_live_settings()` |
| 第二轮重复完整历史和 continuation | contract test 失败 | delta messages 与 caller-owned state |
| 框架比较与成熟度文档冲突 | 文档验证失败 | 单一成熟度来源与验证日期 |

## 自动验证

```bash
cd reference-implementation
uv run --frozen --no-sync --group dev --extra live pytest \
  tests/test_core.py tests/test_fake_model.py tests/test_live_gates.py \
  tests/test_import_isolation.py -q
uv run --frozen --no-sync --group dev --extra live ruff check .
```

默认命令不发起模型请求。学习者还要提交一张依赖方向图和一份框架选择记录，说明哪些判断来自稳定应用合同，哪些来自有日期的成熟度矩阵。

## 作业与评分

| 评分项 | 分值 | 满分证据 |
| --- | ---: | --- |
| ModelGateway 边界 | 25 | 签名、Fake/Live compatibility、remaining-token 证据 |
| RunContext 与依赖方向 | 25 | trusted identity、tenant 隔离、无 provider 泄漏 |
| Pydantic 边界 | 15 | DTO/strict schema/错误分类 |
| 框架选择记录 | 20 | 最小层、成熟度来源、重新评估触发条件 |
| 自动验证与复盘 | 15 | focused tests、Ruff、一次失败分析 |

总分 100 分。Core 及格线为 70 分；若模型可提供身份、默认路径需要网络，或业务层绕过 `ModelGateway`，本章不及格。

## 4.13 本章自测题

### 概念题

1. OpenAI SDK 和 OpenAI Agents SDK 的核心区别是什么？
2. Pydantic 与 Pydantic AI 分别解决什么问题？
3. 为什么不建议一开始就使用太多框架？
4. LangGraph 更适合什么类型的任务？
5. Go 在本课程里更适合承担哪些模块？

### 判断题

1. 使用 Agent 框架后，应用自动变得稳定可靠。  
2. 普通问答 MVP 可以先用 OpenAI SDK。  
3. RAG 还没跑通前，先学习数据链路比堆框架更重要。  
4. Go 适合在业务边界稳定后实现独立工具服务。  

参考答案：

1. 错。  
2. 对。  
3. 对。  
4. 对。  

## Core / Advanced / Production 完成标准

| 等级 | 完成标准 |
| --- | --- |
| Core | 默认 Fake 与 import-isolation tests 通过；Service 只依赖 `ModelGateway`；身份只来自 `RunContext`；能用 Pydantic 定义边界并解释框架选择。 |
| Advanced | 在三重门禁下比较 Responses-owned loop 与 SDK-owned run，记录模型、预算和脱敏结果；可替换一个 adapter 而不改业务合同。 |
| Production | 实现依赖注入、secret/workload identity、配置验证、provider failover 策略、usage/SLO、trace、发布门禁和 adapter contract tests；Go 只承接有证据的稳定边界。 |

## 4.15 本章学习资料

### 必读资料

- [OpenAI SDKs](https://developers.openai.com/api/docs/libraries)
- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### 扩展资料

- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [Pydantic AI Durable Execution](https://pydantic.dev/docs/ai/integrations/durable_execution/overview/)
- [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/)
- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [Google Agent Development Kit](https://adk.dev/)
- [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)
- [LlamaIndex Documentation](https://docs.llamaindex.ai/)
- [MCP SDKs](https://modelcontextprotocol.io/docs/sdk)

## 4.16 本章复盘模板

```markdown
# 第 4 章复盘

## 我完成了哪些接口

## OpenAI SDK 的优点和不足

## OpenAI Agents SDK 的优点和不足

## 我更适合用哪个作为当前主线

## 我对 AI 应用分层的理解

## 哪些模块未来适合 Go 化

## 进入 Tool Calling 前我还不清楚的问题
```
