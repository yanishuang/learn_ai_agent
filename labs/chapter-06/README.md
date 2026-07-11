# Lab 06：有边界的单 Agent Runtime

## 目标

验证 application-owned loop 的 turn/tool/token/time 预算、停止原因、权限终止、重复工具保护、session 隔离和 trace 脱敏。

## 默认离线步骤

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_agent_runner.py -q
```

预期形状：runner 测试全部通过；输出只含 pytest 摘要，不要求固定 trace ID。

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_agent_runner.py -q -k normal_order_fixture
```

预期轨迹形状：2 个 model turns、1 个 `query_order_status` model call、1 个成功 tool result、`stop_reason=completed`。

## 故意失败

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_agent_runner.py -q -k 'repeat_fixture or max_turns or tool_call_budget or output_token_budget'
```

fixtures 故意制造重复调用或超预算。预期停止形状分别包含 `repeated_tool_call`、`max_turns`、`max_tool_calls`、`max_output_tokens`，并且超界动作/内容不执行或不持久化。

## 调试顺序

1. 先看 `stop_reason`，再看最终文本。
2. 对比 `model_turn_count`、`model_tool_calls` 和实际 `tool_results`。
3. 检查 fingerprint 是否基于 canonical tool name + arguments。
4. 检查 permission/policy/validation failure 是否 terminal。
5. 检查相同 session ID 是否仍按 tenant/user 分区，trace 是否写入前脱敏。

## 默认验证

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_agent_runner.py tests/test_evals.py -q
```

预期形状：runner 与 trajectory evaluator 全部通过，退出码 0。

## 可选 Live 扩展（显式付费）

设置总门禁后，学习者可创建 bounded Live comparison，必须沿用 `RunLimits`、strict tools、trusted context 和重复运行预算。先创建测试/runner 文件，再执行该 learner-created command；不得在 Core 命令中启用 Live，也不得以提高 limits 掩盖循环问题。

## 提交证据

正常与四类 budget stop shape、一次权限拒绝、session/trace 断言、失败根因和 A6 评分。
