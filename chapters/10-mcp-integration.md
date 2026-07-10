# 第 10 章：MCP 集成与信任治理

更新时间：2026-07-09
建议学习时间：5-7 天  
适合阶段：已经实现本地工具调用，希望把企业工具和数据源标准化接入 Agent 平台  
本章产出：一个 Python MCP Server、一个 MCP Client 接入示例、一个可选 Go MCP Server 设计、一份 MCP 工具安全清单、一份 MCP Server 信任与授权说明

## 10.1 本章学习目标

学完本章后，你应该能做到：

1. 解释 MCP 的 Host、Client、Server 三个角色。
2. 说明 MCP Tools、Resources、Prompts 的区别。
3. 使用 MCP Python SDK 实现一个 stdio MCP Server。
4. 使用 MCP Inspector 调试工具列表和调用结果。
5. 从 Python Agent 应用调用 MCP 工具。
6. 判断哪些工具适合做成本地 function tool，哪些适合做成 MCP Server。
7. 设计 MCP 工具的权限、审计、限流和信任边界。
8. 知道何时用 Go 实现 MCP Server。
9. 了解 remote MCP、MCP Authorization、MCP Apps 与 Apps SDK 的关系。

MCP 是工具和上下文接入协议，不是 Agent 本身，也不是权限系统本身。

![MCP 工具接入边界](../assets/agent-ecosystem-illustrations/02-mcp-boundary.png)

## 10.2 MCP 解决什么问题

没有 MCP 时，每个 Agent 应用都要自己接：

```text
订单 API
库存 API
知识库 API
报表 API
权限 API
搜索 API
```

MCP 的价值是把这些能力标准化暴露：

```text
企业系统 -> MCP Server -> MCP Client -> Agent / Host
```

这样 Agent 平台可以发现工具、读取工具 schema、调用工具，并拿到结构化结果。

## 10.3 MCP 基本角色

| 角色 | 说明 | 例子 |
| --- | --- | --- |
| Host | 使用 MCP 能力的应用 | Agent 平台、IDE、桌面应用 |
| Client | Host 内部连接某个 MCP Server 的组件 | Python Agent 里的 MCP client |
| Server | 暴露工具、资源、提示词的服务 | 订单 MCP Server、知识库 MCP Server |

MCP Server 不应该直接信任模型。它接收的是工具调用请求，但仍然要自己做权限、参数校验和审计。

## 10.4 Tools、Resources、Prompts

| 能力 | 用途 | 例子 |
| --- | --- | --- |
| Tools | 可执行能力 | `query_order_status`、`search_knowledge` |
| Resources | 可读取资源 | 文档、配置、数据集 |
| Prompts | 可复用提示词模板 | 报告生成模板、代码审查模板 |

本课程第 10 章先做 Tools。Resources 和 Prompts 放到平台化阶段再深入。

2026 年需要额外知道的是：MCP 也在向交互式结果发展。MCP Apps / Apps SDK 可以让工具结果返回结构化数据和 UI 组件，但这属于体验层扩展；它不改变 MCP Server 必须做权限、审计和限流的基本原则。

## 10.5 Transport 选择

| Transport | 适合场景 |
| --- | --- |
| stdio | 本地工具、开发调试、CLI 启动的 Server |
| Streamable HTTP | 远程服务、企业部署、多客户端访问 |
| 旧 HTTP+SSE | 兼容历史实现，作为了解即可 |

学习阶段优先 stdio，因为最容易调试。企业部署阶段再考虑 Streamable HTTP。

如果要接入 OpenAI Responses API 的 remote MCP，优先选择支持 Streamable HTTP 的 MCP Server，并确认认证、工具白名单、调用日志和超时策略已经配置好。

截至 2026-07-09，课程稳定基线仍建议使用 MCP `2025-11-25` 规范；`2026-07-28` release candidate 可作为观察项，用来了解 Tasks、Extensions、MCP Apps 和授权强化方向，但不建议初学者直接按 RC 改造主项目。

## 10.6 什么时候用 MCP

适合 MCP：

- 工具要被多个 Agent 或应用复用。
- 工具属于企业系统边界。
- 工具有明确 schema。
- 工具需要独立部署、审计、限流。
- 工具可能由 Go、Python 或其他语言实现。

