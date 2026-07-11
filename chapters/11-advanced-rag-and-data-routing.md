# 第 11 章：高级 RAG 与受治理的数据路由

更新时间：2026-07-10
建议学习时间：7-10 天
本章产出：一个以 RRF 为默认融合策略的高级检索设计、一份多源路由合同、一套 Text2SQL 信任边界，以及一份基于同一评估集的策略对比报告。

## 本章定位

第 7 章已经建立确定性、权限优先、可引用和资料不足拒答的 RAG Core。本章只在测量发现真实瓶颈后增加查询改写、混合检索、rerank、表格处理和结构化数据路由。复杂组件不能补救错误 ACL、不可复现评估或缺失引用。

参考实现当前只有依赖少、完全离线的 `InMemoryRetriever`，没有生产全文索引、向量库、reranker、SQL parser 或数据库凭证。本文的 RRF 函数可直接运行；多源生产控制是明确的实现设计，不描述成参考应用已经具备的能力。

## 前置知识

- 已完成第 7、9 章，理解 `DocumentChunk`、`RetrievalHit`、引用、权限前置过滤和 RAG 回归评估。
- 理解排序、集合去重、参数化 SQL、只读数据库角色和 pytest。
- 已按 `reference-implementation/README.md` 同步环境；默认测试不需要 API Key、向量服务或数据库。

## 学习目标

完成本章后，你应该能够：

1. 把解析、切片、授权、召回、融合、rerank、上下文和生成问题分开诊断。
2. 用原始 query fallback 做受控查询改写。
3. 用 Reciprocal Rank Fusion 融合向量和关键词排名，而不假设两类分数可直接相加。
4. 说明 weighted score fusion 为什么必须先归一化并用数据验证。
5. 为表格、文档、SQL、图谱、API 设计权限一致的结构化路由。
6. 把 Text2SQL 限制在模板或 AST 验证、只读凭证、超时、行数、租户和审计边界内。
7. 用同一评估集证明复杂检索相对 Core 的收益、延迟和失败变化。

## 核心知识

### 11.1 先定位瓶颈

| 现象 | 可能原因 | 最先验证 |
| --- | --- | --- |
| 完全检索不到 | 解析/切片丢失，query 表达不一致 | 原文、chunk、原始 query hit@k |
| 正确 chunk 被 ACL 排除 | 身份或文档策略错误 | 可信 `RunContext` 与授权日志 |
| 正确 chunk 排名靠后 | 单路召回偏差 | 分路 ranking、RRF 前后名次 |
| top-k 正确但回答错 | 上下文或生成问题 | quote、citation、拒答规则 |
| 编号/型号不稳定 | 向量不擅长精确词 | 关键词/全文检索 |
| 表格计算错 | 表头、单位、坐标丢失 | 结构化表格或 SQL route |
| 跨租户命中 | 过滤在召回后执行 | 数据源查询与 ACL 顺序 |

每次只改变一个变量并保存策略版本。先把第 7 章结果作为 baseline，再比较 rewrite、第二路召回、RRF、rerank 和路由各自的增量。

### 11.2 查询改写与 fallback

查询改写只产生检索候选，不直接回答用户，也不能添加用户没有的权限或事实：

```python
from pydantic import BaseModel, Field


class QueryRewriteResult(BaseModel):
    original_query: str
    search_queries: list[str] = Field(min_length=1, max_length=5)
    intent: str
    filters: dict[str, str] = Field(default_factory=dict)
```

`search_queries` 必须包含原始 query 或在改写失败时回退原始 query。过滤字段只允许从服务端白名单映射；模型不能生成 `tenant_id`、用户权限或任意数据库条件。日志记录原始 query、改写列表、模型/提示版本和 fallback 原因，敏感内容按数据策略脱敏。

### 11.3 混合检索默认使用 RRF

向量检索擅长语义和同义表达，全文/关键词检索擅长编号、名称和精确术语。元数据与 ACL 不是第三个相关性分数，而是在每条召回路径中先执行的候选资格条件。

