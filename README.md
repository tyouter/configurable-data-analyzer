# ChatBI MCP Server

Project-agnostic conversational data analysis platform, exposing data analysis capabilities to AI Agents via the [MCP protocol](https://modelcontextprotocol.io/).

## Highlights

- **Agent-Driven Semantic Injection** — Agent reads reference docs, injects metrics/events via `define_metric`/`register_events` into MCP semantic layer
- **Split-Workflow** — Agent handles understanding, MCP handles data & rendering; clean boundary
- **Spec-Driven Dashboard** — Define chart specs in JSON, auto-generate complete dashboard with one tool call
- **3-Level Query** — L1 structured query / L2 analysis templates (retention, funnel, PoP) / L3 raw SQL
- **8+ Chart Types** — line, bar, pie, funnel, scatter, bar_line, boxplot, ranking_bar, plus any ECharts type (area, radar, gauge, ring, stackedBar, candlestick, heatmap, treemap, sankey, etc.)
- **Intent-Driven Rendering** — Semantic layer describes visualization goals, rendering layer dynamically selects chart type via LLM + rules
- **Data Quality Layer** — Industry-driven data cleaning with user dialogue (generic, behavior analysis, time series rules)
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
│  server.py — Thin MCP Wrapper (33 tools)        │
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

## Split-Workflow

```
Agent（理解层）                         MCP（数据层）
  ├─ 读取参考文档 (openpyxl)              ├─ DuckDB 存储/查询
  ├─ 推导 KPI 口径                        ├─ 语义层管理（指标注册/SQL验证）
  ├─ 发现业务事件                         ├─ 数据质量审计
  ├─ 注入指标/事件到 MCP                  ├─ 图表渲染（ECharts inline）
  └─ 编排查询→渲染→Dashboard             └─ Dashboard 持久化/导出
```

Agent 负责理解、MCP 负责执行。参考文档永远由 Agent 读取，不走 MCP。

## MCP Tools (33)

### Project Management

| Tool | Description |
|------|-------------|
| `create_project` | Create project (6-stage interactive pipeline) |
| `list_projects` | List all projects |
| `switch_project` | Switch current project |
| `get_current_project` | Get current project info |
| `delete_project` | Delete a project |

### Semantic Injection (Agent-Driven)

| Tool | Description |
|------|-------------|
| `define_metric` | Define or update a single metric |
| `register_events` | Batch register or update events |
| `validate_metric` | Validate a single metric's SQL |

### Pipeline & Migration

| Tool | Description |
|------|-------------|
| `execute_pipeline_step` | Execute a single pipeline step |
| `regenerate_semantic_layer` | Regenerate semantic layer |
| `migrate_project` | Migrate old project format |

### Data Understanding & Quality

| Tool | Description |
|------|-------------|
| `review_data_understanding` | Review AI's data understanding report |
| `review_data_issues` | Deep data quality check with industry rules |
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
| `render_chart` | Intent-driven chart (intent/confirm/use_llm params) |
| `generate_dashboard_from_spec` | Generate full dashboard from spec JSON |
| `list_dashboards` | List dashboards |
| `create_dashboard` | Create a new dashboard |
| `save_chart_to_dashboard` | Save chart to dashboard |
| `delete_chart` | Delete a chart |
| `delete_dashboard` | Delete a dashboard |
| `export_dashboard` | Export as self-contained HTML |
| `save_dashboard_as_spec` | Export dashboard as versioned spec JSON |
| `validate_dashboard_spec` | Validate spec structure + metric refs |

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | No | — | LLM API Key（未配置时 Agent 委托模式） |
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

**Streamable HTTP Transport:**

```bash
python mcp_server/server.py --transport streamable-http --port 8000
```

## Agent Skills

Pre-built skill files guide AI agents to use ChatBI tools correctly.

### Claude Desktop / Trae

The skill is bundled in `.claude/skills/data-analysis/SKILL.md` and `.trae/skills/data-analysis/SKILL.md`. No extra installation needed — it activates automatically when you discuss data analysis.

### Hermes

Install the skill from GitHub:

```
/install-skill https://github.com/tyouter/configurable-data-analyzer/tree/master/skills/chatbi
```

Or manually copy `skills/chatbi/` to your Hermes skills directory. The skill teaches Hermes to use ChatBI MCP tools instead of writing ad-hoc Python scripts for data tasks.

## Requirements

- Python 3.10+
- DuckDB (embedded, per-project)
- LLM API access (DeepSeek, OpenAI, or compatible)

## License

[MIT](LICENSE)
