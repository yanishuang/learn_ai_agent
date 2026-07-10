# 第 8 章：Workflow 与持久化执行

更新时间：2026-07-10
建议学习时间：5-7 天  
本章产出：一个版本化、可暂停审批、可恢复、可取消、可超时且有幂等冲突检查的离线研究 Workflow；以及一份生产持久化、重试和副作用提交设计。

## 本章定位

Agent 适合在边界内选择下一步，Workflow 适合明确保存“现在走到哪里、下一步允许做什么、失败后从哪里继续”。只要任务包含长等待、人工输入、审批、重试或不可逆副作用，就不能把可靠性寄托在一次 HTTP 请求或模型记忆上。

当前 `ResearchWorkflow` 是一个确定性的**内存教学实现**。它真正实现 `workflow_version`、`state_version`、审批 payload hash、幂等冲突、租户/所有者边界、`waiting_for_approval`、`running`、`completed`、`cancelled` 和 `timed_out`。它没有数据库、worker、外部模型调用、外部副作用、`waiting_for_input`、`retrying`、持久化 expiry 或崩溃恢复。后几项会在本章以**生产设计练习**明确标注。

## 前置知识

- 已完成第 6 章，能解释 Agent run、`RunContext`、预算停止、trace 和审批边界。
- 理解状态机、Pydantic 不可变模型、SHA-256、数据库唯一约束与 pytest。
- 已按 `reference-implementation/README.md` 同步环境；本章命令从 `reference-implementation/` 执行。

## 学习目标

完成本章后，你应该能够：

1. 判断何时使用 Workflow 而不是开放 Agent loop。
2. 准确使用当前 `WorkflowRun`、`ApprovalPayload`、`ApprovalDecision` 和 `WorkflowStatus`。
3. 解释 `workflow_version` 与 `state_version` 的不同职责。
4. 用 hash 把审批决定绑定到 run、tenant、workflow version、state version 和实际内容。
5. 解释当前开始与审批幂等键的作用域、重放行为和冲突行为。
6. 设计包含 `waiting_for_input`、`retrying`、`timed_out` 和 `cancelled` 的生产状态机。
7. 把模型输出作为版本化快照保存，在确定 checkpoint 边界恢复，而不是重新询问模型后假装继续同一次运行。
8. 把副作用放在可提交、可去重、可审计的边界内，并用数据库唯一约束防止并发重复执行。

## 核心知识

### 8.1 Workflow 与 Agent 的职责

| 维度 | Workflow | Agent |
| --- | --- | --- |
| 下一步 | 状态机允许的显式 transition | 模型在工具边界内选择 |
| 恢复 | checkpoint + 版本化状态 | 单次 run continuation 或重开 run |
| 等人 | 持久化 waiting 状态后释放 worker | 不应占住一次模型循环等待 |
| 重试 | 按错误分类、attempt 和 idempotency 策略 | 容易重放未知副作用 |
| 审计 | state transition、actor、payload、版本 | 依赖 trace，还需外部策略约束 |
| 适合 | 审批、发布、批处理、长任务 | 局部探索、工具选择、开放分析 |

推荐组合：Workflow 控制主流程，Agent 只在一个可重试或可人工复核的节点内处理开放任务，Tool 执行具体动作。

### 8.2 当前可执行状态机

参考实现的状态枚举只有以下五项：

```python
from agent_course.workflows import WorkflowStatus


assert {status.value for status in WorkflowStatus} == {
    "waiting_for_approval",
    "running",
    "completed",
    "cancelled",
    "timed_out",
}
```

当前 transition：

```text
start
  -> waiting_for_approval
       -> approve(true) -> running -> resume -> completed
       -> approve(false) -> cancelled
       -> cancel -> cancelled
       -> deadline materialized by approve/resume/cancel -> timed_out

running
  -> resume -> completed
  -> cancel -> cancelled
  -> deadline materialized by resume/cancel -> timed_out

completed / cancelled / timed_out
  -> resume or cancel returns the same terminal run
```

`resume()` 在 `waiting_for_approval` 时原样返回，不会越过审批。终态重复 resume/cancel 也是幂等读取，不增加 `state_version`。

