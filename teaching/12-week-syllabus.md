# 12 周教师带领路线

本路线以 [课程总览](../README.md) 和 [课程 manifest](../docs/course-manifest.json) 为共同地图。默认实验使用确定性 Fake Model、无需密钥且不访问模型网络。任何 Live 对比都是付费的显式选修，不能补偿 Core 验收失败。

## 统一验收标准

| ID | 周次 | 不可降低的验收证据 | 评分入口 |
| --- | --- | --- | --- |
| A0 | 1 | 根 validator 与测试通过；能解释 Fake/Live、密钥和成本边界 | R1 正确性、R2 安全边界、R7 解释 |
| A1 | 1 | 给定需求能区分 chat、RAG、tool、Workflow、Agent，写出 Know-Engine Core 范围 | R1、R7 |
| A2 | 2 | Fake Model 直接回答、结构化边界和失败分类可重复 | R1、R5、R6 |
| A3 | 3 | prompt/context 版本化；不可信内容不成为系统权限 | R2、R3、R7 |
| A4 | 4 | provider-neutral 依赖方向、Pydantic 边界和离线测试成立 | R1、R6、R7 |
| A5 | 5 | 严格工具参数、可信 `RunContext`、权限拒绝和结构化结果有证据 | R1、R2、R3、R5 |
| A6 | 6 | runner 强制 turn/tool/token/time 预算、停止原因、session 隔离和 trace 脱敏 | R1-R5 |
| A7 | 7 | tenant/user/permission 在相关性前过滤；引用来自真实 hit；不可答时拒答 | R1-R3、R7 |
| A8 | 8 | Workflow 可暂停、审批、恢复、取消、超时；hash/version/idempotency 绑定正确 | R1-R5 |
| A9 | 9 | 离线 eval 覆盖任务、工具、参数、权限、轨迹和脱敏；红队检查副作用 | R1-R5、R7 |
| A10 | 10 | stdio MCP 可离线发现/调用；输入输出校验、allowlist、timeout 和 cleanup 有证据 | R1-R5 |
| A11 | 11 | Chapter 13 生产评审完成；Know-Engine M1-M6 可独立重跑 | R1-R7 |
| A12 | 12 | Know-Engine M1-M7 全部通过、完整离线回归与演示；Core 不含 graph/multi-Agent | R1-R7，最终项目 rubric |

`R1-R7` 的定义见 [评估量规](assessment-rubrics.md)。任何补课、延期或恢复周都使用同一行验收，不删测试、不放宽权限、不以 Live 演示替代离线证据。

## 每周安排

| 周 | 章节与主题 | 课堂实验 | 当周产出与闸门 |
| --- | --- | --- | --- |
| 1 | [课程准备](../chapters/00-course-setup.md) + [第 1 章](../chapters/01-ai-agent-overview.md) | 环境基线、边界分类 | 环境记录、范围图；A0、A1 |
| 2 | [第 2 章](../chapters/02-llm-application-basics.md) | [Lab 02](../labs/chapter-02/README.md) | Fake 模型探针与失败说明；A2 |
| 3 | [第 3 章](../chapters/03-prompt-and-context-engineering.md) | prompt/context 合同测试 | prompt 版本、注入威胁说明；A3 |
| 4 | [第 4 章](../chapters/04-python-ai-application-stack.md) | 依赖方向与 API 边界 | 架构图、Pydantic 合同；A4 |
| 5 | [第 5 章](../chapters/05-tool-calling.md) | [Lab 05](../labs/chapter-05/README.md) | 工具 schema、拒绝与审计证据；A5 |
| 6 | [第 6 章](../chapters/06-agent-runtime.md) | [Lab 06](../labs/chapter-06/README.md) | bounded run、停止原因、trace；A6 |
| 7 | [第 7 章](../chapters/07-rag-core.md) | [Lab 07](../labs/chapter-07/README.md) | 权限 RAG、引用、拒答；A7 |
| 8 | [第 8 章](../chapters/08-workflow-durable-execution.md) | [Lab 08](../labs/chapter-08/README.md) | checkpoint、审批、恢复证据；A8 |
| 9 | [第 9 章](../chapters/09-agent-evaluation-observability-security.md) | [Lab 09](../labs/chapter-09/README.md) | eval report、红队数据、trace grading；A9 |
| 10 | [第 10 章](../chapters/10-mcp-integration.md) | [Lab 10](../labs/chapter-10/README.md) | stdio MCP 与信任评审；A10 |
| 11 | [第 13 章](../chapters/13-product-experience-and-production.md) + [第 14 章](../chapters/14-know-engine-capstone.md) M1-M6 | 集成演练、故障注入、生产评审 | 可独立重跑的 M1-M6；A11 |
| 12 | 第 14 章 M7、最终评估与演示 | 干净环境重放、同伴答辩 | Know-Engine Core 完成；A12 |

## Enrichment 边界

[第 11 章](../chapters/11-advanced-rag-and-data-routing.md)、[第 12 章](../chapters/12-agent-interoperability.md) 和 [第 15 章](../chapters/15-dodo-agent-capstone.md) 明确是 enrichment / Optional Advanced。它们只能在 A12 通过后进入，不占用 12 周 Core 的验收时间，也不能用高级 RAG、多 Agent 或 Dodo 演示替代 Know-Engine Core。

## 课程完成证据

提交命令与输出形状、失败注入前后对比、测试摘要、脱敏 trace、权限矩阵、eval 数据版本、架构/威胁模型和短解释。随机 run ID、trace ID、时间戳不得作为逐字匹配目标；只断言字段、类型、顺序和不变量。
