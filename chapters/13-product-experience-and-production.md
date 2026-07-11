# 第 13 章：产品体验、企业集成与生产治理

更新时间：2026-07-11
建议学习时间：4-6 天
本章产出：一套任务 UX 状态机与事件合同、一个进度客户端原型、一张企业 IM 边界图，以及一份有验证证据的生产就绪评审。

## 本章定位

Agent 产品不能只给用户一个旋转图标。用户需要知道任务是否已入队、正在做什么、为何等待、哪些工具被调用、依据来自哪里，以及失败后能否安全地取消或重试。运营团队还需要知道谁以什么身份执行了什么动作、数据保存多久、事故发生时如何止损。

本章把前面章节的 Agent、RAG、Workflow、MCP、评估与 trace 组合成一个可理解、可控制、可运营的产品表面。Apps SDK 和 MCP Apps 只作为可选交互表面；它们不能替代服务端身份、业务授权、持久化状态、审批与审计。

### 当前参考实现与生产目标

必须先准确区分两层：

| 层 | 当前真实行为 | 不得声称已有 |
| --- | --- | --- |
| 参考 API | `POST /v1/agent/runs` 同步执行；`GET /v1/agent/runs/{run_id}` 查询；`GET /v1/agent/runs/{run_id}/events` 返回已保存事件列表 | 后台队列、SSE、WebSocket、取消、重试、审批 API |
| Run 状态 | `running`、`completed`、`failed` | `queued`、`waiting`、`cancelled` 的统一 API 状态 |
| Run 事件 | `run.created`、`run.started`、`run.completed` 或 `run.failed`，带单调递增 `sequence` | token 流、工具活动、引用、审批事件与断线续传 |
| 保存位置 | `CourseApplication` 进程内字典；session 与 trace 也为 in-memory 教学实现 | 跨进程持久化、worker 恢复、事件总线、多副本一致性 |
| Workflow | `ResearchWorkflow` 独立支持等待审批、运行、完成、取消和超时，但同样为进程内教学实现 | 已暴露在 FastAPI、数据库 durability、分布式 lease |

参考实现适合离线合同测试，不是生产任务平台。本章其余设计以它的 `RunContext`、`RunLimits`、`AgentResult`、Workflow 审批 hash 和事件顺序为起点，但新增能力必须由学员实现并测试。

## 前置知识

- 完成第 6-10 章，能读取 `RunContext`、`RunLimits`、`AgentResult`、RAG citation、Workflow 状态和 MCP 结构化结果。
- 理解 FastAPI request dependency、SSE 或 WebSocket 的一种传输方式。
- 能区分认证身份、workload identity、业务授权、模型输入和审计记录。
- 能运行参考实现的离线测试，不依赖 API key 或网络。

## 学习目标

完成本章后，你应该能够：

1. 定义 `queued`、`running`、`waiting`、`completed`、`failed`、`cancelled` 的权威 UX 状态机。
2. 设计任务创建、幂等提交、SSE/WebSocket 进度、断线恢复、取消和受限重试。
3. 以结构化方式展示引用、工具活动、审批内容、失败原因和下一步动作。
4. 说明企业 IM adapter 与核心 Agent 服务的身份、权限和数据边界。
5. 设计部署、secrets、workload identity、限流、配额、租户隔离和保留策略。
6. 建立 incident handling、CI release gates 与生产就绪评审证据。
7. 明确区分当前 in-memory 参考行为和生产设计，避免用演示通过替代生产证明。

## 核心知识

### 13.1 任务创建合同

生产任务创建建议接受业务输入、客户端生成的 `Idempotency-Key` 和可选 `session_id`，但不接受 `tenant_id`、`user_id`、permissions、审批状态或无限预算。服务端从可信身份提供者构造 `RunContext`，再按产品策略收紧 `RunLimits`。

```http
POST /v1/tasks
Idempotency-Key: 01J...
Authorization: Bearer ...
Content-Type: application/json

{"question":"差旅住宿标准是什么？","session_id":"s-42"}
```

建议返回 `202 Accepted`、`task_id`、当前 `status`、状态查询 URL 和事件 URL。相同租户、用户、operation 与 idempotency key 的相同 payload 返回原任务；同 key 不同 payload 返回 `409`。服务端保存 request hash、policy/budget version 和创建者身份，不能让前端伪造。

当前 `POST /v1/agent/runs` 返回 `201` 且在响应前完成 Fake Agent；它可用来验证身份注入、预算上限和事件合同，但不是上述异步 `202` 设计的实现。

### 13.2 明确的 UX 状态机

状态属于服务端权威记录，UI 只是投影。统一状态机如下：