不一定需要 MCP：

- 只在当前 Agent 内使用的小函数。
- 快速实验中的临时工具。
- 输入输出还不稳定的能力。
- 调用成本比收益更高的简单函数。

推荐演进：

```text
Python function tool
  -> Tool Registry
  -> Python MCP Server
  -> Go MCP Server / 企业 MCP Server
```

## 10.7 MCP 工具设计

以订单查询为例：

```json
{
  "name": "query_order_status",
  "description": "根据订单号查询订单状态。只用于只读查询，不会修改订单。",
  "input_schema": {
    "type": "object",
    "properties": {
      "order_id": {
        "type": "string",
        "description": "订单号，例如 O1001"
      }
    },
    "required": ["order_id"]
  }
}
```

返回：

```json
{
  "order_id": "O1001",
  "status": "已发货",
  "latest_event": "包裹已到达上海转运中心"
}
```

不要返回：

- 用户手机号。
- 用户地址。
- 内部备注。
- 未授权字段。

## 10.8 Python MCP Server 示例

下面示例展示核心结构，具体 API 以当前 MCP Python SDK 文档为准。

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("order-tools")


@mcp.tool()
async def query_order_status(order_id: str) -> dict:
    """根据订单号查询订单状态。只读工具。"""
    if order_id != "O1001":
        return {
            "success": False,
            "error_code": "ORDER_NOT_FOUND",
            "message": "未找到该订单",
        }

    return {
        "success": True,
        "order_id": "O1001",
        "status": "已发货",
        "latest_event": "包裹已到达上海转运中心",
    }


if __name__ == "__main__":
    mcp.run()
```

本章示例可以使用假数据。进入项目实战后，MCP Server 应接入真实服务或只读副本。

## 10.9 MCP Client 接入 Agent

接入方式取决于所用 Agent 框架。原则是：

1. Agent 应用启动 MCP Client。
2. Client 连接 Server。
3. 读取工具列表。
4. 将 MCP 工具注册给 Agent。
5. Agent 调用工具时由 Client 转发给 MCP Server。
6. 工具结果返回 Agent。

无论框架如何封装，都要保留：

- 工具调用日志。
- 工具参数。
- Server 名称和版本。
- 调用耗时。
- 错误码。

## 10.10 MCP Inspector 调试

每个 MCP Server 都应该先用 Inspector 调试：

检查项：

- Server 是否能启动。
- 工具列表是否正确。
- 工具描述是否清晰。
- 参数 schema 是否符合预期。
- 成功调用是否返回结构化结果。
- 错误参数是否返回可解释错误。

不要跳过 Inspector 直接接 Agent，否则问题会混在模型、Agent 和工具之间。

## 10.11 安全边界

MCP Server 必须自己做安全控制：

| 风险 | 控制 |
| --- | --- |
| 参数注入 | Pydantic / schema 校验 |
| 越权访问 | Server 侧权限校验 |
| 敏感字段泄露 | 返回字段白名单 |
| 滥用调用 | 限流和配额 |
| 高风险操作 | 人工确认 |
| 审计缺失 | 工具调用日志 |
| Server 被污染 | 固定可信 Server 列表 |

不要因为工具通过 MCP 暴露，就默认它是安全的。

### MCP Authorization 与业务权限

MCP Authorization 解决的是客户端、资源服务器、授权服务器之间如何安全授权的问题。业务权限仍然要由 MCP Server 或后端系统强制执行。

| 层级 | 负责什么 |
| --- | --- |
| MCP Authorization | 谁可以连接这个 Server、获取什么 token、代表哪个用户 |
| Server 信任列表 | 当前 Agent 平台允许连接哪些 MCP Server |
| 工具风险等级 | 某个工具是否只读、是否高风险、是否需要人工确认 |
| 业务权限 | 用户是否能查这个订单、文档、报表或客户数据 |
| 审计日志 | 谁在何时调用了什么工具，参数和结果摘要是什么 |

不要只在 prompt 里写“不要越权”。越权检查必须在 Server 侧或业务系统侧完成。

## 10.12 Python 与 Go 的分工

Python MCP Server 适合：

- 快速验证工具 schema。
- 包装已有 Python RAG 服务。
- 实验型工具。
- 与 Agent 逻辑强相关的工具。

Go MCP Server 适合：

- 企业系统适配。
- 高并发只读查询。
- 权限和审计服务。
- 长期稳定工具。
- 需要单文件部署或低资源占用的服务。

判断标准：

| 问题 | 如果答案是“是” |
| --- | --- |
| schema 稳定吗 | 可以考虑 Go |
| 需要高并发吗 | 可以考虑 Go |
| 工具会被多个应用复用吗 | 可以考虑 MCP |
| 还在频繁试错吗 | 先留在 Python |

## 10.13 MCP Server Registry

平台化后需要记录 MCP Server：

```sql
create table mcp_servers (
  id text primary key,
  name text not null,
  transport text not null,
  command text,
  url text,
  status text not null,
  risk_level text not null,
  created_at timestamptz not null default now()
);
```

工具清单：

```sql
create table mcp_tools (
  id text primary key,
  server_id text not null references mcp_servers(id),
  name text not null,
  description text not null,
  input_schema_json jsonb not null,
  risk_level text not null,
  enabled boolean not null default true
);
```

Agent 只能使用已启用、已授权、风险等级允许的工具。

## 10.14 MCP Apps 与 Apps SDK

MCP Apps / Apps SDK 的价值是把工具结果从“纯文本”升级为“可交互界面”。例如：

- 查询订单后返回订单状态卡片。
- 检索知识库后返回引用列表和筛选器。
- 报告生成后返回进度、章节树和下载入口。
- 数据分析后返回图表组件和追问按钮。

但它不应该在第 10 章抢主线。学习顺序建议：

```text
MCP Tools 跑通
  -> 工具 schema、权限、日志稳定
  -> Streamable HTTP / remote MCP
  -> MCP Apps / Apps SDK 交互式结果
