---
name: chatbi
description: "Conversational data analysis via ChatBI MCP: import data, check quality, query with semantics, visualize with intent-driven charts, build dashboards."
version: 0.2.0
metadata:
  hermes:
    tags: [data-analysis, mcp, charts, dashboard, duckdb, sql, visualization]
    related_skills: [native-mcp]
    mcp_server: chatbi
    tools_pattern: "mcp_chatbi_*"
---

# ChatBI — Conversational Data Analysis

Analyze data through the ChatBI MCP server. Supports multi-project management, 3-level query protocol (L1/L2/L3), intent-driven visualization, and spec-driven dashboards.

## Prerequisites

- ChatBI MCP server must be configured in `config.yaml` under `mcp_servers.chatbi`
- Tools are prefixed `mcp_chatbi_*` (e.g. `mcp_chatbi_create_project`)
- DEEPSEEK_API_KEY must be set in the server env config

## When to Use This Skill

Use ChatBI tools when the user wants to:

- **Analyze data files** (CSV, Excel, JSON) — create a project, let ChatBI handle ingestion
- **Query data** with natural language — use semantic_query (L1/L2) or raw_sql (L3)
- **Visualize data** — render charts with intent-driven selection
- **Build dashboards** — generate complete dashboards from specs
- **Check data quality** — deep audit with industry-specific rules
- **Explore a dataset** — understand columns, metrics, events before querying

Do NOT write custom Python scripts to read Excel/CSV files when ChatBI can handle them natively. Use `mcp_chatbi_create_project` instead.

## Workflow

### 1. Create Project (Interactive Pipeline)

```
mcp_chatbi_create_project(name="Sales Analysis", data_files=["/path/to/sales.xlsx"])
```

This starts the 6-stage pipeline:
1. **INGEST** — file classification + data audit
2. **ALIGN** — review AI's data understanding
3. **MAP** — generate semantic layer (metrics, dimensions, events)
4. **VERIFY** — SQL validation + quality checks
5. **BUILD** — build with business domain tags
6. **SERVE** — dashboard ready

After build, **always run data quality check**:

```
mcp_chatbi_review_data_issues(project_type="behavior_analysis")
```

Show all issues (errors/warnings/suggestions) to the user. Discuss each one. Do NOT auto-fix.

### 2. Explore the Data

```
mcp_chatbi_get_semantic_context(section="all")
```

Show the user available metrics, dimensions, and events.

```
mcp_chatbi_explore_column_values(column="event_type", pattern="%click%")
```

Always explore column values before writing SQL filters.

### 3. Query (Returns Data Only, No Charts)

**L1 — Structured Query:**
```
mcp_chatbi_semantic_query(
  level="L1",
  metric="dau",
  dimensions=["event_date"],
  filters=[{"field": "event_date", "op": "gte", "value": "2024-01-01"}]
)
```

**L2 — Analysis Templates:**
```
# Retention
mcp_chatbi_semantic_query(level="L2", analysis_type="retention",
  analysis_params={"anchor_event": "signup", "return_event": "login", "day_offsets": [1,3,7]})

# Funnel
mcp_chatbi_semantic_query(level="L2", analysis_type="funnel",
  analysis_params={"steps": ["view_page", "add_cart", "purchase"], "within_days": 7})

# Period over Period
mcp_chatbi_semantic_query(level="L2", analysis_type="period_over_period",
  analysis_params={"metric": "revenue", "dimension": "date", "period_type": "day"})
```

**L3 — Raw SQL:**
```
mcp_chatbi_raw_sql(sql="SELECT event_date, COUNT(*) FROM events GROUP BY event_date LIMIT 100")
```

**Important:** Show query results to the user (SQL, row count, columns, preview data) before rendering charts.

### 4. Visualize (Interactive Confirmation)

**Preview first:**
```
mcp_chatbi_render_chart(
  data=<query_result>,
  intent="Show daily active users trend over time",
  confirm=True
)
```

Show the render spec to the user (chart type, reasoning, alternatives). Let them confirm or adjust.

**Then render:**
```
mcp_chatbi_render_chart(
  data=<query_result>,
  intent="Show daily active users trend over time",
  chart_type="line"
)
```

