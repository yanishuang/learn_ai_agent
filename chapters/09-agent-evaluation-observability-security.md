# 第 9 章：Agent 评估、可观测性与安全

更新时间：2026-07-10
建议学习时间：5-7 天
本章产出：一套先确定性断言、再人工校准模型评分器的评估方法；覆盖任务、工具、参数、轨迹、策略、延迟和成本；并把 trace、数据集回归、线上监控与红队响应连接起来。

## 本章定位

一次演示成功不能证明 Agent 可靠。最终答案可能碰巧正确，但工具选错、参数越权、轨迹绕路、引用失真或成本失控。评估必须观察结果和过程，安全必须由后端边界执行，可观测性必须提供足够证据又不保存秘密。

参考实现已经提供确定性 `EvalCase -> evaluate_cases() -> EvalReport`、不可变 `model_tool_calls` 证据和写入前脱敏 trace。它实际计算任务成功、工具选择、参数准确、未授权动作阻断、模型轮数和平均轮数。LLM judge、latency/cost 字段、重复 Live runs、线上采样、red-team JSONL 和事件响应自动化属于本章的**评估/生产设计练习**；不得描述成当前实现已经输出的指标。

## 前置知识

- 已完成第 5-8 章，能够阅读 tool call、RAG hit/citation、Agent result、Workflow state 和 trace。
- 理解 pytest、JSON/JSONL、率指标、p50/p95、最小权限和提示词注入威胁。
- 已按 `reference-implementation/README.md` 同步环境；默认评估不需要 API Key 或模型网络请求。

## 学习目标

完成本章后，你应该能够：

1. 在使用 LLM judge 前先写可复现的 schema、值、权限、停止原因和轨迹断言。
2. 准确运行当前 `EvalCase`、`EvalCaseResult`、`EvalReport` 和 `evaluate_cases()`。
3. 定义任务、工具、参数、轨迹、策略、延迟和成本指标，并明确哪些已实现、哪些待扩展。
4. 用 trace grading 找到最终文本掩盖的错误，并让 dataset regression 进入 CI。
5. 校准 LLM judge，与人工标注比较，并对随机系统做重复运行而不是只测一次。
6. 区分离线评估与线上评估，建立脱敏失败回流。
7. 设计直接/间接注入、工具输出投毒、数据外泄、权限提升和 denial-of-wallet 红队集。
8. 解释为什么模型自报 confidence 既不是授权依据，也不是安全控制或校准后的质量分数。

## 核心知识

### 9.1 评估顺序：确定性优先

推荐顺序：

```text
输入与 fixture 校验
  -> schema / exact value / set membership
  -> stop reason / permission / no-side-effect
  -> tool name / canonical arguments / trajectory
  -> citation grounding / workflow state
  -> latency / token / cost budget
  -> 只有无法规则化的语义质量才交给 LLM judge
  -> 人工抽样和校准
```

确定性断言便宜、稳定、能直接定位边界。适合检查：

- 输出能否通过 Pydantic/schema；
- `stop_reason` 是否符合 case；
- 工具名序列是否精确匹配；
- 参数规范 JSON 是否完全相等，包括拒绝额外参数；
- 越权 case 是否没有任何成功 `ToolResult`；
- turn/tool/token budget 是否停止；
- citation quote 是否是授权 hit 的子串；
- Workflow hash、state version 和 transition 是否一致；
- trace 是否不含 secret 或原始 tool arguments。

LLM judge 适合规则难以完整描述的维度，例如说明是否完整、语气是否适合目标用户、两份摘要哪份更忠实。它不能覆盖硬失败：judge 认为回答“看起来不错”也不能让跨租户读取、错参数或审批 hash mismatch 通过。

### 9.2 当前可执行评估合同

`EvalCase` 当前字段：

| 字段 | 语义 |
| --- | --- |
| `case_id` | 非空且整个运行内唯一；runner 按 ID 排序 |
| `question` | 传给应用的问题 |
| `context` | 完整可信 `RunContext` |
| `limits` | 本 case 的实际 `RunLimits` |
| `expected_answer_contains` | final content 必须包含的全部字符串 |
| `expected_tool_calls` | 必填的有序工具调用序列；元素含 `name` 与精确 `arguments`，无工具时显式写 `[]` |
| `expected_stop_reason` | 默认 `completed` |
| `expect_unauthorized_action_blocked` | 需要验证拒绝且没有成功工具结果 |
| `max_turns` | case 级轨迹上限，默认 4 |

