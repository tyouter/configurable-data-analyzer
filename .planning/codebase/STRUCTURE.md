# Codebase Structure

**Analysis Date:** 2026-04-30 — Updated 2026-05-04

## Directory Layout

```
configurable-data-analyzer/
├── mcp_server/                 # Core Python package — MCP server + services
│   ├── __init__.py             # Package marker
│   ├── server.py               # MCP tool definitions (24 tools, ~2022 lines)
│   ├── project_model.py        # Project CRUD + DuckDB data layer + Pipeline state (~1029 lines)
│   ├── semantic_generator.py   # LLM semantic layer generation + domain tagging (~1225 lines)
│   ├── semantic_query.py       # SQL validation (~42 lines)
│   ├── semantic_validator.py   # SQL+Quality+Coverage verification (~195 lines)
│   ├── analysis_templates.py   # L2 templates: retention/funnel/period (~280 lines)
│   ├── chart_renderer.py       # ECharts chart generation + funnel conversion (~258 lines)
│   ├── dashboard_html.py       # Dashboard HTML: domain grouping + time filter + dark mode (~645 lines)
│   ├── dashboard_store.py      # Dashboard persistence + encoding fix + quality check (~252 lines)
│   ├── file_classifier.py      # File type classification (~342 lines)
│   ├── data_auditor.py         # Data quality auditing (~164 lines)
│   ├── reference_parser.py     # Reference document parsing (~606 lines)
│   └── cli.py                  # Terminal CLI interface (~473 lines)
├── projects/                   # Per-project data directories
│   └── 1bd90a0c/               # Rednote project
│       ├── project.yaml        # Project config + semantic layer
│       ├── 1bd90a0c.duckdb     # DuckDB analytical database
│       └── dashboards/         # Dashboard JSON files
├── data/                       # Source data files (gitignored)
│   └── rednote analysis/       # Rednote raw data
├── .trae/                      # Trae IDE configuration
│   ├── rules/                  # GSD framework rules
│   └── skills/                 # Trae skills
├── .planning/                  # GSD planning artifacts
│   ├── codebase/               # Codebase analysis docs
│   ├── phases/                 # Phase context docs
│   └── plans/                  # Phase execution plans
├── .mcp.json                   # MCP client config
├── claude_desktop_config.json  # Claude Desktop MCP config
├── CLAUDE.md                   # Claude Code project instructions
├── DESIGN-ferrari.md           # Design specs
├── requirements.txt            # Python dependencies
└── .gitignore
```

## Directory Purposes

**`mcp_server/`:**
- Purpose: All Python source code — MCP server, services, CLI
- Contains: 13 Python modules
- Key files: `server.py` (entry point), `project_model.py` (data layer)

**`projects/`:**
- Purpose: Per-project persistent storage
- Contains: YAML configs, DuckDB databases, dashboard JSONs, pipeline state
- Key files: `{id}/project.yaml` (semantic layer + config), `{id}/.pipeline_state.json`

**`data/`:**
- Purpose: Raw source data files (input only, never modified)
- Contains: Excel, CSV files
- Gitignored: Yes — data files not committed

**`.trae/rules/`:**
- Purpose: Trae IDE project rules and GSD framework configuration
- Contains: 3 markdown files defining GSD commands, agents, references

## Key File Locations

**Entry Points:**
- `mcp_server/server.py`: MCP server (stdio/SSE transport)
- `mcp_server/cli.py`: Terminal CLI interface

**Configuration:**
- `projects/{id}/project.yaml`: Per-project config + semantic layer
- `projects/{id}/.pipeline_state.json`: Pipeline stage state
- `.mcp.json`: MCP client connection config
- `claude_desktop_config.json`: Claude Desktop MCP config
- `requirements.txt`: Python dependencies

**Core Logic:**
- `mcp_server/project_model.py`: Project CRUD + DuckDB data management
- `mcp_server/semantic_generator.py`: LLM-assisted semantic layer + domain tagging
- `mcp_server/semantic_validator.py`: SQL + data quality + coverage verification
- `mcp_server/analysis_templates.py`: L2 analysis patterns

**Dashboard:**
- `mcp_server/dashboard_html.py`: HTML rendering with domain grouping + time filter
- `mcp_server/dashboard_store.py`: Persistence + encoding fix + quality check
- `mcp_server/chart_renderer.py`: ECharts generation + funnel conversion rates

**Testing:**
- `mcp_server/test_project_system.py`: Basic integration test

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `project_model.py`, `chart_renderer.py`)
- Config files: `lowercase.ext` (e.g., `project.yaml`, `.mcp.json`)
- Data files: Mixed naming in source data (e.g., `rednote KPI definition_20260323.xlsx`)

**Directories:**
- Python package: `mcp_server/` (single package, no sub-packages)
- Projects: `{project_id}/` (hash-based ID)

## Where to Add New Code

**New MCP Tool:**
- Tool definition: `mcp_server/server.py` — add `@mcp.tool()` function
- Supporting logic: New module in `mcp_server/` or extend existing module

**New Analysis Template:**
- `mcp_server/analysis_templates.py` — add params dataclass + SQL builder

**New Chart Type:**
- `mcp_server/chart_renderer.py` — extend `build_echarts_option()`

**New Dashboard Feature:**
- `mcp_server/dashboard_html.py` — HTML rendering changes
- `mcp_server/dashboard_store.py` — persistence changes

**New Validation Rule:**
- `mcp_server/semantic_validator.py` — add validation method

**Utilities:**
- New module in `mcp_server/` for significant new capabilities

## Special Directories

**`projects/`:**
- Purpose: Per-project runtime data
- Generated: Yes (by `create_project` tool)
- Committed: Partially (YAML configs yes, DuckDB no)

**`data/`:**
- Purpose: Source data files
- Generated: No (user-provided)
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD framework planning artifacts
- Generated: Yes (by GSD commands)
- Committed: Recommended

---

*Structure analysis: 2026-04-30 — Updated 2026-05-04 (Milestone 2 completed)*
