# 教师指南

配套路线见 [12 周 syllabus](12-week-syllabus.md)，统一验收和评分见 [评估量规](assessment-rubrics.md)。每周演示命令从仓库根目录执行；所有 `pytest` 命令均为离线 Fake/本地依赖路径，不要求 API key。

## 第 1 周：环境与边界

- 准备：通读课程准备、第 1 章和 A0-A1；确认 `python3`、`uv` 可用。
- 15 分钟 opener：用 knowledge/action/autonomy/state/risk 区分 chat、RAG、tool、Workflow、Agent。
- 演示：`python3 scripts/validate_course.py && python3 -m pytest tests/test_validate_course.py -q`。输出形状为 validator 成功行和 pytest 全通过摘要。
- Lab block：学员画 Know-Engine Core/非目标边界并运行基线。
- 失败注入：把一个本地 Markdown 链接临时指向不存在路径，观察 validator 报文件与目标；演示后撤销课堂临时改动。
- 讨论：为什么多 Agent 不是“更高级所以默认更好”？
- Exit ticket：写出 Fake 与 Live 的两个边界，以及 A0/A1 一条证据。
- 作业/评分：环境记录与范围图；A0-A1，R1/R2/R7。

## 第 2 周：模型应用基础

- 准备：第 2 章、[Lab 02](../labs/chapter-02/README.md)、精确 Fake fixtures。
- 15 分钟 opener：provider-neutral gateway、消息角色、结构化输出与错误分类。
- 演示：`cd reference-implementation && uv run --group dev --extra live pytest tests/test_fake_model.py tests/test_live_gates.py -q -k 'plain_answer or strict_environment_gate'`。
- Lab block：运行直接回答、timeout 和 Live gate 探针。
- 失败注入：缺少 `AGENT_COURSE_LIVE_TESTS=1` 时构造 Live adapter，预期请求前拒绝。
- 讨论：为什么 Fake 可证明应用合同，却不能证明真实模型质量？
- Exit ticket：列出构造 Live adapter 的三个必要变量。
- 作业/评分：Lab 02 evidence；A2，R1/R5/R6/R7。

## 第 3 周：Prompt 与 Context

- 准备：第 3 章；准备一段含恶意指令的“检索文档”。
- 15 分钟 opener：instruction/context/data 分层与版本化。
- 演示：`cd reference-implementation && uv run --group dev --extra live pytest tests/test_agent_runner.py -q -k high_risk_input`。
- Lab block：为正常输入与注入输入写合同断言，记录 prompt/context 版本。
- 失败注入：把文档中的“忽略系统指令”错误拼入 system instruction，分析权限为何仍必须由后端控制。
- 讨论：内容隔离和授权隔离分别防什么？
- Exit ticket：写出一条不能由 prompt 承担的控制。
- 作业/评分：prompt 版本、反例与威胁说明；A3，R2/R3/R7。

## 第 4 周：Python 应用架构

- 准备：第 4 章；复核 `ModelGateway`、`CourseApplication` 边界。
- 15 分钟 opener：依赖反转、Pydantic 边界、composition root。
- 演示：`cd reference-implementation && uv run --group dev pytest tests/test_core.py tests/test_import_isolation.py -q`。
- Lab block：画 provider、domain、API、tool、trace 依赖方向并标注 optional import。
- 失败注入：讨论在 core 模块顶层 import `openai` 如何破坏无 Live extra 的离线路径。
- 讨论：Pydantic schema 和业务授权各自负责什么？
- Exit ticket：指出一个只应出现在 composition root 的依赖。
- 作业/评分：架构图与合同说明；A4，R1/R6/R7。

## 第 5 周：受控工具

- 准备：第 5 章和 [Lab 05](../labs/chapter-05/README.md)。
- 15 分钟 opener：严格 schema、effect、idempotency、可信 context。
- 演示：`cd reference-implementation && uv run --group dev --extra live pytest tests/test_tools.py -q`。
- Lab block：正常 lookup、缺权限、未知字段三条轨迹。
- 失败注入：模型参数加入 `tenant_id=attacker`，预期 handler 前 `INVALID_ARGUMENTS`。
- 讨论：读工具为什么仍需要权限、审计和 timeout？
- Exit ticket：说明 tenant 为什么不能来自模型参数。
- 作业/评分：Lab 05 evidence；A5，R1/R2/R3/R5。

## 第 6 周：Bounded Agent Runtime

- 准备：第 6 章和 [Lab 06](../labs/chapter-06/README.md)。
- 15 分钟 opener：循环所有权、limits、stop reason、session 和 trace。
- 演示：`cd reference-implementation && uv run --group dev --extra live pytest tests/test_agent_runner.py -q`。
- Lab block：正常 tool loop、重复调用、max turns、permission denial。
- 失败注入：`[fixture:repeated-order-call]`，预期只执行一次工具后停止。
- 讨论：为什么最终答案正确仍可能是失败轨迹？
- Exit ticket：列出四类预算和一个服务端证据字段。
- 作业/评分：Lab 06 evidence；A6，R1-R5。

