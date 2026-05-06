# ROADMAP.md

## Milestone 1: Data Pre-Analysis Flow (Completed)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | 文件分类 + 数据审计 + 参考文档解析 | Completed |
| Phase 2 | 交互式认知对齐流程 (4阶段状态机) | Completed |
| Phase 3 | 参考文档约束注入语义层生成 | Completed |
| Phase 4 | P0 Bug 修复 + 集成验证 | Completed |

---

## Milestone 2: Pipeline Architecture Refactoring

### Phase 5: Pipeline 解耦

**Goal:** 拆分 BUILD 阶段为独立可重试的子步骤，语义层配置模块化

**Scope:**
- 将 `_create_phase_build` 拆分为独立步骤：数据加载 → 派生列创建 → 语义层生成 → 语义层保存
- 每个步骤可独立执行，失败可从断点重试
- 中间结果持久化到项目目录
- 语义层配置拆分为 columns/events/metrics/dimensions 四个独立 JSON 块
- 新增 MCP 工具支持单步执行和重试

**Depends on:** Phase 4
**Files:** `server.py`, `project_model.py`, `semantic_generator.py`
**Plans:** 3-4

---

### Phase 6: 人机协同增强

**Goal:** 增强 ALIGN 阶段，让用户能审阅和修正 AI 的数据理解

**Scope:**
- ALIGN 阶段生成结构化数据理解报告（列映射、事件解析、业务上下文）
- 用户可修正列的业务名称、类型、派生逻辑
- 用户可修正事件名称和 SQL 匹配模式
- 用户可添加/删除/调整指标
- 修正结果持久化并传递给 MAP 阶段
- 新增 MCP 工具：`review_data_understanding`、`update_column_mapping`、`update_event_mapping`

**Depends on:** Phase 5
**Files:** `server.py`, `project_model.py`
**Plans:** 2-3

---

### Phase 7: 语义验证

**Goal:** 语义层生成后自动验证 SQL 可执行性、指标覆盖率和数据质量

**Scope:**
- 新增 `SemanticValidator` 类：自动验证所有指标 SQL
- SQL 可执行性验证：每个指标 SQL 能否在 DuckDB 中执行
- 数据质量校验：零数据/全NULL/异常值检测
- 指标覆盖率检查：对比参考文档中的 KPI 定义
- 生成验证报告，标记通过/警告/失败的指标
- VERIFY 阶段集成到 Pipeline 状态机
- 失败指标自动回退到 MAP 阶段重新生成

**Depends on:** Phase 5
**Files:** 新增 `semantic_validator.py`, `server.py`, `project_model.py`
**Plans:** 3-4

---

### Phase 8: Dashboard 增强

**Goal:** Dashboard 按业务域分组布局，支持全局筛选器和新图表类型

**Scope:**
- 指标增加 `business_domain` 标签（用户行为、内容消费、转化漏斗、系统性能等）
- Dashboard 按业务域分组布局（每组一个 section）
- 新增全局时间筛选器（event_date 范围选择）
- 新增漏斗图类型支持
- 新增表格类型支持
- KPI 卡片按域分组展示
- Dashboard 标题和描述从语义层自动生成

**Depends on:** Phase 7
**Files:** `server.py`, `dashboard_html.py`, `dashboard_store.py`, `chart_renderer.py`
**Plans:** 3-4

---

### Phase 9: 端到端验证

**Goal:** 通过 SKILL/MCP 完整流程测试，验证 Pipeline 稳定性

**Scope:**
- 使用 SKILL 模式创建完整项目
- 验证6阶段 Pipeline 全流程
- Dashboard 质量验证（数据准确性、图表完整性、布局合理性）
- 数据准确性交叉校验（与参考文档 KPI 对比）
- 异常场景测试（LLM 不可用、数据质量问题、用户修正后重试）
- 性能基准测试

**Depends on:** Phase 8
**Files:** 测试脚本
**Plans:** 2-3

---

## Progress

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1 | Completed | 100% |
| Phase 2 | Completed | 100% |
| Phase 3 | Completed | 100% |
| Phase 4 | Completed | 100% |
| Phase 5 | Completed | 100% |
| Phase 6 | Completed | 100% |
| Phase 7 | Completed | 100% |
| Phase 8 | Completed | 100% |
| Phase 9 | Completed | 100% |

---
*Last updated: 2026-05-04 — Milestone 2 completed*