### 5. Save and Export

```
mcp_chatbi_save_chart_to_dashboard(dashboard_name="KPI Dashboard", chart={...})
mcp_chatbi_export_dashboard(dashboard_name="KPI Dashboard", theme="ggplot2_minimal")
```

## Tool Reference (26 tools)

### Project Management
| Tool | Purpose |
|------|---------|
| `mcp_chatbi_create_project` | Create project (6-stage interactive) |
| `mcp_chatbi_list_projects` | List all projects |
| `mcp_chatbi_switch_project` | Switch active project |
| `mcp_chatbi_get_current_project` | Get current project info |
| `mcp_chatbi_delete_project` | Delete a project |
| `mcp_chatbi_migrate_project` | Migrate old project format |

### Pipeline
| Tool | Purpose |
|------|---------|
| `mcp_chatbi_execute_pipeline_step` | Execute single pipeline step (resumable) |
| `mcp_chatbi_regenerate_semantic_layer` | Regenerate semantic layer |

### Data Understanding & Quality
| Tool | Purpose |
|------|---------|
| `mcp_chatbi_review_data_understanding` | Review AI's data understanding report |
| `mcp_chatbi_review_data_issues` | Deep data quality check with industry rules |
| `mcp_chatbi_update_column_mapping` | Modify column business name, type, derived logic |
| `mcp_chatbi_update_event_mapping` | Modify event name and SQL pattern |
| `mcp_chatbi_update_metric` | Add/remove/adjust metric definitions |

### Semantic Layer
| Tool | Purpose |
|------|---------|
| `mcp_chatbi_get_semantic_context` | Get semantic layer metadata |
| `mcp_chatbi_validate_semantic_layer` | Validate SQL + data quality + coverage |
| `mcp_chatbi_explore_column_values` | Explore distinct values in a column |

### Query & Analysis
| Tool | Purpose |
|------|---------|
| `mcp_chatbi_semantic_query` | L1 structured / L2 analysis templates |
| `mcp_chatbi_raw_sql` | L3 raw SQL (read-only, max 2000 rows) |

### Visualization & Dashboard
| Tool | Purpose |
|------|---------|
| `mcp_chatbi_render_chart` | Intent-driven chart (confirm/use_llm params) |
| `mcp_chatbi_generate_dashboard_from_spec` | Generate full dashboard from spec JSON |
| `mcp_chatbi_list_dashboards` | List dashboards |
| `mcp_chatbi_create_dashboard` | Create empty dashboard |
| `mcp_chatbi_save_chart_to_dashboard` | Save chart to dashboard |
| `mcp_chatbi_delete_chart` | Delete a chart |
| `mcp_chatbi_delete_dashboard` | Delete a dashboard |
| `mcp_chatbi_export_dashboard` | Export dashboard as self-contained HTML |

## Key Principles

- **Query and render are separate** — `semantic_query` returns data only, `render_chart` handles visualization
- **Show results at each step** — query results → render spec → final chart
- **Intent-driven** — describe visualization goals, not chart types
- **All ECharts types supported** — line, bar, pie, funnel, scatter, bar_line, boxplot, ranking_bar, area, radar, gauge, ring, stackedBar, candlestick, heatmap, treemap, sankey, etc.
- **LLM-assisted chart selection** — auto-downgrades to rules when no API key

## Data Quality Rules

`review_data_issues` applies industry-specific checks:

- **Generic** (all projects): null rate, duplicates, future dates, negatives, single-value cols
- **Behavior analysis**: event format, low-freq events, session anomalies, date gaps
- **Time series**: interval consistency, value spikes, stale data

Always present findings to the user and collect decisions. Do NOT auto-process.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tools not showing | Restart `hermes chat` to reconnect MCP server |
| `DEEPSEEK_API_KEY not set` | Add to `config.yaml` → `mcp_servers.chatbi.env` |
| `numpy` compatibility error | Install `numpy<2.0.0` in server's Python env |
| DuckDB file locked | Close other connections to the project |
| Chart type mismatch | Use `confirm=True` to preview before rendering |
