---
name: data-analysis
description: 数据分析SKILL - 通过ChatBI MCP Server进行对话式数据分析，支持多项目管理、语义查询和可视化
trigger:
  - 分析数据
  - 数据分析
  - 统计分析
  - 用户分析
  - 查询数据
  - 分析报告
  - 创建项目
  - 语义查询
---

# 数据分析 Skill

通过 ChatBI MCP Server 对项目数据进行分析。MCP Server 已在 `.mcp.json` 中配置，所有工具自动可用。

## 工作流程

### 1. 确认当前项目

先检查是否有活跃项目：

```
调用 get_current_project()
```

- 如果有项目 → 直接进入分析
- 如果没有项目 → 调用 `list_projects()` 查看已有项目，或 `create_project()` 创建新项目

### 2. 了解项目语义层

分析前先了解当前项目有哪些指标、维度和事件：

```
调用 get_semantic_context(section="all")
```

重点关注：
- **metrics**：可用的指标名称和含义
- **dimensions**：可用的维度列
- **events**：事件定义（行为分析项目）
- **analysis_templates**：支持的 L2 分析模板

### 3. 选择查询级别

根据用户需求复杂度选择查询级别：

**L1 — 简单结构化查询**（覆盖 80% 场景）
```
semantic_query(
  level="L1",
  metric="dau",
  dimensions=["event_date"],
  filters=[{"field":"page_root","op":"eq","value":"discovery"}],
  limit=100
)
```

**L2 — 分析模板**（留存/漏斗/同环比）
```
semantic_query(
  level="L2",
  analysis_type="retention",
  analysis_params={
    "anchor_event": "login_page_pageshow",
    "return_event": "discovery_page_pageshow",
    "day_offsets": [1, 3, 7, 14, 30]
  }
)
```

**L3 — 原始SQL**（L1/L2 无法覆盖时）
```
raw_sql(sql="SELECT ... FROM events WHERE ... LIMIT 100")
```

### 4. 可视化

查询结果需要可视化时：
```
render_chart(
  data=<查询结果>,
  chart_type="line",
  title="日活趋势"
)
```

支持所有 ECharts 图表类型，常用包括：`line`, `bar`, `pie`, `funnel`, `scatter`, `bar_line`, `boxplot`, `ranking_bar`, `area`, `radar`, `gauge`, `ring`, `stackedBar`, `candlestick`, `heatmap`, `treemap`, `sankey` 等

### 5. 保存到看板

重要图表保存到 Dashboard：
```
save_chart_to_dashboard(
  dashboard_name="核心指标看板",
  chart={chart_type, chart_option, title, sql}
)
```

或从 spec JSON 一键生成完整看板：
```
generate_dashboard_from_spec(
  spec_path="dashboard_spec.json",
  dashboard_name="KPI看板",
  theme="ggplot2_minimal"
)
```

### 6. 导出 HTML

```
export_dashboard(
  dashboard_name="KPI看板",
  theme="ggplot2_minimal"
)
```

生成自包含 HTML 文件，双击即可在浏览器中打开。

## 项目管理

### 创建新项目（6阶段交互）

| 阶段 | action | 说明 |
|------|--------|------|
| 启动 | `start` | 提交数据文件，自动分类+审计+解析 |
| 修正 | `classify` | 用户修正文件分类（可多轮） |
| 确认 | `confirm` | 用户确认导入文件和分析目标 |
| 构建 | `build` | 导入文件，生成语义层 |

快捷方式：`create_project(name, data_files)` 等同于 action="start"

### 切换项目

```
switch_project(project_id="rednote")
```

## 数据理解与修正

### 查看数据理解报告
```
review_data_understanding(project_id)
```

### 修正映射
```
update_column_mapping(project_id, columns={...})
update_event_mapping(project_id, updates={...})
update_metric(project_id, updates={...}, delete_metrics=[...])
```

### 验证语义层
```
validate_semantic_layer(project_id, checks=["sql_executable", "data_quality", "coverage"])
```

### 探索列值
```
explore_column_values(column="span_name", pattern="login%", limit=50)
```

## L2 分析模板参数

**留存分析 (retention)**
```
analysis_params: {
  anchor_event: "事件名",
  return_event: "事件名",
  day_offsets: [1, 3, 7, 14, 30]
}
```

**漏斗分析 (funnel)**
```
analysis_params: {
  steps: ["步骤1事件", "步骤2事件", "步骤3事件"],
  within_days: 7
}
```

**同环比分析 (period_over_period)**
```
analysis_params: {
  metric: "指标名",
  dimension: "event_date",
  period_unit: "day"
}
```

## 注意事项

- 优先使用 L1/L2，L3 仅作兜底
- 指标名和维度名必须来自当前项目的语义层定义
- 事件名必须精确匹配 `get_semantic_context(section="events")` 中的定义
- 所有查询只读，L3 SQL 禁止 DDL/DML
- 分析结论用中文总结
