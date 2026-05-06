# ChatBI MCP Server

Project-agnostic conversational data analysis platform via MCP protocol.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Client Layer (Claude Desktop / Trae / Cursor)  │
└────────────────────┬────────────────────────────┘
                     │ MCP Protocol
┌────────────────────▼────────────────────────────┐
│  server.py — Thin MCP Wrapper (26 tools)        │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Service Layer (single source of truth)          │
├─────────────┬──────────────┬─────────────────────┤
│ project.py  │ query.py     │ dashboard.py        │
│ context.py  │              │                     │
├─────────────┴──────────────┴─────────────────────┤
│  Core Modules                                    │
├─────────────┬──────────────┬─────────────────────┤
│ Model+DuckDB│ SemanticGen  │ ChartRenderer       │
│ Validator   │ Templates    │ DashboardHtml       │
│ Themes      │ LLM Client   │ Store               │
└─────────────┴──────────────┴─────────────────────┘
```

## Project Structure

```
mcp_server/
├── server.py               # MCP entry (26 tools, thin wrapper)
├── cli.py                  # CLI interface (chatbi command)
├── service/                # Service layer
│   ├── project.py          # Project CRUD + pipeline
│   ├── query.py            # L1/L2/L3 query engine + data quality review
│   ├── dashboard.py        # Dashboard + chart + spec generation
│   └── context.py          # Semantic context + validation
├── project_model.py        # Project model + DuckDB manager
├── semantic_generator.py   # LLM semantic layer generation
├── semantic_validator.py   # SQL + data quality validation
├── semantic_query.py       # SQL builder + validation utils
├── analysis_templates.py   # L2 templates (retention/funnel/period)
├── chart_selector.py       # Intent-driven chart type resolution (LLM + rules)
├── chart_renderer.py       # ECharts chart generation (all types)
├── dashboard_html.py       # Dashboard HTML renderer (domain grouping + dark mode)
├── dashboard_store.py      # Dashboard persistence + quality check
├── llm_client.py           # Multi-provider LLM client
├── file_classifier.py      # File type classification
├── data_auditor.py         # Data quality auditing + industry-driven deep audit
├── data_skills/            # Industry data quality rules
│   ├── generic.py          #   Null rate, duplicates, future dates, negatives
│   ├── behavior_analysis.py#   Event format, session anomalies, date gaps
│   └── time_series.py      #   Interval consistency, spikes, stale data
├── reference_parser.py     # Reference document parsing
└── themes/                 # ECharts themes (ggplot2_minimal / ggplot2_dark)
```

## Core Capabilities

### 6-Stage Interactive Pipeline

```
INGEST → ALIGN → MAP → VERIFY → BUILD → SERVE
```

Each stage has checkpoint persistence, supporting resume from any point.

### 3-Level Query Protocol

| Level | Method | Description |
|-------|--------|-------------|
| L1 | `semantic_query(level="L1")` | Metric + dimensions + filters → auto SQL |
| L2 | `semantic_query(level="L2")` | Retention/funnel/period-over-period templates |
| L3 | `raw_sql()` | Raw SQL fallback with safety limits |

Query and rendering are separated: `semantic_query` returns data + metadata only. Agent shows results to user, then calls `render_chart` separately.

### Intent-Driven Chart Selection

```
visualization_goal (semantic layer) → chart_selector.resolve_chart_type() → chart_renderer
```

- **Priority**: user explicit type > LLM inference from intent > rule-based fallback
- **confirm mode**: `render_chart(intent, confirm=True)` returns spec for user review
- **LLM optional**: works without API key (rule-based fallback)
- Supports all ECharts chart types via generic option builder

### Data Quality Layer

After data import, `review_data_issues` runs industry-driven quality checks:
- **Generic**: null rate, duplicates, future dates, negative values, single-value cols
- **Behavior analysis**: event name format, low-freq events, session anomalies, date gaps
- **Time series**: interval consistency, value spikes, stale data

Returns errors/warnings/suggestions for Agent to discuss with user.
User decisions are saved as `data_cleaning` rules in semantic config, applied as DuckDB views.

### Dashboard Features

- Spec-driven dashboard generation (`generate_dashboard_from_spec`)
- Business domain grouping with KPI cards and charts
- Global time filter (JavaScript front-end filtering)
- Dark mode toggle (ggplot2_minimal / ggplot2_dark themes)
- All ECharts chart types supported (line, bar, pie, funnel, scatter, bar_line, boxplot, ranking_bar, area, radar, gauge, ring, stackedBar, candlestick, heatmap, treemap, sankey, etc.)
- Funnel chart with automatic conversion rates

## MCP Tools (26)

### Project Management (5)

| Tool | Function |
|------|----------|
| `create_project` | Create project (6-stage interactive pipeline) |
| `list_projects` | List all projects |
| `switch_project` | Switch current project |
| `get_current_project` | Get current project info |
| `delete_project` | Delete a project |

### Pipeline & Migration (3)

| Tool | Function |
|------|----------|
| `execute_pipeline_step` | Execute single pipeline step |
| `regenerate_semantic_layer` | Regenerate semantic layer |
| `migrate_project` | Migrate old project format |

### Data Understanding & Quality (5)

| Tool | Function |
|------|----------|
| `review_data_understanding` | Review AI's data understanding report |
| `review_data_issues` | Deep data quality check with industry rules |
| `update_column_mapping` | Modify column business name, type, derived logic |
| `update_event_mapping` | Modify event name and SQL pattern |
| `update_metric` | Add/remove/adjust metric definitions |

### Semantic Layer (3)

| Tool | Function |
|------|----------|
| `get_semantic_context` | Get semantic layer metadata |
| `validate_semantic_layer` | Validate SQL + data quality + coverage |
| `explore_column_values` | Explore distinct values in a column |

### Query & Analysis (2)

| Tool | Function |
|------|----------|
| `semantic_query` | Structured query (L1) or analysis template (L2) |
| `raw_sql` | Raw SQL query (L3 fallback) |

### Visualization & Dashboard (8)

| Tool | Function |
|------|----------|
| `render_chart` | Intent-driven chart generation (intent/confirm/use_llm) |
| `generate_dashboard_from_spec` | Generate full dashboard from spec JSON |
| `list_dashboards` | List dashboards |
| `create_dashboard` | Create a new dashboard |
| `save_chart_to_dashboard` | Save chart to dashboard |
| `delete_chart` | Delete a chart |
| `delete_dashboard` | Delete a dashboard |
| `export_dashboard` | Export dashboard as self-contained HTML |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | Yes | — | LLM API Key |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | LLM API Base URL |
| `BI_MODEL` | No | `deepseek-chat` | LLM model name |
| `CHATBI_PROJECTS_DIR` | No | `./projects` | Project data directory |

## MCP Client Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "python",
      "args": ["<path>/mcp_server/server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### SSE / HTTP Transport

```bash
python mcp_server/server.py --transport sse --port 8000
```

## Dependencies

```
numpy>=1.24.0,<2.0.0
pandas>=2.0.0
openpyxl>=3.1.0
pyyaml>=6.0
duckdb>=0.9.0
mcp[cli]>=1.0.0
fastapi>=0.100.0
uvicorn>=0.24.0
requests>=2.31.0
python-dotenv>=1.0.0
```
