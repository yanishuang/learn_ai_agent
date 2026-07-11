# Labs

所有命令默认从仓库根目录执行。Core 使用 `reference-implementation/` 的确定性 Fake Model、本地内存组件和 stdio MCP；不会发起模型网络请求，也不需要 API key。先按 [参考实现 README](../reference-implementation/README.md) 完成 `uv lock --check` 与一次 `uv sync --frozen --group dev --extra live`。

| Lab | 主题 | 默认离线验收 |
| --- | --- | --- |
| [Chapter 02](chapter-02/README.md) | Fake 模型与 Live gate | direct/timeout/gate tests |
| [Chapter 05](chapter-05/README.md) | 严格工具与可信 context | tool tests |
| [Chapter 06](chapter-06/README.md) | bounded Agent runtime | runner tests |
| [Chapter 07](chapter-07/README.md) | 权限感知 RAG | RAG tests |
| [Chapter 08](chapter-08/README.md) | 可恢复 Workflow | workflow tests |
| [Chapter 09](chapter-09/README.md) | eval、trace 与 red team | eval/data checks |
| [Chapter 10](chapter-10/README.md) | stdio MCP | MCP client/tests |

每次提交都包含：执行命令、退出码、稳定输出形状、一次故意失败及解释、修复/定位步骤、focused test 摘要和脱敏证据。不要断言随机 run ID、trace ID 或时间戳的精确值。

## Live 扩展统一门禁

Live 会产生费用，且不属于 Core。只有操作者确认账户限额后，才能显式设置三个变量：

```bash
export AGENT_COURSE_LIVE_TESTS=1
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="your-explicit-model"
```

缺少任一项必须在请求前失败。不得提交 `.env`、真实 key、原始敏感 prompt/response；Live 结果用重复运行分布和输出 shape 报告，不能替代默认离线验收。
