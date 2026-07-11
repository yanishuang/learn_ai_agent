# 第 15 章：Dodo-Agent 进阶项目

更新时间：2026-07-11
建议学习时间：完成 Know-Engine 后 1-2 周 Optional Advanced
本章产出：一个由单一 Router、KnowledgeAgent 与 ReportAgent 组成的最小多 Agent 系统；分层评估与失败证据；可选的 ResearchAgent、handoff、Registry 和 A2A adoption record。

## 本章定位

Dodo-Agent 是可选进阶项目，不属于必修 12 周路线。它只回答一个问题：把知识回答和报告整理拆成明确 specialist，是否比 bounded single Agent 在质量、职责隔离、成本或可维护性上更好？

第一版必须恰好从一个 Router、KnowledgeAgent 和 ReportAgent 开始。Router 做结构化分派，KnowledgeAgent 返回有引用的知识结果，ReportAgent 把已验证的结构化材料整理为可审核报告。ResearchAgent、handoff、Registry 与远程 A2A 都要等第一版和单 Agent baseline 通过后才进入 Advanced。

明确不做：自动 Agent 生成、任意代码执行、通用/万能 runtime abstraction、自动高风险动作。也不构建 Agent marketplace、自修改 prompt 平台或无限自治团队。

## 前置知识

- Know-Engine Core 的七个里程碑全部通过。
- 学完第 11、12 章，能解释 agents-as-tools、handoff、Workflow、MCP 与 A2A 的边界。
- 已有固定 eval set、脱敏 trace、可信 `RunContext`、`RunLimits` 和受控工具。
- 理解当前 reference 没有 multi-Agent runtime、Router、Registry 或 A2A adapter；本章合同是项目新增实现。

## 学习目标

完成项目后，你应该能够：

1. 为 Router、KnowledgeAgent 与 ReportAgent 定义版本化、`extra="forbid"` 的输入输出合同。
2. 让平台而非模型执行 route，传递可信身份并分配总预算。
3. 分别评估 route、specialist 与端到端结果，并与单 Agent baseline 比较。
4. 控制错误路由、schema drift、循环/重复调用、timeout、取消与部分失败。
5. 在有真实需要时再引入 ResearchAgent、handoff 和 Registry。
6. 准确说明 A2A 1.0 Stable 但 Optional，且 A2A 与 MCP 互补。
7. 拒绝自动 Agent 生成、任意代码、万能 runtime 和自动高风险动作等范围蔓延。

## 核心知识

### 15.1 Core 架构与固定职责

```text
User task -> Router -> KnowledgeAgent -> KnowledgeResult
                    -> ReportAgent    -> ReportResult

Platform owns: RunContext, total budget, dispatch, schemas, trace, cancellation
Workflow owns: approvals, waiting, retries, durable side effects
MCP/tools own: bounded external capabilities, not task ownership
```

Router 只输出 `knowledge`、`report` 或 `clarify`。如果一个请求先取知识再写报告，平台执行固定两步 composition：KnowledgeAgent 先返回严格 `KnowledgeResult`，ReportAgent 只接收允许字段。Router 不生成新 Agent、不写 Python、不选择任意 endpoint 或工具。

KnowledgeAgent 只做 permission-aware retrieval 与受控只读工具，返回 answer、citations、refused、child trace 和 stop reason。ReportAgent 不重新检索、不执行副作用，只把结构化来源组织为 report sections，并保留 citation IDs。高风险动作交给显式 Workflow + 权威审批，本项目不允许 Agent 自动批准或执行。

### 15.2 结构化合同

项目至少固定以下语义：

| 合同 | 必须字段 | 约束 |
| --- | --- | --- |
| `RouteDecision` | route、reason、confidence label | route 仅 knowledge/report/clarify；confidence 不是授权 |
| `KnowledgeTask` | objective、allowed_source_ids | 不含 tenant/user/permissions |
| `KnowledgeResult` | status、answer、citations、trace_id | citation 可回溯；refused 合法 |
| `ReportTask` | objective、knowledge_result、format | 只接收校验后的结构化材料 |
| `ReportResult` | status、sections、citation_ids、trace_id | 不得发明来源或动作 |

