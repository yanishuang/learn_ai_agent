# 第 5 章：Tool Calling / Function Calling

更新时间：2026-07-09
建议学习时间：5-7 天  
适合阶段：已经能完成模型调用和 Prompt 管理，准备让模型使用外部工具  
本章产出：3 个可调用工具、一个 Tool Calling API、一套工具权限校验、一张工具调用日志表、一份危险工具安全清单

## 5.1 本章学习目标

学完本章后，你应该能做到：

1. 解释 Tool Calling / Function Calling 的工作机制。
2. 区分“模型选择工具”和“后端执行工具”。
3. 设计工具名称、描述、参数 Schema 和返回值。
4. 使用 Python function tool 暴露业务能力。
5. 使用 Pydantic 校验工具参数和返回值。
6. 为工具调用增加参数校验、权限校验、日志和错误处理。
7. 识别哪些工具不能让模型自动执行。
8. 实现天气查询、订单查询、知识库搜索 3 个示例工具。
9. 知道何时可以把稳定工具服务抽到 Go 或 MCP Server。
10. 了解 built-in tools、remote MCP、tool search 等现代工具入口的适用边界。

Tool Calling 是 Agent 的基础。没有工具，Agent 只能说；有了工具，Agent 才能查、算、读、写、执行。

## 5.2 什么是 Tool Calling

Tool Calling 是让模型在需要外部能力时，输出一个“工具调用请求”，由应用程序执行工具，再把工具结果返回给模型。

注意：模型本身不执行工具。真正执行工具的是你的后端程序。

### 基本流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant A as Python 应用
    participant M as 大模型
    participant T as 工具服务

    U->>A: 我的订单现在到哪里了？
    A->>M: 用户问题 + 可用工具列表
    M-->>A: 调用工具 query_order_status(order_id)
    A->>A: 参数校验 / 权限校验
    A->>T: 执行 query_order_status
    T-->>A: 工具结果
    A->>M: 工具结果
    M-->>A: 生成最终回答
    A-->>U: 您的订单已发货...
```

### 关键点

- 模型决定“是否需要工具”和“调用哪个工具”。
- 后端决定“工具是否允许执行”。
- 后端负责真实调用数据库、API 或业务服务。
- 工具返回结果后，模型再组织成用户能理解的回答。

## 5.3 Tool Calling 和普通结构化输出的关系

Tool Calling 本质上也是一种结构化输出。

普通结构化输出：

```json
{
  "answer": "RAG 是检索增强生成",
  "difficulty": "beginner"
}
```

工具调用输出：

```json
{
  "toolName": "query_order_status",
  "arguments": {
    "order_id": "O1001"
  }
}
```

区别在于：工具调用输出会触发后端执行动作。因此 Tool Calling 比普通结构化输出更危险，也更需要工程控制。

## 5.4 一个好工具的设计标准

工具不是随便把 Python 函数暴露给模型。一个好工具应该满足：

| 标准 | 说明 |
| --- | --- |
| 名称清晰 | 模型看到名字就知道用途 |
| 描述明确 | 说明什么时候使用、什么时候不要使用 |
| 参数简单 | 参数越清楚越稳定 |
| 返回结构化 | 方便模型理解，也方便日志记录 |
| 权限可控 | 后端能判断用户是否能调用 |
| 无副作用优先 | 初期优先查询类工具 |
| 错误可解释 | 工具失败时返回明确错误 |

### 工具名称示例

好的名称：

```text
query_order_status
search_course_knowledge
get_current_weather
calculate_sales_growth
```

不好的名称：

```text
do_it
helper
call_api
query
tool1
```

模型依赖工具名称和描述来选择工具，命名模糊会显著降低调用质量。

## 5.5 工具分类

按风险分：

| 类型 | 例子 | 是否可自动执行 |
| --- | --- | --- |
| 只读查询 | 查天气、查订单、查知识库 | 通常可以 |
| 计算转换 | 计算增长率、格式化 JSON | 通常可以 |
| 写入操作 | 创建任务、保存草稿 | 需要谨慎 |
| 外部发送 | 发邮件、发群消息 | 建议人工确认 |
| 高风险操作 | 删除数据、退款、转账、改权限 | 必须人工确认或禁止 |

课程第 5 章只建议实现只读查询和计算类工具。

## 5.6 参数设计

参数应该简单、明确、可校验。

### 好的参数

```python
from pydantic import BaseModel, Field


