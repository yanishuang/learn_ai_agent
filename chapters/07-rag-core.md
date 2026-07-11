# 第 7 章：RAG 核心：从文档到可信答案

更新时间：2026-07-10
建议学习时间：7-10 天
本章产出：一个确定性、权限感知、能拒答并返回真实引用的离线 RAG；以及一份可迁移到 PostgreSQL/pgvector 的版本化数据与授权查询设计。

## 本章定位

RAG 不是“把向量查出来再塞给模型”，而是一条可检查的数据链：来源解析、版本化、切片、索引、授权过滤、相关性排序、上下文组装、回答和引用。任何一环缺少身份、版本或来源，答案就难以复现。

参考实现的主线刻意保持离线和确定性：`InMemoryRetriever` 使用规范化 token overlap，不调用 embedding 服务，不要求 PostgreSQL，也不调用生成模型。它已经实现租户、用户 allowlist 和权限集合过滤、阈值、稳定排序、拒答与引用。PostgreSQL/pgvector、完整摄取元数据、HNSW/IVFFlat 和用户访问表属于本章的**生产数据模型设计练习**，不是当前可执行实现。

## 前置知识

- 已完成第 3 章的上下文来源与间接提示词注入威胁模型。
- 已完成第 4-6 章，理解 Pydantic 边界对象、`RunContext`、工具权限和确定性测试。
- 能阅读基本 SQL、pytest 和排名指标。
- 已按 `reference-implementation/README.md` 同步环境；本章命令从 `reference-implementation/` 执行。

## 学习目标

完成本章后，你应该能够：

1. 解释摄取、切片、索引、授权检索、回答与引用的完整链路。
2. 使用当前 `DocumentChunk`、`RetrievalHit`、`RagCitation` 和 `RagAnswer` 合同。
3. 在相关性计算之前执行租户、用户 allowlist 和 trusted permission 过滤。
4. 设计包含 `document_version`、`content_hash`、`embedding_model`、`embedding_dimensions`、`chunker_version`、`page_number`、`source_offset` 和 `access_scope` 的生产数据模型。
5. 在 SQL 检索查询本身加入租户和用户访问条件，而不是先取回越权候选再在 Python 中过滤。
6. 比较 HNSW 与 IVFFlat 的构建、内存、查询、调参和过滤权衡。
7. 从检索 hit 构造真实 quote，并在授权资料不足时稳定拒答。
8. 用确定性 case 回归检索、引用和租户隔离。

## 核心知识

### 7.1 可执行 RAG 合同

当前参考实现的 `DocumentChunk` 字段必须原样理解：

| 字段 | 当前语义 |
| --- | --- |
| `chunk_id` | 片段 ID，非空 |
| `document_id` | 来源文档 ID，非空 |
| `tenant_id` | 强制租户边界，非空 |
| `title` | 可展示来源标题，非空 |
| `content` | 检索和 quote 的原始片段，非空 |
| `allowed_user_ids` | `None` 表示不做用户 allowlist；集合表示只允许列出的用户 |
| `required_permissions` | chunk 所需权限集合，必须是 `RunContext.permissions` 的子集 |

返回对象为：

- `RetrievalHit(chunk_id, document_id, title, content, score, citation)`，其中 `score` 在 0 到 1 之间。
- `RagCitation(citation_id, document_id, chunk_id, title, quote)`，`citation_id` 从 1 开始。
- `RagAnswer(answer, citations=(), refused=False)`。

当前回答对象没有 `confidence`、`missing_info`、page number 或 URI。不要在示例 API 中声称这些字段已经存在。

### 7.2 授权必须先于相关性

`InMemoryRetriever.search(query, context, top_k)` 的执行顺序是：

1. 要求 `top_k > 0`。
2. 对每个 chunk 先检查 `tenant_id`。
3. 再检查 `allowed_user_ids`。
4. 再检查 `required_permissions <= context.permissions`。
5. 只有可见 chunk 才计算 token overlap 和最低匹配词数。
6. 按 `(-score, document_id, chunk_id)` 稳定排序，最后截取 `top_k`。

这个顺序同时是安全边界和评估边界。若先对全库做 top-k，再从结果中删掉越权项，至少有四个问题：候选数量和时序会泄露信息、授权结果可能不足 top-k、索引/缓存可能记录越权内容、评分与线上行为不一致。

