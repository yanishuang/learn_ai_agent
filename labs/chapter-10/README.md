# Lab 10：MCP stdio 与信任治理

## 目标

验证本地 stdio server/client 的初始化、工具发现、结构化调用、业务错误、total timeout 和子进程清理。

## 默认离线步骤

```bash
cd reference-implementation
uv run python -m agent_course.mcp.client O1001 --timeout 5
```

预期形状：一个 JSON object；`tool_names` 含 `query_order_status`，`structured_result` 含成功 code 与 tenant-scoped order output。不要匹配 SDK stderr 日志或进程 ID。

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_mcp.py tests/test_tools.py -q
```

预期形状：MCP 与底层 strict tool tests 全部通过。

## 故意失败

```bash
cd reference-implementation
uv run python -m agent_course.mcp.client O9999 --timeout 5
```

预期退出码 1，stderr 形状以 `error:` 开头并说明 caller tenant 中找不到订单；这属于结构化业务失败，不是 transport failure。

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_mcp.py -q -k 'errors_and_cleans_up or times_out'
```

预期测试通过，证明业务错误和 timeout 后都回收子进程。

## 调试顺序

1. 先确认 server 命令是当前 Python 的 `-m agent_course.mcp.server`。
2. 检查 initialize/list_tools/call_tool 的顺序和 allowlist 工具名。
3. 区分 `isError`、缺 structured content、schema drift 与 transport timeout。
4. 确认 timeout 覆盖完整 exchange，所有路径退出 context manager。
5. 工具描述/结果按不可信数据处理，业务权限仍由 tool 后端执行。

## 默认验证

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_mcp.py tests/test_tools.py tests/test_agent_runner.py -q
```

预期形状：全部通过，退出码 0；不访问远程 MCP。

## 可选 Live 扩展（显式联网）

`npx` Inspector 可能下载包，不属于离线 Core。若明确允许联网，可先记录 Node/npm 版本与下载边界，再运行 Chapter 10 记录的 Inspector 工作流。Remote MCP、OAuth/consent 或 Go server 必须由学习者先创建配置、allowlist 和合同测试，再执行其 learner-created command；不能声称当前参考实现已提供。

## 提交证据

成功 exchange JSON shape、O9999 错误与退出码、timeout/cleanup 测试摘要、信任边界说明和 A10 评分。