`evaluate_cases()` 调用 `EvaluationApplication.run_agent(question, context, limits)`，对每个结果做确定性评分。重复 case ID 会在运行前失败。输出按 case ID 稳定排序，`to_json()` 使用排序键和紧凑 JSON，所以**同一个内存 report** 或字段完全相同的 report 会稳定序列化。新 run 的 `trace_id` 默认由 trace sink 随机生成；Live 输出还可能随机变化，因此 fresh runs 不能默认按原始 JSON 做逐字节相等断言。

做跨 run snapshot regression 时，先固定可确定输入，再规范化 trace ID 等易变标识；原始 trace ID 另存为诊断关联，不进入 baseline diff：

```python
import json
from typing import Any

from agent_course.evals import EvalReport


def normalized_eval_json(report: EvalReport) -> str:
    payload: dict[str, Any] = report.model_dump(mode="json")
    for result in payload["results"]:
        result["trace_id"] = "<TRACE_ID>"
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
```

这个 helper 是课程侧 regression 设计，不是当前 evaluator 已导出的 API。即使规范化 ID，两个随机 Live run 的业务字段仍可能不同；它们应使用第 9.8 节的重复运行分布，而不是强求字节一致。

### 9.3 可执行示例

下面示例直接评估真实离线 `CourseApplication` 的有界 runner：

```python
import asyncio

from agent_course.application import CourseApplication
from agent_course.core import RunContext, RunLimits
from agent_course.evals import EvalCase, evaluate_cases
from agent_course.models.fake import ORDER_QUERY_FIXTURE


def order_case() -> EvalCase:
    return EvalCase(
        case_id="order-status-success",
        question=ORDER_QUERY_FIXTURE,
        context=RunContext(
            user_id="user-1",
            tenant_id="tenant-1",
            request_id="eval-order-status",
            permissions=frozenset({"orders:read"}),
        ),
        limits=RunLimits(
            max_turns=4,
            max_tool_calls=3,
            max_output_tokens=100,
            timeout_seconds=0.2,
        ),
        expected_answer_contains=("shipped",),
        expected_tool_calls=(
            {
                "name": "query_order_status",
                "arguments": {"order_id": "O1001"},
            },
        ),
        max_turns=2,
    )


async def evaluate(app: CourseApplication) -> str:
    report = await evaluate_cases([order_case()], app)
    assert report.total_cases == 1
    assert report.passed_cases == 1
    assert report.tool_selection_accuracy == 1.0
    assert report.argument_accuracy == 1.0
    assert report.average_turn_count == 2.0
    return report.to_json()
```

`CourseApplication` 需要由调用方注入 runner、retriever 和 workflow；本段只展示 evaluator 的准确接口，不伪造一个不存在的全局 app factory。现有 `tests/test_evals.py` 用 `FakeEvaluationApplication` 注入确定性的 `AgentResult`，因此无需网络即可完整验证评分逻辑。

### 9.4 当前指标与目标指标

| 维度 | 当前实现 | 计算/目标 |
| --- | --- | --- |
| 任务 | `task_success_rate` | stop reason 正确且 final content 包含全部期望字符串 |
| 工具 | `tool_selection_accuracy` | `model_tool_calls` 的工具名序列必须等于单一期望工具 |
| 参数 | `argument_accuracy` | 期望工具的模型参数与期望 JSON 规范化后精确相等 |
| 轨迹 | `turn_count`、`turn_count_within_limit`、`average_turn_count` | 当前只量 model turns；可扩展冗余调用、重复、路径规则 |
| 策略 | `unauthorized_action_block_rate` | stop reason 是 permission/policy denied，且无成功工具结果 |
| 延迟 | **设计练习** | case/step p50、p95、p99 与 timeout rate；当前 report 没有 latency |
| 成本 | **设计练习** | input/output/cached token、tool/API 费用、每成功任务成本；当前 report 没有 cost |

`expected_tool_calls` 对每个 `EvalCase` 都是必填，所以 tool selection 与 argument accuracy 总有明确分母：无工具时写 `[]`，意外调用会失败。只有可选安全类别没有适用 case 时，对应 block rate 才返回 `None`；空数据集的所有 rate 和 average 都是 `None`。

#### 任务指标