默认融合输入是每个检索器按相关性排好的稳定 ID 列表。使用下面这个可运行的 RRF 实现：

```python
def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.__getitem__, reverse=True)
```

示例：

```python
vector_ids = ["chunk-b", "chunk-a", "chunk-d"]
keyword_ids = ["chunk-a", "chunk-c", "chunk-b"]

assert reciprocal_rank_fusion([vector_ids, keyword_ids]) == [
    "chunk-a",
    "chunk-b",
    "chunk-c",
    "chunk-d",
]
```

RRF 只依赖名次，不要求 BM25、余弦距离或供应商分数处于同一尺度。`k=60` 是起点，不是普适最优值；在固定评估集上调整。生产函数还应验证 `k > 0`、空 ID、每路重复 ID 和稳定 tie-break。上面的函数按 brief 保持最小教学合同；相同融合分数依赖首次插入顺序，因此每条输入 ranking 本身必须稳定。

### 11.4 Weighted score fusion 是受验证的替代项

不要直接写：

```python
final_score = vector_score * 0.7 + keyword_score * 0.3
```

原始向量相似度、距离、BM25 分数和 reranker logit 的方向、范围与分布不同。Weighted score fusion 只有在以下条件全部满足时才可采用：

1. 明确每种分数是越大越好还是越小越好，并将方向统一。
2. 在固定语料和查询分布上做归一化，例如有界 min-max、z-score 后映射或校准模型。
3. 处理零方差、极值、缺失分数和索引版本变化。
4. 用 held-out 评估集验证权重，而不是凭感觉选 `0.7/0.3`。
5. 保存归一化参数、索引版本、权重和评估证据。

当供应商分数定义或分布变化时必须重新校准。没有这些证据就使用 RRF。

### 11.5 Dedup、rerank 与上下文预算

推荐管线：

```text
可信身份/ACL
  -> vector top 20 + keyword top 20
  -> RRF + stable ID dedup
  -> 可选 rerank top 10
  -> context top 5 + token budget
  -> grounded answer + citations
```

去重使用稳定 `chunk_id` 或 `(document_id, document_version, chunk_id)`，不能只按文本。rerank 只接收用户可见候选，记录输入顺序、输出顺序、模型版本、延迟和成本。它增加了模型和供应链边界；只有 citation accuracy、context precision 或任务成功有稳定提升时才保留。

### 11.6 表格与结构化数据

| 数据形态 | 默认路径 | 必须保留 |
| --- | --- | --- |
| 小型说明表 | Markdown/结构化 chunk | 表名、表头、单位、sheet、行列范围 |
| 多 sheet Excel | 每 sheet 独立摄取 | workbook/sheet/version/ACL |
| 合并单元格 | 解析时展开 | 原值与坐标映射 |
| 大型事实表/聚合 | SQL | schema、度量定义、租户边界 |
| 实时订单/库存 | API 或 MCP tool | 服务端权限、超时、审计 |

RAG 不替代数据仓库。表格问题若需要过滤、聚合或精确计算，应路由到受控结构化查询，而不是把整张表塞给模型。

### 11.7 多源路由合同

```python
from typing import Literal

from pydantic import BaseModel


class RetrievalRoute(BaseModel):
    route: Literal["document", "sql", "graph", "api", "direct", "clarify"]
    reason: str
    confidence: Literal["high", "medium", "low"]
```

规则先处理稳定信号，例如订单 ID、显式报表名和用户要求的文档。模型只输出受限 route；后端根据可信用户、租户、数据分类和风险再次授权。低置信度、多意图或高风险请求进入 `clarify`/Workflow，不能把 confidence 当作授权。

每个 route 统一输出结构化结果、来源、数据版本、权限决策和 trace ID。这样最终生成层不需要猜测 SQL 行、图节点和文档 citation 的来源。

### 11.8 Text2SQL：模板优先

Core/Advanced 的首选是固定模板加有限参数：

