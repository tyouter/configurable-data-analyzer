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

## 交互式工作流程

### 1. 确认当前项目

```
调用 get_current_project()
```

- 如果有项目 → 直接进入分析
- 如果没有 → `list_projects()` 查看已有项目，或 `create_project()` 创建

### 2. 了解语义层

```
调用 get_semantic_context(section="all")
```

向用户展示可用的指标、维度、事件，让用户了解项目能分析什么。

### 3. 执行查询（只返回数据，不渲染图表）

```
semantic_query(level="L1", metric="dau", dimensions=["event_date"])
```

返回: `{data, sql, row_count, columns, data_preview, visualization_goal, summary}`

**重要：向用户展示查询结果摘要**
```
"查询返回 25 行 × 2 列，日期范围 2024-01 到 2024-06。
 执行的SQL：SELECT event_date, COUNT(DISTINCT reduser_id) FROM events GROUP BY event_date
 前3行数据：..."
```

### 4. 预览渲染方案（让用户参与决策）

```
render_chart(
  data=<查询结果>,
  intent=visualization_goal,
  confirm=True
)
```

返回: `{status: "confirm_required", render_spec: {chart_type, reasoning, alternatives}}`

**向用户展示渲染建议**
```
"建议使用 bar_line 图表：
  X轴: event_date（时间）
  Y轴左: 活跃人数（柱状）
  Y轴右: 增长率（折线）
  原因: 你想同时看到绝对值和趋势变化
  备选方案: line（纯折线图）, area（面积图）
 确认？还是想调整？"
```

### 5. 实际渲染（用户确认后）

```
render_chart(
  data=<查询结果>,
  intent=visualization_goal,
  chart_type="bar_line"
)
```

### 6. 保存和导出

```
save_chart_to_dashboard(dashboard_name="KPI看板", chart={...})
export_dashboard(dashboard_name="KPI看板", theme="ggplot2_minimal")
```

## 项目创建（多阶段交互）

```
1. create_project(name, data_files) → 审计报告
2. 向用户展示分类结果，询问是否修正
3. create_project(action="confirm", confirmed_raw_files=[...])
4. create_project(action="build") → 导入数据 + 语义层生成
5. review_data_issues(project_type="behavior_analysis") → 数据质量检查
   向用户展示发现的问题（错误/警告/建议），逐个确认处理方式
6. get_semantic_context() → 展示给用户检查
```

### 数据质量检查详情

`review_data_issues` 基于行业经验规则检查数据质量：

**通用规则**（所有项目都会检查）：
- 高空值率列、完全重复行、未来日期、负数异常值、单一值列、疑似ID列

**行为分析规则**（project_type="behavior_analysis"）：
- 事件名格式规范、低频事件、负/超长会话时长、用户事件爆发、日期断档
- 派生列建议：page_root（页面根路径）、event_action（动作类型）、user_tenure_days（用户天数）

**时序分析规则**（project_type="time_series"）：
- 时间间隔不一致、数值突刺、数据停滞、零值异常
- 派生列建议：差分值（增量）、滚动平均值

**Agent 必须向用户展示所有问题并收集决策**，不要自动处理。

## 查询协议

### L1 结构化查询
```
semantic_query(level="L1", metric="dau", dimensions=["event_date"], filters=[...])
```

### L2 分析模板

**留存分析**
```
semantic_query(level="L2", analysis_type="retention",
  analysis_params={anchor_event: "...", return_event: "...", day_offsets: [1,3,7]})
```

**漏斗分析**
```
semantic_query(level="L2", analysis_type="funnel",
  analysis_params={steps: ["step1", "step2", "step3"], within_days: 7})
```

**同环比分析**
```
semantic_query(level="L2", analysis_type="period_over_period",
  analysis_params={metric: "...", dimension: "event_date", period_unit: "day"})
```

### L3 原始SQL
```
raw_sql(sql="SELECT ... FROM events WHERE ... LIMIT 100")
```

## 关键原则

- **查询和渲染分离**：semantic_query 只返回数据，不自动渲染图表
- **每个关键步骤向用户展示并确认**：查询结果 → 渲染方案 → 最终图表
- **意图驱动**：使用 visualization_goal 而非硬编码图表类型
- **支持所有 ECharts 图表类型**：line, bar, pie, funnel, scatter, bar_line, boxplot, ranking_bar, area, radar, gauge, ring, stackedBar 等
- **LLM 辅助图表选择**：无 API Key 时自动降级为规则推断