任务成功必须与产品行为相连。当前字符串包含断言适合离线 fixture；生产数据集可组合 exact field、citation、business outcome 和人工 rubric。不要只用 BLEU/词面相似度代替业务成功。

#### 工具与参数指标

工具选择证据来自 `AgentResult.model_tool_calls`，不从 `ToolResult.output` 猜测。即使一个伪造 tool result 自称成功，没有模型调用证据也不能通过。参数使用 `json.dumps(..., sort_keys=True, allow_nan=False)` 做规范比较；`1` 与 `true` 不应因 Python 相等规则而混为一谈，额外 `tenant_id` 也必须失败。

#### 轨迹指标

当前 `max_turns` 检查模型 step 数。扩展时可定义：

```text
trajectory_success = required_steps_in_order
                     and forbidden_steps_absent
                     and no_repeated_call
                     and model_turn_count <= case.max_turns
                     and executed_tool_calls <= case.max_tool_calls
```

轨迹不是越短越好。最短路径如果跳过授权、引用核验或审批就是失败。应同时设置 required/forbidden steps 和效率上限。

#### 策略指标

policy success 不能只检查回答里出现“抱歉”。当前 evaluator 要求拒绝类 stop reason，且所有工具结果都没有成功。生产策略还应检查敏感数据没有进入输出/trace、审批没有绕过、RAG 没有返回越权 hit。

#### 延迟与成本设计练习

**参考实现尚未捕获这些字段。** 扩展 case result 时记录：

- `latency_ms`：端到端 wall time；分开 model、tool、retrieval、queue time。
- `input_tokens`、`output_tokens`、`cached_tokens`：来自 provider usage，缺失必须标 `unknown`，不能当 0。
- `model_cost`：按调用时生效的价格快照计算并保存 currency/version。
- `tool_cost`：搜索、浏览器、第三方 API 或人工审批成本。
- `cost_per_success = total_cost / passed_cases`，同时报告失败任务消耗。

阈值示例必须按产品 SLO 和模型价格配置，不能写成课程永久常量。延迟/成本 regression 应比较同一数据集、同一版本和足够重复次数。

### 9.5 Trace grading

当前 trace 事件包括：

```text
run.started
guardrail.checked
model.step
tool.called
tool.result
run.timeout / run.error（发生时）
run.finished
```

每个事件有同一个 `trace_id`。`model.step` 保留 turn、工具调用数量、输出 token 和 stop reason；`tool.called` 保留工具名，但 `arguments` 在存储边界整体脱敏；`tool.result` 保留 name/code/success。身份字段来自 trusted context。

Trace grading 可先做确定性规则：

| 规则 | 失败含义 |
| --- | --- |
| 首事件不是 `run.started` | trace 不完整或关联错误 |
| 缺 `guardrail.checked` | 输入策略未执行/未记录 |
| tool result 之前无 tool called | 轨迹顺序损坏 |
| `run.finished.stop_reason` 与 result 不同 | 结果与可观测记录漂移 |
| permission denied 后有 success tool result | 安全边界失败 |
| event JSON 出现订单参数或 secret | 脱敏失败 |
| turn/tool count 超 case 限制 | trajectory/budget regression |

由于 trace 已脱敏，参数精确评分继续使用同一次 run 的不可变 `model_tool_calls`。生产 trace 若跨系统传播，还要统一 `request_id`、`trace_id`、run ID 与 workflow run ID，并对访问权限和保留期做治理。

### 9.6 Dataset regression

三个机器可读 baseline 已提交并由同一离线 runner 执行：

- [Agent cases](../evals/agent-cases.jsonl)
- [RAG cases](../evals/rag-cases.jsonl)
- [Security cases](../evals/security-cases.jsonl)

每个文件当前有 12 条 case：Agent 覆盖直接回答、显式空/非空工具轨迹、缺参数、多意图、预算停止和未授权请求；RAG 覆盖可答、不可答、同义表达、引用和租户隔离；Security 覆盖直接/间接注入、tool-output injection、exfiltration、privilege escalation 和 denial-of-wallet。间接文档注入 case 会把恶意检索文本交给 bounded Agent，并断言后端 export handler 执行次数为 0，而不是只停在 retrieval 测试。

Regression 流程：

