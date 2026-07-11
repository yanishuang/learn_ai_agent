# 第 14 章：Know-Engine 毕业项目

更新时间：2026-07-11
建议学习时间：2 周整合与答辩
本章产出：一个必做、可离线复现的企业知识任务系统；七个可独立演示的里程碑证据包；一份红队报告和生产就绪评审。

## 本章定位

Know-Engine 是课程必做毕业项目。它用一个边界清晰的企业知识任务串联文档摄取、引用、权限感知 RAG、有预算的单 Agent、Workflow、MCP、评估、trace 和生产评审。项目复用前面章节与 `reference-implementation/`，不另起一套平行合同。

Core 的目标是证明一条受控单 Agent 链路有价值且可复现。图数据库、知识图谱、LangGraph、多 Agent、handoff、A2A、自动 Agent 生成和复杂前端都不属于 Core；不要用扩展项替代权限、评估和失败恢复。

## 前置知识

- 完成第 1-10 章与第 13 章 Core；第 11、12 章是 Optional Advanced。
- 能运行 `reference-implementation/` 的 Fake Model 离线 suite。
- 理解当前 `DocumentChunk`/`RagCitation`、`RunContext`/`RunLimits`、`AgentResult`、`ResearchWorkflow`、MCP stdio client/server 和 `EvalReport`。
- 接受当前 reference 是 in-memory teaching scaffold：没有完整 ingestion pipeline、持久数据库、异步队列或统一 Workflow API。

## 学习目标

完成项目后，你应该能够：

1. 从固定样例文档复现环境和索引产物。
2. 返回可定位、可授权、与答案一致的 citation。
3. 在相关性计算前执行 tenant、user allowlist 和 permission 过滤。
4. 用 `BoundedAgentRunner` 和版本化 Workflow 完成固定业务任务。
5. 通过 MCP 接入一个 allowlisted、结构化、超时受限的能力。
6. 用固定数据集评估任务、工具、权限、引用、预算与失败，并形成红队闭环。
7. 用威胁模型、容量/成本、保留、incident、CI 与 rollback 证据完成生产评审。

## 核心知识

### 14.1 项目任务与范围

选择一个可在样例文档中验证的企业任务，例如“按员工所在地与差旅等级解释住宿标准并生成带引用答复”。每个任务必须有：明确用户、允许数据、可信身份、正确答案/拒答条件、允许工具、预算、审批点和可测价值。

Core 架构保持简单：

```text
Client -> trusted API/RunContext -> bounded single Agent
                                  -> permission-aware Retriever -> citations
                                  -> versioned Workflow/approval
                                  -> allowlisted MCP or local tool
                                  -> redacted trace + offline eval
```

当前 reference 可直接提供 typed contracts 与确定性 tests；学员 capstone 负责补齐 ingestion、composition、持久化选择和产品表面。每个新增组件都要标注“已实现并测试”或“Production 设计待实现”。

### 14.2 统一证据规则

七个里程碑必须独立 demo，不能只在最终视频中一闪而过。每个 `evidence/mN/` 包含：

- `README.md`：精确命令、预期结果、环境与版本；
- machine-readable 输出或测试报告；
- 一条成功 case、一条失败/拒绝 case；
- 本里程碑架构变化与已知限制；
- commit SHA、数据/schema/prompt/tool/workflow/eval 版本。

命令必须从干净 clone 可运行；任何 live/paid 命令单独标记，不得成为 Core 通过条件。

### 14.3 M1：可复现设置与样例文档

**交付。** 固定 Python 与 lockfile，保留 `reference-implementation/sample-data/hr-policy.md`，再增加至少两份去敏样例文档和 manifest。manifest 记录 document ID、tenant、版本、content hash、ACL、来源与许可；不得提交真实 secrets 或公司机密。

**独立演示命令。** 先证明 reference 环境，再执行学员的 fixture 检查：

```bash
cd reference-implementation
uv sync --group dev --extra live
uv run --group dev --extra live pytest tests/test_core.py tests/test_fake_model.py -q
test -f sample-data/hr-policy.md
```

学员项目增加：

```bash
uv run python -m know_engine.fixtures verify --manifest sample-data/manifest.json
```

