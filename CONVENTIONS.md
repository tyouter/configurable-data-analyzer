# ChatBI — Engineering Conventions

> 本文档是 ChatBI MCP Server 的工程宪法。所有贡献者（人类和 AI Agent）必须遵守。

---

## 1. Architecture Boundary

### MCP Server (this repo) — Data Layer ONLY

MCP 只做以下五件事：
1. DuckDB 数据存储与查询（L1/L2/L3）
2. 语义层管理（指标注册、SQL 验证、配置持久化）
3. 数据质量审计（行业规则检查）
4. 图表渲染（ECharts inline，不依赖 CDN）
5. Dashboard 持久化与导出（JSON + 自包含 HTML）

MCP **禁止**做的事：
- 读取或解释参考文档（KPI 定义、数据字典、需求文档）
- 推导 KPI 口径或业务含义
- 文件分类的语义判断（只做扩展名/格式检测）

这些由 Agent（Hermes / Claude / Trae）负责。Agent 用 openpyxl 等标准库直接读文件，基于完整 LLM 上下文理解文档语义。

### Agent — Understanding Layer

Agent 负责：
- 读取参考文档 → 推导 KPI 定义
- 发现事件 → 筛选业务相关事件
- 注入指标/事件到 MCP 语义层
- 编排查询 → 渲染 → Dashboard 全流程

---

## 2. Downstream Sync Checklist

当 MCP 工具变更（新增/删除/改名/修改参数签名）时，必须同步更新以下文件：

| 变更类型 | 必须同步的文件 |
|---------|-------------|
| MCP 工具新增/删除/改名 | `skills/chatbi/SKILL.md` + `README.md` 工具表 + `.trae/skills/data-analysis/SKILL.md` |
| 工具参数签名变更 | 同上 |
| 项目模型变更 | `CLAUDE.md`（架构说明） |
| 依赖变更 | `pyproject.toml` + `requirements.txt` |
| 版本号变更 | `pyproject.toml` + `mcp_server/__init__.py` |

**多 Agent 兼容**：ChatBI 被 Claude Desktop、Trae、Hermes 三者共用。工具变更后三个 Skill 文件必须同步：
- `skills/chatbi/SKILL.md` → Hermes
- `.trae/skills/data-analysis/SKILL.md` → Trae
- `CLAUDE.md` → Claude Code / DS TUI

---

## 3. Test Discipline

### TDD 铁律

```
红（写失败测试） → 绿（最小实现） → 重构（优化结构） → 全绿
```

### 测试层级

| 层级 | 说明 | 执行频率 |
|------|------|---------|
| Characterization tests | 基于 rednote-bi-semantic-reference.json 的 34 指标快照测试 | 每次 commit |
| MCP 契约快照 | 工具名 + 参数 schema 一致性检查 | 每次 commit |
| 单元测试 | 各模块纯逻辑测试（mock DuckDB/LLM） | 每次 commit |
| 集成测试 | 真实 DuckDB 内存模式 | Phase 结束前 |
| E2E 测试 | 全链路：创建项目 → 注入指标 → 查询 → 渲染 | Phase 结束时 |

### 覆盖率门禁

- Phase 0 结束：characterization tests 覆盖 34 指标
- Phase 5 结束：≥ 80% 行覆盖率

---

## 4. Git Strategy

### 分支策略

```
master ← refactor/phase-0 ← refactor/phase-1 ← ...
```

### Commit 规范

- 粒度：一个逻辑变更一个 commit
- 格式：`[Phase N] <简短描述>`
- 示例：`[Phase 0] Add characterization tests for 34 metrics`
- 禁止：force push 到 master
- 回滚：`git revert`，不从历史删除

### Commit 前检查

1. `pytest` 全绿
2. `git diff --stat` 确认变更范围合理
3. 如有 MCP 工具变更，确认下游文件已同步

---

## 5. Hallucination Prevention

针对 LLM 模型特质，设置以下探测和管控机制：

### 代码修改自检

1. 每次代码修改后立即跑 `pytest` 相关测试
2. 新增文件/函数需通过 `mypy` 或 `pylint` 存在性检查
3. 删除文件后 `grep` 确认无残留引用

### 引用完整性

1. 修改 import 路径后，`grep` 旧路径确认无遗漏
2. 新增 MCP 工具后，确认 `server.py` 中已注册
3. 修改函数签名后，`grep` 所有调用点

### 行为一致性

1. Characterization tests 重构前后结果必须一致
2. 如有差异：要么是 bug（修复），要么是预期行为变更（更新快照并记录）

---

## 6. Testing Artifacts Cleanup

### Fixture 清理策略

1. DuckDB 测试使用内存模式（`:memory:`），无需手动清理
2. 文件级 fixture 使用 `tmp_path`，pytest 自动清理
3. 项目级 fixture 必须在 `teardown` 中调用 `delete_project()`

### 禁止残留的文件

- `*.duckdb` 文件（除 `projects/` 下的生产数据）
- 临时 Excel/CSV 副本
- 测试生成的 `dashboard_spec.json` 副本
- 测试生成的 HTML 导出文件

---

## 7. Documentation Consistency

### 自检机制

1. MCP 工具数量变更 → 检查 README.md 工具表是否同步（`grep -c "@mcp.tool()" mcp_server/server.py`）
2. 版本号变更 → 检查 `pyproject.toml` 和 `mcp_server/__init__.py` 是否一致
3. 环境变量变更 → 检查 `.env.example` 和 README.md 配置表

### 发布前检查清单

- [ ] `pytest` 全绿，覆盖率 ≥ 80%
- [ ] `grep` 确认工具数量与 README 一致
- [ ] `git diff --stat` 确认下游文件已同步
- [ ] 无临时测试文件残留
- [ ] `pyproject.toml` 版本号已更新
- [ ] CLAUDE.md 架构说明与代码一致