| 状态 | 用户看到什么 | 允许的服务端转换 | 可用动作 |
| --- | --- | --- | --- |
| `queued` | 已接收、队列位置或预计开始时间 | `running`、`cancelled`、`failed` | 取消、查看详情 |
| `running` | 当前步骤、工具活动、耗时和预算摘要 | `waiting`、`completed`、`failed`、`cancelled` | 请求取消、查看活动 |
| `waiting` | 等待原因、审批 payload、审批者、到期时间 | `running`、`cancelled`、`failed` | 有权限者批准/拒绝；创建者取消 |
| `completed` | 最终答案、引用、工具结果摘要 | 终态 | 查看证据、基于新 task 重跑 |
| `failed` | 稳定错误码、可重试性、已完成副作用 | 终态 | 满足策略时创建 retry task |
| `cancelled` | 取消者、取消时间、已完成副作用 | 终态 | 基于新 task 重跑 |

合法转换可写成：

```text
queued -> running | cancelled | failed
running -> waiting | completed | failed | cancelled
waiting -> running | cancelled | failed
completed | failed | cancelled -> terminal
```

取消是请求加最终确认，不是前端本地改状态。平台先记录 `cancel_requested`，传播到 worker、Workflow 和下游调用，在安全边界停止后写 `run.cancelled`。若不可中断副作用已经提交，必须显示其结果，不能假装回滚。

`waiting` 是产品统一投影；当前 `ResearchWorkflow` 的具体值是 `waiting_for_approval`。Adapter 应显式映射，不能静默改写持久化 Workflow enum。

### 13.3 事件合同与 SSE/WebSocket

事件至少包含 `event_id`、run 内单调 `sequence`、`type`、`occurred_at`、`run_id`、`request_id`、版本化 `data`。事件类型建议限定为：

- 生命周期：`run.queued`、`run.started`、`run.waiting`、`run.completed`、`run.failed`、`run.cancelled`；
- Agent 活动：`agent.step.started`、`agent.step.completed`；
- 工具活动：`tool.call.started`、`tool.call.completed`、`tool.call.failed`；
- RAG：`retrieval.completed`、`citation.added`；
- 审批：`approval.requested`、`approval.resolved`；
- 控制：`cancel.requested`、`retry.created`、heartbeat。

SSE 适合服务端单向进度：客户端发送 `Last-Event-ID`，服务端从持久事件日志补发，定期 heartbeat，终态后关闭。WebSocket 适合需要双向低延迟控制的界面，但取消和审批仍应走鉴权命令端点，不能把任意 socket message 当权威动作。两者都要处理反向代理 idle timeout、慢消费者、重连、重复事件和 sequence gap。

UI 按 `(run_id, sequence)` 幂等应用事件；发现 gap 时先重新查询 run snapshot，再从最后已确认 sequence 续传。token delta 可以短期展示，但最终答案和引用以服务端完成快照为准。

### 13.4 引用、工具活动与审批体验

引用至少展示 title、可定位 quote、document/chunk ID 和版本。点击引用前，服务端再次按当前 `RunContext` 授权；引用 URL 不能成为永久公开下载链接。无足够证据时展示明确拒答，而不是空 citation 或模型自报置信度。

工具活动面向用户展示工具显示名、目的、状态、耗时、风险级别和脱敏结果摘要。默认隐藏 secrets、原始 token、内部 prompt 和敏感参数。审计系统可保存 hash、schema version 和策略决定，但也必须遵守最小化原则。

审批卡片必须显示即将执行的确定 payload、目标资源、风险、预计影响、到期时间和批准者范围。批准提交包含 payload hash、workflow/run ID、state version 和 idempotency key。服务端重新校验身份、权限、状态、过期时间和 hash；payload 改变必须重新审批。拒绝、撤销或过期都不能被模型文本覆盖。

### 13.5 取消、重试与失败语言

将失败分为：

| 类别 | 默认是否自动重试 | 要求 |
| --- | --- | --- |
| 网络中断、`429`、临时 `5xx` | 在 budget 内可以 | 指数退避+jitter、总 deadline、attempt 事件 |
| 读取型工具超时 | 仅幂等且无副作用时 | 同一 operation id、下游幂等保证 |
| 参数/schema 错误 | 否 | 修复输入或代码 |
| permission/policy denied | 否 | 不通过重试绕过授权 |
| 审批 hash 不匹配或已过期 | 否 | 重新生成审批请求 |
| 未知副作用结果 | 否，先 reconciliation | 查询下游 operation 状态，避免重复执行 |

Retry 创建新 run，并通过 `retry_of` 指向旧 run；旧 run 保持终态和审计证据。UI 使用稳定错误码与可执行建议，不泄露堆栈、凭据或跨租户对象是否存在。

### 13.6 企业 IM 入口边界