**通过证据。** 离线命令 exit 0；manifest 中每个 hash 与文件一致；缺文件和 hash drift 命令非零退出；记录 `uv.lock` hash。当前 reference 只提供一份样例和环境测试，`know_engine.fixtures` 是 capstone 必须实现的命令，不得声称现有源码已经提供。

### 14.4 M2：摄取与引用

**交付。** 实现确定性 parse、normalize、chunk、index；每个 chunk 保留 `chunk_id`、`document_id`、title、content 与 citation 定位。生产设计再记录 document version、content hash、parser/chunker/embedding version、page/offset 和 publication state。重复摄取相同版本必须幂等，失败版本不能进入当前 published index。

**独立演示命令。**

```bash
uv run python -m know_engine.ingest \
  --manifest sample-data/manifest.json --rebuild
uv run python -m know_engine.query \
  --tenant tenant-1 --user learner --question "员工差旅住宿标准是什么？" \
  --show-citations
uv run --group dev pytest tests/capstone/test_ingestion.py \
  tests/capstone/test_citations.py -q
```

当前 reference citation 合同可先单独证明：

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_rag.py \
  -q -k "source_quote or grounded"
```

**通过证据。** 输出答案带 `[1]`；citation 的 document/chunk/title/quote 可回到原文；重复摄取不重复 chunk；解析失败不污染 published index；篡改 quote 的测试失败。命令和输出保存到 `evidence/m2/`。

### 14.5 M3：权限感知检索

**交付。** API 从可信认证构造 `RunContext`。检索在 relevance scoring 前按 tenant、`allowed_user_ids` 与 `required_permissions` 过滤；工具再次做业务授权。请求 body、query 或模型参数不能提供可信身份。

**独立演示命令。**

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_rag.py tests/test_api.py \
  -q -k "tenant or access or permission or trusted or isolated"
```

capstone 再运行同一问题的权限矩阵：

```bash
uv run python -m know_engine.auth_matrix \
  --cases tests/fixtures/permission-cases.json
```

**通过证据。** 允许用户得到引用；不同 tenant、未 allowlist 用户与缺 permission 用户得到空检索/拒答，不泄露文档存在性；伪造 body 身份返回 validation error；报告列出每个 case 的 trusted context 与 decision，敏感字段脱敏。

### 14.6 M4：有边界的单 Agent 与 Workflow

**交付。** 只用一个 Agent，调用严格注册工具；复用 `RunLimits` 的 turns、tool calls、output tokens 和 total timeout，并保存 typed `stop_reason`、model tool-call evidence 与 trace。固定步骤、审批、等待、恢复、取消和副作用放入 Workflow，不用自由对话模拟 durability。

Workflow state 固定 version；start/approval 使用 idempotency key；审批绑定 run、tenant、workflow version、state version、action 与 payload hash；权限、tenant 和 owner 均由服务端验证。

**独立演示命令。**

```bash
cd reference-implementation
uv run --group dev --extra live pytest \
  tests/test_agent_runner.py tests/test_tools.py tests/test_workflow.py -q
```

capstone 场景命令：

```bash
uv run python -m know_engine.demo bounded-run --fixture permission-denied
uv run python -m know_engine.demo workflow --pause-at approval --resume
```

**通过证据。** 成功 run、预算停止、permission denied 不重试、重复工具调用停止各有 typed result；Workflow 可从 approval checkpoint 恢复且不重复副作用；修改审批 payload、跨租户、过期与重复 idempotency 均被拒绝。明确记录当前 reference Workflow 为 in-memory，Production durability 仍需数据库/engine 与恢复演练。

### 14.7 M5：MCP 集成

**交付。** 接入一个固定 MCP Server，先 list tools、校验 allowlist 与 input/output schema，再调用；设置 total deadline、清理子进程/连接、校验 structured result。身份与业务权限留在 host/server，模型不能通过参数选择 tenant。

**独立演示命令。** 当前 stdio fixture 可直接运行：

```bash
cd reference-implementation
uv run python -m agent_course.mcp.client O1001 --timeout 5
uv run --group dev --extra live pytest tests/test_mcp.py tests/test_tools.py -q
```

