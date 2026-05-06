# Architecture

**Analysis Date:** 2026-04-30

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                            │
├──────────────────┬──────────────────┬───────────────────────┤
│   Hermes Agent   │  Claude Desktop  │     CLI (cli.py)      │
│   (Docker/Feishu)│   (Local Dev)    │     (Terminal)        │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Protocol Layer                        │
│              `mcp_server/server.py` (FastMCP)                │
│         24 tools: project mgmt, query, chart, dashboard      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
├────────────────┬──────────────────┬─────────────────────────┤
│ ProjectModel   │ SemanticGenerator │  AnalysisTemplates      │
│ `project_      │ `semantic_        │  `analysis_             │
│  model.py`     │  generator.py`    │  templates.py`          │
│ CRUD + DuckDB  │ LLM API calls     │  Retention/Funnel/      │
│ Data loading   │ Schema analysis   │  Period-over-Period     │
│ Pipeline state │ Domain tagging    │                         │
└───────┬────────┴────────┬─────────┴─────────────────────────┘
        │                  │
        ▼                  ▼
┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  DuckDB        │  │  DeepSeek API    │  │ SemanticValidator│
│  (per-project) │  │  (LLM inference) │  │ `semantic_       │
│                │  │                  │  │  validator.py`   │
└────────────────┘  └──────────────────┘  │ SQL+Quality+     │
                                           │ Coverage checks  │
                                           └──────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Persistence Layer                                           │
│  `projects/{id}/project.yaml` + `{id}.duckdb`               │
│  `projects/{id}/dashboards/*.json`                           │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| MCP Server | Tool registration, request routing, session management | `mcp_server/server.py` |
| ProjectSession | Current project state, per-request context | `mcp_server/server.py` (inline) |
| ProjectStore | Project CRUD, YAML persistence | `mcp_server/project_model.py` |
| ProjectDataManager | DuckDB loading, SQL execution, data export | `mcp_server/project_model.py` |
| SemanticGenerator | LLM-assisted semantic layer generation, domain tagging | `mcp_server/semantic_generator.py` |
| SemanticQuery | SQL validation and safety checks | `mcp_server/semantic_query.py` |
| SemanticValidator | SQL executability, data quality, coverage verification | `mcp_server/semantic_validator.py` |
| AnalysisTemplates | L2 analysis patterns (retention, funnel, etc.) | `mcp_server/analysis_templates.py` |
| ChartRenderer | ECharts option generation, chart type suggestion, funnel conversion | `mcp_server/chart_renderer.py` |
| DashboardStore | Dashboard CRUD, chart persistence, encoding fix, quality check | `mcp_server/dashboard_store.py` |
| DashboardHtml | Dashboard HTML rendering, domain grouping, time filter, dark mode | `mcp_server/dashboard_html.py` |
| FileClassifier | File type classification (data vs reference) | `mcp_server/file_classifier.py` |
| DataAuditor | Data quality auditing | `mcp_server/data_auditor.py` |
| ReferenceParser | Reference document parsing (KPI definitions, data dictionaries) | `mcp_server/reference_parser.py` |
| CLI | Terminal interface mirroring MCP tools | `mcp_server/cli.py` |

## Pattern Overview

**Overall:** Layered service architecture with MCP tool facade

**Key Characteristics:**
- Single-process, synchronous Python
- Per-project isolation (separate DuckDB instances)
- LLM-assisted semantic layer generation
- Three-level query protocol (L1 structured, L2 templates, L3 raw SQL)
- Session-based project context (not multi-user)

## Layers

**MCP Tool Layer:**
- Purpose: Expose business capabilities as MCP tools
- Location: `mcp_server/server.py`
- Contains: 24 `@mcp.tool()` decorated functions
- Depends on: All service modules
- Used by: Hermes Agent, Claude Desktop, CLI

**Service Layer:**
- Purpose: Business logic implementation
- Location: `mcp_server/project_model.py`, `semantic_generator.py`, etc.
- Contains: Data classes, CRUD operations, LLM calls, SQL builders
- Depends on: DuckDB, Pandas, DeepSeek API
- Used by: MCP Tool Layer

**Persistence Layer:**
- Purpose: Data and configuration storage
- Location: `projects/{project_id}/`
- Contains: YAML configs, DuckDB databases, JSON dashboards
- Depends on: Filesystem
- Used by: Service Layer