身份从父 `RunContext` 传递；specialist 不能请求扩权。父 `RunLimits` 分配给 route 与 child，不能每个 Agent 重置完整 budget。平台校验 child stop reason、schema、citation 与权限证据后才进入下一步。

### 15.3 Router：建议与权威 dispatch

优先使用确定性规则处理明确意图，再用受限分类模型处理剩余 case；低置信度或多义输入返回 `clarify`。模型的 route 只是建议，平台检查 target allowlist、版本、权限、enabled 状态与剩余预算后 dispatch。

Core target 固定写在配置中，不需要 Registry。任何 unknown target、额外字段、disabled Agent、schema mismatch 或预算不足都结构化失败。路由评估至少报告 per-class precision/recall、clarify rate、错误路由成本和 latency，不能只给总体准确率。

### 15.4 最小协作：先 agents-as-tools/固定 composition

Core 保留 orchestrator 所有权。KnowledgeAgent 和 ReportAgent 可作为 typed specialist functions 或 agents-as-tools 调用；用户只看到一个父 run。固定 composition 比自由 handoff 更容易控制上下文、预算和取消。

传递最小上下文：objective、允许 source IDs、结构化结果和 trace link。不要传整个聊天历史、隐藏 prompt、secrets、所有检索 chunk 或全部 tool registry。父取消要传播到活动 child；child timeout 计入父 deadline；部分失败按预先声明的 fail/clarify/partial policy 处理。

### 15.5 分层评估与单 Agent baseline

必须保留 Know-Engine bounded single Agent baseline，使用同一数据集和预算比较：

- Router：route、clarify、unknown/disabled target、latency；
- KnowledgeAgent：retrieval/citation、refusal、权限、tool/argument、budget；
- ReportAgent：结构完整、citation preservation、无 unsupported claim；
- composition：任务成功、总 turns/tools/tokens/time、取消、失败传播、parent/child trace；
- baseline delta：质量、p95 latency、成本、失败率和维护复杂度。

只有至少一个预注册指标显著改善且新增风险可控，才保留多 Agent。否则项目的正确结论可以是回退到单 Agent。

### 15.6 Advanced 1：ResearchAgent

Core 通过后，只有存在“需要受控外部研究且 KnowledgeAgent 不应拥有这些工具”的证据，才增加 ResearchAgent。它使用 endpoint/domain allowlist、egress/SSRF 控制、引用合同、时间/费用预算和不可信内容隔离；结果先校验再给 ReportAgent。

ResearchAgent 不能浏览任意内网、下载并执行代码、安装包、读取本机 secrets 或自动发布结果。外部来源内容不能改变 tool policy、route 或权限。

### 15.7 Advanced 2：handoff 与 Registry

只有 specialist 必须直接接管会话、独立追问时才采用 handoff。请求固定 target、objective、reason、allowed context IDs 和 remaining handoffs；平台维护 visited set、最大深度、owner、parent/child run 和预算。循环、禁用 target、版本不兼容与权限不相交都停止。

Registry 只在 Agent 数量、独立部署或版本治理产生真实需要时加入。至少记录 stable ID、version、owner、input/output schema hash、allowed tools/data、required permissions、risk、maturity、eval version、enabled、timeout 和 endpoint allowlist。更新要审核与原子切换；run 固定实际版本。Registry 不是自动生成或动态下载 Agent 的目录。

### 15.8 Advanced 3：A2A 1.0 Stable，但 Optional

截至[生态成熟度矩阵](../docs/ecosystem-maturity.md)的 2026-07-11 记录，A2A Protocol 1.0 是 **Stable**。它仍然是 Optional，因为协议稳定不等于项目需要跨部署/跨组织远程 Agent 协作。

A2A 只在本地 typed composition 与 handoff 已通过、且远程边界有明确 owner/identity/version/SLO 时评估。Agent Card/能力描述按不可信元数据处理；endpoint allowlist、认证、业务授权、delegation、tenant policy、schema、幂等、timeout、取消、审计和 fallback 缺一不可。

MCP 接工具/资源/上下文，A2A 处理远程 Agent 任务协作；A2A 不替代 MCP，也不继承 MCP 工具授权。A2A adapter 与具体框架 integration 的成熟度必须分别核实。Core 和默认离线 suite 不依赖 A2A SDK 或网络。