class OrderStatusRequest(BaseModel):
    order_id: str = Field(min_length=3, max_length=64)


class WeatherRequest(BaseModel):
    city: str = Field(min_length=1, max_length=64)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=5, ge=1, le=10)
```

### 不好的参数

```python
class ToolRequest(BaseModel):
    data: str
```

问题：

- 参数含义不清。
- 不方便校验。
- 模型容易乱填。
- 日志不可读。

## 5.7 返回值设计

工具返回给模型的结果应该结构化、简洁、无敏感信息。

### 订单查询返回

```json
{
  "order_id": "O1001",
  "status": "已发货",
  "logistics_company": "顺丰",
  "tracking_no": "SF123456",
  "latest_event": "包裹已到达上海转运中心"
}
```

不应该返回：

```json
{
  "buyer_phone": "13800000000",
  "buyer_address": "上海市...",
  "internal_remark": "重要客户，优先处理"
}
```

除非这些字段对回答必要，且用户有权限。

### 工具错误返回

建议统一格式：

```json
{
  "success": false,
  "error_code": "ORDER_NOT_FOUND",
  "message": "未找到该订单"
}
```

这样模型可以根据错误结果继续追问或解释。

## 5.8 Python Tool 基础：普通函数版

先不用 Agent 框架，直接把工具当普通函数实现。

`app/tools/weather.py`：

```python
from pydantic import BaseModel


class WeatherResult(BaseModel):
    city: str
    weather: str
    temperature_c: int
    suggestion: str


async def get_current_weather(city: str) -> WeatherResult:
    # 课程示例先使用假数据；真实项目里调用天气 API。
    return WeatherResult(
        city=city,
        weather="晴",
        temperature_c=26,
        suggestion="适合外出，注意防晒",
    )
```

普通函数版的价值：

- 容易单元测试。
- 不依赖具体 Agent 框架。
- 权限、日志、异常处理更清晰。

## 5.9 Agents SDK Tool 示例

OpenAI Agents SDK 支持把 Python 函数注册为工具。下面示例展示核心思路，具体 API 以当前 SDK 文档为准。

```python
from agents import Agent, Runner, function_tool


@function_tool
async def get_current_weather(city: str) -> str:
    """查询指定城市的当前天气。只用于天气查询，不用于旅行规划。"""
    return f"{city} 当前天气晴，26 摄氏度，适合外出。"


assistant = Agent(
    name="tool_calling_assistant",
    instructions="你是企业助手。需要外部信息时使用工具，不要编造工具结果。",
    tools=[get_current_weather],
)


async def ask_with_tools(question: str) -> str:
    result = await Runner.run(assistant, question)
    return result.final_output
```

测试输入：

```text
上海今天适合出门吗？
```

期望行为：

- 模型选择天气工具。
- 应用执行天气函数。
- 模型基于工具结果回答。

## 5.10 示例：订单查询工具

### 返回对象

```python
from pydantic import BaseModel


class OrderStatusResult(BaseModel):
    order_id: str
    status: str
    logistics_company: str | None = None
    tracking_no: str | None = None
    latest_event: str | None = None
```

### 工具函数

```python
class PermissionDenied(Exception):
    pass


async def query_order_status(
    user_id: str,
    order_id: str,
) -> OrderStatusResult:
    if not await can_view_order(user_id=user_id, order_id=order_id):
        raise PermissionDenied("当前用户无权查看该订单")

    # 课程示例先使用假数据；真实项目里查询订单服务或数据库。
    if order_id != "O1001":
        raise ValueError("未找到该订单")

    return OrderStatusResult(
        order_id="O1001",
        status="已发货",
        logistics_company="顺丰",
        tracking_no="SF123456",
        latest_event="包裹已到达上海转运中心",
    )


async def can_view_order(user_id: str, order_id: str) -> bool:
    return user_id == "u_001" and order_id == "O1001"
```

### 重要提醒

权限检查不能交给模型判断。模型只能提出“想查订单”，后端必须根据真实用户身份和资源权限判断是否允许。

## 5.11 示例：知识库搜索工具

第 5 章先做一个假的知识库搜索工具，第 7 章再升级成真正的 RAG 检索。

```python
from pydantic import BaseModel, Field