```sql
select product_name, sales_amount, growth_rate
from sales_summary
where tenant_id = :tenant_id
  and quarter = :quarter
order by growth_rate desc
limit :row_limit;
```

模板 ID 由路由选择；`tenant_id` 来自可信上下文，`quarter` 通过枚举/格式校验，`row_limit` 由服务端设置上限。模型不能提供凭证、租户、表名、字段名、排序表达式或 SQL 片段。

### 11.9 自由度更高的 Text2SQL 必须过 AST

如果评估证明模板覆盖率不足，Production 设计可以引入 SQL parser（例如 SQLGlot）并校验抽象语法树。**正则或字符串前缀检查不是 SQL 安全边界。** 实现必须：

1. 只接受单条 statement，parse 失败即拒绝。
2. AST 根节点只允许查询；拒绝 DDL、DML、COPY、CALL、事务、注释逃逸和多 statement。
3. 对每个 table、column、function、join、subquery 和 set operation 做 allowlist/复杂度限制。
4. 在 AST 中注入或验证不可移除的 `tenant_id` 条件；外层有 tenant filter 但子查询泄露也必须拒绝。
5. AST 重写服务端 `LIMIT`，不能信任模型给出的更大值或只在返回后截断。
6. 用独立只读数据库凭证连接只读副本；数据库角色本身不得写入或绕过 row-level security。
7. 每个事务设置较短 `statement_timeout`，同时限制连接、锁等待、内存/扫描预算和并发。
8. 审计原始问题、route、模板或规范化 AST hash、实际参数、可信租户、数据库角色、行数、耗时、超时/拒绝原因和结果摘要。

AST 验证、只读凭证、statement timeout、row limit、tenant enforcement 和 audit 是相互独立的纵深控制；缺一个不能由另一个替代。数据库端 RLS 可以再加一层，但应用仍要显式传递并验证租户。

### 11.10 Text2Cypher 与图查询

图查询同样模板优先，固定标签、关系、方向、返回字段和 `LIMIT`：

```cypher
match (p:Product {tenant_id: $tenant_id, id: $product_id})
      -[:DEPENDS_ON]->(d:Dependency)
return d.name, d.version, d.risk_level
limit 20
```

更自由的 Cypher 需要 parser/AST、只读角色、标签/关系 allowlist、tenant 约束、遍历深度、路径数量、timeout、row limit 和审计，不能把自然语言直接变成生产查询。

### 11.11 评估与选择门槛

至少比较：hit@k、context recall/precision、citation accuracy、拒答准确率、权限泄露数、端到端任务成功、p50/p95 延迟和每 query 成本。对每个阶段保存失败 case，而不只报平均值。

升级门槛示例：RRF 相对单路 baseline 提升关键 query 的 hit@10 且不产生 ACL 回归；rerank 提升 citation accuracy 足以覆盖延迟/成本；Text2SQL 提高结构化问题成功率且所有越权、超时和大结果 case 被后端阻断。没有可测收益就删除复杂层。

## 教师演示

1. 运行第 7 章 focused tests，确认授权在打分前发生。
2. 用两组固定 ranking 执行 RRF，逐项计算 `1 / (k + rank)` 并解释稳定 ID 去重。
3. 故意把未归一化 BM25 与距离分数相加，展示尺度变化如何翻转结果。
4. 展示固定 SQL 模板如何从可信上下文注入租户和 row limit。
5. 用 `SELECT ...; DELETE ...`、跨租户子查询和超大 LIMIT 说明为什么必须解析 AST 并叠加数据库控制。

## 学员实验

本章没有单独的 Core lab 目录，因为它是 enrichment。Advanced 学员在自己的提交中使用独立 Python 草稿和新增测试完成：

