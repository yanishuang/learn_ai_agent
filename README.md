# AI Agent 学习大纲与课程设计

更新时间：2026-05-26  
适用对象：有 Java / Spring Boot 基础，想系统学习企业级 AI Agent、RAG、MCP 与多智能体应用开发的工程师。

## 课程定位

这份大纲基于截图中的 AI Agent 学习资料整理而成。原资料的核心方向是：以 Java 21、Spring Boot、Spring AI、LangChain4j 为主栈，围绕企业知识库问答系统和多智能体平台，学习 RAG、Tool Calling、MCP、Workflow、多 Agent 协作与工程化落地。

课程不只追逐框架关键词，而是围绕一个主线展开：

> 从“能调用大模型”到“能构建可评估、可观测、可部署的企业级 AI Agent 系统”。

最终建议完成两个作品：

1. **Know-Engine：企业级知识库问答系统**
2. **Dodo-Agent：企业级端到端通用智能体平台**

## 学习目标

学完后应具备以下能力：

- 理解 AI Agent、RAG、Workflow、MCP、多 Agent 的边界与适用场景。
- 使用 Spring AI / LangChain4j 构建 Java 大模型应用。
- 实现文档解析、切片、向量化、混合检索、重排、引用溯源等 RAG 核心能力。
- 设计可控的 Tool Calling / Function Calling 机制，让模型安全调用业务能力。
- 使用 MCP 将企业内部工具、知识库、数据库和外部 API 标准化接入 Agent。
- 设计单 Agent、多 Agent、Plan-Execute、ReAct、State Machine 等执行模式。
- 建立评估、日志、追踪、权限、成本控制、异常恢复等生产级工程能力。

## 技术栈建议

| 层级 | 推荐技术 |
| --- | --- |
| 语言与框架 | Java 21、Spring Boot 3.x、Spring AI、LangChain4j |
| 模型接入 | OpenAI API、兼容 OpenAI 协议的模型服务、本地模型服务 |
| Agent 协议 | MCP，重点学习 stdio 与 Streamable HTTP；旧 HTTP+SSE 作为兼容知识 |
| 检索与存储 | PostgreSQL + pgvector、Elasticsearch、Neo4j、MySQL |
| 文件与对象存储 | MinIO |
| 缓存与并发控制 | Redis、Redisson |
| 文档处理 | PDF、Word、Excel、CSV、HTML 表格解析 |
| 任务与调度 | XXL-Job 或 Spring Scheduler |
| 观测与评估 | OpenTelemetry、日志链路、RAG 评估、Agent 轨迹追踪 |
| 交互体验 | SSE 流式输出、任务进度、会话管理、引用来源展示 |

## 课程结构总览

| 阶段 | 章节 | 核心产出 |
| --- | --- | --- |
| 基础篇 | 1-4 章 | 会调用模型、写 Prompt、做结构化输出、接入工具 |
| RAG 篇 | 5-7 章 | 完成可用的企业知识库问答 MVP |
| Agent 篇 | 8-10 章 | 实现 ReAct、Workflow、MCP 工具接入 |
| 平台篇 | 11-13 章 | 完成多 Agent 平台与企业级工程能力 |
| 实战篇 | 14-15 章 | 交付 Know-Engine 与 Dodo-Agent 两个项目 |

## 第 1 章：AI Agent 全景与学习路线

详细学习文档：[第 1 章：AI Agent 全景与学习路线](chapters/01-ai-agent-overview.md)

### 学习目标

- 区分 Chatbot、RAG 应用、Workflow、Agent、多 Agent。
- 理解截图资料中的 Know-Engine 与 Dodo-Agent 分别解决什么问题。
- 建立“先稳定工作流，再引入 Agent 自主性”的工程判断。

### 核心内容

- AI Agent 的基本组成：模型、指令、工具、上下文、记忆、执行循环、评估。
- Workflow 与 Agent 的区别：Workflow 强约束，Agent 更自主。
- 企业级 Agent 的典型场景：知识库问答、市场情报分析、智能办公助手、多轮深度调研、PPT/报告生成。
- 课程项目蓝图：Know-Engine 与 Dodo-Agent。

### 实战任务

- 画出自己要做的 Agent 系统架构图。
- 列出 3 个适合用 RAG 的场景，3 个适合用 Agent 的场景，3 个更适合固定 Workflow 的场景。

### 学习资料

