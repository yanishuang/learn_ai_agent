# 第 2 章：大模型应用基础

更新时间：2026-07-10
建议学习时间：3-5 天  
适合阶段：已经理解 AI Agent 全景，准备开始动手调用大模型  
本章产出：一个 FastAPI 大模型问答 API、一个结构化输出接口、一个 SSE 流式响应接口、一份调用日志与错误处理清单

## 2.1 本章学习目标

学完本章后，你应该能做到：

1. 解释大模型应用的一次完整调用链路。
2. 区分 system、user、assistant、tool 消息的职责。
3. 理解 temperature、top_p、max tokens、上下文窗口、流式输出的作用。
4. 使用 Python + OpenAI SDK / Responses API 完成一次基础模型调用。
5. 使用 Pydantic 校验模型结构化输出。
6. 使用 FastAPI + SSE 把模型输出实时推送给前端。
7. 为模型调用增加基础错误处理、超时、日志和成本意识。
8. 知道哪些参数和输出不能盲目信任。

本章不是 Agent，也不是 RAG。它只解决一个基础问题：如何把大模型稳定接入到后端应用里。

## 2.2 本章先学什么

建议按下面顺序学习：

```text
大模型调用链路
  -> 消息结构
  -> 模型参数
  -> Python OpenAI SDK
  -> FastAPI 普通问答 API
  -> Pydantic 结构化输出
  -> SSE 流式响应
  -> 错误处理与日志
```

不要一开始就做工具调用或 RAG。先把最基础的模型调用做稳定，后面章节才有地基。

## 2.3 大模型应用的一次完整调用链路

一个最小的大模型应用调用链路如下：

```mermaid
flowchart LR
    User["用户输入"] --> API["FastAPI 接口"]
    API --> Service["AI Service"]
    Service --> Prompt["组装消息 / Prompt"]
    Prompt --> Model["模型服务"]
    Model --> Parse["解析响应"]
    Parse --> Validate["Pydantic 校验"]
    Validate --> Log["记录日志"]
    Log --> Response["返回前端"]
```

真实项目里还会增加：

- 用户身份识别。
- 请求参数校验。
- 敏感信息脱敏。
- 模型路由。
- 超时控制。
- 重试策略。
- token 与费用统计。
- 审计日志。

## 2.4 消息角色：System、User、Assistant、Tool

大模型对话通常不是只传一段字符串，而是传一组消息。不同角色有不同职责。

| 角色 | 作用 | 示例 |
| --- | --- | --- |
| system | 定义模型身份、任务边界、规则和输出约束 | 你是企业知识库助手，只能基于资料回答 |
| user | 用户提出的问题或任务 | 请解释什么是 MCP |
| assistant | 模型之前的回答 | MCP 是一种工具和上下文接入协议 |
| tool | 工具调用结果 | 搜索知识库返回了 5 条结果 |

本章先使用 system + user 完成最小调用。Tool 消息会在第 5 章详细学习。

## 2.5 模型参数：先理解影响结果的旋钮

常见参数如下：

| 参数 | 作用 | 建议 |
| --- | --- | --- |
| model | 选择使用哪个模型 | 根据任务复杂度、成本、速度选择 |
| temperature | 控制随机性 | 问答/结构化任务偏低，创意任务可适当提高 |
| top_p | 控制采样范围 | 通常不要和 temperature 同时大幅调整 |
| max_output_tokens | 限制最大输出长度 | 根据输出需求设置，避免无限生成 |
| stream | 是否流式返回 | 长回答、聊天体验、任务进度建议开启 |
| response schema | 输出格式约束 | 结构化输出任务应使用，并由后端校验 |

模型名称、参数名和可用能力会随平台演进变化。实际项目要以当前账号和官方文档为准，不要把课程里的模型名写死成不可配置常量。

## 2.6 Python 项目骨架建议

本章建议先用 FastAPI 做一个最小服务。目录可以这样设计：

```text
agent-course/
  pyproject.toml
  .env.example
  app/
    main.py
    settings.py
    ai/
      client.py
      schemas.py
      service.py
    api/
      routes.py
    observability/
      logging.py
```

### 依赖建议

```bash
uv init agent-course
cd agent-course
uv add fastapi uvicorn openai pydantic pydantic-settings python-dotenv
```

不用 `uv` 也可以使用 `pip` 或 Poetry。关键不是工具，而是把依赖、配置、代码和测试分清楚。

### 配置原则

不要把 API Key 写进代码或提交到仓库。

`.env.example`：

```text
# 只有显式设置为 1 才允许构造 Live adapter。
AGENT_COURSE_LIVE_TESTS=
OPENAI_API_KEY=
OPENAI_MODEL=
REQUEST_TIMEOUT_SECONDS=60
```

