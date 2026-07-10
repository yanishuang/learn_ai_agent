# 第 15 章：Dodo-Agent 进阶项目

## 本章定位

Dodo-Agent 是可选的进阶毕业项目，用最小多 Agent 系统验证职责拆分、结构化协作、路由和互操作。项目从一个 router 与两个 specialist 开始，不把通用平台、自动生成 Agent 或任意代码执行作为目标。

## 前置知识

学员应完成 Know-Engine 的 Core 标准，并学习第 11 章和第 12 章。学员需要已有稳定的单 Agent、评估集、trace、受控工具和持久化 Workflow，避免用增加 Agent 数量掩盖基础能力缺失。

## 学习目标

- 学员能够定义 router 与两个 specialist 的清晰职责、输入输出和失败契约。
- 学员能够在 handoff 与 agents-as-tools 之间做有证据的选择。
- 学员能够设计包含所有者、版本、能力、风险和状态的 Agent Registry。
- 学员能够分别评估 specialist、路由决策和端到端任务结果。
- 学员能够解释 MCP、A2A 和交互式应用表面的不同边界，并把 A2A 保持为可选研究。

## 核心知识

本项目覆盖能力分解、结构化合同、路由、所有权转移、共享上下文最小化、registry 治理和跨 Agent trace。多 Agent 的价值必须通过质量、延迟、成本或职责隔离指标证明；如果单 Agent 更稳定，就应保留单 Agent 方案。

## 教师演示

教师用一个 router 将知识检索与报告生成分配给两个 specialist，展示 handoff 前后的结构化 payload、所有权和 trace。随后教师制造错误路由和 specialist 超时，演示系统如何停止、回退或转人工，而不是让 Agent 无限互相调用。

## 学员实验

学员实现一个 router 和两个 specialist，并为每个 Agent 定义版本化输入输出模型、允许的工具和预算。学员还要建立最小 registry，比较 agents-as-tools 与 handoff 的一次实现选择，并用固定数据集报告单 Agent 与多 Agent 的差异。

## 失败注入与排错

学员注入错误路由、合同校验失败、上下文泄漏、循环 handoff、specialist 超时和 registry 版本不兼容。排错必须结合跨 Agent trace、结构化错误和预算状态，证明系统能够停止并保留明确的任务所有者。

## 自动验证

自动验证应对路由准确率、合同 schema、允许工具、最大 handoff 次数、specialist 结果和端到端任务成功作确定性断言。可选 A2A 实验必须与核心测试隔离，不能让预 1.0 协议成为完成项目的必要条件。

## 作业与评分

项目总分 100 分，其中职责与合同设计占 20 分，路由和协作实现占 25 分，registry 与治理占 15 分，分层评估占 25 分，失败恢复与架构说明占 15 分。仅展示多个 Agent 对话而没有指标、合同和停止条件不能获得及格分。

## Core / Advanced / Production 完成标准

- Core：一个 router 和两个 specialist 通过结构化合同完成固定任务，并有独立与端到端评估。
- Advanced：比较 handoff 与 agents-as-tools，加入 registry 版本治理，并用指标证明多 Agent 的必要性。
- Production：建立跨 Agent 身份、租户隔离、配额、审计、兼容性策略和故障降级演练。

## 本章资料

本章资料应优先使用 OpenAI Agents SDK 的 handoff 与 agents-as-tools 文档、MCP 规范和 A2A 的官方状态说明。每项互操作技术都必须记录成熟度、验证日期、主线角色和不采用时的替代设计。

## 复盘模板

复盘时请完整回答：为什么这个任务需要多个 Agent；路由和 specialist 分别如何失败；结构化合同阻止了什么问题；多 Agent 相比单 Agent 改善了哪个指标；哪些平台化想法被明确留在项目范围之外。
