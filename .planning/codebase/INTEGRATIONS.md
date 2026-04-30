# External Integrations

**Analysis Date:** 2026-04-30

## APIs & External Services

**LLM API:**
- DeepSeek API — Semantic layer generation, query interpretation
  - SDK/Client: `requests` library (raw HTTP)
  - Auth: `DEEPSEEK_API_KEY` env var
  - Base URL: `DEEPSEEK_BASE_URL` env var (default: `https://api.deepseek.com`)
  - Model: `BI_MODEL` env var (default: `deepseek-chat`, current: `deepseek-v4-pro`)

## Data Storage

**Databases:**
- DuckDB (embedded, per-project)
  - Connection: File-based (`projects/{project_id}/{project_id}.duckdb`)
  - Client: `duckdb` Python package (direct API)
  - Schema: Auto-generated from imported data files

**File Storage:**
- Local filesystem only
  - Projects: `projects/{project_id}/` directory
  - Data files: Copied into `projects/{project_id}/data/`
  - Dashboards: `projects/{project_id}/dashboards/*.json`
  - Semantic layer: Embedded in `projects/{project_id}/project.yaml`

**Caching:**
- None — No caching layer implemented

## Authentication & Identity

**Auth Provider:**
- None (internal tool)
  - MCP tools have no authentication
  - Project access is filesystem-based

## Monitoring & Observability

**Error Tracking:**
- None — No Sentry, no error tracking service

**Logs:**
- stdout/stderr only (MCP stdio transport)
- No structured logging framework

## CI/CD & Deployment

**Hosting:**
- Docker (Hermes Agent gateway)
- Local development (Claude Desktop, CLI)

**CI Pipeline:**
- None — No CI/CD configured

## Environment Configuration

**Required env vars:**
- `DEEPSEEK_API_KEY` — LLM authentication (CRITICAL: currently missing in Docker)
- `DEEPSEEK_BASE_URL` — LLM endpoint (optional, has default)
- `BI_MODEL` — Model selection (optional, has default)

**Secrets location:**
- `.env` file (local development)
- Docker environment variables (production)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-04-30*
