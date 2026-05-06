# ChatBI MCP Server

Project-agnostic conversational data analysis platform via MCP protocol.

## Project Structure

```
mcp_server/
├── server.py               # MCP tool entry (24 tools, ~2022 lines)
├── project_model.py        # Project CRUD + DuckDB + Pipeline state (~1029 lines)
├── semantic_generator.py   # LLM semantic layer + domain tagging (~1225 lines)
├── semantic_validator.py   # SQL + data quality + coverage validation (~195 lines)
├── semantic_query.py       # L1/L2/L3 query engine (~42 lines)
├── analysis_templates.py   # L2 templates: retention/funnel/period (~280 lines)
├── chart_renderer.py       # ECharts chart + funnel conversion (~258 lines)
├── dashboard_html.py       # Dashboard HTML: domain grouping + time filter + dark mode (~645 lines)
├── dashboard_store.py      # Dashboard persistence + encoding fix + quality check (~252 lines)
├── file_classifier.py      # File type classification (~342 lines)
├── data_auditor.py         # Data quality auditing (~164 lines)
├── reference_parser.py     # Reference document parsing (~606 lines)
└── cli.py                  # Terminal CLI interface (~473 lines)
```

## Core Capabilities

### 6-Stage Interactive Pipeline

```
INGEST → ALIGN → MAP → VERIFY → BUILD → SERVE
```

Each stage has checkpoint persistence (`.pipeline_state.json`), supporting resume from any point.

- **INGEST**: File classification + data audit + reference document parsing
- **ALIGN**: User reviews and confirms AI's data understanding
- **MAP**: Semantic layer generation (metrics, dimensions, events)
- **VERIFY**: SQL executability + data quality + KPI coverage validation
- **BUILD**: Semantic layer built with business_domain tags
- **SERVE**: Dashboard rendered with domain grouping and time filter

### 3-Level Query Protocol

| Level | Method | Description |
|-------|--------|-------------|
| L1 | `semantic_query(level="L1")` | Metric + dimensions + filters → auto SQL |
| L2 | `semantic_query(level="L2")` | Retention/funnel/period-over-period templates |
| L3 | `raw_sql()` | Raw SQL fallback with safety limits |

### Dashboard Features

- Business domain grouping (KPI cards per domain, charts below)
- Global time filter (JavaScript front-end filtering)
- Dark mode toggle (ggplot2_minimal / ggplot2_dark themes)
- Funnel chart with automatic conversion rates
- Double UTF-8 encoding auto-fix on save

## MCP Tools (24)

### Project Management

| Tool | Function |
|------|----------|
| `create_project` | Create project (6-stage pipeline) |
| `list_projects` | List all projects |
| `switch_project` | Switch current project |
| `get_current_project` | Get current project info |
| `delete_project` | Delete a project |

### Pipeline Execution

| Tool | Function |
|------|----------|
| `execute_pipeline_step` | Execute single pipeline step (supports retry) |
| `get_pipeline_status` | Get current pipeline state |

### Data Understanding

| Tool | Function |
|------|----------|
| `review_data_understanding` | Review AI's data understanding report |
| `update_column_mapping` | Modify column business name, type, derived logic |
| `update_event_mapping` | Modify event name and SQL pattern |
| `update_metric_mapping` | Add/remove/adjust metric definitions |

### Semantic Layer

| Tool | Function |
|------|----------|
| `get_semantic_context` | Get semantic layer metadata |
| `regenerate_semantic_layer` | Regenerate semantic layer |
| `validate_semantic_layer` | Validate SQL + data quality + coverage |

### Query & Analysis

| Tool | Function |
|------|----------|
| `semantic_query` | Structured query (L1) or analysis template (L2) |
| `raw_sql` | Raw SQL query (L3 fallback) |

### Visualization & Dashboard

| Tool | Function |
|------|----------|
| `render_chart` | Generate ECharts chart |
| `list_dashboards` | List dashboards |
| `create_dashboard` | Create a new dashboard |
| `save_chart_to_dashboard` | Save chart to dashboard (auto domain matching) |
| `delete_chart` | Delete a chart |
| `delete_dashboard` | Delete a dashboard |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | Yes | — | LLM API Key |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | LLM API Base URL |
| `BI_MODEL` | No | `deepseek-chat` | LLM model name |
| `CHATBI_PROJECTS_DIR` | No | `./projects` | Project data directory |

## MCP Client Configuration

### Trae / VS Code

Copy `.mcp.json.example` to `.mcp.json` and fill in your API key.

### Claude Desktop

Add to Claude Desktop config:

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "<python-absolute-path>",
      "args": ["<project-absolute-path>/mcp_server/server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "<your-api-key>",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "BI_MODEL": "deepseek-chat"
      }
    }
  }
}
```

## Development

### Running Tests

```bash
python tests/test_classifier.py
python tests/test_auditor.py
python tests/test_parser.py
python tests/test_kpi_validator.py
python tests/test_report_persist.py
```

### Creating a New Project

Use the `create_project` tool's 6-stage interactive pipeline, or step through with `execute_pipeline_step`.

## Dependencies

```
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