class KnowledgeSnippet(BaseModel):
    title: str
    content: str
    source: str


class KnowledgeSearchResult(BaseModel):
    query: str
    snippets: list[KnowledgeSnippet] = Field(default_factory=list)


COURSE_KNOWLEDGE = [
    KnowledgeSnippet(
        title="RAG 基本流程",
        content="RAG 通常包括文档解析、切片、向量化、检索、上下文组装和生成答案。",
        source="chapter-01-agent-overview.md",
    ),
    KnowledgeSnippet(
        title="Tool Calling 边界",
        content="模型选择工具，应用程序执行工具，后端负责参数校验、权限校验和日志记录。",
        source="chapter-05-tool-calling.md",
    ),
]


async def search_course_knowledge(query: str, top_k: int = 5) -> KnowledgeSearchResult:
    hits = [
        item
        for item in COURSE_KNOWLEDGE
        if query.lower() in item.title.lower() or query.lower() in item.content.lower()
    ]
    return KnowledgeSearchResult(query=query, snippets=hits[:top_k])
```

工具描述可以写成：

```text
搜索 AI Agent 课程知识库。
当用户询问课程概念、章节内容、学习路线、实践任务时使用。
输入 query 应该是简洁的检索关键词或问题。
本工具返回相关资料片段，不保证一定包含答案。
```

## 5.12 多工具调用服务

当系统有多个工具时，建议统一管理工具元数据。

```python
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk_level: str
    handler: Callable[..., Awaitable[object]]


TOOLS = {
    "get_current_weather": ToolSpec(
        name="get_current_weather",
        description="查询指定城市当前天气。",
        risk_level="low",
        handler=get_current_weather,
    ),
    "query_order_status": ToolSpec(
        name="query_order_status",
        description="根据订单号查询订单状态。必须先校验用户权限。",
        risk_level="medium",
        handler=query_order_status,
    ),
    "search_course_knowledge": ToolSpec(
        name="search_course_knowledge",
        description="搜索 AI Agent 课程知识库。",
        risk_level="low",
        handler=search_course_knowledge,
    ),
}
```

统一管理的好处：

- 能记录工具清单。
- 能按风险等级加人工确认。
- 能统一做日志。
- 能逐步迁移到 MCP Server。

### 5.12.1 现代工具入口：内置工具、remote MCP 与 tool search

2026 年的 Agent 工具生态已经不只是一组本地 Python 函数。学习时可以按下面三层理解：

| 类型 | 例子 | 适合场景 | 注意事项 |
| --- | --- | --- | --- |
| 本地 function tool | 天气、订单、课程知识库搜索 | 学习、快速实验、工具边界还在变化 | 后端必须做参数和权限校验 |
| remote MCP tool | 企业知识库、CRM、工单、报表系统 | 工具需要被多个 Agent / 应用复用 | 需要可信 Server、授权、审计和限流 |
| built-in tool | Web search、file search、code interpreter、deep research 等 | 平台已提供的通用能力 | 仍要记录来源、成本和失败状态 |

当工具数量变多时，不要把所有工具一次性塞给模型。推荐做法：

1. 先用规则或路由模型筛选候选工具。
2. 再把少量相关工具暴露给当前 run。
3. 对高风险工具强制人工确认。
4. 对工具选择、参数和结果做 trace。
5. 对大量工具或 MCP Server 使用 tool search / tool registry 思路，按需发现和加载。

这能避免上下文膨胀、工具误选和调用成本失控。

注意：tool search、built-in tools、remote MCP 的具体可用性会受模型、账号、平台和 SDK 版本影响。课程里学习的是设计思想和工程边界，真实项目要以当前官方文档和运行环境为准。

## 5.13 参数校验

参数校验至少包括：

- 类型。
- 必填。
- 长度。
- 枚举值。
- 数字范围。
- 业务合法性。

示例：

```python
from pydantic import BaseModel, Field, field_validator


class SafeOrderRequest(BaseModel):
    order_id: str = Field(min_length=3, max_length=64)

    @field_validator("order_id")
    @classmethod
    def order_id_must_start_with_o(cls, value: str) -> str:
        if not value.startswith("O"):
            raise ValueError("订单号必须以 O 开头")
        return value
