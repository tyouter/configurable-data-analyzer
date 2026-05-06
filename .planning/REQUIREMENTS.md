# REQUIREMENTS.md

## Validated (Milestone 1)

- ✓ 多项目管理（create/list/switch/delete）— existing in `server.py`
- ✓ 语义层生成（LLM-assisted）— existing in `semantic_generator.py`
- ✓ 三级查询协议（L1/L2/L3）— existing in `server.py`
- ✓ ECharts 图表生成 — existing in `chart_renderer.py`
- ✓ Dashboard CRUD — existing in `dashboard_store.py`
- ✓ MCP stdio/SSE/streamable-http transport — existing in `server.py`
- ✓ CLI 接口 — existing in `cli.py`
- ✓ 文件分类能力 (R1) — Phase 1
- ✓ LLM 预分析 (R2) — Phase 1
- ✓ 参考文档解析 (R3) — Phase 1
- ✓ 数据审计报告 (R4) — Phase 1
- ✓ 多轮认知对齐 (R5) — Phase 2
- ✓ 人工审批门控 (R6) — Phase 2
- ✓ 参考文档约束 LLM (R7) — Phase 3
- ✓ 审计报告持久化 (R8) — Phase 3
- ✓ load_dotenv() (R9) — Phase 4
- ✓ 绝对路径 (R10) — Phase 4

## Validated (Milestone 2)

### P0 — Pipeline 解耦 (Phase 5)

- ✓ **R11: BUILD 阶段步骤拆分** — 将 BUILD 拆分为 LOAD_DATA → CREATE_DERIVED → GEN_SEMANTIC → SAVE_SEMANTIC 四个独立步骤
- ✓ **R12: 步骤状态持久化** — 每个步骤完成后持久化到 `.pipeline_state.json`，支持断点续做
- ✓ **R13: 语义层配置模块化** — semantic_config.json 拆分为 columns/events/metrics/dimensions 四个独立 JSON 块
- ✓ **R14: 单步执行 MCP 工具** — 新增 `execute_pipeline_step` 工具支持单步执行和重试

### P0 — 人机协同增强 (Phase 6)

- ✓ **R15: 数据理解报告** — ALIGN 阶段生成结构化数据理解报告（列映射、事件解析、业务上下文）
- ✓ **R16: 列映射修正** — 用户可修正列的业务名称、类型、派生逻辑
- ✓ **R17: 事件映射修正** — 用户可修正事件名称和 SQL 匹配模式
- ✓ **R18: 指标调整** — 用户可添加/删除/调整指标定义

### P0 — 语义验证 (Phase 7)

- ✓ **R19: SQL 可执行性验证** — 每个指标 SQL 能否在 DuckDB 中执行
- ✓ **R20: 数据质量校验** — 零数据/全NULL/异常值自动检测
- ✓ **R21: 指标覆盖率检查** — 对比参考文档中的 KPI 定义，标记缺失指标
- ✓ **R22: 验证报告** — 生成验证报告，标记通过/警告/失败的指标
- ✓ **R23: VERIFY 阶段集成** — 集成到 Pipeline 状态机，失败指标自动回退

### P1 — Dashboard 增强 (Phase 8)

- ✓ **R24: 业务域标签** — 指标增加 business_domain 标签
- ✓ **R25: 业务域分组布局** — Dashboard 按业务域分组展示
- ✓ **R26: 全局时间筛选器** — event_date 范围选择
- ✓ **R27: 漏斗图支持** — 新增漏斗图图表类型（含转化率）
- ✓ **R28: 表格类型支持** — 新增表格展示类型

### P1 — 端到端验证 (Phase 9)

- ✓ **R29: SKILL/MCP 完整流程测试** — 24个 MCP 工具全量注册验证通过
- ✓ **R30: Dashboard 质量验证** — 域分组、时间筛选、暗色主题、编码修复验证通过
- ✓ **R31: 异常场景测试** — 30/30 边界测试通过（空数据/空Dashboard/编码/漏斗转化率）

## Out of Scope

- L2 模板参数化（hardcoded column names）— 后续迭代
- CLI 同步更新 — 后续迭代
- 多用户/并发支持 — 当前不需要
- Docker 适配优化 — 后续迭代
- PDF/Word 参考文档解析 — 后续迭代

---
*Last updated: 2026-05-04 — Milestone 2 completed*