### 15.9 永久范围护栏

下列能力在 Core、Advanced、Production 都不因“做得更完整”而自动进入范围：

| 排除项 | 原因 | 合法替代 |
| --- | --- | --- |
| 自动 Agent 生成 | 无 owner、权限、eval 与供应链边界 | 人工评审的版本化 Agent 定义 |
| 任意代码执行 | 直接扩大 RCE、数据与 secret 风险 | allowlisted typed tools、sandboxed 专项系统另立项目 |
| universal runtime abstraction | 过早抽象，掩盖不同框架语义 | provider/framework-neutral contracts + 少量 adapter |
| 自动高风险动作 | 模型不能授权自己 | durable Workflow、payload-bound 人工审批、reconciliation |

同样禁止无限 handoff、自扩权、任意 MCP/A2A endpoint、把完整上下文广播给所有 Agent，以及把模型 confidence 用作安全门。

### 15.10 可独立演示的项目里程碑

| 里程碑 | 范围 | 独立证据命令 |
| --- | --- | --- |
| D1 baseline/contracts | 单 Agent baseline + 五个 schema | `uv run pytest tests/dodo/test_contracts.py tests/dodo/test_baseline.py -q` |
| D2 Router + KnowledgeAgent | knowledge/clarify、权限 citation | `uv run pytest tests/dodo/test_router.py tests/dodo/test_knowledge_agent.py -q` |
| D3 ReportAgent/composition | typed knowledge -> report、引用保留 | `uv run pytest tests/dodo/test_report_agent.py tests/dodo/test_composition.py -q` |
| D4 eval/failure demo | 分层指标、budget/cancel/trace | `uv run python -m dodo.eval --dataset evals/dodo-core.jsonl --compare single-agent` |
| D5 Optional Advanced | Research/handoff/Registry/A2A adoption gate | 分别使用显式 `tests/dodo/advanced/` 命令，不进入 Core gate |

这些 `dodo.*` 命令和目录是学员项目必须实现的接口，当前 reference 不提供。每个 milestone 的 `evidence/dN/` 保存命令、machine-readable 输出、成功与失败 case、版本和限制。

## 教师演示

1. 用同一数据集先运行 bounded single Agent baseline。
2. 展示 Router 的 strict decision，平台拒绝 unknown target，并在低置信度时 clarify。
3. 运行 KnowledgeAgent，检查权限、citation 与 child trace。
4. 把校验后的 `KnowledgeResult` 交给 ReportAgent，证明 citation IDs 保留且没有额外工具。
5. 注入 child timeout、schema extra field 和父取消，展示总预算与所有权。
6. 比较 baseline 后再决定是否保留拆分；最后说明 A2A Stable 但 Optional。

## 学员实验

1. 建立 D1 单 Agent baseline 与 strict contracts。
2. 完成 D2：一个 Router 只分到 KnowledgeAgent 或 clarify。
3. 完成 D3：ReportAgent 只消费 validated `KnowledgeResult`，形成可审核报告。
4. 完成 D4：specialist、route、composition 与 baseline 四层报告。
5. 注入错误路由、越权、schema drift、citation 丢失、timeout、cancel 和预算耗尽。
6. 写 go/no-go：保留多 Agent、缩小拆分或回退单 Agent。
7. Optional Advanced：按顺序评估 ResearchAgent、handoff、Registry，最后才是 A2A adoption record。

## 失败注入与排错

| 注入 | 预期结果 | 首查位置 |
| --- | --- | --- |
| Router unknown target | 平台拒绝，不 dispatch | route schema/allowlist |
| Router 低置信度 | `clarify` | route policy |
| child 请求额外权限 | 权限不扩大，动作拒绝 | inherited RunContext |
| KnowledgeAgent 跨 tenant citation | case 失败且无内容泄露 | retrieval filter |
| ReportAgent 发明 citation | output validation/eval 失败 | report contract |
| child extra field/schema drift | adapter 隔离 | schema hash/version |
| child timeout | 父 run 结构化失败/partial | budget controller |
| 父取消 | 传播到活动 child | cancellation tree |
| handoff A -> B -> A | visited/depth guard 停止 | handoff controller |
| Agent Card prompt injection | 仅作不可信 metadata | A2A registry |
| 高风险动作请求 | 转 Workflow/审批，不自动执行 | risk policy |