```

参数校验失败时，不要直接让模型换个参数重试无数次。应该把错误返回给模型，必要时追问用户。

## 5.14 权限校验

权限校验维度：

| 维度 | 例子 |
| --- | --- |
| 用户身份 | 当前登录用户是谁 |
| 租户 | 是否属于同一个企业或组织 |
| 资源权限 | 是否能查看该订单或文档 |
| 操作权限 | 是否允许查询、创建、删除 |
| 数据范围 | 是否只能看自己部门的数据 |

错误做法：

```text
只在 prompt 里写：“不要查询无权限订单。”
```

正确做法：

```python
if not await can_view_order(user_id, order_id):
    raise PermissionDenied("当前用户无权查看该订单")
```

Prompt 是提示，权限是后端规则。

## 5.15 工具调用日志

工具调用日志建议包含：

| 字段 | 说明 |
| --- | --- |
| tool_call_id | 工具调用唯一 ID |
| run_id | 所属 Agent run |
| user_id | 调用用户 |
| tool_name | 工具名 |
| arguments | 参数，敏感字段脱敏 |
| result_summary | 结果摘要 |
| status | success / failed / blocked |
| error_code | 错误码 |
| latency_ms | 耗时 |
| created_at | 调用时间 |

数据表示例：

```sql
create table tool_call_logs (
  id text primary key,
  run_id text not null,
  user_id text not null,
  tool_name text not null,
  arguments_json jsonb not null,
  result_summary text,
  status text not null,
  error_code text,
  latency_ms integer not null,
  created_at timestamptz not null default now()
);
```

日志注意：

- 不记录完整敏感信息。
- 参数要可追溯。
- 失败原因要可分析。
- 高风险工具要记录人工确认人。

## 5.16 危险工具与人工确认

高风险工具包括：

- 删除数据。
- 退款。
- 转账。
- 发邮件或群消息。
- 修改权限。
- 执行代码。
- 写入生产数据库。

人工确认流程：

```mermaid
flowchart TD
    A["模型提出工具调用"] --> B["后端识别为高风险"]
    B --> C["生成确认卡片"]
    C --> D["用户或管理员确认"]
    D --> E{是否通过}
    E -->|通过| F["执行工具"]
    E -->|拒绝| G["返回取消结果"]
```

确认内容：

- 工具名称。
- 操作对象。
- 关键参数。
- 影响范围。
- 风险说明。
- 确认人。
- 确认时间。

## 5.17 工具调用失败后的处理

常见失败：

- 参数缺失。
- 参数格式错误。
- 用户无权限。
- 资源不存在。
- 上游 API 超时。
- 上游服务返回错误。

失败结果要结构化：

```json
{
  "success": false,
  "error_code": "PERMISSION_DENIED",
  "message": "当前用户无权查看该订单",
  "retryable": false
}
```

模型收到失败结果后可以：

- 追问用户补充参数。
- 换一个工具。
- 告诉用户无法完成。
- 在可重试错误上尝试有限次数重试。

## 5.18 Tool Calling 和 Agent 的关系

Tool Calling 是 Agent 的基础，但不等于 Agent。

| 能力 | Tool Calling | Agent |
| --- | --- | --- |
| 选择工具 | 可以 | 可以 |
| 执行多轮任务 | 不一定 | 核心能力 |
| 记忆上下文 | 不一定 | 通常需要 |
| 规划步骤 | 不一定 | 通常需要 |
| 失败恢复 | 简单 | 更复杂 |

第 5 章只要求你掌握工具调用。第 6 章才会进入 Agent 执行循环。

## 5.19 Go 扩展：什么时候把工具抽到 Go

Go 不适合在本章替代 Python 主线，但适合把稳定工具服务独立出来。

适合 Go 化的情况：

- 工具逻辑已经稳定。
- 输入输出 schema 清晰。
- 需要高并发、低资源占用。
- 需要接入已有 Go 企业系统。
- 工具服务希望被多个 Agent 或应用复用。

不适合 Go 化的情况：

- 工具边界还在频繁变化。
- 你还没跑通 Python Agent。
- 只是为了“技术栈更酷”。
- Go 服务反而让调试链路变长。

推荐演进路径：

```text
Python 普通函数
  -> Python tool registry
  -> Python MCP Server
  -> Go MCP Server 或 Go 工具微服务
