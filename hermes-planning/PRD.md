# ChatBI MCP 重构 —— 产品需求文档 (PRD)

> 版本：0.1 | 日期：2026-05-09 | 状态：待实施
> 目标读者：DeepSeek-TUI（实现者）、Ray（决策者）

---

## 0. 产品概述

### 0.1 产品定位

ChatBI 是一个通过自然语言对话进行数据分析的工具。用户上传数据文件 → 用中文提问 → 自动生成图表和 Dashboard。核心价值是**让非技术用户也能自助分析数据**，同时**让技术用户的重复分析工作自动化**。

产品形态：Hermes Agent 的 MCP 工具集（28 个工具），嵌入在飞书/TUI 对话中。

### 0.2 目标客户

| 客户类型 | 典型用户 | 使用场景 | 核心需求 |
|---------|---------|---------|---------|
| **独立创作者/自媒体** | 内容创作者、播客主理人（如 Ray 自己） | 分析小红书/B站内容数据、用户行为 | 快速出图、不用写 SQL |
| **小型创业团队** | 产品经理、运营（3-50人团队） | 分析用户埋点数据、产品 Metrics | 自助分析、不用等数据工程师 |
| **数据分析师** | SQL 熟练的数据分析师 | 加速日常分析、复用分析模板 | 减少重复工作、可审计 |
| **汽车行业客户** | 车企产品/市场部门 | 竞品分析、销量预测、用户行为 | 行业特定分析模板 |

**当前阶段**：先服务好 Ray 自己（独立创作者+汽车行业），再扩展服务小型团队。

### 0.3 业务流程（正向）

#### 核心流程：一次数据分析的完整链路

```
用户有数据 + 有疑问
    │
    ▼
① 上传数据（Excel/CSV 拖入飞书）
    │  自动检测文件类型、数据格式
    ▼
② 对齐理解（人机对齐）
    │  Agent 解释数据→用户确认/修正→对齐
    ▼
③ 配置语义层
    │  定义指标口径、事件映射、维度关系
    ▼
④ 分析提问
    │  用户用自然语言提问（"DAU趋势""留存率"）
    │  Agent 理解意图→查询数据→展示结果
    ▼
⑤ 可视化
    │  自动选择图表类型 → 渲染 → 用户确认/调整
    ▼
⑥ Dashboard 沉淀
    │  保存为可复用的 Dashboard → 导出分享
```

#### 辅助流程：分析模板复用

```
一次高质量分析完成
    │
    ▼
保存为分析模板（dashboard_spec.json）
    │  包含：指标定义、口径、图表类型、布局
    ▼
新数据来了 → 加载模板 → 快速出报告
```

### 0.4 产品目标

| 维度 | 目标 | 衡量标准 |
|------|------|---------|
| 易用性 | 零 SQL 完成 80% 的常见分析 | 非技术用户首次使用能在 10 分钟内出第一张图 |
| 准确性 | 分析结果可信、口径一致 | 同一指标不同查询给出相同结果 |
| 可追溯 | 每个数字都知道怎么算出来的 | 每个指标可追溯到原始定义和 source |
| 可复用 | 一次配置，多次使用 | Dashboard 模板可跨项目复用 |
| 速度 | 从上传到第一张图 < 5 分钟 | 平均端到端用时 |

### 0.5 用户故事（User Stories）

**故事 1：创作者的数据自查**
> 作为小红书内容创作者，我想知道"上周发的 5 篇笔记中，哪篇的互动率最高"，这样我可以调整内容方向。
> 
> 期望：上传埋点数据 → 问"上周笔记互动率排名" → 自动出排名图

**故事 2：运营的日常监控**
> 作为产品运营，我想每天早上看到"昨天的 DAU、新用户数、核心功能使用率"的变化趋势，这样我能及时发现异常。
> 
> 期望：打开 Dashboard → 看到 3 张核心指标卡片 → 数据自动刷新

**故事 3：分析师的深度分析**
> 作为数据分析师，我想做"用户在 App 内的行为路径分析"，从首页→搜索→详情页→下单每一步的转化率。
> 
> 期望：说"做个漏斗分析，步骤是首页→搜索→详情→下单" → 自动出漏斗图

