# Quick Start Guide

Get ChatBI MCP Server running in 5 minutes.

## Prerequisites

- Python 3.10+
- An LLM API key (DeepSeek, OpenAI, or compatible)

## Step 1: Install

```bash
git clone https://github.com/your-org/configurable-data-analyzer.git
cd configurable-data-analyzer
pip install -r requirements.txt
```

## Step 2: Configure API Key

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```env
DEEPSEEK_API_KEY=sk-your-actual-api-key-here
```

### Using OpenAI or Compatible APIs

If you're using OpenAI or an OpenAI-compatible provider (Moonshot, Zhipu, Ollama, etc.):

```env
DEEPSEEK_API_KEY=your-provider-api-key
DEEPSEEK_BASE_URL=https://api.openai.com/v1
BI_MODEL=gpt-4o
```

Common provider URLs:

| Provider | Base URL | Model Example |
|----------|----------|---------------|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Zhipu | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |
| Ollama (local) | `http://localhost:11434/v1` | `qwen2.5` |

## Step 3: Connect Your MCP Client

### Option A: Trae / VS Code

Copy the example config and fill in your key:

```bash
cp .mcp.json.example .mcp.json
```

Edit `.mcp.json`:

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-your-actual-api-key-here",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "BI_MODEL": "deepseek-chat"
      }
    }
  }
}
```

Restart your IDE. The ChatBI tools will appear in the MCP tools panel.

### Option B: Claude Desktop

Add to your Claude Desktop config file:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/.claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "python",
      "args": ["<absolute-path-to-project>/mcp_server/server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-your-actual-api-key-here",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "BI_MODEL": "deepseek-chat"
      }
    }
  }
}
```

Restart Claude Desktop.

### Option C: SSE / HTTP Transport

For remote access or web integration:

```bash
# SSE transport
python mcp_server/server.py --transport sse --port 8000

# Streamable HTTP transport
python mcp_server/server.py --transport streamable-http --port 8000
```

## Step 4: Create Your First Project

In your MCP client, start a conversation:

```
I want to analyze my sales data. The files are in /path/to/data/.
```

The AI agent will guide you through the 6-stage pipeline:

1. **INGEST** — Files are classified (data vs. reference docs) and audited
2. **ALIGN** — Review and confirm the AI's understanding of your data
3. **MAP** — Semantic layer is generated (metrics, dimensions, events)
4. **VERIFY** — SQL validation + data quality checks
5. **BUILD** — Semantic layer is built with business domain tags
6. **SERVE** — Dashboard is generated with domain grouping

You can also use the tools directly:

```
Create a project called "Sales Analysis" with files: /path/to/sales.csv, /path/to/kpi_definitions.xlsx
```

## Step 5: Query and Visualize

Once your project is set up, ask questions naturally:

```
What's the monthly revenue trend?
Show me the top 10 products by sales.
Compare this month vs. last month by region.
```

The system automatically:
- Maps your question to the right metric and dimensions
- Generates and executes SQL against your DuckDB
- Renders an ECharts chart
- Groups results by business domain on the dashboard

## What's Next?

- **Customize metrics:** Use `update_metric_mapping` to add or adjust metric definitions
- **Validate quality:** Use `validate_semantic_layer` to check SQL executability and data coverage
- **Export dashboard:** Dashboard HTML files are saved in `projects/{id}/dashboards/`
- **Multiple projects:** Use `list_projects` and `switch_project` to manage several datasets

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `DEEPSEEK_API_KEY not set` | Ensure `.env` file exists and contains your key |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `DuckDB file locked` | Close other connections to the same project |
| Charts not rendering | Check that `chart_option` is not null in dashboard JSON |
| Chinese text garbled | Dashboard store auto-fixes double encoding on save |

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | Yes | — | LLM API key |
| `DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | LLM API base URL |
| `BI_MODEL` | No | `deepseek-chat` | LLM model name |
| `CHATBI_PROJECTS_DIR` | No | `./projects` | Project data storage directory |
| `PORT` | No | `8000` | Port for SSE/HTTP transport |
| `HOST` | No | `0.0.0.0` | Host for SSE/HTTP transport |