```

## 5.20 本章完整实践任务

### 任务 1：天气查询工具

要求：

- 工具名：`get_current_weather`。
- 参数：`city`。
- 返回：城市、天气、温度、建议。
- 使用假数据即可。

验收：

- 用户问天气时模型会调用工具。
- 用户没给城市时先追问城市。
- 工具返回结构化结果。

### 任务 2：订单查询工具

要求：

- 工具名：`query_order_status`。
- 参数：`order_id`。
- 必须传入当前 `user_id` 做权限校验。
- 返回订单状态，不返回手机号、地址、内部备注。

验收：

- 有权限用户能查到。
- 无权限用户被拒绝。
- 订单不存在时返回明确错误。

### 任务 3：课程知识库搜索工具

要求：

- 工具名：`search_course_knowledge`。
- 参数：`query`、`top_k`。
- 先使用内存假数据。
- 第 7 章再升级为向量检索。

验收：

- 能搜索 RAG、Tool Calling、MCP 等课程概念。
- 返回片段包含 `title`、`content`、`source`。

### 任务 4：多工具路由

要求：

- 同一个 Agent 同时拥有天气、订单、知识库工具。
- 模型根据用户问题选择工具。
- 工具执行前后都有日志。

测试问题：

```text
上海今天适合出门吗？
```

```text
我的订单 O1001 到哪里了？
```

```text
课程里 RAG 和 Tool Calling 有什么区别？
```

验收：

- 每个问题选择正确工具。
- 工具参数正确。
- 最终回答基于工具结果。

### 任务 5：工具调用日志

要求：

- 每次工具调用记录 tool_call_id。
- 记录工具名、参数摘要、状态、耗时。
- 失败时记录错误码。

验收：

- 能回放一次完整工具调用轨迹。
- 日志不包含敏感信息明文。

### 任务 6：危险工具安全清单

写一份清单：

```markdown
# 危险工具安全清单

## 工具名称

## 风险等级

## 是否允许自动执行

## 是否需要人工确认

## 参数校验规则

## 权限校验规则

## 日志字段

## 失败回滚方式
```

至少列出：

- 删除文档。
- 发送邮件。
- 创建退款。
- 修改权限。

## 5.21 本章自测题

### 概念题

1. Tool Calling 的完整流程是什么？
2. 为什么模型不能直接执行工具？
3. 好工具的设计标准有哪些？
4. 参数校验和权限校验分别解决什么问题？
5. 哪些工具必须人工确认？
6. Tool Calling 和 Agent 有什么区别？

### 判断题

1. 工具描述越短越好，不需要说明边界。  
2. 只读查询工具通常比写入工具安全。  
3. 权限校验可以只写在 prompt 里。  
4. 工具返回值应该避免包含敏感信息。  
5. Tool Calling 就等于完整 Agent。  

参考答案：

1. 错。  
2. 对。  
3. 错。  
4. 对。  
5. 错。  

## 5.22 本章完成标准

完成本章后，你应该能做到：

- 能解释 Tool Calling 的执行流程。
- 能设计清晰的工具名称、描述、参数和返回值。
- 能用 Python 实现至少 3 个工具。
- 能用 Pydantic 校验工具参数。
- 能做用户权限校验。
- 能记录工具调用日志。
- 能识别危险工具并设计人工确认。
- 能说清楚哪些工具未来适合抽到 Go 或 MCP Server。

## 5.23 本章学习资料

### 必读资料

- [OpenAI Agents SDK - Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Responses API - Tools](https://developers.openai.com/api/docs/guides/tools)
- [OpenAI Responses API - Remote MCP](https://developers.openai.com/api/docs/guides/tools-connectors-mcp)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/getting-started/intro)

### 扩展资料

- [MCP SDKs](https://modelcontextprotocol.io/docs/sdk)
- [OpenAI Agents SDK - Guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

## 5.24 本章复盘模板

```markdown
# 第 5 章复盘

## 我实现了哪些工具

## 模型什么时候会选择正确工具

## 模型什么时候会选错工具

## 我做了哪些参数校验

## 我做了哪些权限控制

## 我记录了哪些工具调用日志

## 哪些工具我认为必须人工确认

## 哪些工具未来适合抽到 Go / MCP Server

## 进入单 Agent Runtime 前我还不清楚的问题
```

Tool Calling 是让 AI 应用从“会说”走向“会做”的第一步。越早建立工具边界、权限和日志意识，后面的 Agent 才越不容易失控。