**故事 4：团队的数据统一**
> 作为团队负责人，我希望"团队所有人对"活跃用户"的定义是一致的"，避免不同人算出的数字打架。
> 
> 期望：指标口径在语义层统一注册 → 任何人查询都基于同一口径

### 0.6 功能全景

```
ChatBI 功能
├── 数据接入
│   ├── 文件上传（Excel/CSV/JSON）
│   ├── 自动类型检测
│   └── 数据质量审计
│
├── 语义层管理
│   ├── 指标注册（define_metric）
│   ├── 事件注册（register_events）
│   ├── 维度管理
│   └── SQL 验证（validate_metric）
│
├── 分析查询
│   ├── L1 结构化查询（指标+维度+过滤）
│   ├── L2 分析模板（留存/漏斗/同环比）
│   └── L3 原始 SQL（高级用户）
│
├── 可视化
│   ├── 意图驱动图表选择
│   ├── 多图表类型（20+）
│   ├── 手动调整
│   └── Playwright 截图导出
│
├── Dashboard
│   ├── 业务域分组
│   ├── KPI 卡片
│   ├── 全局时间筛选
│   ├── 暗色/亮色主题
│   └── spec 持久化（导入/导出）
│
└── 协作
    ├── 分析模板复用
    └── 指标口径统一（团队共享）
```

### 0.7 非功能需求

| 需求 | 要求 |
|------|------|
| 数据安全 | raw_sql 只读，禁止 DDL/DML |
| 查询限制 | 单次查询最多 2000 行 |
| 错误处理 | 每个工具返回结构化错误信息 |
| 审计日志 | 每次查询可追溯 |
| 配置持久化 | 容器重启后数据不丢失 |

---

## 1. 背景摘要

ChatBI MCP 是一个嵌入式数据分析工具（基于 DuckDB + ECharts），通过 MCP 协议与 Hermes Agent 集成。当前在 Rednote BI 项目实战中暴露了职责越界、流程形式化、缺乏中间产物等结构性问题。

**一句话结论**：MCP 做数据层（存储/查询/渲染），Agent 做理解层（文档读取/口径推导/指标注入）。当前 MCP 在错误层面做了错误的事。

---

## 1. 当前架构现状

### 1.1 代码结构

```
chatbi/mcp_server/
├── server.py                 # MCP 入口，28个工具，thin wrapper
├── cli.py                    # CLI 接口
├── project_model.py          # 项目模型 + DuckDB 管理器
│
├── semantic_generator.py     # LLM 语义层生成（全量） ⚠️ 问题点
├── semantic_validator.py     # SQL + 数据质量验证
├── semantic_query.py         # SQL 构建器
│
├── reference_parser.py       # 参考文档解析（pandas.to_string + 关键词） ⚠️ 问题点
├── file_classifier.py        # 文件分类（rule-based, ~60%准确率） ⚠️ 问题点
├── data_auditor.py           # 数据质量审计
├── data_skills/              # 行业数据质量规则
│
├── chart_selector.py         # 意图驱动图表类型选择
├── chart_renderer.py         # ECharts 图表生成
├── dashboard_html.py         # Dashboard HTML 渲染
├── dashboard_store.py        # Dashboard 持久化
├── analysis_templates.py     # L2 分析模板（留存/漏斗/同环比）
│
├── llm_client.py             # LLM 客户端（多 Provider）
├── excel_utils.py            # Excel 工具
│
└── service/
    ├── project.py            # 项目 CRUD + 管线
    ├── query.py              # L1/L2/L3 查询引擎
    ├── dashboard.py          # Dashboard + 图表 + spec 生成
    └── context.py            # 语义上下文 + 验证
```

### 1.2 管线流程（当前）

```
用户发起 → INGEST → ALIGN → MAP → VERIFY → BUILD → SERVE
                                                ↓
                                         regenerate_semantic_layer (全量核武器)
```

6 阶段管线，每个阶段都有 checkpoint 持久化。

### 1.3 查询协议（好的部分，保留）

