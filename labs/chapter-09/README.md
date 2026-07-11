# Lab 09：离线评估、Trace 与红队数据

## 目标

验证 `EvalCase` 合同、稳定聚合、数据集唯一 ID/覆盖、trace grading 和禁止副作用断言。

## 数据合同

- `agent-cases.jsonl` 每行必须直接通过当前 `EvalCase.model_validate()`；该模型 `extra="forbid"`，因此版本放在 `case_id` 的 `agent-v1-` 前缀，不增加 `schema_version` 字段。
- `rag-cases.jsonl` 使用 `rag-case-v1`，输入必须能构造 `RunContext`、`DocumentChunk` 和 `InMemoryRetriever`；runner 比较拒答、稳定 hit 顺序、citation document 和答案片段。synonym case 只验证显式词表替换，不宣称语义检索。
- `security-cases.jsonl` 使用可执行的 `security-case-v1` 红队合同：威胁、确定性 target/fixture、可信 context、单一预期 outcome、禁止副作用、精确 observation、trace 断言、严重度和 owner。

## 默认离线步骤

```bash
cd reference-implementation
uv run python ../evals/run_baseline.py --dataset all
```

预期形状：退出码 0，并输出一个 JSON object；`agent`、`rag`、`security` 各为 `{"passed":12,"total":12}`。runner 实际执行 Agent、RAG、guardrail、tool registry、trace redaction 和 bounded custom model adapters，不只解析 JSON。

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_course_datasets.py tests/test_evals.py -q
```

预期形状：dataset CLI contract 和 evaluator tests 全部通过；rate 仅对适用 case 计算，空类别为 JSON `null`。

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
uv run python ../evals/run_baseline.py --dataset all
uv run --group dev --extra live pytest tests/test_evals.py tests/test_agent_runner.py tests/test_rag.py tests/test_workflow.py tests/test_tools.py -q
```

预期形状：course validator 成功，三个数据集均 12/12，focused security/eval dependencies 全部通过。

## 可选 Live 扩展（显式付费）

先冻结 case/version/model/prompt、设置费用和重复次数，再创建独立 Live evaluator。报告 pass@1、重复通过率、最差 slice、成本/延迟；judge 必须先与人工 gold 校准。Live 不能改写安全硬断言或进入默认 CI。

## 提交证据

dataset count/schema/coverage、eval report shape、一个失败 case 的 failure list、脱敏 trace 规则、A9/R3 自评。