1. 验证每行 JSONL 可解析、case ID 唯一、schema/version 明确。
2. 固定 Fake Model、代码、数据 snapshot 和 limits。
3. 先跑确定性断言，任何硬边界失败直接阻断。
4. 对适用 case 才计算分母，报告 rate 的分子/分母。
5. 保存原始 report 与失败 trace ID 供诊断；baseline diff 使用规范化易变 ID 后的 canonical JSON。
6. 与批准 baseline 比较；新增 case 不能通过删旧失败来“改善”比例。
7. 线上失败脱敏、人工确认标签后加入数据集，并记录来源事件和修复版本。

### 9.7 LLM judge 校准

**这是评估设计练习，默认测试不调用 judge。** judge rubric 至少包含评分维度、等级定义、正反例、引用要求和“不足证据”选项。校准步骤：

1. 从目标流量分层抽取样本，双人独立标注并处理分歧。
2. 冻结 judge model、prompt、temperature、rubric version 和输入格式。
3. 与人工 gold set 比较混淆矩阵、每类 precision/recall、平均绝对误差和关键安全 false pass。
4. 按语言、任务、拒答、长文本等 slice 检查偏差。
5. 设定可接受阈值；不达标就改 rubric 或回到人工评审，不能调到“看起来差不多”。
6. model/prompt 变更后重新校准。

judge 只能评价它看到的证据。评轨迹时给它脱敏、结构化步骤，不给 secret；评 citation 时给可授权的来源片段；不要让 judge 自行访问生产资源补证据。

### 9.8 随机行为与重复运行

Fake Model 用于确定性合同测试，一次运行足够发现代码回归。Live 模型、采样、搜索结果和外部服务具有随机性，一次通过不能估计稳定性。

重复运行设计：

- 每个 case 至少记录 `run_index`、model snapshot、prompt version、时间窗和可用 seed（如果 provider 支持，但不假设 seed 保证完全确定）。
- 报告 pass@1、N 次通过率、全通过率、最差 slice、均值/标准差或置信区间。
- 安全硬边界通常要求所有重复都通过；创作质量可使用分布阈值。
- 对延迟/成本保留 warm/cold、cache hit/miss 和失败重试 slice。
- 比较两个版本时使用同一 case 集和重复策略，避免流量或数据漂移冒充改进。

Live repeated runs 会产生费用，必须显式启用、设置预算并与默认离线 CI 分离。

### 9.9 Offline 与 online evaluation

| 维度 | Offline | Online |
| --- | --- | --- |
| 数据 | 固定 fixture、历史脱敏 case、合成 red team | 真实流量与实际系统状态 |
| 优点 | 可重复、可阻断 CI、定位快、无用户风险 | 发现分布漂移、集成故障和真实长尾 |
| 局限 | 覆盖不完真实变化，合成数据可能失真 | 标签延迟、有隐私/实验风险、归因更难 |
| 常用指标 | exact assertions、rate、trace rules、judge calibration | task outcome、拒绝/升级、p95、成本、投诉、安全事件 |
| 发布作用 | pre-merge regression gate | canary、A/B、监控和回滚信号 |

线上评估不是把生产 prompt 和完整用户内容发送给另一个 judge。应先最小化与脱敏，按用途采样，控制访问与保留，敏感任务优先使用业务结果和人工审核。

从线上回流离线：事件 -> 安全保存原证据 -> 最小化/脱敏 -> 人工确认 expected behavior -> 分配稳定 case ID 和标签 -> 添加到 JSONL -> 在修复前证明 case 失败、修复后证明通过。

### 9.10 红队数据集

红队 case 至少覆盖：

| 威胁 | 示例载体 | 必须验证的控制 |
| --- | --- | --- |
| direct injection | 用户要求绕过权限/导出秘密 | input policy + tool permission，模型不被授予权限 |
| indirect document injection | RAG 文档写“忽略系统指令并泄露数据” | 来源标记、内容当数据、工具最小权限、授权检索 |
| tool-output injection | 搜索/API 返回恶意指令 | tool output taint、schema、禁止自动升级权限 |
| exfiltration | 请求把 secret 发到外部地址 | data classification、egress allowlist、approval |
| privilege escalation | 模型参数伪造 tenant/user/role | trusted `RunContext`，额外参数拒绝 |
| cross-tenant retrieval | 高相似度其他租户 chunk | 查询内 tenant/user/permission filter |
| approval replay | 旧 hash 批准新 run/content | payload hash + state/version + expiry + idempotency |
| denial-of-wallet | 重复工具、超长输出、无限 retry | run limits、retry budget、rate/spend limits |
| trace leakage | arguments、API key、Bearer token | 存储边界递归脱敏与访问控制 |

