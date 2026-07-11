# Lab 07：权限感知 RAG 与真实引用

## 目标

验证 tenant/user/permission 在评分前过滤、同义/关键词覆盖、稳定排序、引用来自真实 hit，以及无授权答案时拒答。

## 默认离线步骤

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_rag.py -q
```

预期形状：`6 passed`；覆盖真实 quote、tenant/ACL/permission、拒答和 grounded citation。

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_rag.py -q -k 'normalized_overlap or grounded'
```

预期 hit/answer 形状：score 在 0-1、citation ID 从 1 开始，document/chunk/title/quote 与授权 chunk 一致，answer 使用 `[1]`。

## 故意失败

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_rag.py -q -k 'filters_tenant or missing_trusted_permission or refuses'
```

fixtures 故意放入跨租户、高相似但无权限或误导性单词重叠的 chunk。预期不可见或 `refused=true`，pytest 通过。

## 调试顺序

1. 先检查 `_is_visible` 的 tenant/user/permission 输入来自 trusted context。
2. 再检查 query tokenization、最低分和至少匹配词数。
3. 检查稳定排序键，不依赖随机向量顺序。
4. 从 hit 构造 quote/citation；禁止模型自由编 source ID。
5. 无 hit 时走固定拒答，不用常识补全。

## 默认验证

```bash
cd reference-implementation
uv run --group dev --extra live pytest tests/test_rag.py tests/test_api.py -q -k 'rag or search or citation or tenant'
```

预期形状：选中的检索、API 身份隔离和引用测试全部通过。

## 可选 Live 扩展（显式付费）

Live 只可生成基于已授权 hits 的回答；retrieval ACL 和 citation validation 仍由后端确定性执行。先创建 held-out answer test 和成本上限，再运行 learner-created Live comparison。不得把其他 tenant 文本发送给模型或 judge。

## 提交证据

可答、拒答、跨租户和 permission case；citation 字段 shape；过滤顺序解释；A7/R2 自评。