## Data Flow

### Primary Request Path (Data Query)

1. User sends natural language query via Hermes/CLI (`server.py:semantic_query`)
2. Tool resolves current project via `_require_project()` (`server.py:82`)
3. Parameters mapped to SQL via semantic layer or analysis template (`semantic_query.py`, `analysis_templates.py`)
4. SQL executed against project DuckDB (`project_model.py:ProjectDataManager`)
5. Results serialized and returned (`server.py:_serialize_data`)

### Project Creation Path

1. User calls `create_project(name, data_files)` (`server.py:create_project`)
2. Files copied to project directory (`project_model.py:ProjectStore.create_project`)
3. Pipeline enters INGEST stage: files classified, data loaded into DuckDB, reference docs parsed
4. Pipeline advances through ALIGN → MAP → VERIFY → BUILD → SERVE stages
5. Each stage has checkpoint persistence (`.pipeline_state.json`)
6. User can review/modify at ALIGN (data understanding) and MAP (semantic layer) stages
7. VERIFY stage runs SQL executability + data quality + coverage checks
8. BUILD stage generates semantic layer with business_domain tags
9. SERVE stage renders Dashboard with domain grouping and time filter

**State Management:**
- Global `_session` singleton in `server.py` (module-level)
- `ProjectSession` holds current project + data manager
- No thread safety, no concurrency control

## Key Abstractions

**Project:**
- Purpose: Represents an imported dataset with its analysis context
- Examples: `projects/rednote/` (only existing project)
- Pattern: Dataclass → YAML serialization

**Semantic Layer:**
- Purpose: Maps raw columns to business concepts (metrics, dimensions, events)
- Examples: Embedded in `project.yaml` under `semantic_layer` key
- Pattern: LLM-generated, YAML-stored, SQL-templated

**Three-Level Query Protocol:**
- L1 (Structured): `metric` + `dimensions` + `filters` → SQL via semantic layer
- L2 (Templates): Retention, Funnel, Period-over-Period → parameterized SQL
- L3 (Raw SQL): Direct read-only SQL with safety limits

## Entry Points

**MCP Server (stdio):**
- Location: `mcp_server/server.py`
- Triggers: MCP client (Hermes, Claude Desktop)
- Responsibilities: Tool registration and dispatch

**MCP Server (SSE):**
- Location: `mcp_server/server.py --transport sse`
- Triggers: HTTP client
- Responsibilities: Same as stdio but over HTTP

**CLI:**
- Location: `mcp_server/cli.py`
- Triggers: Terminal user
- Responsibilities: Interactive REPL mirroring MCP tools

## Architectural Constraints

- **Threading:** Single-threaded, synchronous. No async. `_session` is a global mutable singleton.
- **Global state:** `_session` in `server.py` — holds current project, not safe for concurrent access.
- **Circular imports:** None detected — clean import hierarchy.
- **Path resolution:** `PROJECTS_DIR` uses relative path from `__file__` — may break in Docker if CWD differs.

## Anti-Patterns

### ~~Blind Data Concatenation~~ (FIXED in Phase 1)

**What was wrong:** `ProjectDataManager._load_from_source()` concatenated ALL imported files with `pd.concat`, regardless of file type.
**Fix:** `FileClassifier` separates data files from reference documents; only data files loaded into DuckDB.

### ~~Missing load_dotenv()~~ (FIXED in Phase 4)

**What was wrong:** `server.py` imported `os.environ.get("DEEPSEEK_API_KEY")` but never called `load_dotenv()`.
**Fix:** Added `from dotenv import load_dotenv; load_dotenv()` at server startup.

## Error Handling

**Strategy:** Exception-based with tool-level error responses

**Patterns:**
- Tools return `{"error": "message"}` dicts on failure
- `_require_project()` raises `ValueError` when no project selected
- LLM calls raise `ValueError` when API key is missing

## Cross-Cutting Concerns

**Logging:** No logging framework — print/stdout only
**Validation:** SQL validation via `semantic_query.py` (basic keyword blacklist)
**Authentication:** None — trusted internal network

---

*Architecture analysis: 2026-04-30 — Updated 2026-05-04 (Milestone 2 completed)*