排错顺序：父 run/owner、route decision、target/version、可信 context、child input、child trace/budget、child output、composition、UI。远程 Advanced 再查 endpoint、协议、认证与业务授权。

## 自动验证

先验证可复用的当前 Agent/tool/RAG/eval 合同：

```bash
cd reference-implementation
uv run --group dev --extra live pytest \
  tests/test_agent_runner.py tests/test_tools.py tests/test_rag.py \
  tests/test_evals.py tests/test_workflow.py tests/test_mcp.py -q
```

Dodo Core gate 必须由项目补充并保持离线：

```bash
uv run pytest \
  tests/dodo/test_contracts.py tests/dodo/test_baseline.py \
  tests/dodo/test_router.py tests/dodo/test_knowledge_agent.py \
  tests/dodo/test_report_agent.py tests/dodo/test_composition.py -q
uv run python -m dodo.eval \
  --dataset evals/dodo-core.jsonl --compare single-agent
```

Advanced remote/A2A tests 使用独立 marker 和凭据 gate，失败不能阻塞 Core。当前 reference suite 不证明任何 multi-Agent、Registry 或 A2A 行为。

## 作业与评分

| 项目 | 权重 | 评分证据 |
| --- | ---: | --- |
| baseline 与 contracts | 20 | 同数据预算、strict schemas、版本 |
| Router + KnowledgeAgent | 20 | route/clarify、权限、citation |
| ReportAgent + composition | 20 | 结构化传递、引用保留、无越权工具 |
| 分层 eval 与比较 | 25 | specialist/route/e2e/baseline delta |
| 失败、预算与 trace | 15 | timeout/cancel/schema/owner 证据 |

Advanced 加分独立记录，不可补偿 Core 权限或合同失败。多个 Agent 自由聊天、没有 baseline/指标/停止条件，不能及格。

## Core / Advanced / Production 完成标准

| 等级 | 完成标准 |
| --- | --- |
| Core | 恰好一个 Router、KnowledgeAgent、ReportAgent；typed composition、可信 context、总预算、分层 eval、single-Agent baseline、失败/取消/trace 证据。 |
| Advanced | Core 通过后按证据加入 ResearchAgent，再评估 handoff 与 Registry；A2A 1.0 可做 Stable-but-Optional 远程实验，且有 fallback。 |
| Production | 每个 Agent 有 owner/version/SLO/eval；身份、tenant、quota、审计、兼容、取消和降级跨边界成立；高风险动作仍由 Workflow + 人工审批。永久排除自动 Agent 生成、任意代码、万能 runtime 和自动高风险动作。 |

## 本章资料

- [第 12 章：多 Agent 设计与互操作](12-agent-interoperability.md)
- [Know-Engine 必做项目](14-know-engine-capstone.md)
- [生态成熟度矩阵](../docs/ecosystem-maturity.md)
- [A2A 1.0 announcement](https://a2a-protocol.org/latest/announcing-1.0/)
- [A2A released specification](https://a2a-protocol.org/dev/specification/)
- [OpenAI Agents SDK: Agent orchestration](https://openai.github.io/openai-agents-python/multi_agent/)
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)

框架文档只用于可选 adapter 比较。采用前按矩阵记录精确 artifact/package、版本、语言、upstream maturity、验证日期和 fallback；不得把产品家族的一个成熟度标签推给所有 integration。

## 复盘模板

1. 哪个预注册指标证明拆分优于 single Agent；若没有，为何回退？
2. Router、KnowledgeAgent、ReportAgent 的 owner、权限、输入输出和停止条件是什么？
3. 哪条结构化合同阻止了上下文泄漏、citation 伪造或预算失控？
4. ResearchAgent、handoff、Registry 或 A2A 分别解决了什么真实问题？
5. 为什么 A2A Stable 仍然 Optional，MCP 与 A2A 的授权边界如何分开？
6. 四项永久排除范围是否被任何“方便”的实现绕过？
