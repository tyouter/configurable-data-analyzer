# Phase 2 Plan: 交互式认知对齐流程

**Phase:** 2
**Goal:** 重构 `create_project` MCP 工具为状态机驱动的4阶段交互流程
**Status:** Planned

---

## Overview

Phase 2 是整个重构的核心 — 将 `create_project` 从一个原子操作拆成4个阶段，通过状态机控制流程。Hermes Agent 的 ReAct 循环天然支持多轮对话，因此**不需要新增多个 MCP 工具**，而是在单个 `create_project` 工具内部通过 `action` 参数控制阶段推进。

**原则：** 单工具 + 状态机，MCP 协议层面只暴露一个 `create_project` 工具。

---

## Architecture

### 状态机

```
                    action="start"
                         ↓
                  ┌──────────────┐
                  │  PRE_ANALYZE │  自动：分类 + 审计 + 解析
                  └──────┬───────┘
                         ↓ 返回审计报告
                  ┌──────────────┐
                  │    ALIGN     │  等待用户反馈/确认
                  └──────┬───────┘
                         ↓ action="confirm"
                  ┌──────────────┐
                  │   CONFIRM    │  用户审批门控
                  └──────┬───────┘
                         ↓ action="build"
                  ┌──────────────┐
                  │    BUILD     │  仅导入确认的数据 + 生成语义层
                  └──────────────┘
```

### MCP 工具接口设计

**单个工具，通过 action 参数区分阶段：**

```python
@mcp.tool()
def create_project(
    action: str = "start",       # start | classify | confirm | build
    name: str = None,            # 项目名称 (action=start)
    data_files: list[str] = None, # 文件路径 (action=start)
    # action=classify 参数
    corrections: dict = None,     # 用户对分类的修正
    questions: str = None,        # 用户的问答
    # action=confirm 参数
    confirmed_raw_files: list[str] = None,   # 确认导入的原始数据文件
    confirmed_ref_files: list[str] = None,   # 确认作为参考的文件
    analysis_goals: list[str] = None,        # 确认的分析目标
    # action=build 参数
    use_llm: bool = True,
) -> dict:
```

### 状态持久化

```json
{
  "state": "ALIGN",
  "project_id": "abc12345",
  "name": "Rednote Analysis",
  "data_files": ["/data/file1.xlsx", "/data/file2.csv"],
  "audit_report": { ... },
  "user_corrections": { ... },
  "created_at": "2026-04-30T12:00:00",
  "updated_at": "2026-04-30T12:01:00"
}
```

文件路径：`{project_id}/.create_state.json`

### Agent 交互流程

```
Agent: create_project(action="start", name="Rednote", data_files=[...])
Server: {
    "state": "ALIGN",
    "project_id": "abc12345",
    "audit_report": {
        "file_classifications": [
            {"filename": "rednote.xlsx", "category": "raw_data", "confidence": 0.8},
            {"filename": "kpi_def.xlsx", "category": "reference_kpi", "confidence": 0.85},
            ...
        ],
        "summary": {"raw_files": 1, "ref_files": 3, "total_rows": 65722},
        "kpi_definitions": [...],
        "field_definitions": [...],
    },
    "message": "请确认文件分类和KPI定义是否正确"
}

Agent: (展示给用户，用户说"数据字典应该也是参考文档")

Agent: create_project(action="classify", project_id="abc12345",
                      corrections={"Rednote tracking.xlsx": "reference_dict"})

Server: {
    "state": "ALIGN",
    "updated_classifications": [...],
    "message": "已修正。还有其他修正吗？"
}

Agent: (用户确认完毕)

Agent: create_project(action="confirm", project_id="abc12345",
                      confirmed_raw_files=["rednote.xlsx"],
                      confirmed_ref_files=["kpi_def.xlsx", "tracking.xlsx"],
                      analysis_goals=["用户行为分析", "KPI监控"])

Server: {
    "state": "BUILD_READY",
    "plan": {"raw_files": 1, "ref_files": 2, "kpis": 15, ...},
    "message": "确认后将开始构建语义层"
}

Agent: create_project(action="build", project_id="abc12345")

Server: {
    "state": "COMPLETED",
    "project_id": "abc12345",
    "metrics_count": 12,
    "events_count": 5,
    ...
}
```

---

## Plan 2.1: 新增 CreateProjectState 数据结构和状态管理

**File:** `mcp_server/project_model.py`

**What:**

