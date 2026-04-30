# PROJECT.md

## What This Is

**ChatBI MCP Server** — 项目无关的对话式数据分析平台，通过 MCP 协议暴露数据分析能力给 AI Agent（如 Hermes）。

当前改造目标：**将 `create_project` 从原子操作重构为多阶段交互流程**，实现数据预分析、文件分类、用户认知对齐后再生成语义层。

## Core Value

1. **数据理解先于分析** — 导入数据前先理解数据，和用户对齐认知
2. **参考文档是资产不是噪音** — KPI定义、数据字典作为 LLM 约束而非被当作数据导入
3. **人工审批门控** — 关键决策点需要用户确认，不盲目自动执行
4. **向后可追溯** — 审计报告和数据理解文档持久化，可复盘

## Context

### Background

ChatBI 是一个 MCP Server，支持多项目管理，每个项目有独立的数据文件、语义层和 DuckDB 实例。用户通过 Hermes Agent（飞书）或 CLI 使用。

### Problem

当前 `create_project` 存在严重缺陷：
- 所有文件一锅炖（`pd.concat`），不区分原始数据和参考文档
- KPI定义文档、数据字典被当作数据导入，产生垃圾行
- 没有和用户对齐数据理解就直接生成语义层
- 语义层质量完全依赖 LLM 输出，没有人工确认环节
- 实际业务场景中，数据目录包含4类文件：原始数据、KPI定义、数据字典、需求文档

### Existing Codebase

Brownfield 项目，已有完整 MCP Server：
- `mcp_server/server.py` — 19个 MCP 工具（~891行）
- `mcp_server/project_model.py` — 项目 CRUD + DuckDB 数据层（~450行）
- `mcp_server/semantic_generator.py` — LLM 语义层生成（~470行）
- `mcp_server/analysis_templates.py` — L2 分析模板（~280行）
- `mcp_server/chart_renderer.py` — ECharts 图表（~203行）
- `mcp_server/dashboard_store.py` — Dashboard 持久化（~127行）
- `mcp_server/cli.py` — CLI 接口（~353行）

详细分析见 `.planning/codebase/` 目录下的7个文档。

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MCP工具内原生交互 | Hermes Agent 通过 ReAct 循环自然支持多轮对话 | 采用 |
| 参考文档通过 LLM Prompt 注入 | KPI定义、数据字典解析后注入 Prompt 作为约束 | 采用 |
| 最小化改造范围 | 只改 create_project 流程，不动查询/图表/Dashboard | 采用 |
| 强制迁移旧项目 | 旧项目结构不兼容，需要迁移到新结构 | 采用 |
| LLM 自动分类+用户确认 | LLM 分析文件名+列结构+内容样本自动分类，用户多轮澄清直到对齐 | 采用 |
| 单工具+状态机 | create_project 内部拆成4步，通过状态机控制流程 | 采用 |

## Constraints

- Python 3.10+，无 async
- MCP stdio/SSE transport
- DeepSeek API 作为 LLM（通过 `requests` 库）
- DuckDB 作为分析数据库
- Hermes Agent 作为主要使用者（飞书平台）
- Docker 部署环境

## Out of Scope

- L2 模板参数化（hardcoded column names）— 后续迭代
- CLI 同步更新 — 后续迭代
- 多用户/并发支持 — 当前不需要
- 新增测试框架 — 后续迭代
- Docker 适配优化 — 后续迭代

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions

---
*Last updated: 2026-04-30 after initialization*
