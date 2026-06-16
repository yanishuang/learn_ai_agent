# 第 7 章：高级 RAG：检索增强、多源路由与评估

更新时间：2026-06-16  
建议学习时间：7-10 天  
适合阶段：已经完成基础 RAG MVP，但发现召回、引用、表格、多源数据和效果评估仍不稳定  
本章产出：一个支持查询改写、混合检索、rerank、多源路由和回归评估的 RAG 增强版

## 7.1 本章学习目标

学完本章后，你应该能做到：

1. 诊断 RAG 效果差到底是解析、切片、召回、排序、上下文还是生成问题。
2. 实现查询改写，提升同义表达和长问题的召回率。
3. 使用向量检索 + 全文检索做混合检索。
4. 使用 rerank 提升最终上下文质量。
5. 为文档、SQL、图谱、API 设计受控多源路由。
6. 为 RAG 建立可重复运行的评估集和回归报告。
7. 明确 Text2SQL / Text2Cypher 的安全边界。

本章的核心是：不要用“感觉回答不错”判断 RAG，要用可复现测试判断每一步。

## 7.2 RAG 问题诊断表

| 现象 | 可能原因 | 优先检查 |
| --- | --- | --- |
| 完全检索不到 | query 和文档表达不一致 | 查询改写、全文检索 |
| 检索到错误文档 | 向量相似但语义不匹配 | rerank、metadata filter |
| 检索到正确文档但答错 | 上下文太长或 prompt 约束弱 | 上下文压缩、引用规则 |
| 答案没有引用 | 生成层没有强制引用 | 后端生成 citations |
| 表格问题答错 | 表格结构在切片中丢失 | 表格专门解析 |
| SQL 问答危险 | 模型生成了任意 SQL | SQL 模板、只读白名单 |
| 多源路由错 | 意图分类不稳定 | 规则优先，模型辅助 |

先定位瓶颈，再优化。不要一上来堆框架。

## 7.3 查询改写

查询改写适合处理：

- 用户问题太长。
- 口语化表达。
- 缩写、同义词。
- 多意图问题。
- 需要补全上下文的追问。

推荐输出结构：

```python
from pydantic import BaseModel, Field


class QueryRewriteResult(BaseModel):
    original_query: str
    search_queries: list[str] = Field(min_length=1, max_length=5)
    intent: str
    filters: dict[str, str] = Field(default_factory=dict)
```

示例：

```json
{
  "original_query": "入职一年后假期怎么算？",
  "search_queries": ["员工入职满一年 年假 休假制度", "年假计算规则 入职一年"],
  "intent": "policy_qa",
  "filters": {
    "document_type": "hr_policy"
  }
}
```

约束：

- 改写只用于检索，不直接回答用户。
- 改写后的 query 要记录到日志。
- 改写失败时回退原始 query。

## 7.4 混合检索

基础向量检索适合语义相近问题，但对精确词、编号、制度名、产品型号不一定稳定。混合检索结合：

| 检索方式 | 擅长 |
| --- | --- |
| 向量检索 | 语义相近、同义表达 |
| 全文检索 | 精确词、编号、名称、专业术语 |
| 元数据过滤 | 租户、部门、文档类型、时间范围 |

融合策略可以先用简单加权：

```python
final_score = vector_score * 0.7 + keyword_score * 0.3
```

也可以使用 Reciprocal Rank Fusion：

```python
def rrf(rank: int, k: int = 60) -> float:
    return 1 / (k + rank)
```

本章优先实现可解释、可调参的融合方式，不追求复杂算法。

## 7.5 Rerank

Rerank 的作用是对初步召回的候选 chunk 重新排序。

推荐流程：

```text
query
  -> vector top 20
  -> keyword top 20
  -> merge/deduplicate
  -> rerank top 10
  -> context top 5
```

Rerank 适合解决：

- Top-K 里有正确片段，但排得靠后。
- 向量召回片段相似但不回答问题。
- 需要更高引用准确率。

注意：