`app/settings.py`：

```python
import os
from dataclasses import dataclass


class LiveConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveSettings:
    openai_api_key: str
    openai_model: str
    request_timeout_seconds: int


def load_live_settings() -> LiveSettings:
    missing: list[str] = []
    if os.getenv("AGENT_COURSE_LIVE_TESTS") != "1":
        missing.append("AGENT_COURSE_LIVE_TESTS=1")

    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "")
    if not api_key.strip():
        missing.append("OPENAI_API_KEY must be non-empty")
    if not model.strip():
        missing.append("OPENAI_MODEL must be non-empty")
    if missing:
        raise LiveConfigurationError(
            "live adapter is disabled; required: " + ", ".join(missing)
        )

    return LiveSettings(
        openai_api_key=api_key.strip(),
        openai_model=model.strip(),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
    )
```

不要在默认应用组合的模块导入时调用 `load_live_settings()`。下面的
`app.ai.client` 是 Live-only adapter，默认 Fake 组合不得导入它。默认练习和自动测试
使用 `FakeModelGateway`，应当离线、无密钥、无网络且可重复；只有付费的 Live 对比
实验才加载 Live adapter。Live 模式没有默认模型，`OPENAI_MODEL` 必须由操作者明确
选择。

## 2.7 实践一：普通问答 API

### 目标

实现一个接口：

```text
POST /api/ai/chat
```

输入：

```json
{
  "message": "请解释什么是 AI Agent"
}
```

输出：

```json
{
  "answer": "AI Agent 是..."
}
```

### DTO 设计

`app/ai/schemas.py`：

```python
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
```

### OpenAI Client

`app/ai/client.py`：

```python
from openai import AsyncOpenAI

from app.settings import load_live_settings


settings = load_live_settings()
client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    timeout=settings.request_timeout_seconds,
)
```

### Service 示例

`app/ai/service.py`：

```python
from app.ai.client import client, settings


SYSTEM_PROMPT = """
你是 AI Agent 课程助教。
请用准确、清晰、适合初学者的方式回答。
如果你不确定，请明确说“不确定”，不要编造。
回答中优先使用课程中的术语：RAG、Workflow、Agent、MCP。
""".strip()


async def chat(message: str) -> str:
    response = await client.responses.create(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
    )
    return response.output_text
```

### Route 示例

`app/api/routes.py`：

```python
from fastapi import APIRouter

from app.ai.schemas import ChatRequest, ChatResponse
from app.ai.service import chat

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    answer = await chat(request.message)
    return ChatResponse(answer=answer)
```

`app/main.py`：

```python
from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="AI Agent Course")
app.include_router(router)
```

### 验收方式

启动服务：

```bash
uvicorn app.main:app --reload
```

调用接口：

```bash
curl -X POST http://127.0.0.1:8000/api/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"请用三句话解释什么是 RAG"}'
```

能得到中文回答，即完成本章第一个目标。

## 2.8 实践二：结构化输出

### 为什么需要结构化输出

企业应用不能只拿一段自然语言。很多场景需要：

- 前端渲染字段。
- 后端保存结果。
- 后续流程判断。
- 自动评估回答质量。

所以模型输出必须经过后端校验。

### 输出对象设计

在 `app/ai/schemas.py` 追加：

```python
from typing import Literal


class Citation(BaseModel):
    source: str
    quote: str


class LessonAnswer(BaseModel):
    answer: str
    confidence: Literal["high", "medium", "low"]
    citations: list[Citation] = Field(default_factory=list)
    missing_info: str | None = None
```

### Service 示例

Live adapter 使用 Responses API 的原生结构化输出，让 SDK 按 Pydantic 类型解析；
应用仍然要处理拒绝、缺失输出和上游错误。第 7 章进入 RAG 后，`citations`
必须来自真实检索结果，而不是模型自由编造。

```python
from app.ai.client import client, settings
from app.ai.schemas import LessonAnswer


SYSTEM_PROMPT = """
你是 AI Agent 课程助教。
请准确回答；没有检索资料时 citations 必须为空数组，不要编造来源。
""".strip()


async def structured_chat(message: str) -> LessonAnswer:
    response = await client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        text_format=LessonAnswer,
    )
    if response.output_parsed is None:
        raise ValueError("Responses API returned no parsed output")
    return response.output_parsed
```

参考实现中的 `OpenAIResponsesGateway.parse_structured()` 使用同一合同：模型来自
显式的 `OPENAI_MODEL`，调用 `AsyncOpenAI.responses.parse()`，并在
`output_parsed` 缺失时失败。构造 gateway 仍受 `AGENT_COURSE_LIVE_TESTS=1`、
非空 Key 和非空模型三重门禁约束。

