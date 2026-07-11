# 课程成果地图

本表把课程准备和全部十五章映射到可验收能力。命令均从仓库根目录执行，且只引用当前已经存在的文件。标记为“设计证据”的章节没有虚构专用 lab；其验收依赖评审材料或已有参考实现检查。

| Chapter | Capability | Lab | Automated check | Portfolio evidence | Required in 12 weeks |
| --- | --- | --- | --- | --- | --- |
| [准备](../chapters/00-course-setup.md) | 建立 Python/`uv` 环境，区分 Fake、Live、密钥与成本边界 | 参考实现基线；无专用 lab | [Python 3.12、lock 与 Live gate](#setup-check) | 环境记录、命令输出、Fake/Live 边界说明 | 是（A0） |
| [1](../chapters/01-ai-agent-overview.md) | 区分 Chat、RAG、Tool、Workflow、Agent，界定 Know-Engine Core | 设计证据；无专用 lab | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_core.py tests/test_fake_model.py -q` | 系统边界图、Core/非目标清单、Python/Go 决策卡 | 是（A1） |
| [2](../chapters/02-llm-application-basics.md) | 使用 provider-neutral 模型合同获得确定性回答、结构化边界与失败分类 | [Lab 02](../labs/chapter-02/README.md) | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_fake_model.py -q` | Fake 探针、稳定输出 shape、timeout/invalid-output 解释 | 是（A2） |
| [3](../chapters/03-prompt-and-context-engineering.md) | 版本化 prompt/context，并把不可信内容隔离在权限之外 | 设计证据；无专用 lab | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_course_datasets.py tests/test_evals.py -q` | Prompt 版本、context 清单、注入威胁说明 | 是（A3） |
| [4](../chapters/04-python-ai-application-stack.md) | 建立 `ModelGateway`、Pydantic 合同和 provider-neutral 依赖方向 | 参考实现架构检查；无专用 lab | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_core.py tests/test_import_isolation.py tests/test_live_gates.py -q` | 依赖图、输入输出合同、框架取舍记录 | 是（A4） |
| [5](../chapters/05-tool-calling.md) | 用严格 schema、可信 `RunContext`、权限拒绝和审计结果约束工具 | [Lab 05](../labs/chapter-05/README.md) | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_tools.py -q` | 工具 schema、允许/拒绝样例、脱敏调用证据 | 是（A5） |
| [6](../chapters/06-agent-runtime.md) | 构建受 turn/tool/token/time 预算约束且可解释停止的单 Agent runner | [Lab 06](../labs/chapter-06/README.md) | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_agent_runner.py -q` | bounded run、停止原因、session 隔离、脱敏 trace | 是（A6） |
| [7](../chapters/07-rag-core.md) | 在相关性排序前执行 tenant/user/permission 过滤，并返回真实引用或拒答 | [Lab 07](../labs/chapter-07/README.md) | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_rag.py -q` | 索引样例、权限矩阵、引用与拒答证据 | 是（A7） |
| [8](../chapters/08-workflow-durable-execution.md) | 实现可暂停、审批、恢复、取消、超时且绑定 hash/version/idempotency 的 Workflow | [Lab 08](../labs/chapter-08/README.md) | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_workflow.py -q` | 状态图、checkpoint、审批与冲突重放证据 | 是（A8） |
| [9](../chapters/09-agent-evaluation-observability-security.md) | 用离线数据评估任务、工具、参数、权限、轨迹、拒绝与副作用 | [Lab 09](../labs/chapter-09/README.md) | `cd reference-implementation && uv run python ../evals/run_baseline.py --dataset all` | 版本化 eval 数据、统一报告、红队结果、脱敏 trace | 是（A9） |
| [10](../chapters/10-mcp-integration.md) | 通过受 allowlist、schema、deadline 与 cleanup 约束的 stdio MCP 调用工具 | [Lab 10](../labs/chapter-10/README.md) | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_mcp.py tests/test_tools.py -q` | Server 信任记录、发现/调用输出、timeout 与 cleanup 证据 | 是（A10） |
| [11](../chapters/11-advanced-rag-and-data-routing.md) | 以 baseline 对比高级检索和受治理的数据路由，不扩大权限边界 | 设计/实验提案；无专用 lab | [Standalone RRF assertion](#chapter-11-rrf-check) | baseline、路由决策、收益/成本、权限与 fallback | 否（Advanced） |
| [12](../chapters/12-agent-interoperability.md) | 判断何时采用多 Agent、MCP 或 A2A，并定义协议和失败边界 | 设计证据；无专用 lab | [文档合同检查](#chapter-12-contract-evidence-check)；不声称已实现多 Agent/A2A | 拓扑图、任务合同、身份传播、失败与 fallback 设计 | 否（Advanced） |
| [13](../chapters/13-product-experience-and-production.md) | 完成 API、体验、企业集成、SLO、数据治理与发布评审 | 生产评审证据；无专用 lab | `cd reference-implementation && uv run --group dev --extra live pytest tests/test_api.py tests/test_evals.py -q` | API/事件合同、SLO、威胁模型、故障演练与发布清单 | 是（A11） |
| [14](../chapters/14-know-engine-capstone.md) | 集成并从干净环境重放 Know-Engine M1-M7 | Capstone milestones；无独立 lab 目录 | `cd reference-implementation && uv run --group dev --extra live pytest -q` | 可运行项目、M1-M7 证据包、最终评估与答辩 | 是（A11-A12） |
| [15](../chapters/15-dodo-agent-capstone.md) | 用受约束 specialist 对比 bounded single Agent，并证明收益或回退 | 设计/实验提案；无专用 lab | [文档证据检查](#chapter-15-contract-evidence-check)；不声称 Dodo 代码已存在 | baseline、角色/任务合同、质量与成本对比、fallback | 否（Advanced） |

## Standalone checks

### Setup check

从仓库根目录执行。`uv run python` 验证项目解释器，不依赖宿主机 `python3` 的版本：

```bash
uv lock --check --directory reference-implementation
cd reference-implementation
uv run python -c 'import sys; assert sys.version_info >= (3, 12), sys.version'
uv run --group dev --extra live pytest tests/test_live_gates.py -q \
  -k strict_environment_gate
```

### Chapter 11 RRF check

这是第 11 章当前可独立执行的最小 RRF 合同，不声称 reranker、SQL parser 或生产数据路由已经存在：

```bash
python3 - <<'PY'
def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.__getitem__, reverse=True)