Slack、Teams、企业微信或邮件 adapter 只负责：验证平台签名、把外部 user/workspace 映射到内部身份、规范化消息/附件、提交任务、渲染状态与审批链接。它不持有 Agent loop、不自行拼接权限、不直接访问向量库，也不在 webhook 进程执行高风险工具。

核心服务负责 `RunContext`、租户/用户授权、budgets、RAG、工具、Workflow、审批和审计。身份映射必须有生命周期：加入、离职、workspace 迁移、撤销和重新授权。群聊内容不能默认授权每个成员读取发起者的私有资料；bot token 也不能等同于终端用户 delegation。

交互卡片中的按钮只提交 command。服务端再次鉴权并返回最新状态，防止旧卡片重放。Apps SDK/MCP Apps 如被采用，也遵循同一原则，并按[生态成熟度矩阵](../docs/ecosystem-maturity.md)记录精确 artifact、成熟度、验证日期和 fallback。

### 13.7 部署、secrets 与 workload identity

生产部署至少分离 API、worker、持久状态库、事件通道和受控 egress。worker 使用 lease/heartbeat 防止任务永久占用；副作用用 outbox 或幂等 operation 记录。滚动部署必须让旧版本完成或安全 checkpoint，并固定每个 run 的 workflow、prompt、tool schema 和 model configuration version。

secrets 进入专用 secret manager，不进入仓库、镜像、prompt、trace 或客户端。实施短期凭据、轮换、审计和紧急吊销。服务间优先使用 workload identity 和短期 token，校验 issuer、audience、subject 与 scope；不要把一把长期 API key 共享给所有租户和环境。

### 13.8 限流、配额与成本预算

限流至少按 tenant、user、API route、tool 和 provider 设置；队列还要限制并发与 backlog。配额按日/月 token、模型费用、检索量、存储、工具调用和高风险操作计量。服务端在入队前预检，在执行中累计，在边界处停止并返回 typed reason。

防止 noisy neighbor：每租户独立 concurrency、队列权重和最大单 run budget；全局熔断保护下游。成本告警不能只看模型 token，还要覆盖 embedding、rerank、外部搜索、数据库、网络和人工审批等待成本。

### 13.9 租户隔离与数据保留

`tenant_id` 只来自可信身份。API 查询、事件、session、cache、retrieval、tool、Workflow、object storage 和 trace 每层都执行租户约束。当前参考 API 还按 user 隐藏 run，并以 `404` 防止对象枚举；生产系统应保持等价的 fail-closed 行为，并用数据库约束/RLS 与隔离测试提供第二道防线。

保留矩阵按数据类型定义目的、字段、地域、TTL、legal hold、删除方式和备份过期：原始文档、chunk/embedding、prompt/answer、tool 参数/结果、事件、trace、eval 与审批证据不应共享一个无限 TTL。删除请求要传播到索引、cache、派生数据和备份周期；审计记录在法规允许范围内保留最小必要字段或不可逆 hash。

### 13.10 Incident handling

预先定义触发器：跨租户暴露、secret 泄露、异常工具副作用、prompt injection 扩散、成本突增、模型/provider 故障、错误发布和审计缺口。runbook 至少包含：

1. 停用特定 tool/model/tenant/connector 的 kill switch；
2. 暂停队列与审批，吊销 token，隔离受影响版本；
3. 保存脱敏证据并确定受影响 run、用户、文档和副作用；
4. 通知责任人、合规与客户，按时限升级；
5. 修复、回放只读事件、受控恢复和加强监控；
6. 形成无责复盘、修复 owner、截止日期和回归 case。

不要在事故中批量自动重跑未知副作用任务。

### 13.11 CI release gates 与生产评审

每次发布至少执行：课程/文档 validator、单元与合同测试、Fake Model 离线回归、RAG 权限隔离、Workflow 幂等/审批/cancel、MCP schema/timeout、eval 阈值、secret/SCA 扫描、迁移检查和回滚演练。Live eval 是显式启用的补充，记录模型、配置、数据集版本、费用和方差，不能替代确定性回归。

生产评审必须给出证据，而不是勾选“已考虑”：架构与数据流、威胁模型、身份/权限矩阵、SLO/容量、成本上限、保留表、incident runbook、发布/回滚记录、eval 报告、已知风险和 owner。高风险工具没有权威审批与 reconciliation 时不得上线。

## 教师演示

1. 运行当前 API focused tests，指出同步 `201`、三个实际状态和 polled event list。
2. 在白板上把它扩展为六状态 UX 状态机，演示 SSE 重连、sequence gap 和 snapshot 恢复。
3. 展示一次 `running -> waiting -> running -> completed` 审批流程，再修改 payload 证明旧 hash 失效。
4. 注入工具超时与未知副作用，比较安全 retry 和必须 reconciliation 的失败。
5. 用两个可信 context 查询同一 run，展示服务端 tenant/user 隔离。
6. 走一遍 connector token 泄露 runbook 与 release rollback evidence。

