# Codebase Structure

**Analysis Date:** 2026-04-30

## Directory Layout

```
configurable-data-analyzer/
├── mcp_server/                 # Core Python package — MCP server + services
│   ├── __init__.py             # Package marker
│   ├── server.py               # MCP tool definitions (19 tools, ~891 lines)
│   ├── project_model.py        # Project CRUD + DuckDB data layer (~450 lines)
│   ├── semantic_generator.py   # LLM semantic layer generation (~470 lines)
│   ├── semantic_query.py       # SQL validation (~42 lines)
│   ├── analysis_templates.py   # L2 templates: retention/funnel/period (~280 lines)
│   ├── chart_renderer.py       # ECharts chart generation (~203 lines)
│   ├── dashboard_store.py      # Dashboard persistence (~127 lines)
│   ├── cli.py                  # Terminal CLI interface (~353 lines)
│   └── test_project_system.py  # Basic integration test
├── projects/                   # Per-project data directories
│   └── rednote/                # Existing rednote project
│       ├── project.yaml        # Project config + semantic layer
│       └── rednote.duckdb      # DuckDB analytical database
├── data/                       # Source data files (gitignored)
│   └── rednote analysis/       # Rednote raw data
│       ├── rednote20260319-20260412.xlsx
│       ├── rednote KPI definition_20260323.xlsx
│       ├── Rednote tracking datastracture_20260331.xlsx
│       └── Rednote dashboard V1.0 5-30 requirements.xlsx
├── .trae/                      # Trae IDE configuration
│   ├── rules/                  # GSD framework rules
│   │   ├── project_rules.md
│   │   ├── gsd-agents.md
│   │   └── gsd-references.md
│   └── skills/                 # Trae skills
├── .planning/                  # GSD planning artifacts
│   └── codebase/               # Codebase analysis docs (this file)
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
- Contains: 9 Python modules
- Key files: `server.py` (entry point), `project_model.py` (data layer)

**`projects/`:**
- Purpose: Per-project persistent storage
- Contains: YAML configs, DuckDB databases, dashboard JSONs
- Key files: `{id}/project.yaml` (semantic layer + config)

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
- `.mcp.json`: MCP client connection config
- `claude_desktop_config.json`: Claude Desktop MCP config
- `requirements.txt`: Python dependencies

**Core Logic:**
- `mcp_server/project_model.py`: Project CRUD + DuckDB data management
- `mcp_server/semantic_generator.py`: LLM-assisted semantic layer
- `mcp_server/analysis_templates.py`: L2 analysis patterns

**Testing:**
- `mcp_server/test_project_system.py`: Basic integration test

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `project_model.py`, `chart_renderer.py`)
- Config files: `lowercase.ext` (e.g., `project.yaml`, `.mcp.json`)
- Data files: Mixed naming in source data (e.g., `rednote KPI definition_20260323.xlsx`)

**Directories:**
- Python package: `mcp_server/` (single package, no sub-packages)
- Projects: `{project_name}/` (lowercase)

## Where to Add New Code

**New MCP Tool:**
- Tool definition: `mcp_server/server.py` — add `@mcp.tool()` function
- Supporting logic: New module in `mcp_server/` or extend existing module

**New Analysis Template:**
- `mcp_server/analysis_templates.py` — add params dataclass + SQL builder

**New Project Type:**
- `mcp_server/semantic_generator.py` — add to `TYPE_TEMPLATES` dict

**New Chart Type:**
- `mcp_server/chart_renderer.py` — extend `build_echarts_option()`

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

*Structure analysis: 2026-04-30*