```

如果工具结果还不稳定，不要先做 UI 组件；否则会把问题混在模型、工具、协议和前端四层里。

## 10.15 MVP / 进阶 / 生产化验收

### MVP

- 能启动一个 Python stdio MCP Server。
- 暴露订单查询和知识库搜索两个工具。
- 能用 Inspector 调用成功。
- Python Agent 能调用 MCP 工具。

### 进阶

- MCP Server 有参数校验。
- 工具有错误返回。
- 工具调用写日志。
- Agent trace 能显示 MCP 工具调用。

### 生产化

- 支持 Streamable HTTP。
- 有 MCP Server Registry。
- 有工具风险等级。
- 有 Server 可信列表。
- 有 MCP Authorization 或等价的连接授权方案。
- Go 实现至少一个稳定企业工具 Server。
- 权限、限流、审计在 Server 侧强制执行。

## 10.16 常见误区

- 把 MCP 当成 Agent。
- 把 MCP 当成权限系统。
- 所有小函数都做成 MCP Server。
- MCP 工具返回敏感字段。
- 让 Agent 连接任意未知 MCP Server。
- 没有用 Inspector 调试工具 schema。
- 先做 MCP Apps UI，但工具 schema、权限和日志还没有稳定。

## 10.17 本章学习资料

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/getting-started/intro)
- [MCP SDKs](https://modelcontextprotocol.io/docs/sdk)
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Specification 2026-07-28 Release Candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector)
- [MCP Authorization](https://modelcontextprotocol.io/docs/tutorials/security/authorization)
- [MCP Apps](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)
- [OpenAI Responses API - Remote MCP](https://developers.openai.com/api/docs/guides/tools-connectors-mcp)
- [OpenAI Apps SDK](https://developers.openai.com/apps-sdk)
- [OpenAI Agents SDK - Tools](https://openai.github.io/openai-agents-python/tools/)

## 10.18 本章复盘模板

```markdown
# 第 10 章复盘

## 我实现了哪些 MCP 工具

## 工具 schema 是什么

## 我如何用 Inspector 验证

## Python Agent 如何调用 MCP 工具

## 哪些工具适合继续留在 Python

## 哪些工具适合迁移到 Go

## MCP Server 做了哪些权限和审计

## 我如何限制 Agent 只能使用可信 MCP Server

## MCP Authorization 和业务权限如何分工

## 哪些结果未来适合做成 MCP Apps / Apps SDK UI
```