```python
class CreateState(str, Enum):
    PRE_ANALYZE = "PRE_ANALYZE"
    ALIGN = "ALIGN"
    CONFIRM = "CONFIRM"
    BUILD = "BUILD"
    COMPLETED = "COMPLETED"

@dataclass
class CreateProjectState:
    state: str = "PRE_ANALYZE"
    project_id: str = ""
    name: str = ""
    data_files: list = field(default_factory=list)
    audit_report: dict = field(default_factory=dict)
    user_corrections: dict = field(default_factory=dict)
    confirmed_raw_files: list = field(default_factory=list)
    confirmed_ref_files: list = field(default_factory=list)
    analysis_goals: list = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict: ...
    
    @classmethod
    def from_dict(cls, d: dict) -> "CreateProjectState": ...
```

在 `ProjectStore` 中新增：
- `save_create_state(project_id, state: CreateProjectState)`
- `load_create_state(project_id) -> Optional[CreateProjectState]`
- `delete_create_state(project_id)`

**Constraints:**
- 状态文件路径：`{project_id}/.create_state.json`（不用 YAML，JSON 更适合程序化读写）
- `audit_report` 存储为 dict（由 `DataAuditReport.to_dict()` 序列化）
- `data_files` 存储原始路径（未复制到项目目录的路径）

**Verification:**
- 创建状态 → 保存 → 加载 → 验证数据完整

---

## Plan 2.2: 实现 PRE_ANALYZE 阶段

**File:** `mcp_server/server.py` (create_project 重构)

**What:**

当 `action="start"` 时：

1. 生成 `project_id`
2. 调用 Phase 1 的三个引擎：
   - `FileClassifier.classify_all(data_files)`
   - `DataAuditor.audit_all(classifications)` （仅 RAW_DATA 文件）
   - `ReferenceParser.parse_all(classifications)` （仅 REFERENCE 文件）
3. 组装 `DataAuditReport`
4. 创建 `CreateProjectState(state="ALIGN", ...)`
5. 保存状态到 `.create_state.json`
6. 返回审计报告给 Agent

**返回结构：**
```python
{
    "state": "ALIGN",
    "project_id": "...",
    "audit_report": {
        "file_classifications": [...],
        "raw_data_schemas": [...],
        "reference_contents": [...],
        "summary": {...},
    },
    "message": "数据预分析完成。请确认文件分类和KPI定义。",
    "next_actions": ["classify", "confirm"],
}
```

**Constraints:**
- PRE_ANALYZE 是自动阶段，不需要用户输入
- 如果只有1个文件且明显是数据文件（无参考文档），仍生成报告供用户确认
- 文件路径检查：跳过不存在的文件

---

## Plan 2.3: 实现 ALIGN 阶段（多轮交互）

**File:** `mcp_server/server.py`

**What:**

当 `action="classify"` 时：

1. 加载 `.create_state.json`
2. 验证 state == "ALIGN"
3. 处理用户修正：
   - `corrections`: `{"filename": "new_category"}` → 更新分类
   - `questions`: 用户的自然语言问题 → 基于审计报告回答
4. 重新生成受影响的 Schema/Reference 内容
5. 更新状态
6. 返回更新后的审计报告

**返回结构：**
```python
{
    "state": "ALIGN",
    "project_id": "...",
    "updated_classifications": [...],
    "answer": "...",  # 对用户问题的回答（如果有）
    "message": "已更新。请确认或继续修正。",
    "next_actions": ["classify", "confirm"],
}
```

**Constraints:**
- 允许多轮 classify（用户可以反复修正）
- corrections 中的 category 必须是有效值（raw_data, reference_kpi 等）
- 每次修正后重新运行受影响的引擎（仅对变更的文件）

---

## Plan 2.4: 实现 CONFIRM 阶段（审批门控）

**File:** `mcp_server/server.py`

**What:**

当 `action="confirm"` 时：

1. 加载 `.create_state.json`
2. 验证 state == "ALIGN"
3. 记录用户确认：
   - `confirmed_raw_files`: 用户确认要导入的原始数据文件列表
   - `confirmed_ref_files`: 用户确认作为参考的文件列表
   - `analysis_goals`: 用户确认的分析目标
4. 生成构建计划（哪些文件导入、哪些作为参考、预期KPI数量等）
5. 更新 state → "CONFIRM"
6. 返回构建计划给用户最终确认

**返回结构：**
```python
{
    "state": "BUILD_READY",
    "project_id": "...",
    "build_plan": {
        "raw_files_to_import": [...],
        "ref_files_for_context": [...],
        "kpi_count": 15,
        "field_definitions_count": 48,
        "analysis_goals": [...],
    },
    "message": "确认后将开始构建语义层。是否继续？",
    "next_actions": ["build"],
}
```