- rerank 会增加延迟和成本。
- rerank 输入不要太多，先召回 20-50 个候选即可。
- rerank 结果要记录，便于评估。

## 7.6 Metadata 与权限过滤

企业 RAG 里，metadata 不是锦上添花，而是安全边界。

常见 metadata：

| 字段 | 说明 |
| --- | --- |
| `tenant_id` | 租户隔离 |
| `department_id` | 部门权限 |
| `document_type` | 制度、合同、产品手册 |
| `security_level` | 公开、内部、机密 |
| `effective_date` | 生效时间 |
| `owner_user_id` | 文档所有人 |

权限过滤原则：

1. 检索 SQL 中必须带租户过滤。
2. 用户无权访问的文档不能进入候选集。
3. 不要先把无权限 chunk 送给模型再让模型“不要使用”。
4. retrieval hits 日志只保存用户可见片段。

## 7.7 表格与 Excel 处理

表格是 RAG 的高发失败点。不要把 Excel 直接转成一坨文本。

推荐方法：

| 表格类型 | 处理方式 |
| --- | --- |
| 简单二维表 | 转 Markdown table，并保留表名、表头 |
| 多 sheet Excel | 每个 sheet 单独建元数据 |
| 合并单元格 | 展开合并值，保留原始坐标 |
| 指标表 | 转成长表结构，方便查询 |
| 大表 | 不适合塞进 RAG，转 SQL 查询 |

表格 chunk metadata：

```json
{
  "source_type": "excel",
  "sheet_name": "Q1销售",
  "row_range": "2-20",
  "columns": ["产品", "销售额", "同比增长"]
}
```

判断原则：

- 小表可以 RAG。
- 大表和强计算问题应该走 SQL。
- RAG 不应该替代数据仓库。

## 7.8 Text2SQL 的边界

Text2SQL 可以提升结构化数据问答能力，但风险很高。

禁止做法：

```text
用户问题 -> 模型生成任意 SQL -> 直接执行生产数据库
```

推荐做法：

```text
用户问题
  -> 意图识别
  -> 选择只读查询模板
  -> 填充有限参数
  -> 后端权限校验
  -> 只读副本执行
  -> 返回结构化摘要
```

示例模板：

```sql
select product_name, sales_amount, growth_rate
from sales_summary
where tenant_id = :tenant_id
  and quarter = :quarter
order by growth_rate desc
limit :limit;
```

约束：

- 只允许 SELECT。
- 只查只读副本。
- 表和字段白名单。
- 参数化查询。
- 强制 `tenant_id`。
- 记录 SQL 模板 ID，而不是只记录自然语言问题。

## 7.9 Text2Cypher 与图谱查询

图谱适合：

- 组织关系。
- 产品依赖。
- 知识点关系。
- 供应链关系。
- 权限继承关系。

初学阶段建议用固定 Cypher 模板：

```cypher
match (p:Product {id: $product_id})-[:DEPENDS_ON]->(d:Dependency)
return d.name, d.version, d.risk_level
limit 20
```

不要让模型自由生成复杂 Cypher 后直接执行。图谱查询同样需要：

- 标签白名单。
- 关系白名单。
- 参数校验。
- 结果行数限制。
- 查询超时。

## 7.10 多源路由

多源路由的目标是判断问题应该查哪里：

| 意图 | 数据源 |
| --- | --- |
| 制度/文档问答 | RAG 文档库 |
| 销售额/库存/订单统计 | SQL |
| 组织关系/依赖关系 | 图谱 |
| 实时状态 | 外部 API / MCP 工具 |
| 概念解释 | 模型直接回答或课程知识库 |

路由策略：

1. 规则优先：有订单号就查订单工具。
2. 高风险数据源必须显式确认。
3. 模型路由输出必须结构化。
4. 路由结果要可回放。

路由输出：

```python
from typing import Literal


class RetrievalRoute(BaseModel):
    route: Literal["document", "sql", "graph", "api", "direct"]
    reason: str
    confidence: Literal["high", "medium", "low"]
```

低置信度时不要乱查，应该追问用户或使用更保守的数据源。