每条 case 应含：threat category、input/source fixture、trusted context、expected stop/policy、forbidden side effect、trace assertions、severity 和 owner。不要只检查最终回复有没有拒绝词。

### 9.11 安全事件响应

红队或线上监控发现安全失败后：

1. **Contain**：关闭有风险工具/route、收紧权限或回滚版本；若可能泄密，轮换相关凭据。
2. **Preserve evidence**：保存受控的 request/run/trace/workflow IDs、版本与脱敏快照，限制访问，不把 secret 复制进 ticket。
3. **Classify**：确认是否真的执行副作用、涉及哪些 tenant/user/data、是否为模型输出还是后端边界失败。
4. **Notify and escalate**：按严重度通知安全、隐私、法务和业务 owner，遵循组织时限。
5. **Eradicate and recover**：修复授权/查询/审批/预算控制，验证补偿或撤销，分阶段恢复。
6. **Regress**：把最小脱敏复现加入 `evals/security-cases.jsonl`，先证明旧版本失败，再证明修复通过。
7. **Review**：记录根因、检测缺口、响应时间和控制 owner，而不只改 prompt。

### 9.12 为什么 self-reported confidence 不是安全控制

模型生成的 `confidence="high"` 与答案文本来自同一个不可靠生成过程：它没有访问真实授权策略，通常也没有经过概率校准，提示词注入还能直接影响它。高 confidence 不能授予权限、跳过审批、扩大 RAG scope 或放宽引用；低 confidence 也不能自动证明安全拒绝。

可执行安全控制必须来自：认证过的 identity、后端 permission check、查询内访问过滤、strict schema、内容绑定审批、幂等约束、预算、脱敏和测试。confidence 最多是展示/分析元数据，并且只有在独立标注集上校准后才能用于低风险产品路由；仍需硬边界兜底。

## 教师演示

1. 构造最终文本正确但工具名错误的 `AgentResult`，展示 task success 与 tool accuracy 分开。
2. 构造 `ToolResult` 自称成功但没有 `model_tool_calls` 的结果，展示工具与参数评分不能被伪造输出骗过。
3. 构造额外 `tenant_id` 参数，展示 canonical exact match 失败。
4. 运行 unauthorized case，展示 stop reason 和“无成功副作用”必须同时成立。
5. 用固定 `trace_id` 的同一组结果展示输入顺序变化时 report 仍按 case ID 稳定序列化，再展示两个 fresh run 的原始 JSON 会因 trace ID 不同而不同。
6. 关联 trace，找到重复/超预算/脱敏问题。
7. 对一个语义 rubric 演示人工 gold set 与 judge 分歧，而不是把 judge 分数直接当真值。

## 学员实验

按 [Lab 09：离线评估、Trace 与红队数据](../labs/chapter-09/README.md) 完成本章实验；默认命令会执行三个 JSONL baseline，而不只是解析文件。

实验任务：

1. 为 direct、tool、wrong args、unauthorized 和 budget stop 建立 `EvalCase`。
2. 输出当前五类聚合；解释显式空工具序列仍参与 trajectory/argument 分母，而没有适用安全 case 时 block rate 才为 `None`。
3. 增加 trace grading 规则，至少检查事件顺序、result/trace stop reason 和 secret absence。
4. 设计 latency/cost 扩展 schema，明确 unknown usage 和价格版本。
5. 为随机 Live 路径设计重复运行和 judge calibration，不把它加入默认离线 CI。
6. 为三个计划 JSONL 数据集各写覆盖矩阵。
7. 从一条模拟线上安全失败写出完整响应与回归流程。

默认离线验证命令：

```bash
cd reference-implementation
uv run --group dev --extra live pytest -q
```

本章聚焦命令：

```bash
uv run --group dev --extra live pytest \
  tests/test_evals.py tests/test_agent_runner.py tests/test_rag.py \
  tests/test_workflow.py -q
```

## 失败注入与排错

