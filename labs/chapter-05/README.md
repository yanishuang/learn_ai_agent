# Lab 05：严格工具与可信执行上下文

## 目标

证明模型只能提供 `order_id`，tenant/user/permission 来自 `RunContext`，无权限和未知参数在 handler 边界被结构化拒绝。

## 默认离线步骤

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_tools.py -q
```

预期形状：`10 passed`；覆盖严格 schema、可信 identity、permission、unknown tool 和 trace redaction。

```bash
cd reference-implementation
uv run python - <<'PY'
import asyncio
from agent_course.core import RunContext
from agent_course.tools.orders import QueryOrderStatusTool

async def main():
    context = RunContext(user_id="learner", tenant_id="tenant-1", request_id="lab-05", permissions=frozenset({"orders:read"}))
    result = await QueryOrderStatusTool().execute(
        {"order_id": "O1001"}, context=context
    )
    print(result.model_dump_json())

asyncio.run(main())
PY
```

预期形状：`success=true`、`code="OK"`，output 含 order/status/tenant/requested_by；字段值来自可信 context 和本地 fixture。

## 故意失败

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_tools.py -q -k 'missing_permission or override_tenant or unknown_fields'
```

这些测试故意提交缺权限或额外 identity/secret 参数。预期是 `PERMISSION_DENIED` 或 `INVALID_ARGUMENTS`，handler 不执行，pytest 通过。

## 调试顺序

1. 打印 `ToolDefinition.input_schema`，确认 `additionalProperties=false` 且 required 只有 `order_id`。
2. 检查 context 是平台注入，不由模型 JSON 合并。
3. 区分 unknown tool、invalid arguments、permission denied 和业务 not found。
4. 只在幂等边界内重试；权限/校验错误不重试。

## 默认验证

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_tools.py tests/test_agent_runner.py -q -k 'tool or permission or validation_failure'
```

预期形状：选中测试全部通过，结构化拒绝不会变成成功 tool result。

## 可选 Live 扩展（显式付费）

先设置总门禁变量，再由学习者创建一个只暴露相同 strict schema 的 Live tool-selection test。创建步骤必须先写测试文件和固定 expected tool/arguments，再运行；不得让 Live 模型提供 tenant/user/permission，也不得把付费结果加入默认 CI。

## 提交证据

正常与拒绝结果 shape、schema 摘要、handler 未执行证据、一次错误方案解释和 A5/R2 自评。