### 7.3 离线检索与拒答

下面示例与参考实现完全一致：

```python
from agent_course.core import RunContext
from agent_course.rag import DocumentChunk, InMemoryRetriever


context = RunContext(
    user_id="user-1",
    tenant_id="tenant-1",
    request_id="chapter-07-demo",
    permissions=frozenset({"knowledge:read"}),
)
retriever = InMemoryRetriever(
    [
        DocumentChunk(
            chunk_id="hr-leave",
            document_id="hr-policy",
            tenant_id="tenant-1",
            title="HR Policy - Annual Leave",
            content="Employees receive 15 days of paid annual leave each year.",
            required_permissions=frozenset({"knowledge:read"}),
        ),
        DocumentChunk(
            chunk_id="other-tenant",
            document_id="private-plan",
            tenant_id="tenant-2",
            title="Private Plan",
            content="Employees receive 30 days of paid annual leave each year.",
        ),
    ]
)

answer = retriever.answer("paid annual leave days", context, top_k=3)

assert answer.refused is False
assert answer.answer == (
    "Employees receive 15 days of paid annual leave each year. [1]"
)
assert answer.citations[0].document_id == "hr-policy"
assert answer.citations[0].quote in retriever.search(
    "paid annual leave days", context, top_k=3
)[0].content
```

评分是 `query token` 被内容覆盖的比例。默认 `min_score=0.5`，并要求至少匹配 `min(2, query token 数)` 个词，防止“leave password”只因一个词重合就错误回答。没有授权且足够相关的 hit 时，`answer()` 返回：

```text
根据当前资料无法确认。
```

同时 `refused=True`、`citations=()`。这是一条确定性拒答合同，不是模型自报低置信度。

### 7.4 来源与引用

引用必须由检索层从真实 hit 构造：

1. `_best_quote()` 把 chunk 按句界切分。
2. 选择 query overlap 最高的句子；并列时保留较早句子。
3. 后端分配连续 `citation_id`。
4. 回答中的 `[1]` 对应返回的第一个 `RagCitation`。

最小不变量：

```python
def citation_is_grounded(hit_content: str, quote: str) -> bool:
    return bool(quote) and quote in hit_content
```

生产系统还应验证 document/version 可读取、引用区间对应原始来源、页面或 offset 没有跨版本漂移。模型可以组织回答，不能自己发明 citation ID、文档标题或 quote。

### 7.5 生产数据模型设计练习

**以下 SQL 是设计练习，不是参考实现已经创建的表。** `reference-implementation/compose.yaml` 只提供可选 PostgreSQL/pgvector 服务，默认测试不会启动它，也没有迁移脚本。

逻辑文档是 ACL 的唯一事实来源；版本表保存内容历史，`current_published_version` 是默认检索边界：

```sql
create table documents (
  id text not null,
  tenant_id text not null,
  title text not null,
  source_uri text,
  access_scope text not null check (access_scope in ('tenant', 'users')),
  allowed_user_ids text[] not null default '{}',
  required_permissions text[] not null default '{}',
  current_published_version integer check (current_published_version > 0),
  created_by text not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, id),
  check (access_scope = 'users' or cardinality(allowed_user_ids) = 0)
);

create table document_versions (
  tenant_id text not null,
  document_id text not null,
  document_version integer not null check (document_version > 0),
  content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
  publication_status text not null
    check (publication_status in ('building', 'published', 'retired')),
  created_at timestamptz not null default now(),
  primary key (tenant_id, document_id, document_version),
  unique (tenant_id, document_id, content_hash),
  foreign key (tenant_id, document_id)
    references documents (tenant_id, id)
);

create unique index document_versions_one_published_idx
  on document_versions (tenant_id, document_id)
  where publication_status = 'published';

alter table documents
  add constraint documents_current_published_version_fk
  foreign key (tenant_id, id, current_published_version)
  references document_versions (tenant_id, document_id, document_version)
  deferrable initially deferred;
```

版本化 chunk 与 embedding 表：