**通过证据。** CLI 输出含 `query_order_status` 和 structured result；不存在工具、Server error、无 structured content 与 timeout 均 fail closed；记录 tool/schema hash、transport、deadline 和 cleanup。reference fixture 使用 server-owned 固定教学身份，不是生产 MCP Authorization、consent 或远程 tenant delegation。

### 14.8 M6：评估与红队报告

**交付。** 固定并版本化离线 eval set，至少覆盖正确答案/拒答、citation support、工具选择/参数、permission isolation、stop reason、turn/tool/time budget 和 trace。红队覆盖 prompt injection、越权请求、citation 伪造、恶意工具描述、重复副作用、审批重放、secret 泄漏和成本耗尽。

**独立演示命令。**

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_evals.py \
  tests/test_rag.py tests/test_agent_runner.py tests/test_tools.py -q
```

capstone 生成稳定报告：

```bash
uv run python -m know_engine.eval \
  --dataset evals/core.jsonl --output evidence/m6/eval-report.json
uv run python -m know_engine.redteam \
  --dataset evals/redteam.jsonl --output evidence/m6/redteam-report.json
```

**通过证据。** 报告固定 case order，记录 dataset/config versions、pass/fail、trace ID 和失败分类；CI 阈值预先声明；每个红队发现有 severity、复现、影响、修复、owner 和回归 case。不能用模型自报 confidence 当安全控制或评分真值。

### 14.9 M7：生产就绪评审与最终演示

**交付。** 提交 architecture/data-flow、threat model、身份/权限矩阵、容量/SLO、成本预算、tenant isolation、secrets/workload identity、retention/deletion、incident runbook、CI gates、deployment/rollback 和 open risks。每项标明 implemented/tested 或 design-only。

**独立演示命令。**

```bash
python3 scripts/validate_course.py
cd reference-implementation
uv lock --check
uv run --group dev --extra live pytest -q
uv run --group dev --extra live ruff check .
```

capstone release gate：

```bash
uv run python -m know_engine.release_check \
  --evidence evidence --require milestones=1,2,3,4,5,6,7
```

**通过证据。** 所有离线 gate 通过；从干净环境按顺序 demo 七个里程碑；注入一次失败并从 trace/state 找到根因；展示 kill switch 和 rollback 演练；风险表没有无 owner 的 Critical/High。`release_check` 是项目必须实现的证据检查，不是当前 reference command。

### 14.10 最终演示脚本

15 分钟演示遵循固定顺序：环境与数据 hash；成功 ingestion；授权问答与 citation；同问题越权拒绝；单 Agent budget/tool evidence；Workflow 等待与恢复；MCP structured result；eval/red-team delta；生产风险、kill switch 与 rollback。每一步可单独重跑，不依赖剪辑视频。

## 教师演示

1. 从干净 `uv sync` 运行 Fake Model suite，并解释为何 live model 不是复现前提。
2. 用同一问题展示授权 citation 与未授权拒答。
3. 展示 `AgentResult.model_tool_calls`、`tool_results`、stop reason 与 trace，而不是只展示最终文字。
4. 暂停 Workflow、校验 approval hash、恢复并证明副作用只执行一次。
5. 运行 MCP CLI 和 eval report，最后把一个红队失败转成回归 gate。
6. 对照 production review 标记 reference 的 in-memory 限制。

## 学员实验

按 M1-M7 顺序交付。每个里程碑开独立验收，不允许因后续功能尚未完成而无法 demo。评审者可在任意里程碑停止系统、清理临时状态并按该里程碑 README 重跑。

Core 不得加入图/多 Agent scope。Advanced 只在 Core 全部通过后选择一项：RRF hybrid retrieval、rerank、query rewrite、多源路由或显式启用的 live comparison；必须用 held-out eval 证明收益并记录成本/延迟。Production 重点是控制落地与演练，不是增加框架数量。

## 失败注入与排错

| 里程碑 | 注入 | 必须证明 |
| --- | --- | --- |
| M1 | fixture hash drift | verify 非零退出且指出文件 |
| M2 | parser 中途失败/重复摄取 | published index 不污染、不重复 |
| M3 | 跨 tenant/缺 permission | scoring 前过滤且不泄露存在性 |
| M4 | timeout、重复 tool、approval mismatch | typed stop、无盲重试、无重复副作用 |
| M5 | MCP 无工具/超时/坏 structured result | fail closed 并 cleanup |
| M6 | citation 伪造/prompt injection | 报告失败并生成回归 case |
| M7 | 错误 config 发布/provider outage | kill switch、降级、rollback 证据 |

排错顺序：fixture/version、可信身份、publication/ACL、retrieval evidence、Agent budget/tool evidence、Workflow state/idempotency、MCP contract、eval/trace、产品投影。不要用换模型掩盖合同错误。

## 自动验证

Core 的统一 reference baseline：

```bash
cd reference-implementation
uv run --group dev --extra live pytest \
  tests/test_core.py tests/test_fake_model.py tests/test_rag.py \
  tests/test_tools.py tests/test_agent_runner.py tests/test_workflow.py \
  tests/test_mcp.py tests/test_evals.py tests/test_api.py -q
