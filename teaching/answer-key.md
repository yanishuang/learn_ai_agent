# 实验答案与推理

本答案键解释判定依据和常见误区，不提供可照抄的随机 ID。对应实验见 [Labs 索引](../labs/README.md)。

## Chapter 02

正确判断是：Fake 的精确输入产生固定直接回答；Live 构造必须同时具备 flag、key 和显式 model。缺少门禁时在请求前失败是成功的安全行为。常见错误是给 Live adapter 默认模型、在模块导入时读取密钥，或把“客户端已构造”误说成“已发请求”。

## Chapter 05

工具参数只能包含业务字段 `order_id`；tenant、user 和 permission 来自可信 `RunContext`。无权限应得到结构化 `PERMISSION_DENIED`，未知字段应在 handler 前得到 `INVALID_ARGUMENTS`。把 `tenant_id` 加进 schema 看似灵活，实际让不可信模型选择授权域，是零分安全边界。

## Chapter 06

预算必须由 runner 强制，而不是 prompt 建议。重复相同工具 fingerprint 在第二次执行前停止；tool budget 在超额调用执行前停止；权限错误不重试。`final_content` 不是唯一证据，必须同时检查 `stop_reason`、`model_turn_count`、`model_tool_calls`、`tool_results` 和脱敏 trace。增加预算来“修复”无限循环只是隐藏故障。

## Chapter 07

正确顺序是授权过滤、相关性打分、稳定排序、构造来自真实 hit 的 citation。跨租户高相似 chunk 不应先进入候选再过滤；否则日志、cache 或 reranker 已接触未授权数据。无授权 hit 时拒答，不让模型凭常识补全。citation 的 quote/source 必须从 hit 派生，不能让模型自由生成。

## Chapter 08

审批绑定 run、state/version、payload hash 和 expiry。恢复读取已提交 checkpoint，不应重新生成已有模型输出。错误 hash、错误 owner/tenant、过期或取消后的审批都必须失败。只做前端确认、先执行副作用后记 idempotency，或用最新代码无条件解释旧 state，都会破坏可恢复性。

## Chapter 09

确定性硬断言先于 judge：权限、参数、工具选择、预算和 trace 泄漏不交给模型打分。rate 只使用适用 case 作分母；重复 ID 在运行前失败。fresh run 的 trace ID 可变化，所以比较规范化业务字段。红队不能只找拒绝词，还要断言禁止副作用、停止策略和 trace 脱敏。

## Chapter 10

Core 使用本地 stdio MCP：client 启动 server、初始化、发现固定工具、调用并校验 structured content，total timeout 覆盖整个生命周期并确保清理子进程。工具描述和结果仍是不可信输入。任意 command/server、只信描述、不校验 schema，或把 `npx` Inspector 当离线前提都不合格。

## 综合排错顺序

1. 确认当前目录、Python/uv 和 lock 状态。
2. 运行最小 focused test，保留第一条真实失败。
3. 核对 fixture 精确文本、可信 context、limits 和 schema。
4. 检查停止原因与结构化结果，再看最终文本。
5. 检查 trace 是否缺事件、顺序错误或泄漏。
6. focused 通过后重跑完整离线 suite；不删除失败 case，不放宽边界。