```sql
create extension if not exists vector;

create table document_chunks (
  id text primary key,
  document_id text not null,
  tenant_id text not null,
  document_version integer not null check (document_version > 0),
  embedding_model text not null,
  embedding_dimensions integer not null check (embedding_dimensions = 1536),
  chunker_version text not null,
  chunk_index integer not null check (chunk_index >= 0),
  page_number integer check (page_number > 0),
  source_offset integer not null check (source_offset >= 0),
  content text not null,
  embedding vector(1536) not null,
  foreign key (tenant_id, document_id, document_version)
    references document_versions (tenant_id, document_id, document_version),
  unique (
    tenant_id,
    document_id,
    document_version,
    chunker_version,
    chunk_index,
    embedding_model
  )
);
```

`document_chunks` 故意不复制 `access_scope`、`allowed_user_ids` 或 `required_permissions`。这样 chunk 不可能带着比所属文档更宽松的 ACL；复合外键还保证 chunk 的 tenant/document/version 组合确实存在。若业务需要片段级限制，应建立受外键约束的独立 ACL 关系并在查询中同时收紧，不能新增无人校验的重复列。

这些字段解决的问题不同：

| 字段 | 必须回答的问题 |
| --- | --- |
| `document_version` | hit 来自文档的哪一版，更新后能否回放旧答案；默认由 `current_published_version` 选定 |
| `content_hash` | 版本内容是否真的变化，摄取能否幂等去重 |
| `embedding_model` | 哪个模型生成向量，能否安全比较 query/document 向量 |
| `embedding_dimensions` | 存储维度与模型输出是否一致 |
| `chunker_version` | 切片算法变更后如何重建并比较 |
| `page_number` | 可分页来源的显示定位；非分页来源可为 `NULL` |
| `source_offset` | chunk 在规范化源文本中的起点，用于精确追溯 |
| `access_scope` | 逻辑文档是租户内可见还是仅指定用户可见；它是 chunk 查询的权威 ACL |

同一 vector 列的维度是 schema 级约束。若更换为不同维度，应该创建新的列/表/分区并重建索引，不能只改 `embedding_dimensions` 元数据后继续混算。

### 7.6 授权条件必须写进 SQL

**以下仍是生产设计练习。** 查询同时带入认证层提供的 `tenant_id`、`user_id` 和 permission 数组；这些参数不能来自模型生成的 tool arguments。正常检索令两个 replay 参数都为 `NULL`，只读取每个文档当前发布版本；受授权的审计回放必须同时给出一个 document/version，才能读取保留的旧向量。

```sql
select
  c.id,
  c.document_id,
  c.document_version,
  d.title,
  c.content,
  c.page_number,
  c.source_offset,
  1 - (c.embedding <=> :query_embedding) as score
from document_chunks as c
join documents as d
  on d.tenant_id = c.tenant_id
 and d.id = c.document_id
join document_versions as v
  on v.tenant_id = c.tenant_id
 and v.document_id = c.document_id
 and v.document_version = c.document_version
where d.tenant_id = :tenant_id
  and c.embedding_model = :embedding_model
  and c.embedding_dimensions = :embedding_dimensions
  and (
    d.access_scope = 'tenant'
    or (
      d.access_scope = 'users'
      and :user_id = any(d.allowed_user_ids)
    )
  )
  and d.required_permissions <@ cast(:trusted_permissions as text[])
  and (
    (
      :replay_document_id is null
      and :replay_document_version is null
      and d.current_published_version is not null
      and c.document_version = d.current_published_version
      and v.publication_status = 'published'
    )
    or (
      :replay_document_id is not null
      and :replay_document_version is not null
      and c.document_id = :replay_document_id
      and c.document_version = :replay_document_version
      and v.publication_status in ('published', 'retired')
    )
  )
order by c.embedding <=> :query_embedding
limit :top_k;
```

这里的租户、用户和权限过滤都读取 `documents`，与 ANN 排序处于同一查询；chunk 自身没有可漂移的 ACL。普通查询还必须同时满足发布指针和 `publication_status='published'`。发布新版本时，在一个事务中把旧版本标为 `retired`、新版本标为 `published`，再移动 `current_published_version`；旧 chunk/vector 不删除，只能通过受控 replay 参数读取。应用层仍需校验 replay 权限和结果授权，但不能删除这些 SQL 条件。

### 7.7 HNSW 与 IVFFlat 的取舍

