# ROADMAP.md

## Milestone: Data Pre-Analysis Flow

### Phase 1: 文件分类与预分析引擎

**Goal:** 实现 `create_project` 的 Phase 1 — 自动文件分类和 Schema 提取

**Scope:**
- 新增 `FileClassifier` 类：基于 LLM 分析文件名+列结构+内容样本
- 新增 `DataAuditor` 类：对每个文件提取 Schema、统计信息、质量评估
- 新增 `ReferenceParser` 类：解析 KPI 定义、数据字典等参考文档
- 生成 `DataAuditReport` 数据结构（文件分类 + Schema + 质量评估）
- 在 `project_model.py` 中新增相关数据类

**Files:** `project_model.py`, 新增 `file_classifier.py`, `data_auditor.py`
**Plans:** 2-3

---

### Phase 2: 交互式认知对齐流程

**Goal:** 实现 `create_project` 的 Phase 2-3 — 与用户多轮对齐 + 审批门控

**Scope:**
- 重构 `create_project` 为状态机驱动（4个阶段：PRE_ANALYZE → ALIGN → CONFIRM → BUILD）
- Phase ALIGN: 生成审计报告，通过 MCP 工具返回给 Agent，支持多轮问答
- Phase CONFIRM: 用户确认数据理解 + 语义层规划
- 状态持久化到 `{project_id}/.create_state.json`
- 中断恢复能力（用户可以中途退出，下次继续）

**Files:** `server.py` (create_project 重构), `project_model.py`
**Plans:** 2-3

---

### Phase 3: 参考文档约束 + 智能语义层生成

**Goal:** 实现 `create_project` 的 Phase 4 — 结合参考文档约束生成高质量语义层

**Scope:**
- 重构 `semantic_generator.py`：接受参考文档内容作为 Prompt 约束
- KPI 口径注入：将解析的指标定义注入 LLM Prompt
- 数据字典注入：将字段含义注入 LLM Prompt
- 仅导入确认的原始数据文件（不再 pd.concat 所有文件）
- 审计报告持久化到 `{project_id}/audit_report.yaml`
- 强制迁移：旧项目结构升级（project.yaml 格式兼容）

**Files:** `semantic_generator.py`, `project_model.py`, `server.py`
**Plans:** 2-3

---

### Phase 4: P0 Bug 修复 + 集成验证

**Goal:** 修复已知 P0 问题，端到端验证完整流程

**Scope:**
- 添加 `load_dotenv()` 到 `server.py`
- `PROJECTS_DIR` 改用绝对路径
- 端到端测试：从文件导入到语义层生成的完整流程
- Docker 环境验证
- 旧项目迁移验证

**Files:** `server.py`, `project_model.py`
**Plans:** 1-2

---

## Progress

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1 | ✅ Completed | 100% |
| Phase 2 | Not started | 0% |
| Phase 3 | Not started | 0% |
| Phase 4 | Not started | 0% |

---
*Last updated: 2026-04-30 after Phase 1 completion*