assert reciprocal_rank_fusion([
    ["chunk-b", "chunk-a", "chunk-d"],
    ["chunk-a", "chunk-c", "chunk-b"],
]) == ["chunk-a", "chunk-b", "chunk-c", "chunk-d"]
PY
```

### Chapter 12 contract evidence check

这只检查章节中现有的 framework-neutral 合同与未实现声明，不执行远程 A2A：

```bash
python3 - <<'PY'
from pathlib import Path

text = Path("chapters/12-agent-interoperability.md").read_text()
required = (
    "class SpecialistTask",
    "class SpecialistResult",
    "class HandoffRequest",
    "class RouteDecision",
    "不证明 Registry、agents-as-tools、handoff 或 A2A 已实现",
)
assert all(item in text for item in required)
PY
```

### Chapter 15 contract evidence check

这只检查 Dodo 设计合同和“当前 reference 不提供”的边界，不执行尚不存在的学员项目：

```bash
python3 - <<'PY'
from pathlib import Path

text = Path("chapters/15-dodo-agent-capstone.md").read_text()
required = (
    "RouteDecision",
    "KnowledgeTask",
    "KnowledgeResult",
    "ReportTask",
    "ReportResult",
    "当前 reference 不提供",
)
assert all(item in text for item in required)
PY
```

## 使用规则

- 12 周路线以 [教师 syllabus](../teaching/12-week-syllabus.md) 的 A0-A12 和 [评分量规](../teaching/assessment-rubrics.md) 为最终标准。
- 16-20 周路线只增加恢复时间与可选实验，不改变同一能力的验收命令或阈值。
- 默认检查均使用 Fake、本地内存组件或本地 stdio MCP。Live、Go 和 Advanced 证据必须显式选择，不能替代失败的 Core 检查。
- 新增 lab 前先创建路径、命令和自动化检查，再把承诺写入本表；不要把 learner-created 路径伪装成当前仓库资产。