不要把 IVFFlat 当成通用默认值。两者都需要用真实数据量、过滤选择性、延迟目标和 recall 评估。

| 维度 | HNSW | IVFFlat |
| --- | --- | --- |
| 建索引 | 通常更慢、占内存更多 | 通常更快、结构更紧凑 |
| 数据准备 | 不需要训练聚类中心 | 应在有代表性数据后构建 lists |
| 查询 | 常有较好的速度/recall 平衡 | 依赖 `lists` 和查询时 `probes` 调参 |
| 写入变化 | 支持增量，但图维护成本较高 | 数据分布变化后可能需要重建/重调 |
| 内存 | 较高 | 通常较低 |
| 过滤后结果 | 高选择性过滤仍可能减少有效候选，需要测 iterative scan/搜索参数 | 过滤与 probes 共同影响候选和 recall |
| 适合起点 | recall 与低延迟更重要、内存可接受 | 数据规模较大、资源更紧、愿意做聚类与 probes 调优 |

索引选择流程：先保留无 ANN 的精确搜索作为小数据基线；再分别测 HNSW 和 IVFFlat 的 p50/p95 延迟、recall@k、索引时间、磁盘/内存和带授权过滤后的有效 hit 数。最终选择来自数据，不来自教程习惯。

### 7.8 摄取、切片与重建

生产设计中的推荐状态是：

```text
uploaded -> parsing -> chunking -> embedding -> indexed
                                      \-> failed
```

每次摄取应：

1. 规范化来源并计算 `content_hash`。
2. 若 hash 和版本策略表明未变化，幂等返回现有索引结果。
3. 以 `building` 状态创建版本，使用显式 `chunker_version` 生成 chunk，并保存 page/offset。
4. 使用显式 `embedding_model` 和维度生成向量。
5. 在同一事务中发布版本并移动 `current_published_version`；不要让半完成版本进入查询。
6. 保留旧版本和向量用于授权回放，再按明确保留策略清理。

参考实现没有实现这条摄取 pipeline；本章 Core 只要求理解并验证离线 retrieval 合同。

### 7.9 RAG 评估起点

确定性测试优先检查：

| 指标/断言 | 问题 |
| --- | --- |
| authorization exclusion | 其他租户、其他用户、缺权限 chunk 是否完全不出现 |
| retrieval hit | 预期 chunk 是否进入 top-k |
| stable rank | 相同输入是否得到相同顺序 |
| quote grounding | citation quote 是否是 hit content 的真实子串 |
| refusal correctness | 无授权答案或相关性不足时是否拒答 |
| answer grounding | 最终文本是否来自 top hit 并匹配 citation |

[RAG baseline 数据集](../evals/rag-cases.jsonl) 已覆盖 answerable、unanswerable、synonym、citation 和 tenant isolation，并由 `evals/run_baseline.py` 与 `tests/test_course_datasets.py` 离线执行；focused 行为证据来自 `tests/test_rag.py`。

## 教师演示

1. 读取 `sample-data/hr-policy.md`，证明 citation quote 是源文件中的真实句子。
2. 同时放入高相关的跨租户 chunk、用户 allowlist chunk 和可见 chunk，展示前两者在评分前被排除。
3. 删除 `knowledge:read`，展示需要该权限的 chunk 不参与排名。
4. 输入 “leave password”，展示单词重合不足时稳定拒答。
5. 用同一批数据比较精确搜索、HNSW 和 IVFFlat 的设计指标，强调这部分不是默认测试已实现的行为。

## 学员实验

按 [Lab 07：权限感知 RAG](../labs/chapter-07/README.md) 完成本章实验，保存授权过滤、真实 quote、稳定排名和拒答证据。

实验任务：

1. 为同一 query 构造可见、跨租户、错误用户和缺权限四类 chunk。
2. 对 hit、rank、quote 和拒答写确定性断言。
3. 在纸面/SQL 设计中补齐八个版本与来源字段。
4. 编写带租户、用户 allowlist、trusted permissions 的单条检索 SQL。
5. 设计 HNSW/IVFFlat 对比实验，至少记录 recall@k、p95 和索引资源。
6. 说明为什么回答自报 `confidence="high"` 不能覆盖授权或引用断言。

默认离线验证命令：

