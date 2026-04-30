# REQUIREMENTS.md

## Validated

- ✓ 多项目管理（create/list/switch/delete）— existing in `server.py`
- ✓ 语义层生成（LLM-assisted）— existing in `semantic_generator.py`
- ✓ 三级查询协议（L1/L2/L3）— existing in `server.py`
- ✓ ECharts 图表生成 — existing in `chart_renderer.py`
- ✓ Dashboard CRUD — existing in `dashboard_store.py`
- ✓ MCP stdio/SSE transport — existing in `server.py`
- ✓ CLI 接口 — existing in `cli.py`

## Active

### P0 — 核心流程改造

- [ ] **R1: 文件分类能力** — `create_project` 能够区分原始数据文件和参考文档（KPI定义、数据字典、需求文档）
- [ ] **R2: LLM 预分析** — 对每个文件进行 Schema 提取和内容分析，生成文件分析报告
- [ ] **R3: 参考文档解析** — 解析 KPI 定义文档中的指标口径、数据字典中的字段定义
- [ ] **R4: 数据审计报告** — 生成结构化的数据审计报告，包含文件分类、Schema、数据质量评估
- [ ] **R5: 多轮认知对齐** — 与用户交互确认：文件分类是否正确、关键字段映射、分析目标
- [ ] **R6: 人工审批门控** — 在语义层生成前，用户必须确认数据理解和生成计划
- [ ] **R7: 参考文档约束 LLM** — 将 KPI 口径、字段定义注入 Prompt，约束语义层生成
- [ ] **R8: 审计报告持久化** — 数据理解文档和审计报告持久化到项目目录

### P1 — 必要修复

- [ ] **R9: load_dotenv()** — server.py 启动时调用 `load_dotenv()`
- [ ] **R10: 绝对路径** — `PROJECTS_DIR` 使用绝对路径

## Out of Scope

- L2 模板参数化（hardcoded column names）— 后续迭代
- CLI 同步更新 — 后续迭代
- 多用户/并发支持 — 当前不需要
- 新增测试框架 — 后续迭代
- Docker 适配优化 — 后续迭代

---
*Last updated: 2026-04-30*
