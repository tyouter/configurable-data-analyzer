# Technology Stack

**Analysis Date:** 2026-04-30

## Languages

**Primary:**
- Python 3.10+ — All backend logic (MCP server, data processing, LLM integration)

**Secondary:**
- YAML — Project configuration, semantic layer definitions (`project.yaml`)
- SQL (DuckDB dialect) — Data queries via semantic layer and raw SQL
- JSON — Dashboard storage, MCP transport
- Markdown — Documentation, CLAUDE.md

## Runtime

**Environment:**
- Python 3.10+ (CPython)
- Docker (Hermes Agent deployment on Linux)

**Package Manager:**
- pip (via `requirements.txt`)
- No lockfile present (no pip-tools, poetry, or pdm)

## Frameworks

**Core:**
- MCP (Model Context Protocol) `>=1.0.0` — Tool integration protocol for AI agents
- FastMCP — Python MCP server framework (from `mcp[cli]`)
- FastAPI `>=0.100.0` — HTTP API framework (for SSE transport mode)
- Uvicorn `>=0.24.0` — ASGI server

**Data:**
- DuckDB `>=0.9.0` — Embedded analytical database (per-project instances)
- Pandas `>=2.0.0` — Data loading, cleaning, transformation
- NumPy — Numerical operations (transitive via Pandas)

**LLM:**
- DeepSeek API — Semantic layer generation and query interpretation
- Direct HTTP calls via `requests` (no LangChain/LlamaIndex)

**Build/Dev:**
- No build system configured
- No type checking configured (no mypy/pyright)
- No linter configured (no ruff/flake8)

## Key Dependencies

**Critical:**
- `mcp[cli]` — Core MCP protocol server, defines tool interfaces
- `duckdb` — In-process OLAP database, stores per-project analytical data
- `pandas` — Data ingestion pipeline (Excel/CSV → DataFrame → DuckDB)
- `openpyxl` — Excel file reader (required for `.xlsx` data files)
- `pyyaml` — YAML parsing for project config and semantic layer
- `requests` — HTTP client for DeepSeek LLM API calls

**Infrastructure:**
- `fastapi` + `uvicorn` — SSE transport mode for MCP server

## Configuration

**Environment:**
- `DEEPSEEK_BASE_URL` — LLM API endpoint (default: `https://api.deepseek.com`)
- `DEEPSEEK_API_KEY` — LLM authentication key (CRITICAL: must be set)
- `BI_MODEL` — LLM model name (default: `deepseek-chat`, current: `deepseek-v4-pro`)
- `.env` file present but `load_dotenv()` NOT called in server.py

**Build:**
- `requirements.txt` — Python dependencies
- `.mcp.json` — MCP client configuration (Claude Desktop)
- `claude_desktop_config.json` — Claude Desktop MCP config

## Platform Requirements

**Development:**
- Python 3.10+
- DeepSeek API key
- Data files in `data/` directory

**Production (Docker/Hermes):**
- Docker container running Hermes Agent
- MCP server mounted as accessible path
- Data directory bind-mounted (not source code)
- Network access to DeepSeek API

---

*Stack analysis: 2026-04-30*
