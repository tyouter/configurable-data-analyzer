# PROJECT.md

## What This Is

**ChatBI MCP Server** — 项目无关的对话式数据分析平台，通过 MCP 协议暴露数据分析能力给 AI Agent。

## Core Value

1. **数据理解先于分析** — 导入数据前先理解数据，和用户对齐认知
2. **参考文档是资产不是噪音** — KPI定义、数据字典作为 LLM 约束而非被当作数据导入
3. **人工审批门控** — 关键决策点需要用户确认，不盲目自动执行
4. **向后可追溯** — 审计报告和数据理解文档持久化，可复盘
5. **Pipeline 解耦** — 各阶段可独立执行、验证、重试
6. **配置驱动** — 项目语义映射由配置文件驱动，源码只提供方法论

## Milestone History

### Milestone 1: Data Pre-Analysis Flow (Completed)

将 `create_project` 从原子操作重构为4阶段交互流程（PRE_ANALYZE → ALIGN → CONFIRM → BUILD），实现数据预分析、文件分类、用户认知对齐后再生成语义层。

**成果：** 4阶段状态机、FileClassifier、DataAuditor、ReferenceParser、参考文档约束注入

### Milestone 2: Pipeline Architecture Refactoring (Completed)

基于端到端测试暴露的6个架构级缺陷，对数据处理 Pipeline 进行深度重构。

**成果：** 6阶段交互式 Pipeline、语义验证器、业务域分组 Dashboard、端到端验证通过

## Current Problem Statement

Milestone 2 已完成，6个架构级缺陷全部解决。项目进入稳定运行阶段。

## Target Architecture

### 6阶段交互式 Pipeline

```
INGEST ──▶ ALIGN ──▶ MAP ──▶ VERIFY ──▶ BUILD ──▶ SERVE
  │          │         │        │         │         │
  │          │         │        │         │         └─ Dashboard 展示
  │          │         │        │         └─ 按业务域分组生成
  │          │         │        └─ SQL验证 + 数据质量校验
  │          │         └─ 语义层生成（模块化）
  │          └─ 用户确认数据理解
  └─ 文件导入 + 分类 + 审计
```

### 每个阶段的 Checkpoint

- INGEST: 审计报告持久化，用户可审阅
- ALIGN: 数据理解报告，用户可修正
- MAP: 语义层配置，用户可调整
- VERIFY: 验证报告，自动检测问题
- BUILD: Dashboard 草稿，用户可预览
- SERVE: 最终交付

### 语义层模块化

```
semantic_config.json
├── columns/        ← 列映射（字段名 → 业务名 + 类型 + 派生逻辑）
├── events/         ← 事件定义（事件名 → SQL模式 + 业务分组）
├── metrics/        ← 指标定义（指标名 → SQL + 类型 + 图表建议 + 业务域）
└── dimensions/     ← 维度定义（维度名 → 列名 + 类型）
```

## Existing Codebase

| File | Lines | Purpose |
|------|-------|---------|
| `mcp_server/server.py` | ~2022 | 24个 MCP 工具 + 6阶段状态机 |
| `mcp_server/project_model.py` | ~1029 | 项目 CRUD + DuckDB 数据层 + Pipeline 状态 |
| `mcp_server/semantic_generator.py` | ~1225 | LLM 语义层生成 + business_domain 标签 |
| `mcp_server/semantic_query.py` | ~42 | L1 语义查询 |
| `mcp_server/semantic_validator.py` | ~195 | SQL 可执行性 + 数据质量 + 覆盖率验证 |
| `mcp_server/analysis_templates.py` | ~280 | L2 分析模板 |
| `mcp_server/chart_renderer.py` | ~258 | ECharts 图表（含漏斗图转化率） |
| `mcp_server/dashboard_html.py` | ~645 | Dashboard HTML 渲染（域分组+时间筛选+暗色模式） |
| `mcp_server/dashboard_store.py` | ~252 | Dashboard 持久化 + 编码修复 + 质量检查 |
| `mcp_server/file_classifier.py` | ~342 | 文件分类 |
| `mcp_server/data_auditor.py` | ~164 | 数据审计 |
| `mcp_server/reference_parser.py` | ~606 | 参考文档解析 |
| `mcp_server/cli.py` | ~473 | CLI 接口 |

## Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| MCP工具内原生交互 | Agent 通过 ReAct 循环自然支持多轮对话 | Adopted |
| 参考文档通过 LLM Prompt 注入 | KPI定义、数据字典解析后注入 Prompt 作为约束 | Adopted |
| 单工具+状态机 | create_project 内部拆成4步，通过状态机控制 | Adopted |
| semantic_config.json 外部化 | 项目语义映射由配置文件驱动，源码只提供方法论 | Adopted |
| LLM 自动生成 semantic_config | 数据澄清阶段由 LLM 自动生成，不可用时返回错误 | Adopted |
| 6阶段 Pipeline | INGEST→ALIGN→MAP→VERIFY→BUILD→SERVE，每阶段有 checkpoint | Adopted |
| 语义层模块化 | 拆分 columns/events/metrics/dimensions 为独立 JSON 块 | Adopted |
| 数据质量自动校验 | 指标SQL执行后自动检查零数据/全NULL/异常值 | Adopted |
| Dashboard 业务域分组 | 指标增加 business_domain 标签，Dashboard 按域分组 | Adopted |
| 前端时间筛选 | JavaScript 纯前端过滤，无需后端重查 | Adopted |
| 漏斗图转化率 | 首步100%，后续相对首步自动计算 | Adopted |
| 编码自动修复 | Dashboard 保存时自动检测并修复双重 UTF-8 编码 | Adopted |

## Constraints

- Python 3.10+，无 async
- MCP stdio/SSE/streamable-http transport
- DeepSeek API 作为 LLM（通过 `requests` 库）
- DuckDB 作为分析数据库
- Docker 部署环境

## Out of Scope

- L2 模板参数化（hardcoded column names）— 后续迭代
- CLI 同步更新 — 后续迭代
- 多用户/并发支持 — 当前不需要
- Docker 适配优化 — 后续迭代

---
*Last updated: 2026-05-04 — Milestone 2 completed*