### 8.3 Run 与审批合同

`WorkflowRun` 当前字段：

| 字段 | 语义 |
| --- | --- |
| `run_id` | 从 tenant/user/request 的 SHA-256 派生的稳定 ID |
| `workflow_version` | 当前固定为 `research-v1` |
| `state_version` | 每次实际状态更新加 1，从 1 开始 |
| `status` | 当前五状态之一 |
| `tenant_id`、`user_id` | run 所属身份边界 |
| `topic` | 规范化的业务输入 |
| `approval` | 等待审批时的内容绑定 payload |
| `approved_by`、`cancelled_by` | transition actor |
| `report` | 完成后的确定性报告 |
| `error_code` | 当前超时为 `WORKFLOW_TIMEOUT` |

`ApprovalPayload` 包含 `run_id`、`tenant_id`、`workflow_version`、`state_version`、`action`、`topic`、`summary` 和 64 位十六进制 `content_hash`。hash 使用键排序、紧凑 JSON，并覆盖前述所有业务字段。因此：

- 同一 topic 的不同 run 得到不同 hash；
- 旧 state/version 的审批不能批准新内容；
- 决策 hash 不等于已保存 payload hash 时，在改变状态前抛出 `ApprovalPayloadMismatchError`。

`ApprovalDecision` 只含 `approved`、`payload_hash` 和非空 `idempotency_key`。审批 actor 由可信 `RunContext.user_id` 提供，不能由请求 body 自报。

### 8.4 可恢复审批示例

下面示例与当前接口和状态完全一致：

```python
from agent_course.core import RunContext
from agent_course.workflows import (
    ApprovalDecision,
    ResearchWorkflow,
    WorkflowStatus,
)


context = RunContext(
    user_id="user-1",
    tenant_id="tenant-1",
    request_id="chapter-08-demo",
    permissions=frozenset({"research:run", "research:approve"}),
)
workflow = ResearchWorkflow(timeout_seconds=300)

waiting = workflow.start("AI safety", context)
assert waiting.status is WorkflowStatus.WAITING_FOR_APPROVAL
assert waiting.workflow_version == "research-v1"
assert waiting.state_version == 1
assert workflow.resume(waiting.run_id, context) == waiting

approved = workflow.approve(
    waiting.run_id,
    ApprovalDecision(
        approved=True,
        payload_hash=waiting.approval.content_hash,
        idempotency_key="approval-chapter-08-demo",
    ),
    context,
)
assert approved.status is WorkflowStatus.RUNNING
assert approved.state_version == 2

completed = workflow.resume(waiting.run_id, context)
assert completed.status is WorkflowStatus.COMPLETED
assert completed.state_version == 3
assert completed.report == "Research report: AI safety."
assert workflow.resume(waiting.run_id, context) == completed
```

这段“可恢复”指状态保存在同一个 `ResearchWorkflow` 实例中，调用方可以在审批后再次 `resume()`；它不意味着进程重启后仍能恢复。真正的 durable storage 是后面的生产设计练习。

### 8.5 权限、租户与所有者边界

当前权限矩阵：

| 操作 | 权限 | tenant 检查 | owner 检查 |
| --- | --- | --- | --- |
| `start` | `research:run` | 来自 context | 创建者即 owner |
| `get` | `research:run` | 是 | 是 |
| `resume` | `research:run` | 是 | 是 |
| `cancel` | `research:run` | 是 | 是 |
| `approve` | `research:approve` | 是 | 否 |

`approve` 不要求 approver 是 run owner，这是有意支持同租户独立审批者；`approved_by` 记录实际 approver。生产实现还应验证审批者角色、职责分离和 action 级 policy。跨租户审批永远拒绝。

### 8.6 当前幂等语义

开始幂等键不是单独参数，而是：

```text
(tenant_id, user_id, request_id)
```

同一键加相同规范化 topic 返回原 run；同一键换 topic 抛出 `IdempotencyConflictError`。

审批幂等键是：

```text
(tenant_id, decision.idempotency_key)
```

