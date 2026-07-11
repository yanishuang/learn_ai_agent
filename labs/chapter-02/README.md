# Lab 02：Fake 模型与显式 Live 门禁

## 目标

验证精确 Fake fixture、provider-neutral 模型合同、确定性直接回答、原生结构化输出、Responses 剩余 token/终态分类，以及 Live adapter 在缺少配置时请求前拒绝。

本 Lab 的 Core 交付不包含 `/api/ai/chat`、`/api/ai/structured` 或 SSE 端点。Chapter 2 中这些代码是教师演示与 Advanced 扩展；只有学习者另写 API、framing、断连和取消测试后，才能把它们作为已实现交付。

## 默认离线步骤

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_fake_model.py -q
```

预期形状：pytest 显示 `13 passed`；无网络调用、无 API key 提示。

```bash
cd reference-implementation
uv run python - <<'PY'
import asyncio
from agent_course.core import Message
from agent_course.models.fake import FakeModelGateway

async def main():
    step = await FakeModelGateway().next_step(
        [Message(role="user", content="什么是 Agent？")], []
    )
    print(step.model_dump_json())

asyncio.run(main())
PY
```

预期形状：一个 JSON object，`content` 为固定中文解释，`tool_calls` 为空，`stop_reason` 为 `completed`；不要匹配无关序列化空白。

## 故意失败

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_live_gates.py -q -k strict_environment_gate
```

该测试故意删除/置空 Live 配置并断言 `LiveConfigurationError`；预期形状为该参数化测试全部通过。这里的“失败”是 adapter 构造被安全拒绝，不是 lab 失败。

## 调试顺序

1. 确认输入与 README fixture 完全相等，不依赖 substring。
2. 确认传入的是 `Message(role="user", ...)`。
3. timeout/invalid-output 应按异常类型分类，不改成随机重试。
4. Live gate 失败时列出缺失变量名，但绝不打印 key 值。

## 默认验证

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_core.py tests/test_fake_model.py tests/test_live_gates.py -q -k 'not successful_live_gate_construction'
```

预期形状：选中的 core/Fake/gate/structured-output/budget/status tests 全部通过，退出码 0；不启动 Web Server，也不声称验证未实现端点。

## 可选 Live 扩展（显式付费）

先按 [Labs 总门禁](../README.md#live-扩展统一门禁) 设置三个变量并确认费用上限，再由学习者创建单独的 Live smoke test；当前参考实现没有通用付费 CLI，因此本 lab 不伪造命令。提交时记录 model、重复次数、预算、脱敏输出 shape 和异常分布。

## 提交证据

命令及摘要、直接回答 JSON shape、一次 Live gate 拒绝原因、Fake 可证明/不可证明各两点，以及 A2 的自评。
