# Lab 08：可恢复 Workflow

## 目标

验证 versioned state、内容绑定审批、checkpoint 恢复、取消、timeout 和 idempotency 冲突。

## 默认离线步骤

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_workflow.py -q
```

预期形状：`10 passed`；测试使用注入 clock 和内存 store，完全离线。

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_workflow.py -q -k 'start_creates or resume_waits'
```

预期 state shape：start 后有 run/workflow/state version、payload hash 和 waiting approval 状态；批准并 resume 后完成且已有工作不重复。

## 故意失败

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_workflow.py -q -k 'mismatched_payload_hash or replayed or conflicting_reuse or deadline'
```

fixtures 故意重放 hash、复用冲突 idempotency key 或越过 deadline。预期异常/终态由测试捕获，副作用不重复，pytest 通过。

## 调试顺序

1. 记录 run ID 只用于关联，不匹配随机值。
2. 核对 `workflow_version`、`state_version` 和 transition 顺序。
3. 核对 approval 的 owner/tenant/permission、payload hash 与 expiry。
4. 检查模型输出是否已在 checkpoint 固化，resume 不重调。
5. timeout/cancel 后检查终态与幂等重放，不只看抛出的异常。

## 默认验证

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_workflow.py tests/test_api.py -q -k 'workflow or research'
```

预期形状：选中的 workflow/API 边界测试全部通过，退出码 0。

## 可选 Live 扩展（显式付费）

Live 模型只能在首次节点生成待审批内容；先创建 snapshot/replay test，证明 resume 使用已提交输出，再运行 learner-created Live command。任何审批或恢复测试仍使用离线 fixture，避免随机输出破坏 hash 证据。

## 提交证据

start/approve/resume shape、一次 replay/expiry 失败、版本与 hash 说明、无重复工作证据、A8 评分。