保存的 fingerprint 为 `(run_id, approved, payload_hash)`。同一 key 和 fingerprint 返回当前 run；同一 key 换任何内容都冲突。检查顺序还保证 hash 不匹配不会写入 idempotency 记录，也不会改变 run。

当前字典只在单进程内提供这些语义。并发、多 worker 和进程重启需要数据库唯一约束。

### 8.7 Timeout、cancel 与 expiry

`ResearchWorkflow` 接收正数 `timeout_seconds` 和可注入的 monotonic clock。`start()` 保存内部 deadline。每次 `approve()`、`resume()` 或 `cancel()` 先 materialize timeout：若当前时间达到 deadline，run 变为 `timed_out`、`error_code="WORKFLOW_TIMEOUT"`，并增加 state version。

当前审批 payload 没有 `expires_at` 字段，deadline 也没有持久化进 `WorkflowRun`。因此只能准确说“当前内存 run 有统一 deadline，迟到审批会先转成 timed_out”，不能说“审批请求已持久化 expiry”。

**生产设计练习：审批 expiry。** 在 approval row 中保存 `expires_at`，审批 transaction 同时检查：row 未使用、未撤销、`now() < expires_at`、payload hash 和 state version 仍匹配。过期 transition 写审计事件并进入 `timed_out` 或重新申请审批，不能静默刷新旧 hash。

### 8.8 生产状态词汇设计练习

**下面是目标状态模型，不是当前枚举。** 在五个已实现状态之外加入：

| 状态 | 进入条件 | 允许离开方式 |
| --- | --- | --- |
| `waiting_for_input` | 缺少用户业务输入，但不是风险审批 | 提交带 schema/version 的输入后回到 runnable 状态；过期可 timed out |
| `retrying` | 可重试错误已记录，下一次 attempt 尚未到期 | backoff 到期后进入 running；预算耗尽进入 failed/terminal policy |
| `timed_out` | run 或等待期限已到 | 终态；需要新 run 或显式补偿流程 |
| `cancelled` | owner/策略/审批拒绝取消 | 终态；已发生副作用走补偿，不倒写历史 |

不要把 `waiting_for_input` 和 `waiting_for_approval` 合并：前者收集任务数据，后者授予特定副作用权限。不要把 `retrying` 当作 sleep 中的 worker；应保存 `attempt_count`、`next_attempt_at`、`last_error_code` 后释放 worker。

完整生产枚举可以包含：

```text
waiting_for_input
waiting_for_approval
running
retrying
completed
cancelled
timed_out
```

若产品还需要 `failed`，必须定义它和 `timed_out`、重试耗尽之间的精确关系；当前参考实现没有 `failed` workflow 状态。

### 8.9 生产唯一约束设计练习

**以下 SQL 是设计练习，不是已有迁移。** 数据库必须成为并发幂等的裁决者：

```sql
create table workflow_runs (
  run_id text primary key,
  tenant_id text not null,
  user_id text not null,
  request_id text not null,
  workflow_version text not null,
  state_version integer not null check (state_version > 0),
  status text not null,
  input_hash text not null,
  state_json jsonb not null,
  unique (tenant_id, user_id, request_id)
);

create table approval_decisions (
  tenant_id text not null,
  idempotency_key text not null,
  run_id text not null references workflow_runs(run_id),
  payload_hash text not null,
  approved boolean not null,
  approved_by text not null,
  decided_at timestamptz not null,
  primary key (tenant_id, idempotency_key)
);

create table side_effect_commits (
  tenant_id text not null,
  run_id text not null references workflow_runs(run_id),
  step_name text not null,
  business_object_id text not null,
  request_hash text not null,
  status text not null check (status in ('pending', 'committed', 'uncertain')),
  response_snapshot jsonb,
  primary key (tenant_id, run_id, step_name, business_object_id)
);
```

应用使用 insert-on-conflict 后读取既有 row，并比较 hash。不能先 `select` 再无约束 insert，否则并发 worker 仍可能重复发送。

### 8.10 确定性恢复边界与模型快照