## 7.11 RAG 评估体系

基础评估指标：

| 层级 | 指标 | 说明 |
| --- | --- | --- |
| 检索 | hit@k | 预期文档是否进入前 K |
| 检索 | context_recall | 答案所需信息是否被检索到 |
| 检索 | context_precision | 检索结果是否噪声过多 |
| 生成 | faithfulness | 答案是否忠实于上下文 |
| 生成 | answer_correctness | 答案是否符合预期事实 |
| 引用 | citation_accuracy | 引用是否真的支持结论 |
| 安全 | refusal_accuracy | 资料不足时是否拒答 |

最小评估脚本输出：

```json
{
  "total": 30,
  "retrieval_hit_rate": 0.83,
  "citation_present_rate": 0.9,
  "refusal_accuracy": 0.75,
  "failed_cases": ["case_004", "case_011", "case_019"]
}
```

第 7 章建议先用规则指标和人工抽检，不急着引入复杂自动评委。后续可以比较 RAGAS、DeepEval、LlamaIndex evaluation。

## 7.12 回归测试集设计

评估集至少包含：

| 类型 | 数量 | 目的 |
| --- | --- | --- |
| 明确答案 | 10 | 验证基本问答 |
| 同义表达 | 5 | 验证查询改写 |
| 资料不足 | 5 | 验证拒答 |
| 表格问题 | 5 | 验证表格处理 |
| 权限问题 | 5 | 验证权限过滤 |

用例格式：

```json
{
  "id": "case_021",
  "question": "Q1 增长最快的产品是什么？",
  "route": "sql",
  "expected_answer_keywords": ["产品A", "增长率"],
  "expected_sources": ["sales_summary"],
  "must_refuse": false
}
```

每次改动切片、检索、rerank、prompt、模型，都跑同一套评估集。

## 7.13 实施顺序

推荐按下面顺序做：

1. 先保存第 6 章的评估集基线。
2. 增加查询改写。
3. 增加全文检索。
4. 增加融合排序。
5. 增加 rerank。
6. 增加表格特殊处理。
7. 增加 SQL 路由。
8. 增加图谱路由。
9. 对比每一步评估结果。

不要同时改多个变量，否则不知道效果来自哪里。

## 7.14 MVP / 进阶 / 生产化验收

### MVP

- 有 30 条 RAG 评估用例。
- 支持查询改写。
- 支持向量 + 全文混合检索。
- 支持 retrieval hits 回放。
- 能输出评估报告。

### 进阶

- 支持 rerank。
- 支持表格 chunk metadata。
- 支持 SQL 只读模板查询。
- 支持路由输出结构化。
- 能对比不同检索策略的效果。

### 生产化

- 权限过滤覆盖文档、SQL、图谱。
- 评估集进入 CI。
- 每次发版有 RAG 回归报告。
- 支持检索策略版本化。
- 支持线上失败样本回流到评估集。

## 7.15 常见误区

- 只看最终回答，不看检索结果。
- 用模型自动评分替代人工校验所有事实。
- 让模型生成任意 SQL。
- 先查全库再过滤权限。
- RAG 查表格时不保留表头和坐标。
- 同时调整切片、embedding、top_k、prompt，导致无法定位收益。

## 7.16 本章学习资料

- [LlamaIndex Evaluating](https://developers.llamaindex.ai/python/framework/module_guides/evaluating/)
- [RAGAS](https://docs.ragas.io/)
- [DeepEval](https://docs.confident-ai.com/)
- [Elasticsearch kNN Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html)
- [Neo4j Vector Indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- [pgvector](https://github.com/pgvector/pgvector)

## 7.17 本章复盘模板

```markdown
# 第 7 章复盘

## 我的基础 RAG 最大问题是什么

## 查询改写带来了什么变化

## 混合检索和纯向量检索的对比

## Rerank 是否提升了引用准确率

## 我如何处理表格数据

## 哪些问题走文档，哪些问题走 SQL / 图谱

## 我的评估集有哪些类型

## 当前失败最多的 case 是什么
```
