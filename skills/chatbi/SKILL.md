---
name: chatbi
description: "Conversational data analysis via ChatBI MCP: import data, inject metrics/events, query with semantics, visualize with intent-driven charts, build dashboards."
version: 0.3.0
metadata:
  hermes:
    tags: [data-analysis, mcp, charts, dashboard, duckdb, sql, visualization]
    related_skills: [native-mcp]
    mcp_server: chatbi
    tools_pattern: "mcp_chatbi_*"
---

# ChatBI — Conversational Data Analysis

Analyze data through the ChatBI MCP server. Supports multi-project configuration injection, 3-level query protocol (L1/L2/L3), intent-driven visualization, and spec-driven dashboards.

## Architecture: Split-Workflow

```
Agent reads reference docs (openpyxl) → Derives KPI formulas & event mappings
  → Injects via define_metric / register_events → MCP validates SQL
  → Agent queries → MCP renders charts → dashboard_spec.json exported
```

**MCP (this server)**: data storage, query execution, SQL validation, chart rendering, dashboard persistence.
**Agent (Hermes/Claude/Trae)**: reads reference documents, derives KPI definitions, injects metrics/events into MCP.

## When to Use This Skill

- **Analyze data files** (CSV, Excel) — create a project, let MCP handle ingestion + schema audit
- **Configure semantics** — inject metrics via `define_metric`, events via `register_events`
- **Query data** — use `semantic_query` (L1/L2) or `raw_sql` (L3)
- **Visualize data** — render charts with intent-driven selection
- **Build dashboards** — generate from specs, export as self-contained HTML
- **Check data quality** — deep audit with industry-specific rules

## Workflow

### 1. Create Project (Schema Analysis Only)

```
mcp_chatbi_create_project(name="Sales Analysis", data_files=["/path/to/data.xlsx"])
```

MCP imports data, runs schema analysis (DataAuditor), returns column/types/quality info.
**Reference documents (KPI definitions, data dictionaries) are read by Agent directly — NOT by MCP.**

### 2. Agent Reads Reference Docs, Clarifies, then Injects Semantics

**IMPORTANT: Never inject metrics or events without user confirmation.** You are working with unfamiliar data — event names, column meanings, and business logic may differ from your assumptions.

**Step 2a — Explore the schema and show the user what you found:**

After creating the project, always explore schema first:
```
mcp_chatbi_get_semantic_context(section="all")
mcp_chatbi_explore_column_values(column="span_name", pattern="%porsche%")
```

Show the user: column types, top event names (span_name), date range, user counts, and any quality issues. Ask them to clarify: which events are important? What does each span_name mean?

**Step 2b — Propose metrics and wait for confirmation:**

For each metric you derive, present it to the user in a clear table before calling `define_metric`:

```
| 指标名 | SQL 公式 | 验证值 |
|--------|---------|--------|
| dau | COUNT(DISTINCT reduser_id) | 297 |
| porsche_active_rate | 分子 / 分母 * 100 | 3.2% |
```

Ask the user to confirm each formula — especially rates where the numerator/denominator pairing is critical. Only after confirmation, inject:

```
mcp_chatbi_define_metric(name="dau", sql="COUNT(DISTINCT reduser_id)", business_name="日活用户", ...)
```

**Step 2c — Propose events and wait for confirmation:**

List the events you plan to register, showing each span_name and its count:

```
| span_name | 事件数 | 用户数 | 提议的业务名 |
|-----------|--------|--------|------------|
| porsche_page_pageshow | 3518 | 297 | Porsche+页曝光 |
```

Wait for the user to confirm or correct event names and filters. Then register:

```
mcp_chatbi_register_events(events={...})
```

**Step 2d — Validate and show results:**

```
mcp_chatbi_validate_metric(metric_name="dau")
```

Show the validation result (pass/fail, sample value) to the user.

### 3. Explore the Data

```
mcp_chatbi_get_semantic_context(section="all")
mcp_chatbi_explore_column_values(column="span_name", pattern="%porsche%")
```

### 4. Query (Returns Data Only)

**L1 — Structured Query:**
```
mcp_chatbi_semantic_query(level="L1", metric="dau", dimensions=["event_date"],
  filters=[{"field": "event_date", "op": "gte", "value": "2024-01-01"}])
```

**L2 — Analysis Templates:** retention, funnel, period_over_period
**L3 — Raw SQL:** `mcp_chatbi_raw_sql(sql="...")`

### 5. Visualize

Preview: `mcp_chatbi_render_chart(confirm=True)` → Render: `mcp_chatbi_render_chart(chart_type="line")`

### 6. Save & Export

```
mcp_chatbi_save_chart_to_dashboard(dashboard_name="KPI Dashboard", chart={...})
mcp_chatbi_save_dashboard_as_spec(dashboard_name="KPI Dashboard")
mcp_chatbi_validate_dashboard_spec()
mcp_chatbi_export_dashboard(dashboard_name="KPI Dashboard")
```

## Tool Reference (33 tools)

### Project Management (6)
| Tool | Purpose |
|------|---------|
| `create_project` | Create project (schema analysis only) |
| `list_projects` | List all projects |
| `switch_project` | Switch active project |
| `get_current_project` | Get current project info |
| `delete_project` | Delete a project |
| `migrate_project` | Migrate old project format |

### Semantic Injection — Agent-Driven (3)
| Tool | Purpose |
|------|---------|
| `define_metric` | Define/update a single metric (Agent's primary injection channel) |
| `register_events` | Batch register/update events |
| `validate_metric` | Validate a single metric's SQL |

### Data Understanding & Quality (5)
| Tool | Purpose |
|------|---------|
| `review_data_understanding` | Review semantic layer report |
| `review_data_issues` | Deep data quality check |
| `update_column_mapping` | Modify column metadata |
| `update_event_mapping` | Modify event definitions |
| `update_metric` | Bulk metric CRUD |

### Semantic Layer (3)
| Tool | Purpose |
|------|---------|
| `get_semantic_context` | Get semantic layer metadata |
| `validate_semantic_layer` | Full-layer SQL validation |
| `explore_column_values` | Explore distinct values |

### Query & Analysis (2)
| Tool | Purpose |
|------|---------|
| `semantic_query` | L1/L2 queries |
| `raw_sql` | L3 raw SQL (read-only) |

### Visualization & Dashboard (10)
| Tool | Purpose |
|------|---------|
| `render_chart` | Intent-driven chart |
| `generate_dashboard_from_spec` | Generate dashboard from spec |
| `save_dashboard_as_spec` | Export dashboard as versioned spec JSON |
| `validate_dashboard_spec` | Validate spec structure + metric refs |
| `list_dashboards` | List dashboards |
| `create_dashboard` | Create empty dashboard |
| `save_chart_to_dashboard` | Save chart to dashboard |
| `delete_chart` | Delete a chart |
| `delete_dashboard` | Delete a dashboard |
| `export_dashboard` | Export as self-contained HTML |

### Pipeline & LLM (4)
| Tool | Purpose |
|------|---------|
| `execute_pipeline_step` | Execute single pipeline step |
| `regenerate_semantic_layer` | Regenerate (full fallback, use with caution) |
| `llm_status` | Check LLM mode |
| `submit_llm_result` | Submit Agent LLM result |

## Key Principles

- **Agent reads reference docs, MCP does not** — Agent uses openpyxl to read KPI/dictionary files
- **Query and render are separate** — `semantic_query` returns data only
- **Show results at each step** — schema → metric injection → query → chart spec → final chart
- **Intent-driven** — describe visualization goals, not chart types
- **Spec-driven dashboards** — `dashboard_spec.json` as the portable intermediate artifact