Workflow 的 checkpoint 应放在业务语义稳定的位置：

```text
读取已提交 state
  -> 执行纯计算或准备请求
  -> 验证输出 schema
  -> 在 transaction 中保存 output snapshot + 新 state_version
  -> transaction 成功后，后续节点才可见
```

模型调用是非确定性的外部活动。生产流程应保存：prompt/template version、model identifier、结构化输出、usage、必要的来源引用和输出 hash。恢复时读取这个 snapshot，不要默认重新调用模型；重调必须创建新的 attempt，并明确替换规则。否则同一个 `state_version` 可能对应两份不同研究计划，审批 hash 和审计都会失去意义。

`workflow_version` 决定节点图和解释器版本，`state_version` 决定某个 run 已提交了几次 transition。部署新代码时，旧 run 应继续使用兼容 handler，或经过显式迁移；不能用最新代码无条件解释历史 state。

### 8.11 副作用放置与提交顺序

当前 `ResearchWorkflow.resume()` 只生成确定性字符串，没有外部副作用。以下是**生产设计练习**。

副作用节点至少遵守：

1. 在数据库读取并锁定当前 run/state version。
2. 验证 tenant、permission、审批 hash、expiry 和允许的 transition。
3. 用唯一 idempotency constraint 创建 `side_effect_commits` 占位。
4. 若已有相同 request hash 且状态为 `committed`，返回已保存 response；若 hash 不同，报冲突；若状态为 `pending`/`uncertain`，先 reconciliation，不能直接重放。
5. 调用支持 idempotency key 的外部服务。
6. 保存响应 snapshot、审计 actor 和新 state。

数据库无法与任意外部 API 做原子 commit，因此要根据服务能力选择 idempotency key、outbox/inbox、补偿动作和 reconciliation job。绝不能把“发送邮件”放在状态 commit 之前，然后在崩溃恢复时盲目重放。

### 8.12 重试设计

| 错误 | 是否自动重试 | 原因 |
| --- | --- | --- |
| 网络超时、429、短暂 5xx | 可，有限次数与退避 | 可能是暂时失败，仍需幂等 |
| schema/参数错误 | 否 | 相同输入不会自愈 |
| permission/policy denial | 否 | 重试不能创造权限 |
| approval mismatch/expiry | 否 | 必须重新展示并取得新审批 |
| 未知副作用结果 | 不直接重放 | 先向外部系统 reconciliation |

每次 retry 保存 attempt number、错误分类、下一次时间和输入 hash。总 deadline 和 retry budget 都要有上限，防止 denial-of-wallet。

## 教师演示

1. 运行 8.4 示例，展示 state version 1 -> 2 -> 3。
2. 在审批前调用 `resume()`，证明不会越过 `waiting_for_approval`。
3. 用第一条 run 的 hash 审批同 topic 的第二条 run，展示 mismatch 且状态不变。
4. 重放相同 approval key 与内容，展示幂等返回；改变 `approved`，展示冲突。
5. 注入手动 clock，在 deadline 之后 approve/cancel，展示先 materialize `timed_out`。
6. 对照生产状态图，指出 `waiting_for_input`、`retrying` 和数据库 constraints 尚未由参考实现提供。

## 学员实验

Task 11 计划创建本章实验目录 `labs/chapter-08/`；该目录在本次 Task 5 提交中尚未创建，因此不把它写成当前可点击链接，也不宣称已有可运行 lab README。

实验任务：

1. 完成 start -> waiting -> approve -> running -> resume -> completed。
2. 验证拒绝审批进入 `cancelled`，owner cancel 幂等。
3. 验证 payload hash 不能跨 run 重放，idempotency key 冲突不改变 state。
4. 验证 permission、tenant、owner 和独立 approver 边界。
5. 用 injected clock 验证 waiting/running run 的 timeout。
6. 设计包含 `waiting_for_input` 和 `retrying` 的扩展状态图。
7. 提交数据库唯一约束、模型输出 snapshot 和副作用 placement 说明。

默认离线验证命令：

```bash
cd reference-implementation
uv run --group dev --extra live pytest -q
```

