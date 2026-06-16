# 第 4 章：Python AI 应用工程栈

更新时间：2026-06-16  
建议学习时间：3-5 天  
适合阶段：已经能调用模型、能写基础 Prompt，希望进入 Python AI 应用工程化  
本章产出：一个 OpenAI SDK 问答服务、一个 Agents SDK 概念解释 Agent、一份框架取舍报告、一套 AI 应用分层设计

## 4.1 本章学习目标

学完本章后，你应该能做到：

1. 说明 OpenAI SDK、OpenAI Agents SDK、Pydantic AI、LangGraph、LlamaIndex 的定位差异。
2. 使用 OpenAI SDK 封装一个基础 AI 服务。
3. 使用 OpenAI Agents SDK 封装一个简单 Agent。
4. 使用 Pydantic 定义输入、输出和工具参数。
5. 设计 Python AI 应用中的 API、Service、Prompt、Tool、Repository、Trace 分层。
6. 知道什么时候少用框架，什么时候引入 Agent 编排框架。
7. 避免把框架 API 当作 Agent 能力本身。

本章重点不是“哪个框架最强”，而是学会用 Python 工程方式组织 AI 应用。

## 4.2 Python AI 生态里的核心选择

### OpenAI SDK

OpenAI SDK 是模型调用的基础层。它适合：

- 普通问答。
- 结构化输出。
- 流式响应。
- Embedding。
- 直接接入 OpenAI API 或兼容协议服务。

它不是完整 Agent 框架，但学习成本最低，适合第一个 MVP。

### OpenAI Agents SDK

OpenAI Agents SDK 面向 Agent 应用。它适合：

- 定义 Agent instructions。
- 定义 tools。
- 实现 handoff。
- 输出 trace。
- 控制 Agent run。

如果你要学习工具调用、单 Agent、多 Agent、handoff 和 trace，它是本课程推荐的主线框架。

### Pydantic AI

Pydantic AI 强调类型安全和结构化输出。它适合：

- 用 Pydantic 模型定义 Agent 输入输出。
- 管理工具参数。
- 对接不同模型提供商。
- 快速写出可测试的 Python Agent。

如果你的团队重视类型、校验和测试，它很值得学习。

### LangGraph

LangGraph 更适合有状态、多步骤、可恢复的工作流和 Agent 图。它适合：

- Plan-Execute。
- 多步骤研究。
- 状态机。
- 人工确认节点。
- 可恢复执行。

如果任务流程复杂、需要持久化状态，LangGraph 比简单 ReAct 循环更合适。

### LlamaIndex / LangChain / Haystack

这些框架在 RAG 和数据连接器上有大量积累。课程建议：

1. 先自研最小 RAG 链路，理解每一步。
2. 再比较 LlamaIndex、LangChain、Haystack 的实现方式。
3. 项目里只引入真正减少复杂度的部分。

## 4.3 框架对比

| 维度 | OpenAI SDK | OpenAI Agents SDK | Pydantic AI | LangGraph | LlamaIndex |
| --- | --- | --- | --- | --- | --- |
| 定位 | 模型 API 基础层 | Agent 应用框架 | 类型安全 Agent 框架 | 有状态工作流/图 | RAG 数据框架 |
| 学习成本 | 低 | 中 | 中 | 中到高 | 中 |
| Tool Calling | 需要自己封装 | 内置 | 内置 | 可编排 | 可结合 |
| 多 Agent | 需要自己设计 | Handoff 支持 | 可实现 | 图编排支持 | 非主定位 |
| RAG | 需要自己实现 | 可调用检索工具 | 可调用检索工具 | 可编排检索流程 | 强项 |
| 适合阶段 | 第 2 章 | 第 5/8/11 章 | 第 4/5 章 | 第 9 章 | 第 6/7 章 |

课程主线建议：

```text
OpenAI SDK 打地基
  -> Pydantic 管好数据边界
  -> OpenAI Agents SDK 学 Agent
  -> 自研最小 RAG 理解链路
  -> LangGraph 处理复杂工作流
  -> LlamaIndex / Haystack 补数据连接器
```

## 4.4 推荐项目分层

无论用哪个框架，都建议按下面方式组织代码：

```text
app/
  api/
    routes.py
  ai/
    client.py
    agents.py
    service.py
    schemas.py
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
- AI Service 层负责组织模型调用、工具调用和业务规则。
- Prompt 不要散落在 route 或 tool 里。
- Tool 层只暴露边界清晰的业务能力。
- Repository 层处理数据库。
- Observability 层记录 trace、日志、token、耗时和错误。

## 4.5 实践一：OpenAI SDK 问答服务

### 目标

使用 OpenAI SDK 实现一个概念解释服务。

```python
from app.ai.client import client
from app.settings import settings


