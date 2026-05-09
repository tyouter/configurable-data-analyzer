# ChatBI MCP Server — Engineering Conventions

> **Runtime**: Python 3.10+, DuckDB, FastMCP, ECharts
> **Test framework**: pytest (characterization tests for golden master)
> **Git strategy**: refactor/phase-N branches → master

## Downstream Sync Checklist

When MCP tools change (add/rename/delete/modify signature), must sync:

| Source Change | Files to Sync |
|--------------|---------------|
| MCP tool added/removed/renamed | `skills/chatbi/SKILL.md`, `README.md` tool table, `.trae/skills/data-analysis/SKILL.md` |
| Tool parameter signature changed | Same as above |
| Project model changed | `CLAUDE.md` (architecture section) |
| Dependency changed | `pyproject.toml`, `requirements.txt` |
| Version bumped | `pyproject.toml`, `mcp_server/__init__.py` |

## Test Discipline

- Red-green-refactor micro-cycle within each Phase
- Characterization tests lock existing behavior before refactoring
- Golden reference: `tests/.mcp_contract_snapshot.json`
- Target: ≥80% coverage at Phase 5

## Git Strategy

- Branch: `refactor/phase-N` per Phase, merge to `master` on completion
- Commit granularity: one logical change per commit
- Commit format: `[Phase N] brief description`
- Rollback: `git revert`, never force-push to master

## Architecture Rules

- MCP never reads or interprets reference documents. Agent handles all understanding.
- Config injection: each project has independent DuckDB + semantic_config.json + dashboard_spec.json
- No abstraction layers (no QueryExecutor/LLMClient interfaces) — use real data for tests
- Rednote-BI-Analysis-2 is the canonical test project

## Decision Log

See `.deepseek/architecture-decisions.md` for rationale behind key architectural choices.