本章聚焦命令：

```bash
uv run --group dev --extra live pytest tests/test_workflow.py -q
```

## 失败注入与排错

| 注入 | 预期 | 关键证据 |
| --- | --- | --- |
| 旧 run hash 审批新 run | `ApprovalPayloadMismatchError` | 新 run state 不变 |
| 同一 start key 换 topic | `IdempotencyConflictError` | 原 run 仍可读取 |
| 同一 approval key 换 decision | `IdempotencyConflictError` | 无第二次 transition |
| 非 owner resume/cancel | `WorkflowAccessError` | tenant/owner 检查顺序 |
| 同 tenant approver 非 owner | 有 `research:approve` 时可审批 | `approved_by` 是实际 approver |
| deadline 后 approve | `timed_out`，未写 `approved_by` | timeout 先 materialize |
| completed 后 resume | 返回同一 run | state version 不增加 |

排错按 `run_id`、`workflow_version`、`state_version`、status、actor context、approval hash、idempotency fingerprint 和 deadline 顺序检查。不要只看最终 report。

## 自动验证

当前 `tests/test_workflow.py` 已验证：版本化初始状态、内容绑定 hash、跨 run 重放拒绝、mismatch 无状态变更、审批后恢复、开始与审批幂等冲突、permission/tenant/owner、waiting/running timeout，以及 cancel 幂等。

文档验收还应确认：

- 当前五个状态与测试一致；
- `waiting_for_input` 和 `retrying` 明确标为设计练习；
- 没有声称 payload 当前包含 `expires_at`；
- SQL 有真实 unique/primary key 约束；
- 模型输出 snapshot 和副作用 placement 有确定 commit 边界；
- Python fence 可解析，计划 lab 路径不形成失效链接。

## 作业与评分

| 维度 | 分值 | 满分证据 |
| --- | ---: | --- |
| 当前状态机 | 20 | transition、终态和 state version 与实现一致 |
| 审批安全 | 20 | payload hash 覆盖 run/tenant/version/state/content，expiry 设计明确 |
| 幂等与并发 | 20 | 当前 key 语义准确，生产数据库有唯一约束与冲突比较 |
| 恢复与快照 | 15 | checkpoint 确定，模型输出版本化，不隐式重调 |
| 副作用 | 15 | placement、外部 idempotency、outbox/reconciliation 合理 |
| 身份与超时 | 10 | permission/tenant/owner/approver 和 timeout 边界有测试 |

只在前端显示确认弹窗、后端不校验 payload hash 的提交，审批安全项不得分。只在 Python 中查询“是否执行过”却没有数据库唯一约束的生产设计，幂等与并发项不得满分。

## Core / Advanced / Production 完成标准

- **Core**：当前内存 Workflow 的 start、approval、resume、cancel、timeout、版本和边界测试全部通过。
- **Advanced**：能设计并测试 `waiting_for_input`、`retrying`、attempt budget、snapshot 和 deterministic resume boundary。
- **Production（设计与外部基础设施要求）**：持久化数据库、并发唯一约束、worker、审批 expiry、外部副作用幂等/outbox、补偿和版本迁移均已实现并演练崩溃恢复。当前参考实现不宣称达到这一层。

## 本章资料

- [参考实现 README](../reference-implementation/README.md)
- [LangGraph Durable Execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)
- [Temporal Documentation](https://docs.temporal.io/)
- [Pydantic AI Durable Execution](https://ai.pydantic.dev/durable_execution/)
- [OpenAI Background Mode](https://developers.openai.com/api/docs/guides/background)
- [OpenAI Agents SDK - Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

## 复盘模板

```markdown
# 第 8 章复盘

## 当前实现有哪些状态和 transition

## workflow_version 与 state_version 分别保护什么

## 审批 hash 绑定了哪些字段，何时过期

## 开始、审批和副作用各自的幂等键是什么

## 模型输出在哪个 checkpoint 保存，恢复时是否重调

## waiting_for_input 与 waiting_for_approval 有何不同

## 副作用发生前后分别提交什么

## 哪些能力仍只是生产设计练习
```