## 第 7 周：权限感知 RAG

- 准备：第 7 章和 [Lab 07](../labs/chapter-07/README.md)。
- 15 分钟 opener：授权先于相关性、稳定排序、真实 citation、拒答。
- 演示：`cd reference-implementation && uv run --group dev --extra live pytest tests/test_rag.py -q`。
- Lab block：同租户可答、跨租户不可见、同义词和引用验证。
- 失败注入：加入更高相似但其他 tenant 的 chunk，预期结果仍不包含它。
- 讨论：为什么应用层 post-filter 已经太晚？
- Exit ticket：写出 citation 必须来自哪些 hit 字段。
- 作业/评分：Lab 07 evidence；A7，R1-R3/R7。

## 第 8 周：Durable Workflow

- 准备：第 8 章和 [Lab 08](../labs/chapter-08/README.md)。
- 15 分钟 opener：状态机、checkpoint、approval hash、idempotency。
- 演示：`cd reference-implementation && uv run --group dev --extra live pytest tests/test_workflow.py -q`。
- Lab block：start、approve、resume、cancel、timeout 重放。
- 失败注入：用错误 payload hash 审批，预期结构化异常且不执行副作用。
- 讨论：模型输出应该在哪个 checkpoint 固化？
- Exit ticket：区分 `workflow_version` 与 `state_version`。
- 作业/评分：Lab 08 evidence；A8，R1-R5。

## 第 9 周：Eval、Trace 与安全

- 准备：第 9 章、[Lab 09](../labs/chapter-09/README.md) 和三个 JSONL 数据集。
- 15 分钟 opener：确定性断言、适用分母、trace grading、red team。
- 演示：`cd reference-implementation && uv run python ../evals/run_baseline.py --dataset all`。
- Lab block：加载 agent cases、验证 schema/唯一 ID，检查 security case 的禁止副作用。
- 失败注入：复制一个 case ID，预期唯一性检查失败。
- 讨论：哪些指标绝不能交给 LLM judge 决定？
- Exit ticket：说明 fresh trace ID 为什么不能逐字比较。
- 作业/评分：Lab 09 evidence；A9，R1-R5/R7。

## 第 10 周：MCP 信任治理

- 准备：第 10 章和 [Lab 10](../labs/chapter-10/README.md)。
- 15 分钟 opener：host/client/server、transport、schema 和 trust boundary。
- 演示：`cd reference-implementation && uv run python -m agent_course.mcp.client O1001 --timeout 5`。
- Lab block：发现/调用 fixed allowlist 工具，验证 structured content 与 cleanup。
- 失败注入：使用不存在订单，观察业务错误形状，不把它误判为 transport failure。
- 讨论：为什么 MCP 工具描述和输出仍是不可信数据？
- Exit ticket：列出 client 在调用前后的四个验证点。
- 作业/评分：Lab 10 evidence；A10，R1-R5。

## 第 11 周：生产评审与集成

- 准备：第 13、14 章；按 M1-M6 建立 review 表。
- 15 分钟 opener：implemented/tested 与 design-only、SLO/容量/成本/回滚。
- 演示：`cd reference-implementation && uv run --group dev --extra live pytest tests/test_rag.py tests/test_agent_runner.py tests/test_workflow.py tests/test_mcp.py tests/test_evals.py -q`。
- Lab block：按 milestone 独立重跑，做一次 permission 或 timeout 故障演练。
- 失败注入：让一个 M6 security case 失败，要求阻断发布而不是解释豁免。
- 讨论：生产 review 中哪个 open risk 必须由 owner 接受？
- Exit ticket：标记一项 implemented/tested 和一项 design-only。
- 作业/评分：M1-M6 evidence 与生产 review；A11，R1-R7。

## 第 12 周：Know-Engine Core 答辩

- 准备：第 14 章；准备干净环境、固定数据和演示计时表。
- 15 分钟 opener：从用户价值到权限、恢复、评估和生产边界的证据链。
- 演示：`cd reference-implementation && uv lock --check && uv run --group dev --extra live pytest -q && uv run --group dev --extra live ruff check .`。
- Lab block：M1-M7 独立重放、同伴红队和答辩。
- 失败注入：评审者选择跨租户、审批 replay 或 denial-of-wallet case，团队现场定位。
- 讨论：为什么 Core 排除 graph/multi-Agent，何时才值得进入 enrichment？
- Exit ticket：给出一个通过证据、一个残余风险、一个 rollback 信号。
- 作业/评分：最终 Know-Engine；A12 与最终项目 rubric。

## Live 演示规则

Live 不是任何一周的默认演示。只有教师明确宣布付费扩展、确认账户限额，并按参考 README 设置 `AGENT_COURSE_LIVE_TESTS=1`、非空 `OPENAI_API_KEY`、显式 `OPENAI_MODEL` 后才能运行。不得投影或记录密钥；结果按形状与重复运行统计解释，不承诺固定文本。
