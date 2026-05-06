# Quick Start Guide

Get ChatBI MCP Server running in 5 minutes.

## Prerequisites

- Python 3.10+
- An LLM API key (DeepSeek, OpenAI, or compatible)

## Step 1: Install

```bash
git clone https://github.com/tyouter/configurable-data-analyzer.git
cd configurable-data-analyzer
pip install -r requirements.txt
```

## Step 2: Configure API Key

```bash
cp .env.example .env
```

Edit `.env`:

```env
DEEPSEEK_API_KEY=sk-your-actual-key
```

For OpenAI or compatible providers:

```env
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.openai.com/v1
BI_MODEL=gpt-4o
```

| Provider | Base URL | Model |
|----------|----------|-------|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Ollama (local) | `http://localhost:11434/v1` | `qwen2.5` |

## Step 3: Connect Your MCP Client

### Claude Desktop

Add to config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/.claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "chatbi": {
      "command": "python",
      "args": ["<absolute-path>/mcp_server/server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-your-key"
      }
    }
  }
}
```

### Trae / VS Code

```bash
cp .mcp.json.example .mcp.json
```

Edit `.mcp.json` with your API key. Restart IDE.

### SSE / HTTP Transport

```bash
python mcp_server/server.py --transport sse --port 8000
```

## Step 4: Create Your First Project

In your MCP client:

```
Create a project called "Sales Analysis" with files: /path/to/sales.csv
```

The AI will guide you through the 6-stage pipeline:

1. **INGEST** — File classification + data audit
2. **ALIGN** — Review AI's data understanding
3. **MAP** — Generate semantic layer (metrics, dimensions, events)
4. **VERIFY** — SQL validation + quality checks
5. **BUILD** — Build with business domain tags
6. **SERVE** — Dashboard generated

After build, the AI will run `review_data_issues` to check data quality
(duplicates, anomalies, test accounts) and discuss findings with you
before proceeding to analysis.

## Step 5: Query and Visualize

```
What's the monthly revenue trend?
Show me the top 10 products by sales.
Compare this month vs. last month.
```

Or generate a complete dashboard from a spec file:

```
Generate dashboard from spec: /path/to/dashboard_spec.json
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `DEEPSEEK_API_KEY not set` | Ensure `.env` exists with your key |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `numpy` compatibility error | Install `numpy<2.0.0` |
| DuckDB file locked | Close other connections to the project |