**Constraints:**
- `confirmed_raw_files` 必须是分类为 `raw_data` 的文件子集
- `confirmed_ref_files` 必须是分类为 `reference_*` 的文件子集
- 至少要有1个 raw_data 文件才能 build

---

## Plan 2.5: 实现 BUILD 阶段

**File:** `mcp_server/server.py`

**What:**

当 `action="build"` 时：

1. 加载 `.create_state.json`
2. 验证 state == "CONFIRM"
3. 执行构建：
   a. 仅复制确认的 `confirmed_raw_files` 到项目 data 目录
   b. 加载数据到 DuckDB
   c. 将参考文档内容注入语义层生成 Prompt
   d. 调用 `generate_semantic_layer()`
   e. 保存 `audit_report.yaml`
   f. 保存 `project.yaml`
4. 更新 state → "COMPLETED"
5. 删除 `.create_state.json`
6. 切换到新项目

**返回结构：**
```python
{
    "state": "COMPLETED",
    "project_id": "...",
    "name": "...",
    "project_type": "...",
    "data_files": [...],
    "total_rows": 65722,
    "metrics_count": 12,
    "events_count": 5,
    "semantic_source": "llm",
}
```

**Constraints:**
- 仅导入 `confirmed_raw_files`（不再 pd.concat 所有文件）
- 参考文档内容通过 `ReferenceContent` 注入 semantic_generator 的 Prompt（Phase 3 完善）
- 构建完成后删除状态文件
- 失败时保留状态文件，用户可以重试

---

## Plan 2.6: 中断恢复 + 兼容性

**What:**

1. **中断恢复：** 如果用户退出对话后重新调用 `create_project(action="start")`，检查是否有未完成的状态：
   - 有 → 提示用户可以 `action="classify"` 继续
   - 无 → 正常开始新流程

2. **向后兼容：** 保留旧的快速创建路径：
   - 如果用户传 `action="quick"` 或不传 action 且不传 `data_files`，走旧逻辑

3. **状态查询工具：** 新增 `get_create_project_status` MCP 工具：
   - 查看当前是否有进行中的创建流程
   - 返回当前状态和待确认项

**Files:** `server.py`

**Verification:**
- 中断恢复测试：创建到 ALIGN → 模拟退出 → 重新调用 → 恢复
- 向后兼容测试：`create_project(action="start", ...)` → 正常流程
- 状态查询测试

---

## Plan 2.7: 集成测试

**What:**

创建 `tests/test_phase2.py`：
1. 模拟完整的4阶段流程（PRE_ANALYZE → ALIGN → CONFIRM → BUILD）
2. 测试用户修正分类的交互
3. 测试中断恢复
4. 测试仅导入确认文件的构建
5. 用真实 rednote 数据做端到端验证

**Verification:**
- `python tests/test_phase2.py` 全部通过

---

## Execution Order

```
Plan 2.1 (数据结构) → Plan 2.2 (PRE_ANALYZE) → Plan 2.3 (ALIGN)
                                                      ↓
                          Plan 2.4 (CONFIRM) → Plan 2.5 (BUILD)
                                                      ↓
                          Plan 2.6 (恢复+兼容) → Plan 2.7 (集成测试)
```

---

## Files Changed

| File | Action | Plans |
|------|--------|-------|
| `mcp_server/project_model.py` | 修改：+2 dataclass + 3 方法 | 2.1 |
| `mcp_server/server.py` | 修改：重构 create_project + 新增 get_create_project_status | 2.2-2.6 |
| `tests/test_phase2.py` | 新建 | 2.7 |

**不修改的文件：**
- `file_classifier.py` — Phase 1 已完成
- `data_auditor.py` — Phase 1 已完成
- `reference_parser.py` — Phase 1 已完成（Phase 3 增强 Prompt 注入）
- `semantic_generator.py` — Phase 3 才改
- `cli.py` — 后续迭代

---

## Dependencies

- Phase 1 全部产出（FileClassifier, DataAuditor, ReferenceParser, DataAuditReport）
- 现有 `ProjectStore.create_project()` 保留，BUILD 阶段复用其文件复制逻辑

---

## Risks

| Risk | Mitigation |
|------|------------|
| 状态文件损坏 | JSON 解析失败时返回错误信息，用户可重新 start |
| 用户长时间不操作 | 状态文件持久化在磁盘，不依赖内存 |
| 多个创建流程并行 | 全局 `_create_states` dict 管理，project_id 唯一 |
| Hermes Agent 不理解多阶段流程 | tool description 中详细说明 action 参数和返回格式 |
| 旧项目不兼容新结构 | BUILD 阶段检测旧 project.yaml，提示迁移 |

---
*Created: 2026-04-30*