| 层级 | 接口 | 说明 |
|------|------|------|
| L1 | `semantic_query(level="L1")` | 指标 + 维度 + 过滤条件 → 自动 SQL |
| L2 | `semantic_query(level="L2")` | 留存/漏斗/同环比 模板 |
| L3 | `raw_sql()` | 原始 SQL（只读，2000行限制） |

---

## 2. 核心问题

### P0 — 阻碍业务的问题

#### 2.1 MCP 越界做文档理解

**文件**：`reference_parser.py`, `file_classifier.py`

当前行为：
- 对参考文档（KPI 定义、Dashboard 需求、Schema 说明）进行 rule-based 分类
- 用 `pandas.to_string()` 提取文本，然后用关键词匹配做分类
- 准确率约 60%（合并单元格、布局语义、注释全部丢失）

**影响**：用户提供了详细的 31 个 KPI 定义文件，MCP 只推导出 3 个通用指标（total_events, dau, events_per_user）。剩下的 28 个需要 Agent 手动通过 `update_metric` 注入。

**修正方案**：删除 `reference_parser.py` 和 `file_classifier.py` 中的文档理解逻辑。参考文档由 Agent 直接读取（Agent 有完整 LLM 上下文，能理解合并单元格、布局语义）。

#### 2.2 ALIGN 阶段事件发现不完整

**文件**：`service/project.py` → ALIGN 阶段的 `review_data_understanding`

当前行为：
- ALIGN 报告说"发现 14 个事件"
- 实际上 `explore_column_values(column='span_name')` 返回 132 个

**影响**：事件映射严重缺失，后续所有的指标定义都基于错误的事件集。

**修正方案**：ALIGN 阶段改为 Agent 驱动：
1. Agent 调用 `explore_column_values(span_name)` 获取全部事件
2. Agent 结合参考文档筛选业务相关事件
3. Agent 调用 `update_event_mapping` 注入事件定义

#### 2.3 缺乏需求→指标→事件的显式映射

当前状态：
- KPI 定义在参考文档里
- 指标注册在 MCP 语义层
- 事件发现靠 `explore_column_values`
- **三者之间没有显式映射关系**

**影响**：不知道"这个指标的 SQL 对不对"，因为不知道它对应哪个需求。

**修正方案**：引入 `dashboard_spec.json` 作为中间产物，完整记录每个指标的映射链：

```json
{
  "charts": [
    {
      "title": "DAU 趋势",
      "metric": "dau",
      "dimension": "event_date",
      "chart_type": "line",
      "kpi_source": "rednote_KPI_definition.xlsx → 核心指标表",
      "trigger_events": ["login_page_pageshow", "discovery_page_pageshow"],
      "calculation": "COUNT(DISTINCT reduser_id) WHERE page_start NOT NULL",
      "sql": "SELECT event_date, COUNT(DISTINCT reduser_id) ..."
    }
  ]
}
```

#### 2.4 `regenerate_semantic_layer` 是全量核武器

**文件**：`semantic_generator.py`

当前行为：调用一次就重新生成**全部**指标/事件/维度。如果之前手动定义过 28 个指标，全部被抹掉。

**影响**：不敢调用。一旦误触，所有手动工作丢失。

**修正方案**：新增细粒度工具，保留 `regenerate_semantic_layer` 作为全量回退：

| 新增工具 | 功能 |
|---------|------|
| `define_metric(name, sql, business_domain)` | 新增/更新单个指标 |
| `register_events(event_list)` | 批量注册事件 |
| `validate_metric(id)` | 验证单个指标的 SQL |
| `delete_metric(id)` | 删除单个指标 |

### P1 — 需要优化的问题

#### 2.5 工具粒度粗糙

当前 28 个工具中，有超过一半是"全量操作"：
- `create_project` = 6 阶段全流程
- `regenerate_semantic_layer` = 全量生成
- `validate_semantic_layer` = 全量验证

缺少原子操作工具。

#### 2.6 Split-Workflow 模式未标准化

在 Rednote 第二期实战中验证了更快的模式：

```
Agent 读参考文档 → Agent 推导 31 个 KPI → update_metric 注入 → MCP 查询+渲染
```