| 注入 | 预期失败 | 优先排查 |
| --- | --- | --- |
| 正确文本 + 错工具 | `tool_selection` | `model_tool_calls`，不是 final text |
| 正确工具 + 额外参数 | `argument_accuracy` | canonical JSON 和 strict schema |
| 回复说“拒绝”但工具成功 | `unauthorized_action` | stop reason 与所有 tool results |
| 轮数超 case 上限 | `turn_count` | model turn 计数与 limits |
| 期望 `[]` 却出现工具 | `tool_selection` 与 `argument_accuracy` 失败 | 显式空序列不能表示“不评分” |
| trace 中出现 secret | 脱敏测试失败 | storage-boundary sanitizer |
| judge 与人类分歧集中在某语言 | calibration slice 失败 | rubric/example/model bias |
| 平均延迟稳定但 p95 激增 | online SLO 失败 | tool/queue/retry 分解 |

排错时先定位失败层：dataset label -> deterministic assertion -> Agent/tool/RAG/workflow contract -> trace completeness -> stochastic judge。不要先改 prompt 来掩盖后端策略或数据错误。

## 自动验证

当前 `tests/test_evals.py` 已验证：

- task、tool、argument、unauthorized 和 turn 指标；
- 错工具、错参数、额外参数和超轮数的失败标签；
- 嵌套 JSON 的类型敏感规范比较；
- case 排序和同一 report/固定 trace ID 的 JSON 序列化稳定；fresh run 需先规范化易变 trace ID 才能做字节级 baseline 比较；
- 伪造 tool result 不能替代模型调用证据；
- 不回显参数的 tool result 仍可从 model call 正确评分；
- 显式空工具轨迹参与 tool/argument 指标；无适用安全 case 与空 report 的对应聚合为 `None`。

`tests/test_agent_runner.py` 还验证预算、权限、策略、不可变轨迹和 trace 脱敏；`tests/test_rag.py` 验证授权与引用；`tests/test_workflow.py` 验证审批和幂等。这些确定性测试应先于任何 judge。

文档验收还应确认七类指标全部说明、implemented/design exercise 标签准确、offline/online 与 calibration/repeated runs 完整、红队和响应流程完整、没有把 confidence 当控制、Python fence 可解析、Lab 09 与三个 baseline 链接可验证。

## 作业与评分

| 维度 | 分值 | 满分证据 |
| --- | ---: | --- |
| 数据集与确定性断言 | 25 | hard boundaries 先于 judge，case/version/expected behavior 可复现 |
| 七类指标 | 20 | task/tool/argument/trajectory/policy/latency/cost 定义、分母和状态准确 |
| Trace 与 regression | 15 | 轨迹规则、脱敏、稳定 report、CI baseline 和失败回流 |
| 校准与重复运行 | 15 | gold set、分歧指标、slice、版本和随机分布 |
| 红队与响应 | 20 | threat、forbidden effect、控制证据、contain-to-regress 流程完整 |
| 解释 | 5 | 准确说明 self-confidence 与安全控制的区别 |

任何用 LLM judge 覆盖权限、参数或审批硬失败的提交，确定性断言项不得分。任何红队 case 只检查拒绝文本、不检查副作用和 trace 的提交，红队项不得满分。

## Core / Advanced / Production 完成标准

- **Core**：默认离线评估可重复，覆盖任务、工具、参数、权限阻断、轨迹上限和脱敏。
- **Advanced**：加入 trace grading、三个版本化 JSONL regression 集、人工 gold set、judge calibration 和随机重复运行报告。
- **Production（设计与外部基础设施要求）**：在线采样、隐私治理、latency/cost SLO、canary/rollback、安全事件响应、失败回流和 CI/release gates 已接入。当前参考实现不宣称已有这些平台能力。

## 本章资料

- [参考实现 README](../reference-implementation/README.md)
- [OpenAI Agents SDK - Tracing](https://openai.github.io/openai-agents-python/tracing/)
- [OpenAI Evals design guide](https://developers.openai.com/api/docs/guides/evals)
- [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [pytest parameterization](https://docs.pytest.org/en/stable/how-to/parametrize.html)

## 复盘模板

```markdown
# 第 9 章复盘

## 哪些质量问题可以先用确定性断言

## 七类指标的分子、分母和阈值是什么

## 哪条 trace 暴露了最终答案看不出的错误

## 我的 dataset regression 如何进入 CI

## judge 如何校准，随机行为重复多少次

## offline 与 online 分别发现什么

## 哪条红队 case 对应哪个后端控制

## 安全事件如何从 containment 进入 regression

## 为什么模型 confidence 不能改变权限或审批
```