## 学员实验

Task 11 可将实验落到 `labs/chapter-13/`；该目录不在当前提交中。当前先提交设计与测试：

1. 写六状态转换表和每条非法转换的 contract test。
2. 为事件定义 versioned schema，测试 sequence、终态、重复、gap 与 `Last-Event-ID`。
3. 实现一个 SSE 或 WebSocket 客户端原型，显示状态、citation、tool activity 和 approval。
4. 测试取消传播、retry classification、unknown side effect reconciliation 和 payload hash。
5. 画企业 IM adapter、identity provider、core service、worker、data/tool boundary 图。
6. 提交生产评审包，并为每个控制附命令、测试、截图或审计样例。

## 失败注入与排错

| 注入 | 预期结果 | 首查位置 |
| --- | --- | --- |
| 重复 `Idempotency-Key` + 不同 payload | `409`，不创建第二个任务 | request hash store |
| SSE 断线后重连 | 从最后 sequence 补发或 snapshot 恢复 | event log/cursor |
| 慢消费者 | bounded buffer、断开并允许重连 | stream adapter |
| cancel 与 completed 竞争 | 只产生一个合法终态 | transactional transition |
| approval payload 改变 | hash mismatch，重新审批 | state version/hash |
| permission denied 被标记 retryable | 阻止重试并报警 | retry classifier |
| 跨租户 run/event 查询 | `404`/拒绝且无数据泄露 | trusted context/query |
| connector 旧卡片重放 | 重新鉴权并拒绝过期 command | command endpoint |
| worker 在副作用后崩溃 | reconciliation，不盲目重放 | operation/outbox |
| secret 出现在 trace | gate 失败、轮换并启动 incident | redaction pipeline |

排错顺序：可信身份、权威 run snapshot、事件 sequence、worker lease、Workflow/checkpoint、tool operation、stream adapter、UI projection。不要先改 prompt 或让 UI 猜状态。

## 自动验证

先用当前真实合同建立基线：

```bash
cd reference-implementation
uv run --group dev --extra live pytest \
  tests/test_api.py tests/test_workflow.py tests/test_rag.py \
  tests/test_tools.py tests/test_agent_runner.py tests/test_mcp.py \
  tests/test_evals.py -q
```

课程完整回归：

```bash
cd reference-implementation
uv run --group dev --extra live pytest -q
```

这些命令验证当前同步 API 的身份/预算/事件、in-memory Workflow、权限 RAG、工具、Agent、MCP 与 eval；它们不验证生产队列、SSE/WebSocket、数据库隔离、配额、保留或 incident 系统。学员新增这些能力后，必须增加相应集成和故障测试。

## 作业与评分

| 项目 | 权重 | 必须证据 |
| --- | --- | --- |
| 状态机与任务 API | 20% | 合法/非法转换、幂等、终态竞争测试 |
| 进度与证据 UX | 20% | 重连、sequence、citation/tool/approval 演示 |
| 取消与重试 | 15% | cancel propagation、分类与 reconciliation |
| 企业边界 | 10% | 身份映射、旧卡片、权限边界图 |
| 生产治理 | 25% | secrets、identity、隔离、quota、retention、incident 证据 |
| CI 与评审 | 10% | release gates、eval threshold、rollback 记录 |

只有截图、没有服务端状态与测试证据；或把 in-memory reference 称为生产 durability，均不能达到 Core。

## Core / Advanced / Production 完成标准

| 等级 | 完成标准 |
| --- | --- |
| Core | 六状态合同清晰；任务可创建、观察、取消并按策略重试；引用、工具活动、审批和失败可理解；当前参考与目标设计明确分开。 |
| Advanced | 实现一种可重连进度流和一个企业 IM/交互式结果 adapter；加入 schema-versioned event、gap recovery、connector replay 测试。 |
| Production | 持久队列/事件/Workflow、workload identity、租户隔离、限流配额、保留删除、incident runbook、SLO、CI gates 与 rollback 都有执行证据。 |

## 本章资料

- [生态成熟度矩阵](../docs/ecosystem-maturity.md)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [HTML Living Standard: Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Kubernetes Secrets good practices](https://kubernetes.io/docs/concepts/security/secrets-good-practices/)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)

## 复盘模板

1. 用户如何从服务端证据判断任务处于哪个状态？
2. 哪类失败可重试，哪类必须审批、修复或 reconciliation？
3. connector、UI、模型、核心服务和工具分别不能做什么？
4. 当前哪些能力只是 in-memory reference，离生产还缺什么证据？
5. 一次跨租户或未知副作用事故如何被发现、止损、恢复并转成回归 case？