```

最终完整命令：

```bash
python3 scripts/validate_course.py
cd reference-implementation
uv lock --check
uv run --group dev --extra live pytest -q
uv run --group dev --extra live ruff check .
```

reference tests 只证明当前 scaffold。`tests/capstone/`、`know_engine.*` CLI、持久存储、生产身份和 release evidence 是学员新增范围，必须在项目仓库中真实存在后才能计分。

## 作业与评分

| 里程碑 | 分值 | 独立验收重点 |
| --- | ---: | --- |
| M1 设置/样例 | 10 | clean setup、hash、无 secrets |
| M2 摄取/引用 | 15 | 幂等、publication、可回溯 quote |
| M3 权限检索 | 15 | filter-before-score、拒绝矩阵 |
| M4 Agent/Workflow | 20 | budgets、typed stops、approval、恢复 |
| M5 MCP | 10 | allowlist、schema、timeout、cleanup |
| M6 Eval/红队 | 15 | 固定数据、阈值、修复闭环 |
| M7 Production/答辩 | 15 | 威胁、运营、rollback、已知风险 |

任何一个里程碑没有命令与机器可读证据，不能用最终演示补分。缺少 permission isolation、威胁模型、红队报告或离线 tests 中任一项，项目不能判定完成。

## Core / Advanced / Production 完成标准

| 等级 | 完成标准 |
| --- | --- |
| Core | M1-M7 全部独立可演示；固定文档、引用、权限 RAG、一个 bounded Agent、一个 Workflow、一个 MCP integration、离线 eval/红队和 production review；明确排除 graph 与 multi-Agent。 |
| Advanced | Core 通过后，仅用测量证明采用高级 RAG/多源路由或显式 live comparison；记录成熟度、版本、成本、延迟与 fallback。A2A/多 Agent 仍不属于本项目要求。 |
| Production | 持久状态、真实 workload identity、数据库/对象/向量租户隔离、quota/SLO、retention/deletion、incident 与 rollback 已实现和演练；风险有 owner 与期限。 |

## 本章资料

- [参考实现运行说明](../reference-implementation/README.md)
- [第 7 章：RAG 核心](07-rag-core.md)
- [第 8 章：Workflow 与持久化执行](08-workflow-durable-execution.md)
- [第 9 章：Agent 评估、可观测性与安全](09-agent-evaluation-observability-security.md)
- [第 10 章：MCP 集成](10-mcp-integration.md)
- [第 13 章：产品体验、企业集成与生产治理](13-product-experience-and-production.md)
- [生态成熟度矩阵](../docs/ecosystem-maturity.md)
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)

## 复盘模板

1. 哪条用户任务和指标证明 Know-Engine 有价值？
2. 七个里程碑能否在干净环境分别演示，证据在哪里？
3. 哪个身份/权限边界阻止了真实错误？
4. 哪次失败改变了 ingestion、Workflow、MCP 或 release 设计？
5. 哪些是当前实现，哪些仍是 Production design？
6. 为什么 Core 没有加入 graph 或 multi-Agent，Advanced 投资是否有测量依据？