但这个模式没有在代码层面固化，每次都要手动执行。

### P2 — 可优化的问题

#### 2.7 可视化层 CDN 依赖

`render_chart` 和 `dashboard_html.py` 生成的 HTML 从 CDN 加载 ECharts。在 Playwright 截图中，CDN 超时导致图表空白。

已在实战中找到 fix：inline ECharts + `page.set_content()`。

#### 2.8 配置路径不持久

`config.yaml` 中 MCP server 路径指向 `/workspace/projects/chatbi/...`（D: 盘挂载）。容器重启后挂载丢失，ChatBI 工具全部消失。

已经在 Hermes 端做了 fix（改为 `/opt/data/home/chatbi/` 持久卷路径），但 MCP server 自身配置仍有路径硬编码。

---

## 3. 目标架构

### 3.1 协作模型

```
用户飞书
    │
    ▼
Hermes Agent（架构讨论、需求分析、skill 管理）
    │  解释需求、查文档、推导 KPI
    │  输出：brief（几百字方向+约束）
    ▼
DeepSeek-TUI（代码实现）
    explore → plan → implement → review → verify
    │  输出：PR + 测试
    ▼
用户确认
```

### 3.2 MCP 职责边界

```
┌─────────────────────────────────────────┐
│ Agent（理解层）                          │
│  - 读取参考文档（openpyxl / 标准IO）      │
│  - 理解需求→推导 KPI 口径                │
│  - 需求→指标→事件 映射（dashboard_spec）  │
│  - 注入指标/事件到 MCP 语义层             │
└────────────────┬────────────────────────┘
                 │ MCP 工具调用
┌────────────────▼────────────────────────┐
│ MCP Server（数据层）                     │
│  - DuckDB 存储/查询（L1/L2/L3）          │
│  - 语义层管理（指标注册/SQL验证）         │
│  - 数据质量审计                          │
│  - 图表渲染（ECharts + inline）         │
│  - Dashboard 持久化/导出                │
└─────────────────────────────────────────┘
```

### 3.3 重构后管线

```
Agent 接收需求
    │
    ▼
读取参考文档（Agent 直读，不走 MCP）
    │  产出：需求摘要、KPI 列表、事件映射
    ▼
创建项目（MCP create_project，仅带原始数据）
    │  产出：DuckDB 表就绪
    ▼
注入指标/事件（Agent 调用 update_metric / register_events）
    │  产出：完整的语义层
    ▼
验证（MCP validate_semantic_layer）
    │  产出：验证报告
    ▼
查询+渲染（MCP semantic_query / render_chart）
    │  产出：图表/Dashboard
    ▼
dashboard_spec.json 持久化
```

### 3.4 新增/修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `reference_parser.py` | 删除/清空 | 不再做文档理解 |
| `file_classifier.py` | 保留文件分类，删除文档理解 | 只做数据类型判断（raw_data / reference） |
| `semantic_generator.py` | 保留全量生成，新增增量接口 | `regenerate_semantic_layer` 作为全量回退 |
| — | **新增** `semantic_injector.py` | `define_metric`, `register_events`, `validate_metric` 等细粒度工具 |
| `dashboard_store.py` | 扩展 | 支持 `dashboard_spec.json` 的导入/导出/版本管理 |
| `server.py` | 扩展 | 注册新工具，删除过时工具 |
| `service/project.py` | 修改 | ALIGN 阶段简化，不再做文档理解 |
| `chart_renderer.py` | 修改 | inline ECharts 作为默认模式 |
| — | **新增** `CONVENTIONS.md` | 记录 MCP 职责边界、SQL 模式、常见陷阱 |

---

## 4. 实施计划

### Phase 0 — 删减（预计 1 天）

**目标**：先砍掉错误的功能，恢复正确的职责边界。

| 任务 | 文件 | 验收标准 |
|------|------|---------|
| 0.1 删除参考文档理解 | `reference_parser.py` 清空 | `file_classifier` 只做数据类型判断 |
| 0.2 删除文件分类中的文档语义 | `file_classifier.py` | 分类只按扩展名和关键词粗略分 raw_data / reference |
| 0.3 ALIGN 阶段简化 | `service/project.py` | ALIGN 不再尝试理解文档语义 |
| 0.4 更新 server.py 工具列表 | `server.py` | 去掉过时的文档理解相关工具 |