### 兼容说明：Prompt-only JSON

只有旧模型或兼容服务不支持原生结构化输出时，才在 prompt 中要求“只返回 JSON”，
再对 `response.output_text` 执行 `json.loads()` 和
`LessonAnswer.model_validate()`。这是兼容路径，不是本章主线；它必须捕获
`JSONDecodeError` / `ValidationError`，不得把解析失败的文本传给业务流程。

### Route 示例

```python
from app.ai.schemas import ChatRequest, ChatResponse, LessonAnswer
from app.ai.service import chat, structured_chat


@router.post("/structured", response_model=LessonAnswer)
async def structured_endpoint(request: ChatRequest) -> LessonAnswer:
    return await structured_chat(request.message)
```

### 验收标准

输入：

```json
{
  "message": "我刚开始学习 AI Agent，请解释 Tool Calling 是什么"
}
```

输出应该符合：

```json
{
  "answer": "...",
  "confidence": "high",
  "citations": [],
  "missing_info": null
}
```

如果结构化结果缺失或校验失败，后端必须报错或按受控策略重试，不能把脏数据继续传给
业务流程。

## 2.9 实践三：SSE 流式响应

### 为什么需要流式输出

长回答、研究报告、RAG 问答、Agent 执行轨迹都不适合让用户等到最后才看到结果。SSE 可以让前端逐步收到：

- 模型 token。
- 检索进度。
- 工具调用状态。
- Agent 执行步骤。

本章先实现最简单的模型 token 流。

### Service 示例

```python
import asyncio
import json
from collections.abc import AsyncIterator
from collections.abc import Awaitable, Callable

from app.ai.client import client, settings


def sse_event(event: str, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_chat(
    message: str,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    try:
        async with client.responses.stream(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
        ) as stream:
            async for event in stream:
                if await is_disconnected():
                    return
                if event.type == "response.output_text.delta":
                    yield sse_event("delta", {"text": event.delta})
            yield sse_event("done", {"status": "completed"})
    except asyncio.CancelledError:
        # Starlette 取消响应生成器时继续传播取消；async with 会关闭上游流。
        raise
```

### Route 示例

