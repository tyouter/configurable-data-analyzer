# ChatBI MCP Server

Project-agnostic conversational data analysis platform, exposing data analysis capabilities to AI Agents via the [MCP protocol](https://modelcontextprotocol.io/).

## Features

- **MCP Protocol Native** — stdio / SSE / streamable-http transport, works with Claude Desktop, Trae, Cursor, and any MCP-compatible client
- **6-Stage Interactive Pipeline** — INGEST → ALIGN → MAP → VERIFY → BUILD → SERVE, with human-in-the-loop checkpoints
- **3-Level Query Protocol** — L1 structured query / L2 analysis templates (retention, funnel, period-over-period) / L3 raw SQL fallback
- **LLM-Powered Semantic Layer** — Auto-generates metrics, dimensions, and event mappings from your data
- **Semantic Validation** — SQL executability check + data quality verification + KPI coverage analysis
- **Business Domain Grouping** — Dashboard organized by business domain with global time filter and dark mode
- **Funnel Conversion Rates** — Automatic conversion rate calculation for funnel charts
- **Multi-LLM Support** — DeepSeek, OpenAI, and OpenAI-compatible APIs (Moonshot, Zhipu, Ollama, etc.)

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for a 5-minute setup guide.

```bash
# 1. Clone and install
git clone https://github.com/your-org/configurable-data-analyzer.git
cd configurable-data-analyzer
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env and add your LLM API key

# 3. Start the server
python mcp_server/server.py
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Client Layer                       │
├──────────────┬───────────────┬───────────────────────┤
│ Claude Desktop│   Trae IDE   │  Any MCP Client       │
└──────┬───────┴───────┬───────┴──────────┬────────────┘
       │               │                  │
       ▼               ▼                  ▼
┌──────────────────────────────────────────────────────┐
│              MCP Protocol Layer                       │
│        mcp_server/server.py (FastMCP)                 │
│             24 MCP Tools                              │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                  Service Layer                        │
├──────────────┬───────────────┬───────────────────────┤
│ ProjectModel │ SemanticGen   │ SemanticValidator      │
│ DuckDB + CRUD│ LLM + Domain  │ SQL + Quality + Cov    │
├──────────────┼───────────────┼───────────────────────┤
│ ChartRenderer│ DashboardHtml │ DashboardStore         │
│ ECharts+Fun. │ Domain+Filter │ Persist+Encode Fix     │
├──────────────┼───────────────┼───────────────────────┤
│ FileClassifr │ DataAuditor   │ ReferenceParser        │
│ Data vs Ref  │ Quality Audit │ KPI + Dictionary       │
└──────────────┴───────────────┴───────────────────────┘
```

## 6-Stage Pipeline

```
INGEST ──▶ ALIGN ──▶ MAP ──▶ VERIFY ──▶ BUILD ──▶ SERVE
  │          │         │        │         │         │
  │          │         │        │         │         └─ Dashboard display
  │          │         │        │         └─ Domain-grouped generation
  │          │         │        └─ SQL validation + data quality
  │          │         └─ Semantic layer generation
  │          └─ User confirms data understanding
  └─ File import + classification + audit
```

Each stage has a checkpoint persisted to `.pipeline_state.json`, supporting resume from any point.

## MCP Tools (24)

### Project Management

| Tool | Description |
|------|-------------|
| `create_project` | Create project (6-stage interactive pipeline) |
| `list_projects` | List all projects |
| `switch_project` | Switch current project |
| `get_current_project` | Get current project info |
| `delete_project` | Delete a project |

### Pipeline Execution

| Tool | Description |
|------|-------------|
| `execute_pipeline_step` | Execute a single pipeline step (supports retry) |
| `get_pipeline_status` | Get current pipeline state |

### Data Understanding

| Tool | Description |
|------|-------------|
| `review_data_understanding` | Review AI's data understanding report |
| `update_column_mapping` | Modify column business name, type, derived logic |
| `update_event_mapping` | Modify event name and SQL pattern |
| `update_metric_mapping` | Add/remove/adjust metric definitions |

### Semantic Layer

| Tool | Description |
|------|-------------|
| `get_semantic_context` | Get semantic layer metadata |
| `regenerate_semantic_layer` | Regenerate semantic layer |
| `validate_semantic_layer` | Validate SQL + data quality + coverage |

### Query & Analysis

| Tool | Description |
|------|-------------|
| `semantic_query` | Structured query (L1) or analysis template (L2) |
| `raw_sql` | Raw SQL query (L3 fallback) |

### Visualization & Dashboard

| Tool | Description |
|------|-------------|
| `render_chart` | Generate ECharts chart (line/bar/pie/funnel/scatter/table) |
| `list_dashboards` | List dashboards |
| `create_dashboard` | Create a new dashboard |
| `save_chart_to_dashboard` | Save chart to dashboard (auto domain matching) |
| `delete_chart` | Delete a chart from dashboard |
| `delete_dashboard` | Delete a dashboard |

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | Yes | — | LLM API Key (or use `LLM_API_KEY`) |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | LLM API Base URL |
| `BI_MODEL` | No | `deepseek-chat` | LLM model name |
| `CHATBI_PROJECTS_DIR` | No | `./projects` | Project data directory |

### MCP Client Setup

**Trae / VS Code:**

Copy `.mcp.json.example` to `.mcp.json` and fill in your API key.

**Claude Desktop:**

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "python",
      "args": ["<absolute-path>/mcp_server/server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "<your-api-key>",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "BI_MODEL": "deepseek-chat"
      }
    }
  }
}
```

**SSE / HTTP Transport:**

```bash
python mcp_server/server.py --transport sse --port 8000
python mcp_server/server.py --transport streamable-http --port 8000
```

## Project Structure

```
mcp_server/
├── server.py               # MCP tool entry point (24 tools)
├── project_model.py        # Project CRUD + DuckDB + Pipeline state
├── semantic_generator.py   # LLM semantic layer generation
├── semantic_validator.py   # SQL + data quality + coverage validation
├── semantic_query.py       # L1/L2/L3 query engine
├── analysis_templates.py   # L2 templates (retention/funnel/period)
├── chart_renderer.py       # ECharts chart generation
├── dashboard_html.py       # Dashboard HTML (domain grouping + time filter)
├── dashboard_store.py      # Dashboard persistence + encoding fix
├── file_classifier.py      # File type classification
├── data_auditor.py         # Data quality auditing
├── reference_parser.py     # Reference document parsing
└── cli.py                  # Terminal CLI interface
```

## Requirements

- Python 3.10+
- DuckDB (embedded, per-project)
- LLM API access (DeepSeek, OpenAI, or compatible)

## License

[MIT](LICENSE)
