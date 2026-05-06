# ChatBI MCP Server

Project-agnostic conversational data analysis platform, exposing data analysis capabilities to AI Agents via the [MCP protocol](https://modelcontextprotocol.io/).

## Highlights

- **Spec-Driven Dashboard** — Define chart specs in JSON, auto-generate complete dashboard with one tool call
- **6-Stage Pipeline** — INGEST → ALIGN → MAP → VERIFY → BUILD → SERVE, with human-in-the-loop checkpoints
- **3-Level Query** — L1 structured query / L2 analysis templates (retention, funnel, PoP) / L3 raw SQL
- **8 Chart Types** — line, bar, pie, funnel, scatter, bar_line, boxplot, ranking_bar
- **LLM Semantic Layer** — Auto-generates metrics, dimensions, event mappings from your data
- **Multi-LLM** — DeepSeek, OpenAI, and OpenAI-compatible APIs (Moonshot, Zhipu, Ollama, etc.)
- **Service Layer Architecture** — Clean separation: thin MCP wrapper → service modules → core

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/tyouter/configurable-data-analyzer.git
cd configurable-data-analyzer
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env: DEEPSEEK_API_KEY=sk-your-key

# 3. Start the server
python mcp_server/server.py
```

See [QUICKSTART.md](QUICKSTART.md) for detailed setup with different MCP clients.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Client Layer (Claude Desktop / Trae / Cursor)  │
└────────────────────┬────────────────────────────┘
                     │ MCP Protocol
┌────────────────────▼────────────────────────────┐
│  server.py — Thin MCP Wrapper (25 tools)        │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Service Layer                                   │
│  project.py · query.py · dashboard.py · context │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Core: Model+DuckDB · Semantic · Charts · Themes│
└─────────────────────────────────────────────────┘
```

## 6-Stage Pipeline

```
INGEST ──▶ ALIGN ──▶ MAP ──▶ VERIFY ──▶ BUILD ──▶ SERVE
  │          │        │       │          │         │
  │          │        │       │          │         └─ Dashboard display
  │          │        │       │          └─ Domain-grouped generation
  │          │        │       └─ SQL validation + data quality
  │          │        └─ Semantic layer generation
  │          └─ User confirms data understanding
  └─ File import + classification + audit
```

## MCP Tools (25)

### Project Management

| Tool | Description |
|------|-------------|
| `create_project` | Create project (6-stage interactive pipeline) |
| `list_projects` | List all projects |
| `switch_project` | Switch current project |
| `get_current_project` | Get current project info |
| `delete_project` | Delete a project |

### Pipeline & Migration

| Tool | Description |
|------|-------------|
| `execute_pipeline_step` | Execute a single pipeline step |
| `regenerate_semantic_layer` | Regenerate semantic layer |
| `migrate_project` | Migrate old project format |

### Data Understanding

| Tool | Description |
|------|-------------|
| `review_data_understanding` | Review AI's data understanding report |
| `update_column_mapping` | Modify column business name, type, derived logic |
| `update_event_mapping` | Modify event name and SQL pattern |
| `update_metric` | Add/remove/adjust metric definitions |

### Semantic Layer

| Tool | Description |
|------|-------------|
| `get_semantic_context` | Get semantic layer metadata |
| `validate_semantic_layer` | Validate SQL + data quality + coverage |
| `explore_column_values` | Explore distinct values in a column |

### Query & Analysis

| Tool | Description |
|------|-------------|
| `semantic_query` | Structured query (L1) or analysis template (L2) |
| `raw_sql` | Raw SQL query (L3 fallback) |

### Visualization & Dashboard

| Tool | Description |
|------|-------------|
| `render_chart` | Generate ECharts chart (8 types) |
| `generate_dashboard_from_spec` | Generate full dashboard from spec JSON |
| `list_dashboards` | List dashboards |
| `create_dashboard` | Create a new dashboard |
| `save_chart_to_dashboard` | Save chart to dashboard |
| `delete_chart` | Delete a chart |
| `delete_dashboard` | Delete a dashboard |
| `export_dashboard` | Export as self-contained HTML |

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | Yes | — | LLM API Key |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | LLM API Base URL |
| `BI_MODEL` | No | `deepseek-chat` | LLM model name |
| `CHATBI_PROJECTS_DIR` | No | `./projects` | Project data directory |

### MCP Client Setup

**Claude Desktop:**

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "python",
      "args": ["<path>/mcp_server/server.py"],
      "env": { "DEEPSEEK_API_KEY": "<your-key>" }
    }
  }
}
```

**SSE / HTTP Transport:**

```bash
python mcp_server/server.py --transport sse --port 8000
```

## Requirements

- Python 3.10+
- DuckDB (embedded, per-project)
- LLM API access (DeepSeek, OpenAI, or compatible)

## License

[MIT](LICENSE)
