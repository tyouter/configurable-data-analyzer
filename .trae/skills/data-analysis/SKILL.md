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

# 数据分析 SKILL

## 概述

本SKILL通过 ChatBI MCP Server 的工具进行对话式数据分析，支持：
- 多项目管理（创建、切换、删除）
- 交互式项目创建（文件分类、审计、认知对齐）
- 语义层驱动的结构化查询（L1指标查询 + L2分析模板）
- 原始SQL兜底查询
- ECharts图表生成与Dashboard管理

## 工作流程

### 1. 项目准备阶段

如果用户还没有活跃项目：

```
步骤：
1. 调用 list_projects() 查看已有项目
2. 如果有匹配项目 → switch_project(project_id) 切换
3. 如果没有 → create_project(name, data_files) 创建新项目
```

#### 创建项目流程（4阶段交互）

create_project 是多阶段交互流程，不是一次性操作：

| 阶段 | action | 说明 |
|------|--------|------|
| 启动 | `start` | 提交数据文件，自动分类+审计+解析，返回审计报告 |
| 修正 | `classify` | 用户修正文件分类或回答问题（可多轮） |
| 确认 | `confirm` | 用户确认要导入的原始数据文件、参考文档和分析目标 |
| 构建 | `build` | 仅导入确认的文件，生成语义层 |

快捷方式：`create_project(name, data_files)` 等同于 action="start"

### 2. 语义查询阶段

项目就绪后，通过语义层进行结构化查询：

```
步骤：
1. 调用 get_semantic_context(section="all") 了解当前项目的指标、维度、事件
2. 分析用户需求，选择查询级别：
   - L1: 简单指标查询 → semantic_query(level="L1", metric, dimensions, filters)
   - L2: 分析模板 → semantic_query(level="L2", analysis_type, analysis_params)
   - L3: 原始SQL → raw_sql(sql)
3. 如果需要可视化 → render_chart(data, chart_type, title)
4. 如果需要保存 → save_chart_to_dashboard(dashboard_name, chart)
```

### 3. 结果输出阶段

```
输出格式：
- 文字报告：以清晰易读的格式展示分析结果
- 图表：通过 render_chart 生成 ECharts 配置
- Dashboard：保存到项目看板供后续查看
- 进一步分析选项：询问用户是否需要其他分析
```

## MCP 工具参考

### 项目管理

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| `create_project` | 创建项目（4阶段） | action, name, data_files, project_type, corrections, confirmed_raw_files, confirmed_ref_files, analysis_goals |
| `list_projects` | 列出所有项目 | 无 |
| `switch_project` | 切换当前项目 | project_id |
| `get_current_project` | 获取当前项目信息 | 无 |
| `delete_project` | 删除项目 | project_id |
| `regenerate_semantic_layer` | 重新生成语义层 | use_llm |

### 查询

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| `semantic_query` | 结构化语义查询 | level, metric, dimensions, filters, analysis_type, analysis_params |
| `raw_sql` | 原始SQL查询（L3兜底） | sql, limit |
| `get_semantic_context` | 获取语义层元数据 | section: metrics/dimensions/events/analysis_templates/schema/all |

### 可视化与Dashboard

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| `render_chart` | 生成ECharts图表 | data, chart_type, title |
| `list_dashboards` | 列出Dashboard | 无 |
| `create_dashboard` | 创建Dashboard | name |
| `save_chart_to_dashboard` | 保存图表到Dashboard | dashboard_name, chart |
| `delete_chart` | 删除图表 | dashboard_id, chart_id |
| `delete_dashboard` | 删除Dashboard | dashboard_id |

### L2 分析模板

| analysis_type | 说明 | analysis_params |
|---------------|------|-----------------|
| `retention` | 留存分析 | anchor_event, return_event, day_offsets?, start_date?, end_date? |
| `funnel` | 漏斗分析 | steps, within_days?, start_date?, end_date? |
| `period_over_period` | 同环比分析 | metric, dimension, period_type?, start_date?, end_date? |

## 错误处理

### 项目相关
- "No active project" → 先调用 switch_project 或 create_project
- 项目不存在 → 检查 project_id 是否正确，用 list_projects 确认
- 创建流程中断 → 用 create_project(action="status") 查看状态

### 查询相关
- "Unknown metric" → 用 get_semantic_context(section="metrics") 查看可用指标
- L2 参数缺失 → 检查 analysis_type 对应的必需参数
- SQL 执行失败 → 检查表名是否为 events，字段名是否在语义层中定义

### 数据相关
- 文件不存在 → 提供正确的绝对路径
- 文件格式错误 → 支持 xlsx/xls/csv/json 格式
- DuckDB 文件损坏 → 删除项目重新创建

## 分析示例

### 示例1：创建项目并分析

用户：帮我分析这份数据 D:/data/sales.xlsx

执行：
1. create_project(name="销售分析", data_files=["D:/data/sales.xlsx"])
2. 查看审计报告，确认文件分类
3. create_project(action="confirm", project_id=..., confirmed_raw_files=[...], analysis_goals=[...])
4. create_project(action="build", project_id=...)
5. get_semantic_context(section="metrics") 了解可用指标
6. semantic_query(level="L1", metric="total_events", dimensions=["event_date"])

### 示例2：留存分析

用户：看看用户的7日留存

执行：
1. get_semantic_context(section="events") 确认可用事件
2. semantic_query(level="L2", analysis_type="retention", analysis_params={"anchor_event": "login_page_pageshow", "return_event": "discovery_page_pageshow", "day_offsets": [1,3,7]})
3. render_chart(data, chart_type="line", title="7日留存趋势")

### 示例3：漏斗分析

用户：分析从发现页到导航的转化漏斗

执行：
1. semantic_query(level="L2", analysis_type="funnel", analysis_params={"steps": ["discovery_page_pageshow", "post_detail_page_pageshow", "poi_detail_page_pageshow", "poi_detail_page_navigation_button_click"]})
2. render_chart(data, chart_type="funnel", title="发现页→导航转化漏斗")

## 注意事项

1. **数据安全**：仅处理已脱敏的数据文件，不上传数据到云端
2. **项目隔离**：每个项目有独立的语义层和DuckDB实例，互不干扰
3. **语义层驱动**：所有查询基于语义层定义，确保指标计算一致性
4. **交互式创建**：项目创建需要用户确认文件分类和分析目标，不盲目自动执行
5. **L3兜底**：当L1/L2无法满足需求时，使用raw_sql，但需注意SQL安全性