```bash
cd reference-implementation
uv run --group dev --extra live pytest -q
```

本章聚焦命令：

```bash
uv run --group dev --extra live pytest tests/test_rag.py -q
```

## 失败注入与排错

| 注入 | 预期 | 排查点 |
| --- | --- | --- |
| 跨租户 chunk 分数最高 | 结果仍不含该 chunk | 授权是否在评分之前 |
| `allowed_user_ids` 不含当前用户 | chunk 不可见 | `None` 与空集合语义是否混淆 |
| 缺少 required permission | chunk 不可见 | permission 是否来自认证层 |
| query 只有一个误导重合词 | 拒答 | 最低分与最低匹配词数 |
| quote 不在 content | 自动测试失败 | citation 是否由后端 hit 构造 |
| 向量维度与模型不一致 | 索引/查询应在边界失败 | model、dimensions、索引版本是否一起校验 |
| ANN + 高选择性授权过滤返回不足 | 不扩大权限，调搜索参数或回退 | 不得先全库 top-k 再过滤 |

排错时先区分授权为空和相关性为空。两者对用户都可以安全拒答，但 trace/内部指标必须能区分，否则团队可能用降低阈值“修复”一个权限配置问题。

## 自动验证

当前 `tests/test_rag.py` 已验证：

- 规范化 overlap 能命中真实来源 quote；
- tenant 与 user allowlist 在评分前过滤；
- trusted permission 不足时排除 chunk；
- 无答案和误导性单词重合都会拒答；
- 答案来自 top hit，citation quote 是 content 子串。

本章文档验收还应确认：八个指定元数据字段全部出现；ACL 只由文档表提供且 query 不信任 chunk ACL；普通查询只读当前发布版本，显式 replay 才能读保留旧向量；SQL 同时含 tenant 和 user access 条件；HNSW/IVFFlat 被描述为权衡；生产 schema 明确标记为设计练习；Python fence 可解析；Lab 07 与 RAG baseline 链接可验证。

## 作业与评分

| 维度 | 分值 | 满分证据 |
| --- | ---: | --- |
| 可执行检索合同 | 25 | 使用当前模型字段，离线 hit/拒答与测试一致 |
| 权限边界 | 25 | tenant、user、permission 在评分/SQL 查询中生效 |
| 来源与引用 | 15 | quote 来自实际 hit，版本定位方案完整 |
| 数据版本设计 | 20 | 八个必需字段语义、约束和重建策略明确 |
| 索引选择 | 10 | 用数据比较 HNSW/IVFFlat，不宣称万能默认 |
| 解释 | 5 | 清楚区分已实现行为与设计练习 |

任何先查询跨租户候选再在应用层过滤的提交，权限边界项不得分。任何由模型自由生成 quote 或来源 ID 的提交，来源与引用项不得分。

## Core / Advanced / Production 完成标准

- **Core**：离线 retriever 能做 tenant/user/permission 过滤、稳定排序、真实引用和正确拒答。
- **Advanced**：建立版本化摄取、chunk 来源定位和 `evals/rag-cases.jsonl` 回归，并比较切片/检索变更。
- **Production（设计与外部基础设施要求）**：授权过滤进入数据库查询，索引和 embedding 版本可迁移，HNSW/IVFFlat 以真实负载验证，并有审计、保留和回滚。当前内存参考实现不宣称达到这一层。

## 本章资料

- [参考实现 README](../reference-implementation/README.md)
- [Retrieval-Augmented Generation Paper](https://arxiv.org/abs/2005.11401)
- [pgvector](https://github.com/pgvector/pgvector)
- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [OpenAI Embeddings Guide](https://developers.openai.com/api/docs/guides/embeddings)
- [LlamaIndex Documentation](https://docs.llamaindex.ai/)
- [Haystack Documentation](https://docs.haystack.deepset.ai/)

## 复盘模板

```markdown
# 第 7 章复盘

## 我的可执行 DocumentChunk 合同是什么

## tenant、user 和 permission 在哪里过滤

## 八个版本与来源字段分别解决什么问题

## citation 如何证明来自真实 hit

## 哪些输入必须拒答

## HNSW 与 IVFFlat 的选择证据是什么

## 哪些能力仍只是生产设计练习
```