### Phase 1 — 细粒度工具（预计 2-3 天）

**目标**：新增原子操作工具，替代全量操作。

| 任务 | 文件 | 验收标准 |
|------|------|---------|
| 1.1 新增 `define_metric` | `semantic_injector.py`（新） | 单个指标 CRUD |
| 1.2 新增 `register_events` | `semantic_injector.py` | 批量事件注册 |
| 1.3 新增 `validate_metric` | `semantic_injector.py` | 单指标 SQL 验证 |
| 1.4 server.py 注册新工具 | `server.py` | 新增工具在 MCP 协议层可见 |
| 1.5 保留 `regenerate_semantic_layer` 作为回退 | `semantic_generator.py` | 不影响现有功能 |

### Phase 2 — dashboard_spec 持久化（预计 2 天）

**目标**：引入需求→指标→事件的显式映射。

| 任务 | 文件 | 验收标准 |
|------|------|---------|
| 2.1 定义 `dashboard_spec.json` schema | `dashboard_store.py` | JSON Schema 验证通过 |
| 2.2 导入/导出 spec | `dashboard_store.py` | 支持从 spec 文件恢复完整的 Dashboard |
| 2.3 从 spec 生成 Dashboard | `service/dashboard.py` | `generate_dashboard_from_spec(spec_path)` |

### Phase 3 — Split-Workflow 标准化（预计 1 天）

**目标**：将实战验证的加速模式固化为标准流程。

| 任务 | 文件 | 验收标准 |
|------|------|---------|
| 3.1 更新 chatbi skill | `skills/chatbi/SKILL.md` | Pipeline Protocol 反映新流程 |
| 3.2 新增 Split-Workflow 模式文档 | `CONVENTIONS.md` | 包含完整的分工说明和示例 |
| 3.3 参考文件积累 | `references/` | 至少 3 个完整项目参考 |

### Phase 4 — 可视化强化（预计 1 天）

| 任务 | 文件 | 验收标准 |
|------|------|---------|
| 4.1 inline ECharts 默认化 | `chart_renderer.py` | 生成的 HTML 自带 ECharts |
| 4.2 Playwright 截图稳定化 | — | 截图不依赖 CDN |

---

## 5. 验收标准

### 5.1 必须通过

1. **增量指标定义**：创建项目后，调用 `define_metric` 5 次，可以定义 5 个不同指标，各自有不同的 SQL 口径
2. **需求→指标映射可追溯**：每个指标可以追溯到参考文档中的原始定义
3. **`regenerate_semantic_layer` 不破坏手动指标**：调用全量生成后，手动指标保留（或至少提示用户即将被覆盖）
4. **事件注册完整**：`register_events` 可以一次性注册 100+ 事件
5. **不依赖 MCP 做文档理解**：创建项目不需要 MCP 理解参考文档语义

### 5.2 期望通过

6. **`dashboard_spec.json` 可导入导出**：完整的 Dashboard 可以通过一个 JSON 文件恢复
7. **Split-Workflow 可在 3 步内完成**：创建项目 → 注入指标 → 查询渲染
8. **Inline ECharts 截图稳定**：不依赖 CDN 也能正常渲染

---

## 6. 参考

- `projects/chatbi/hermes-planning/README.md` — 完整讨论记录和架构分析
- `chatbi/mcp_server/server.py` — 当前 MCP 入口（28 工具）
- `chatbi/mcp_server/service/project.py` — 6 阶段管线实现
- `chatbi/mcp_server/semantic_generator.py` — 全量语义层生成
- `chatbi/mcp_server/reference_parser.py` — 参考文档解析（待删除）
- `chatbi/mcp_server/file_classifier.py` — 文件分类（待简化）
- `chatbi/mcp_server/dashboard_store.py` — Dashboard 持久化（待扩展）
- `chatbi/mcp_server/chart_renderer.py` — 图表渲染（待优化）