async def explain_with_sdk(concept: str) -> str:
    response = await client.responses.create(
        model=settings.openai_model,
        input=[
            {
                "role": "system",
                "content": "你是 AI Agent 课程助教，请用工程化视角解释概念。",
            },
            {"role": "user", "content": f"请解释：{concept}"},
        ],
        temperature=0.2,
    )
    return response.output_text
```

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
def validate_explanation(payload: dict) -> ConceptExplanation:
    return ConceptExplanation.model_validate(payload)
```

### 验收

- `concept` 为 RAG。
- `definition` 不为空。
- `common_mistakes` 是数组。
- 不符合结构时抛出校验错误。

## 4.7 实践三：OpenAI Agents SDK 概念解释 Agent

下面示例展示核心写法。具体 API 以当前 SDK 文档为准。

```python
from agents import Agent, Runner


concept_agent = Agent(
    name="concept_explainer",
    instructions="""
你是 AI Agent 课程助教。
请用中文解释概念，并给出 Python / FastAPI 工程例子。
回答必须包含：定义、工程例子、常见误区、下一步练习。
""".strip(),
)


async def explain_with_agent(concept: str) -> str:
    result = await Runner.run(concept_agent, f"请解释：{concept}")
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

本章最重要的实践是：用 OpenAI SDK 和 OpenAI Agents SDK 分别实现“概念解释”功能。

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
  "commonMistakes": ["...", "..."],
  "nextPractice": "..."
}
```

### 对比维度

| 维度 | OpenAI SDK | OpenAI Agents SDK | 我的判断 |
| --- | --- | --- | --- |
| 代码复杂度 |  |  |  |
| Prompt 管理 |  |  |  |
| Tool 扩展 |  |  |  |
| Trace 支持 |  |  |  |
| 后续做 RAG |  |  |  |
| 后续做多 Agent |  |  |  |

## 4.9 如何选择框架

### 优先 OpenAI SDK 的情况

- 只是普通问答、结构化输出、Embedding。
- 团队还在验证需求。
- 你想先理解模型调用本质。
- 不需要多 Agent、handoff、复杂 trace。

### 优先 OpenAI Agents SDK 的情况

- 需要工具调用。
- 需要 Agent run 和 trace。
- 需要 handoff 或多 Agent。
- 需要学习 Agent 正统工程结构。

### 优先 Pydantic AI 的情况

- 团队重视类型和校验。
- 输出结构复杂。
- 需要跨模型提供商。
- 希望工具参数和返回值都是强类型。

### 优先 LangGraph 的情况

- 任务有明确状态。
- 需要可恢复、可暂停、可人工确认。
- 工作流步骤多且存在分支。
- 需要把 Agent 变成可审计流程。

### 优先 LlamaIndex / Haystack 的情况

- 文档类型复杂。
- 数据连接器很多。
- RAG 链路不是项目差异化核心。
- 你已经理解基础 RAG，想节省工程时间。

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

## 4.12 本章完整实践任务

### 任务 1：OpenAI SDK 概念解释服务

要求：

- 使用 Python。
- 使用 OpenAI SDK。
- Prompt 不写在 API route 里。
- 输出能解释 RAG、Agent、Workflow、MCP。

验收：

- 每个概念都有定义、例子、误区。
- 不确定时不编造。

### 任务 2：Agents SDK 概念解释 Agent

要求：

- 使用 Agent instructions。
- 与 OpenAI SDK 版本输出字段一致。
- 能观察运行结果和错误。

验收：

- 同一个概念，两种实现都能回答。
- 能解释 Agent 框架带来的额外价值。

### 任务 3：框架取舍报告

写一份报告：

```markdown
# Python AI 应用框架取舍

## 我的实现功能

## OpenAI SDK 实现感受

## OpenAI Agents SDK 实现感受

## Pydantic / Pydantic AI 的价值

## 后续做 Tool Calling 我会选择

## 后续做 RAG 我会选择

## 哪些模块未来适合 Go 化

## 我的结论
```

## 4.13 本章自测题

### 概念题

1. OpenAI SDK 和 OpenAI Agents SDK 的核心区别是什么？
2. Pydantic 在 AI 应用里解决什么问题？
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

## 4.14 本章完成标准

完成本章后，你应该能做到：

- 能用 OpenAI SDK 完成一个问答接口。
- 能用 Pydantic 定义输入输出。
- 能用 OpenAI Agents SDK 完成一个简单 Agent。
- 能说明几个 Python AI 框架的适用边界。
- 能说明 Python 主线和 Go 扩展的合理分工。
- 能说明后续做 Tool Calling 和 RAG 时各框架如何扩展。

## 4.15 本章学习资料

### 必读资料

- [OpenAI SDKs](https://developers.openai.com/api/docs/libraries)
- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### 扩展资料

- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/overview)
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
