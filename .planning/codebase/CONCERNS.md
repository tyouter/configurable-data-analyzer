# Codebase Concerns

**Analysis Date:** 2026-04-30

## Tech Debt

**Blind Data Concatenation:**
- Issue: `_load_from_source()` uses `pd.concat` on ALL imported files, including non-data files (KPI definitions, data dictionaries, requirement docs)
- Files: `mcp_server/project_model.py` (~line 329)
- Impact: Reference documents produce garbage rows in DuckDB, corrupting analysis results
- Fix approach: Add file classification step before loading — separate data files from reference docs

**Missing load_dotenv():**
- Issue: `server.py` reads env vars via `os.environ.get()` but never calls `load_dotenv()`
- Files: `mcp_server/server.py`, `mcp_server/semantic_generator.py`
- Impact: Docker deployments fail silently when API key is not set via Docker env
- Fix approach: Add `from dotenv import load_dotenv; load_dotenv()` at server startup

**Hardcoded Column Names in L2 Templates:**
- Issue: `analysis_templates.py` hardcodes `reduser_id` and `event_name` column names
- Files: `mcp_server/analysis_templates.py`
- Impact: L2 templates (retention, funnel) only work with rednote project, break for any other project
- Fix approach: Parameterize column names from project semantic layer

**Relative Path for PROJECTS_DIR:**
- Issue: `PROJECTS_DIR = os.path.join(os.path.dirname(__file__), "..", "projects")` uses relative path
- Files: `mcp_server/project_model.py` (line 25)
- Impact: Breaks when CWD differs (e.g., Docker deployment)
- Fix approach: Use absolute path resolution with `os.path.abspath()`

## Known Bugs

**DEEPSEEK_API_KEY Missing in Docker:**
- Symptoms: Semantic layer generation fails with `ValueError: DEEPSEEK_API_KEY not set`
- Files: `mcp_server/semantic_generator.py`
- Trigger: Running in Docker without manually setting env var in config.yaml
- Workaround: Manually set via `hermes config set` or Docker env

**Hermes MCP Tool Availability (Upstream):**
- Symptoms: MCP tools registered but not available in Feishu sessions
- Files: Hermes config (Issue #1247)
- Trigger: `platform_toolsets.feishu` missing `mcp-chatbi`
- Workaround: Add to platform_toolsets via `hermes config set`

## Security Considerations

**No Authentication on MCP Tools:**
- Risk: Any MCP client can access all projects and execute arbitrary SQL
- Files: `mcp_server/server.py`
- Current mitigation: Trusted internal network only
- Recommendations: Add API key validation for MCP connections

**API Key Exposure:**
- Risk: `DEEPSEEK_API_KEY` in `.env` file or Docker env could leak
- Files: `.env` (gitignored), Docker config
- Current mitigation: `.env` is gitignored
- Recommendations: Use Docker secrets or vault in production

**SQL Injection (Limited):**
- Risk: L3 raw SQL allows arbitrary read queries
- Files: `mcp_server/semantic_query.py`
- Current mitigation: Basic keyword blacklist (DROP, DELETE, etc.)
- Recommendations: Enforce read-only DuckDB connection

## Performance Bottlenecks

**Full File Load on Project Creation:**
- Problem: All data files loaded into memory via Pandas, then written to DuckDB
- Files: `mcp_server/project_model.py:_load_from_source()`
- Cause: `pd.concat` loads everything at once
- Improvement path: Stream data into DuckDB in chunks, or use DuckDB's native CSV/Excel readers

**LLM Call During Project Creation:**
- Problem: Semantic layer generation is synchronous blocking call to DeepSeek API
- Files: `mcp_server/semantic_generator.py:generate_semantic_layer()`
- Cause: No async, no caching, no retry logic
- Improvement path: Add retry with backoff, cache generated layers

## Fragile Areas

**Project Creation Pipeline:**
- Files: `mcp_server/server.py:create_project`, `mcp_server/project_model.py:create_project`
- Why fragile: Single monolithic operation with no checkpoints — if LLM fails, project is in half-created state
- Safe modification: Break into phases with rollback capability
- Test coverage: Minimal

**Semantic Layer Quality:**
- Files: `mcp_server/semantic_generator.py`
- Why fragile: Quality depends entirely on LLM output, no validation or user review step
- Safe modification: Add human-in-the-loop confirmation
- Test coverage: None

## Scaling Limits

**Single-User Session:**
- Current capacity: 1 active project per server instance
- Limit: Global `_session` singleton, no multi-user support
- Scaling path: Add session management with per-user project context

**DuckDB per Project:**
- Current capacity: 1 DuckDB file per project
- Limit: DuckDB is single-writer, no concurrent access
- Scaling path: Use connection pooling or move to client-server database

## Dependencies at Risk

**DeepSeek API Availability:**
- Risk: API downtime or rate limiting blocks semantic layer generation
- Impact: New projects cannot be created, queries cannot be interpreted
- Migration plan: Support multiple LLM providers (OpenAI, local models)

## Missing Critical Features

**Data Pre-Analysis & Confirmation:**
- Problem: No user review step before semantic layer generation
- Blocks: Ensuring data understanding is aligned with user expectations

**File Type Classification:**
- Problem: No way to distinguish data files from reference documents
- Blocks: Proper data loading without garbage rows

**Project Update/Migration:**
- Problem: No way to update semantic layer or re-import data
- Blocks: Iterative refinement of project configuration

## Test Coverage Gaps

**Semantic Generator:**
- What's not tested: LLM prompt construction, response parsing, error handling
- Files: `mcp_server/semantic_generator.py`
- Risk: Prompt changes or API failures go undetected
- Priority: High

**Analysis Templates:**
- What's not tested: SQL generation for retention, funnel, period-over-period
- Files: `mcp_server/analysis_templates.py`
- Risk: SQL syntax errors or incorrect analysis results
- Priority: High

**Chart Renderer:**
- What's not tested: ECharts option generation, chart type suggestion
- Files: `mcp_server/chart_renderer.py`
- Risk: Malformed chart configs
- Priority: Medium

---

*Concerns audit: 2026-04-30*