1. 保存第 7 章检索结果作为 baseline。
2. 为固定 vector/keyword rankings 运行 `reciprocal_rank_fusion()`，测试重复候选、空 ranking 和稳定顺序。
3. 写 query rewrite fixture，验证失败时原始 query 仍被检索。
4. 为 document/sql/graph/api/direct/clarify 写至少 20 条 route case。
5. 设计两个固定 SQL 模板和可信参数映射。
6. Advanced 设计：写 AST allowlist、tenant 注入、timeout、row limit、只读角色和审计测试矩阵；不要求连接真实数据库。
7. 用同一评估集比较 baseline、RRF 和可选 rerank，记录收益与代价。

## 失败注入与排错

| 注入 | 预期结果 | 首查位置 |
| --- | --- | --- |
| 一路 ranking 为空 | 其余 ranking 仍可融合 | RRF 输入 |
| 同一 ID 在一路重复 | 生产 wrapper 拒绝或先去重 | ranking contract |
| BM25 分布升级后改变 | weighted fusion 重新校准 | normalization version |
| 改写产生无关 query | 原始 query fallback 保留 | rewrite trace |
| rerank 收到无权 chunk | 测试失败，修复 ACL 顺序 | candidate boundary |
| 多 statement SQL | AST gate 拒绝 | parser |
| 缺少 tenant predicate | 后端注入或拒绝 | AST/RLS |
| 慢查询 | statement timeout 中止 | DB session |
| 模型要求 100000 行 | 服务端重写为上限 | AST/row limit |

排错从 source/ACL、每路 ranking、融合、rerank、context、route、数据源执行到生成逐层进行。不要只看最终回答。

## 自动验证

当前参考实现的 focused RAG tests 完全离线：

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_rag.py -q
```

课程完整回归：

```bash
cd reference-implementation
uv run --group dev --extra live pytest -q
```

RRF fence 还应通过 Python AST/直接执行检查。当前参考 suite 验证基础检索、真实 quote、租户/用户/权限过滤和拒答；它尚未验证 RRF、rerank、数据库 AST 或真实凭证。后者必须由学习者在 Advanced/Production 实现中增加确定性测试后才能声称完成。

## 作业与评分

| 项目 | 权重 | 评分证据 |
| --- | --- | --- |
| 诊断与 baseline | 20% | 分层失败 case 与原始指标 |
| RRF 实现 | 25% | 函数、固定 ranking 断言、稳定 ID 说明 |
| 路由与权限 | 20% | 结构化 route、低置信度和 ACL 测试 |
| Text2SQL 控制 | 25% | AST/模板、只读、timeout、limit、tenant、audit |
| 增量评估 | 10% | 同一数据集上的收益、延迟和成本 |

直接加权未归一化分数、召回后再做 ACL、自由 SQL 直连生产库或只靠 prompt 限制 SQL，均不能通过。

## Core / Advanced / Production 完成标准

| 等级 | 完成标准 |
| --- | --- |
| Core | 保持第 7 章权限与引用保证；RRF 函数和固定测试可运行；能解释为何不直接融合原始分数。 |
| Advanced | 有 rewrite fallback、RRF、可选 rerank、表格 metadata、多源 route 和模板 SQL 的对比评估。 |
| Production | 实现 parser/AST gate、只读凭证/副本、statement timeout、row/资源限制、不可绕过 tenant enforcement、审计、版本化和回归门禁。 |

## 本章资料

- [PostgreSQL Full Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [Elasticsearch Reciprocal Rank Fusion](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)
- [Elasticsearch kNN Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html)
- [pgvector](https://github.com/pgvector/pgvector)
- [SQLGlot AST](https://sqlglot.com/sqlglot.html)
- [PostgreSQL Client Connection Defaults - statement_timeout](https://www.postgresql.org/docs/current/runtime-config-client.html)
- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)

## 复盘模板

```markdown
# 第 11 章复盘

## baseline 的瓶颈在哪一层

## 查询改写如何保留原始 query fallback

## 两路 ranking 如何经过 RRF 和稳定去重

## 为什么没有直接融合原始分数

## rerank 是否带来可测净收益

## 每个 route 如何继承相同 ACL

## Text2SQL 的 AST、凭证、timeout、limit、tenant 和 audit 如何实现

## 哪个复杂组件因为没有收益而被删除
```