```python
import asyncio

from fastapi import Request
from fastapi.responses import StreamingResponse


@router.post("/stream")
async def stream_endpoint(
    payload: ChatRequest,
    request: Request,
) -> StreamingResponse:
    async def event_source():
        try:
            async for event in stream_chat(payload.message, request.is_disconnected):
                yield event
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

SSE 的每个 `data:` 都是合法 JSON，文本中的换行符会被 JSON 转义，不会破坏
事件边界。`request.is_disconnected()` 处理已可观察到的断连，
`CancelledError` 处理 ASGI 服务器主动取消；两条路径都会离开 `async with` 并关闭
上游 Responses 流。不要吞掉取消异常，也不要在客户端离开后继续生成和计费。

### 前端接收方式

浏览器 `EventSource` 默认使用 GET。如果你希望使用 POST，可以用 `fetch` 读取流，或把会话 ID 放到 GET 流式接口里。课程项目里建议：

1. `POST /api/ai/tasks` 创建任务。
2. `GET /api/ai/tasks/{task_id}/events` 订阅 SSE。

这样更容易做鉴权、恢复和任务记录。

## 2.10 错误处理

常见错误：

| 错误 | 处理方式 |
| --- | --- |
| API Key 缺失 | 启动时失败，提示配置环境变量 |
| 请求超时 | 返回可重试错误，记录超时阶段 |
| 模型限流 | 仅对可安全重放的请求做有上限、带抖动的退避；记录重试次数 |
| 输出格式错误 | 结构化接口必须重试或报错 |
| 内容过长 | 截断输入、摘要历史、提示用户缩小范围 |
| 上游不可用 | 返回友好错误，不暴露内部堆栈 |

错误响应建议：

```json
{
  "code": "MODEL_TIMEOUT",
  "message": "模型服务响应超时，请稍后重试",
  "requestId": "req_20260616_001"
}
```

## 2.11 日志、成本与性能意识

从第一天就记录调用日志：

| 字段 | 说明 |
| --- | --- |
| request_id | 每次请求唯一 ID |
| user_id | 用户 ID，匿名场景也要有会话 ID |
| model | 使用的模型 |
| prompt_version | Prompt 版本 |
| input_chars | 输入字符数 |
| output_chars | 输出字符数 |
| latency_ms | 总耗时 |
| status | success / failed |
| error_code | 失败原因 |

后续做 RAG 和 Agent 时，还要记录：

- 检索到哪些文档。
- 调用了哪些工具。
- 工具参数摘要是什么（敏感字段脱敏，不保存原始参数）。
- 每轮 Agent 的停止原因。
- token、费用和耗时。

## 2.12 安全注意事项

### API Key 安全

- 不要提交 `.env`。
- 不要把 key 输出到日志。
- 不要在前端直接调用模型 API。
- 为不同环境使用不同 key。

### 输入安全

- 限制输入长度。
- 对上传文件做类型和大小限制。
- 不把用户输入拼进 SQL。
- 不把用户输入当成系统规则。

### 输出安全

- 模型输出必须被视为不可信。
- 结构化输出要校验 schema。
- 引用来源必须来自后端检索结果。
- 高风险动作不能只靠模型一句话触发。

## 2.13 本章完整实践任务

### 任务 1：基础问答接口

要求：

- 使用 FastAPI。
- 默认注入 `FakeModelGateway`，离线且不要求 API Key。
- `POST /api/ai/chat` 能返回中文回答。
- 可选 Live adapter 使用 OpenAI SDK，并只从环境变量读取 Key 和显式模型名。

验收：

- 能回答“什么是 AI Agent”。
- 默认测试不导入可选 Live 包，也不访问网络。
- 缺少精确 Live 开关、非空 Key 或非空 `OPENAI_MODEL` 时，Live adapter 拒绝构造。
- 控制台不打印 API Key。
- 空字符串输入会被 Pydantic 拦截。

### 任务 2：结构化输出接口

要求：

- `POST /api/ai/structured` 返回 `answer`、`confidence`、`citations`、`missing_info`。
- Live 路径使用 `responses.parse(..., text_format=LessonAnswer)`。
- 模型参数来自显式 `OPENAI_MODEL`，没有硬编码默认值。
- Prompt-only JSON 只作为兼容路径，并继续使用 Pydantic 校验。
- 非法输出不能静默通过。

验收：

- `confidence` 只能是 `high`、`medium`、`low`。
- `citations` 是数组。
- 出错时有明确错误信息。

### 任务 3：流式输出接口

要求：

- `POST /api/ai/stream` 使用 SSE 返回。
- 前端或 `curl -N` 能看到分片输出。
- 每个事件的 `data:` 是 JSON，最后发送 `done` 事件。

验收：

- 长回答不需要等到全部生成完成。
- 客户端断开或任务取消时，上游流被关闭，服务端不会继续无限执行。

### 任务 4：调用日志

要求：

- 每次请求生成 `request_id`。
- 记录模型、耗时、状态。
- 失败时记录错误类型。

验收：

- 能根据 `request_id` 找到一次请求的完整日志。
- 日志里没有 API Key 和敏感输入全文。

## 2.14 本章自测题

### 概念题

1. system、user、assistant、tool 消息各自负责什么？
2. 为什么结构化输出还需要后端校验？
3. SSE 和一次性响应分别适合什么场景？
4. 为什么模型输出不能直接写入数据库或触发高风险动作？

### 判断题

1. API Key 可以临时写在代码里，只要不截图就行。  
2. 原生结构化输出成功后，就不需要检查 `output_parsed`。
3. 模型调用日志应该记录 request_id、模型、耗时和失败原因。  
4. 流式输出可以改善长回答的用户体验。  

参考答案：

1. 错。  
2. 错。  
3. 对。  
4. 对。  

## 2.15 本章完成标准

完成本章后，你应该能做到：

- 能启动一个 FastAPI AI 服务。
- 能完成普通问答调用。
- 能用 Pydantic 校验结构化输出。
- 能实现一个 SSE 流式响应接口。
- 能说明调用日志应该记录哪些字段。
- 能说清楚 API Key、输入、输出的安全边界。

## 2.16 本章学习资料

### 必读资料

- [OpenAI API Documentation](https://developers.openai.com/api/docs)
- [OpenAI SDKs](https://developers.openai.com/api/docs/libraries)
- [OpenAI Responses API - Tools](https://developers.openai.com/api/docs/guides/tools)
- [OpenAI Background Mode](https://developers.openai.com/api/docs/guides/background)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

### 扩展资料

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [uv Documentation](https://docs.astral.sh/uv/)

## 2.17 本章复盘模板

```markdown
# 第 2 章复盘

## 我完成的接口

## 我对 system / user / assistant / tool 消息的理解

## 我对结构化输出的理解

## 我在流式输出中遇到的问题

## 我记录了哪些调用日志

## 进入第 3 章前仍然不清楚的问题
```