- [OpenAI Agents SDK - Agents](https://openai.github.io/openai-agents-python/agents/)
- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [LangChain4j Documentation](https://docs.langchain4j.dev/)

## 第 2 章：大模型应用基础

详细学习文档：[第 2 章：大模型应用基础](chapters/02-llm-application-basics.md)

### 学习目标

- 掌握模型调用、消息格式、结构化输出、流式响应。
- 理解 token、上下文窗口、温度、采样、输出约束对结果的影响。

### 核心内容

- Chat Completion / Responses 类接口的基本概念。
- System / User / Assistant / Tool 消息的职责。
- JSON Schema / POJO 映射 / 结构化输出。
- 同步响应、异步响应、SSE 流式输出。
- 常见失败：格式漂移、幻觉、长上下文遗漏、输出截断。

### 实战任务

- 实现一个 Spring Boot 接口：输入问题，返回模型回答。
- 增加结构化输出：让模型返回 `answer`、`confidence`、`citations`。
- 增加 SSE 流式响应。

### 学习资料

- [Spring AI Reference Documentation](https://docs.spring.io/spring-ai/reference/)
- [Spring AI Chat Client API](https://docs.spring.io/spring-ai/reference/api/chatclient.html)
- [OpenAI API Documentation](https://platform.openai.com/docs)

## 第 3 章：Prompt Engineering 与 Context Engineering

详细学习文档：[第 3 章：Prompt Engineering 与 Context Engineering](chapters/03-prompt-and-context-engineering.md)

### 学习目标

- 从“写提示词”升级到“管理上下文”。
- 学会为企业应用设计稳定、可复用、可测试的提示词模板。

### 核心内容

- Prompt 的基本结构：角色、任务、约束、输入、输出格式、失败处理。
- Few-shot 示例、反例约束、输出边界。
- Context Engineering：动态上下文、用户状态、业务数据、会话历史、工具结果。
- 提示词版本管理与 A/B 测试。
- 安全提示：不要把权限判断只交给 Prompt。

### 实战任务

- 为企业知识库问答设计系统提示词。
- 为数据分析 Agent 设计结构化输出模板。
- 建立提示词变更记录表。

### 学习资料

- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Spring AI Prompt API](https://docs.spring.io/spring-ai/reference/api/prompt.html)

## 第 4 章：Spring AI 与 LangChain4j 入门

详细学习文档：[第 4 章：Spring AI 与 LangChain4j 入门](chapters/04-spring-ai-and-langchain4j.md)

### 学习目标

- 掌握 Java 生态下构建 AI 应用的两条常见路线。
- 理解 Spring AI 与 LangChain4j 的定位差异。

### 核心内容

- Spring AI：适合 Spring Boot 体系内统一模型、向量库、Tool、RAG、MCP。
- LangChain4j：适合 Java 应用快速组合 LLM、Tools、Memory、RAG、Agent。
- 模型适配、配置管理、服务封装、异常处理。
- 如何设计自己的 `AiService`、`ToolService`、`KnowledgeService`。

### 实战任务

- 用 Spring AI 实现一个问答接口。
- 用 LangChain4j 实现同样的接口。
- 对比两种实现的依赖、代码结构、扩展方式。

### 学习资料

- [Spring AI Reference Documentation](https://docs.spring.io/spring-ai/reference/)
- [LangChain4j Documentation](https://docs.langchain4j.dev/)
- [LangChain4j Tutorials](https://docs.langchain4j.dev/category/tutorials/)

## 第 5 章：Tool Calling / Function Calling

详细学习文档：[第 5 章：Tool Calling / Function Calling](chapters/05-tool-calling.md)

### 学习目标

- 让模型能够安全调用业务函数、外部 API、数据库查询能力。
- 理解工具定义、参数校验、权限控制和调用回放。

### 核心内容

- Tool Calling 的工作机制：模型选择工具，应用执行工具，结果回传模型。
- 工具描述、参数 Schema、返回值设计。
- Java 方法如何暴露为 Tool。
- 工具权限：用户身份、资源权限、操作白名单。
- 工具调用日志：记录工具名、参数、结果、耗时、失败原因。
- 防止危险工具：删除、转账、发邮件、改权限等操作必须有人类确认。

### 实战任务

- 实现 3 个工具：天气查询、订单查询、知识库搜索。
- 给工具增加参数校验和用户权限校验。
- 记录一次完整工具调用轨迹。

### 学习资料

- [Spring AI Tool Calling](https://docs.spring.io/spring-ai/reference/api/tools.html)
- [LangChain4j Tools Tutorial](https://docs.langchain4j.dev/tutorials/tools/)
- [OpenAI Agents SDK - Tools](https://openai.github.io/openai-agents-python/tools/)

## 第 6 章：RAG 基础：从文档到答案

### 学习目标

- 搭建企业知识库问答系统的最小可用版本。
- 理解 RAG 的关键链路：加载、解析、切片、向量化、检索、生成、引用。

### 核心内容

- RAG 基本流程：Document Loader、Parser、Chunker、Embedding、Vector Store、Retriever、Generator。
- 文档类型：PDF、Word、Excel、CSV、Markdown、网页。
- 切片策略：固定长度、按标题、按段落、父子切片、表格保留。
- Embedding 模型选择与向量维度管理。
- 引用来源与答案可追溯。

### 实战任务

- 上传企业制度文档，完成自动解析和入库。
- 实现“问题 -> 检索 -> 生成答案 -> 返回引用来源”。
- 加入文档列表、文档删除、重新索引能力。

### 学习资料

- [Spring AI ETL Pipeline](https://docs.spring.io/spring-ai/reference/api/etl-pipeline.html)
- [Spring AI Vector Databases](https://docs.spring.io/spring-ai/reference/api/vectordbs.html)
- [LangChain4j RAG Tutorial](https://docs.langchain4j.dev/tutorials/rag/)
- [Retrieval-Augmented Generation Paper](https://arxiv.org/abs/2005.11401)

## 第 7 章：高级 RAG：检索增强与多源路由

### 学习目标

- 解决基础 RAG 的常见问题：召回差、答案虚、表格难查、多数据源难融合。
- 设计企业级知识检索增强链路。

### 核心内容

- 查询改写：同义改写、扩展、纠错、意图识别。
- 混合检索：向量检索 + 全文检索 + 元数据过滤。
- 重排：Rerank、Top-K、阈值过滤。
- 多源路由：Elasticsearch、MySQL、Neo4j、对象存储。
- Text2SQL 与 Text2Cypher 的边界：适合查询结构化数据，不适合替代权限系统。
- Excel 与表格数据的特殊处理：单元格语义、表头、合并单元格、HTML 表格保留。

### 实战任务

- 为知识库增加 Elasticsearch 全文检索。
- 为销售数据增加 MySQL Text2SQL 查询。
- 为组织/产品关系增加 Neo4j Text2Cypher 查询。
- 实现检索路由：让系统判断该查文档、数据库还是图谱。

### 学习资料

- [Elasticsearch Vector Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html)
- [Neo4j Vector Indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- [pgvector](https://github.com/pgvector/pgvector)
- [LangChain4j Embedding Stores](https://docs.langchain4j.dev/integrations/embedding-stores/)

## 第 8 章：Agent 基础：ReAct、记忆与执行循环

### 学习目标

- 从一次性问答升级到能够“思考、调用工具、观察结果、继续行动”的 Agent。
- 理解 Agent 的不稳定性，并学会用限制条件控制它。

### 核心内容

- ReAct：Reasoning + Acting。
- Agent 执行循环：计划、工具调用、观察、下一步决策、完成。
- 会话记忆：短期记忆、摘要记忆、长期记忆。
- Stop condition：最大轮数、最大 token、最大工具次数、超时。
- 工具失败恢复：重试、降级、人工确认、返回失败说明。

### 实战任务

- 实现一个可以查询知识库和天气的 ReAct Agent。
- 增加最多 5 轮工具调用限制。
- 实现工具调用失败后的重试与兜底回答。

### 学习资料

- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [OpenAI Agents SDK - Running Agents](https://openai.github.io/openai-agents-python/running_agents/)
- [LangChain4j AI Services](https://docs.langchain4j.dev/tutorials/ai-services/)

## 第 9 章：Workflow 与 State Machine

### 学习目标

- 学会把不稳定的 Agent 任务拆成更稳定的工作流。
- 选择何时使用 Workflow，何时使用 Agent。

### 核心内容

- Workflow：固定步骤、条件分支、人工确认、状态持久化。
- State Machine：任务状态、失败状态、重试状态、完成状态。
- Plan-Execute：先规划，再逐步执行。
- 多轮深度调研：搜索、阅读、提炼、交叉验证、生成报告。
- PPT 生成：主题理解、大纲生成、素材检索、页面规划、内容生成。

### 实战任务

- 实现一个“市场情报分析”工作流。
- 实现一个“研究主题 -> 报告大纲 -> 资料检索 -> 报告生成”的流程。
- 给每一步记录状态和耗时。

### 学习资料

- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenAI Agents SDK - Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [OpenAI Agents SDK - Guardrails](https://openai.github.io/openai-agents-python/guardrails/)

## 第 10 章：MCP 基础与接入

### 学习目标

- 理解 MCP 的作用：把外部工具和数据源标准化提供给模型应用。
- 掌握 MCP Server 与 MCP Client 的基本实现。

### 核心内容

- MCP 的角色：Host、Client、Server。
- MCP 能力：Tools、Resources、Prompts。
- Transport：stdio 与 Streamable HTTP 是当前重点；旧 HTTP+SSE 作为兼容知识。
- MCP Server：把企业内部服务包装成标准工具。
- MCP Client：在 Agent 应用中发现和调用 MCP 工具。
- MCP 调试工具与连接测试。

### 实战任务

- 实现一个 MCP Server：暴露订单查询、知识库检索两个工具。
- 实现一个 MCP Client：从 Spring Boot 应用调用 MCP 工具。
- 使用 MCP Inspector 调试工具列表和调用结果。

### 学习资料

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/getting-started/intro)
- [MCP Specification - Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [Spring AI MCP Overview](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-overview.html)
- [Spring AI MCP Client Boot Starter](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-client-boot-starter-docs.html)
- [Spring AI MCP Server Boot Starter](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-server-boot-starter-docs.html)

## 第 11 章：多 Agent 架构设计

### 学习目标

- 设计一个可扩展的多智能体平台，而不是把所有能力塞进一个 Agent。
- 掌握 BaseAgent、Agent Registry、任务路由、Agent 协作。

### 核心内容

- BaseAgent：统一输入、输出、上下文、工具、日志、错误处理。
- Agent 类型：智能问答 Agent、文件问答 Agent、深度研究 Agent、PPT 生成 Agent。
- Agent 路由：基于意图分类、规则路由、模型路由。
- Handoff：一个 Agent 把任务交给另一个 Agent。
- 多 Agent 的风险：循环转交、上下文膨胀、责任不清、成本失控。

### 实战任务

- 实现 `BaseAgent` 抽象。
- 实现 3 个 Agent：知识库问答、Web 搜索、报告生成。
- 实现简单任务路由：根据用户意图选择 Agent。

### 学习资料

- [OpenAI Agents SDK - Agents](https://openai.github.io/openai-agents-python/agents/)
- [OpenAI Agents SDK - Handoffs](https://openai.github.io/openai-agents-python/handoffs/)
- [LangChain4j Agents Tutorial](https://docs.langchain4j.dev/tutorials/agents/)

## 第 12 章：交互体验与企业集成

### 学习目标

- 让 AI 应用从“能跑”变成“可用、可感知、可协作”。
- 实现流式输出、进度感知、富媒体卡片和企业 IM 集成。

### 核心内容

- SSE 流式输出：模型 token、工具状态、任务进度。
- 全链路进度：检索中、调用工具中、生成中、完成。
- 富媒体结果：表格、图表、引用、文件、链接。
- 会话管理：多轮上下文、历史记录、会话标题、会话归档。
- 企业 IM 集成：钉钉、飞书、企业微信的消息回调与机器人接入。

### 实战任务

- 为 Know-Engine 增加流式输出和进度条。
- 为 Agent 工具调用增加前端可视化轨迹。
- 接入一个企业 IM 机器人，实现问答入口。

### 学习资料

- [Spring WebFlux Reference](https://docs.spring.io/spring-framework/reference/web/webflux.html)
- [DingTalk Open Platform](https://open.dingtalk.com/document/)
- [OpenAI Agents SDK - Streaming](https://openai.github.io/openai-agents-python/streaming/)

## 第 13 章：企业级工程化

### 学习目标

- 掌握 AI Agent 上生产所需的安全、稳定、可观测、可评估能力。
- 避免“Demo 很惊艳，线上不可控”的常见问题。

### 核心内容

- 权限隔离：用户、租户、知识库、文档、工具权限。
- 数据安全：上传文件加密、访问审计、敏感信息脱敏。
- 评估体系：RAG 命中率、答案忠实度、引用准确率、工具调用成功率。
- 观测体系：Prompt、检索结果、工具调用、token、耗时、异常。
- 成本控制：缓存、摘要记忆、小模型路由、Embedding 批处理。
- 并发与稳定性：限流、熔断、重试、幂等、超时。
- 部署：配置管理、模型密钥管理、Docker、CI/CD。

### 实战任务

- 建立 Agent Run 日志表。
- 为每次回答保存检索结果和引用来源。
- 实现用户级知识库权限过滤。
- 增加 RAG 回归测试集。

### 学习资料

- [OpenAI Agents SDK - Tracing](https://openai.github.io/openai-agents-python/tracing/)
- [LangChain4j Testing and Evaluation](https://docs.langchain4j.dev/tutorials/testing-and-evaluation/)
- [Spring AI Observability](https://docs.spring.io/spring-ai/reference/observability/)

## 第 14 章：项目实战一：Know-Engine 企业知识库问答系统

### 项目目标

构建一个基于 RAG 的企业级知识库问答系统，支持多格式文档接入、智能切片、混合检索、多源路由、流式问答和引用溯源。

### 核心功能

- 文档上传：PDF、Word、Excel、CSV。
- 文档解析：文本、表格、标题层级、元数据。
- 智能切片：固定切片、父子切片、表格保留。
- 知识存储：对象存储 + 元数据表 + 向量库。
- 检索增强：查询改写、向量检索、全文检索、Rerank。
- 多源路由：文档、MySQL、Neo4j、Elasticsearch。
- 问答体验：SSE 流式输出、进度展示、引用来源。
- 管理能力：文档版本、重新索引、删除、权限。

### 建议里程碑

| 里程碑 | 内容 | 验收标准 |
| --- | --- | --- |
| M1 | 文档上传与解析 | 能上传 PDF/Word/Excel/CSV 并抽取文本 |
| M2 | 基础 RAG | 能基于文档回答问题并返回引用 |
| M3 | 混合检索 | 支持向量 + 全文检索 |
| M4 | 多源路由 | 能选择查文档、SQL 或图谱 |
| M5 | 企业化 | 权限、日志、评估、流式进度完整 |

## 第 15 章：项目实战二：Dodo-Agent 多智能体平台

### 项目目标

构建一个企业级端到端通用智能体平台，支持多个 Agent 协作完成问答、文件分析、深度研究、报告生成和 PPT 生成。

### 核心功能

- BaseAgent 抽象：统一输入输出、工具、上下文、日志。
- 智能问答 Agent：WebSearch + ReAct。
- 文件问答 Agent：File RAG + ReAct。
- 深度研究 Agent：Plan-Execute + 多轮搜索与总结。
- PPT 生成 Agent：大纲、页面规划、内容生成、文件导出。
- Agent Registry：注册、发现、路由、版本管理。
- MCP 工具接入：通过 MCP Server 调用企业工具。
- 会话与文件管理：会话历史、上传文件、任务记录。
- 可观测性：展示 Agent 思考步骤、工具调用和失败原因。

### 建议里程碑

| 里程碑 | 内容 | 验收标准 |
| --- | --- | --- |
| M1 | BaseAgent 与工具系统 | 所有 Agent 使用统一执行接口 |
| M2 | 单 Agent 能力 | 完成问答、文件问答、研究 Agent |
| M3 | Workflow 编排 | 深度研究任务可分阶段执行 |
| M4 | MCP 接入 | 至少 2 个企业工具通过 MCP 调用 |
| M5 | 多 Agent 平台 | 用户输入任务后能自动路由和协作 |

## 12 周学习安排

| 周次 | 学习主题 | 产出 |
| --- | --- | --- |
| 第 1 周 | AI Agent 全景、大模型调用、Prompt | 一个基础问答 API |
| 第 2 周 | Spring AI / LangChain4j、结构化输出、流式响应 | 一个 Java AI 服务骨架 |
| 第 3 周 | Tool Calling、工具权限、调用日志 | 3 个可调用业务工具 |
| 第 4 周 | RAG 基础、文档解析、切片、向量库 | 知识库问答 MVP |
| 第 5 周 | 高级 RAG、混合检索、Rerank | 检索增强版本 |
| 第 6 周 | 多源路由、Text2SQL、Text2Cypher | 文档 + SQL + 图谱问答 |
| 第 7 周 | ReAct Agent、记忆、失败恢复 | 单 Agent 执行循环 |
| 第 8 周 | Workflow、Plan-Execute、报告生成 | 深度研究工作流 |
| 第 9 周 | MCP Server / Client | 企业工具 MCP 化 |
| 第 10 周 | 多 Agent 架构 | BaseAgent + 任务路由 |
| 第 11 周 | 企业级工程化 | 权限、日志、评估、追踪 |
| 第 12 周 | 项目整合与答辩 | Know-Engine + Dodo-Agent |

## 学习资料总清单

### 官方文档

- [Spring AI Reference Documentation](https://docs.spring.io/spring-ai/reference/)
- [Spring AI Tool Calling](https://docs.spring.io/spring-ai/reference/api/tools.html)
- [Spring AI ETL Pipeline](https://docs.spring.io/spring-ai/reference/api/etl-pipeline.html)
- [Spring AI Vector Databases](https://docs.spring.io/spring-ai/reference/api/vectordbs.html)
- [Spring AI MCP Overview](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-overview.html)
- [LangChain4j Documentation](https://docs.langchain4j.dev/)
- [LangChain4j RAG Tutorial](https://docs.langchain4j.dev/tutorials/rag/)
- [LangChain4j Tools Tutorial](https://docs.langchain4j.dev/tutorials/tools/)
- [Model Context Protocol Documentation](https://modelcontextprotocol.io/docs/getting-started/intro)
- [MCP Specification - Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI API Documentation](https://platform.openai.com/docs)

### 论文与工程文章

- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Anthropic - Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

### 数据与检索组件

- [pgvector](https://github.com/pgvector/pgvector)
- [Elasticsearch kNN Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html)
- [Neo4j Vector Indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- [MinIO Documentation Repository](https://github.com/minio/docs)
- [Redisson Documentation](https://redisson.pro/docs/)

## 课程设计重点

### 重点一：不要把 Agent 当万能解法

如果任务步骤明确、失败成本高、需要审计，优先用 Workflow。Agent 适合开放问题、工具选择不固定、需要多轮探索的任务。

### 重点二：RAG 是企业 AI 应用的地基

多数企业场景不是缺 Agent，而是缺可用数据链路。文档解析、切片、检索、权限、引用溯源，比“让 Agent 自主思考”更早决定系统质量。

### 重点三：MCP 是工具接入层，不是业务系统本身

MCP 的价值是标准化工具、资源和提示词的接入方式。企业真实权限、审计、限流、幂等、数据隔离仍然要在业务系统中实现。

### 重点四：必须从第一天建立评估意识

每一个 RAG / Agent 功能都要能回答：

- 检索到了哪些材料？
- 为什么选择这个工具？
- 工具参数是什么？
- 回答引用来自哪里？
- 失败时系统如何恢复？
- 本次调用花了多少 token 和时间？

## 建议作业与考核

| 类型 | 内容 | 权重 |
| --- | --- | --- |
| 基础作业 | 模型调用、Prompt、结构化输出、Tool Calling | 20% |
| RAG 作业 | 文档解析、切片、检索、引用溯源 | 25% |
| Agent 作业 | ReAct、Workflow、失败恢复、MCP 调用 | 25% |
| 工程化作业 | 权限、日志、评估、观测、成本控制 | 15% |
| 最终项目 | Know-Engine 或 Dodo-Agent 完整演示 | 15% |

## 推荐学习顺序

建议按以下顺序推进：

```text
大模型调用
  -> Prompt / Context Engineering
  -> 结构化输出
  -> Tool Calling
  -> RAG 基础
  -> 高级 RAG
  -> 单 Agent
  -> Workflow
  -> MCP
  -> 多 Agent
  -> 企业级工程化
  -> 综合项目
```

不要一开始就做多 Agent。先把一个 Agent 做稳定，再把工具、数据、流程、权限、评估补齐，最后再拆成多 Agent 协作。

## 常见误区

- **误区 1：只学框架 API。** 正确做法是理解数据链路、工具边界、评估方法和生产约束。
- **误区 2：所有任务都交给 Agent。** 正确做法是高确定性流程用 Workflow，不确定探索才用 Agent。
- **误区 3：RAG 只做向量检索。** 企业场景通常需要全文检索、元数据过滤、权限过滤、重排和多源路由。
- **误区 4：MCP 等于 Agent。** MCP 是工具协议，Agent 是执行策略，两者可以结合但不是同一层。
- **误区 5：上线后再做观测。** AI 应用从第一版就要记录检索、工具、Prompt、token、耗时和失败原因。

## 最终作品集建议

完成课程后，建议沉淀以下材料：

- 一份 Know-Engine 架构图。
- 一份 Dodo-Agent 架构图。
- 一套 RAG 测试集和评估报告。
- 一套 MCP Server 工具清单。
- 一套 Agent 运行轨迹示例。
- 一份线上部署与安全说明。

这些材料比单纯代码更能体现你真正理解了企业级 AI Agent 的设计与落地。
