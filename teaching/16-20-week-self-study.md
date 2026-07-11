# 16-20 周自学路线

本路线把 [12 周路线](12-week-syllabus.md) 的内容拉长，接受更多复习和可选实验，但不改变 A0-A12 的验收标准。默认路径始终是离线 Fake；Live、Go 和 enrichment 必须显式选择，并且不计入 Core 补偿分。

## 建议节奏

| 周 | 学习与实践 | 周检查点 | 未通过时的恢复动作 |
| --- | --- | --- | --- |
| 1 | 课程准备 | A0 | 保留完整错误，重跑单个失败项，再跑根基线 |
| 2 | 第 1 章 | A1 | 删除越界功能，重写 Core/非目标清单 |
| 3 | 第 2 章 + Lab 02 | A2 | 回到精确 Fake fixture，不启用 Live |
| 4 | 第 3 章 | A3 | 固定 prompt/context 版本，补注入反例 |
| 5 | 第 4 章 | A4 | 画依赖方向，移除领域层 provider import |
| 6 | **恢复周 R1** | 重验 A0-A4，标准不变 | 只修最早失败的 A 项；全部通过后继续 |
| 7 | 第 5 章 + Lab 05 | A5 | 从严格 schema、可信 context、权限拒绝三项逐个排查 |
| 8 | 第 6 章 + Lab 06 | A6 | 缩小到单一 stop reason，再恢复完整 runner suite |
| 9 | 第 7 章 + Lab 07 | A7 | 先证明 tenant 过滤，再检查排序/引用/拒答 |
| 10 | **恢复周 R2** | 重验 A5-A7，标准不变 | 不删失败 case；补齐证据后继续 |
| 11 | 第 8 章 + Lab 08 | A8 | 从 state/version/hash 三元组重放失败路径 |
| 12 | 第 9 章 + Lab 09 | A9 | 检查 case schema、适用分母、轨迹与副作用断言 |
| 13 | 第 10 章 + Lab 10 | A10 | 先跑 server/client focused tests，再检查 timeout/cleanup |
| 14 | **恢复周 R3** | 重验 A8-A10，标准不变 | 形成失败日志、根因、修复和回归四件套 |
| 15 | 第 13 章 + Know-Engine M1-M3 | A11 的 M1-M3 子集 | 每个 milestone 独立复现，不跨阶段掩盖失败 |
| 16 | Know-Engine M4-M6 | A11 全量 | 回到最近一个通过的 milestone，保留同一 acceptance |
| 17 | Know-Engine M7 与演示 | A12 | 从干净环境按 M1-M7 顺序重放 |
| 18 | **最终恢复周 R4** | 重验 A0-A12，标准不变 | Core 未全过则继续修复，不进入 enrichment |
| 19 | 可选 enrichment：第 11 或 12 章 | 独立 Advanced 证据 | 不影响 A12；记录 baseline、收益和 fallback |
| 20 | 可选 enrichment：第 15 章、显式 Live 或 Go | 独立 Advanced 证据 | 设成本/时间上限；失败即回到已通过 Core |

16 周版本可把第 6/10/14 周恢复活动并入下一周开头，在第 16 周完成 A12；18 周版本保留前三个恢复周；20 周版本使用完整表。无论选择哪个长度，A0-A12 的命令、测试、权限边界和评分阈值完全相同。

## 每周自检模板

1. 我运行了哪个默认离线命令，退出码和输出形状是什么？
2. 我故意触发了哪个失败，后端控制在哪里生效？
3. 哪条证据证明没有越权副作用或敏感信息泄漏？
4. 哪个 acceptance ID 尚未通过？下一步只缩小哪个变量？
5. 我是否把 learner-created 路径先创建并测试，或误写成当前已有？

## 恢复协议

恢复周不是降级周。保留失败 case 和原始脱敏证据，先运行最小 focused command，解释根因，修复后重跑 focused 与完整离线 suite。不得用截图代替命令，不得把 `expected_*` 改成错误现状，不得通过增加权限、跳过审批、删除 tenant fixture 或扩大预算来让测试变绿。

## 可选 Live 与 enrichment

只有 A12 通过、操作者确认费用上限并显式设置 Live 三变量时，才按 [参考实现 README](../reference-implementation/README.md) 做真实模型对比。Live 结果按重复运行分布报告，不进入默认 CI。第 11、12、15 章保持 enrichment；Go 只承接稳定服务边界，不重写两套 Agent 编排。
