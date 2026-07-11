# Lab 09：离线评估、Trace 与红队数据

## 目标

验证 `EvalCase` 合同、稳定聚合、数据集唯一 ID/覆盖、trace grading 和禁止副作用断言。

## 数据合同

- `agent-cases.jsonl` 每行必须直接通过当前 `EvalCase.model_validate()`；该模型 `extra="forbid"`，因此版本放在 `case_id` 的 `agent-v1-` 前缀，不增加 `schema_version` 字段。
- `rag-cases.jsonl` 使用 `rag-case-v1`，输入必须能构造 `RunContext`、`DocumentChunk` 和 `InMemoryRetriever`；expected 比较拒答、稳定 hit 顺序、citation document 和答案片段。
- `security-cases.jsonl` 使用第 9 章的 `security-case-v1` 红队合同：威胁、输入/来源 fixture、可信 context、预期 stop/policy、禁止副作用、trace 断言、严重度和 owner。它是设计级基线，不伪装成当前 evaluator 已实现的 schema。

## 默认离线步骤

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_evals.py tests/test_agent_runner.py -q -k 'evaluate_cases or report or trace_sink'
```

预期形状：选中的 evaluator/report/trace tests 全部通过；rate 仅对适用 case 计算，空类别为 JSON `null`。

```bash
cd reference-implementation
uv run python - <<'PY'
import json
from pathlib import Path
from agent_course.evals import EvalCase

path = Path("../evals/agent-cases.jsonl")
cases = [EvalCase.model_validate(json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
assert len(cases) >= 10
assert len({case.case_id for case in cases}) == len(cases)
print({"dataset": path.name, "cases": len(cases), "schema": "EvalCase"})
PY
```

预期形状：单个 dict，cases 至少 10，schema 为 `EvalCase`。

## 故意失败

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_evals.py -q -k 'wrong_tool_arguments or unexpected_arguments or excess_turns'
```

tests 注入错误参数/额外参数/过多 turns，预期 report 标记对应 failure，pytest 通过。另可在内存复制一个 case ID，`evaluate_cases` 必须在运行前抛 `ValueError`；不要修改数据文件制造失败。

## 调试顺序

1. 逐行 JSON parse，再按具体 contract validate。
2. 检查 `schema_version`/case ID 唯一和 category 覆盖。
3. 确认 expected 字段对应当前 evaluator 能评分的证据。
4. rate 分母只含适用 case；安全硬失败不交给 judge。
5. 检查 trace 顺序、stop reason、预算和递归脱敏；不比较随机 trace ID。

## 默认验证

```bash
python3 scripts/validate_course.py
cd reference-implementation
uv run --group dev --extra live pytest tests/test_evals.py tests/test_agent_runner.py tests/test_rag.py tests/test_workflow.py tests/test_tools.py -q
```

预期形状：course validator 成功，focused security/eval dependencies 全部通过。

## 可选 Live 扩展（显式付费）

先冻结 case/version/model/prompt、设置费用和重复次数，再创建独立 Live evaluator。报告 pass@1、重复通过率、最差 slice、成本/延迟；judge 必须先与人工 gold 校准。Live 不能改写安全硬断言或进入默认 CI。

## 提交证据

dataset count/schema/coverage、eval report shape、一个失败 case 的 failure list、脱敏 trace 规则、A9/R3 自评。
