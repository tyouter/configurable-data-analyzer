# Coding Conventions

**Analysis Date:** 2026-04-30

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules (e.g., `project_model.py`, `chart_renderer.py`)

**Functions:**
- `snake_case` for all functions (e.g., `create_project()`, `build_retention_sql()`)
- Private helper prefix `_` (e.g., `_require_project()`, `_serialize_data()`)

**Variables:**
- `snake_case` for all variables (e.g., `total_rows`, `project_id`)
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `PROJECTS_DIR`, `DEEPSEEK_API_KEY`)

**Types:**
- `PascalCase` for dataclasses (e.g., `ColumnDef`, `MetricDef`, `RetentionParams`)
- `PascalCase` for service classes (e.g., `ProjectStore`, `ProjectDataManager`, `ProjectSession`)

## Code Style

**Formatting:**
- No formatter configured (no black, no autopep8)
- 4-space indentation, UTF-8 encoding
- `# -*- coding: utf-8 -*-` header on all files

**Linting:**
- No linter configured (no ruff, no flake8)
- No type checking configured (no mypy, no pyright)

## Import Organization

**Order:**
1. Standard library (`os`, `sys`, `json`, `argparse`, etc.)
2. Third-party (`pandas`, `duckdb`, `yaml`, `requests`)
3. Local modules (`from mcp_server.xxx import ...`)

**Path handling:**
- `_PROJECT_ROOT` computed from `__file__` and added to `sys.path` at module level

## Error Handling

**Patterns:**
- Tool functions return `{"error": "message"}` dicts on failure
- Service functions raise `ValueError` with descriptive messages
- No custom exception classes — uses built-in exceptions only
- No error hierarchy or error codes

## Logging

**Framework:** None — uses print() and stdout

**Patterns:**
- `print()` for informational output in CLI mode
- MCP framework handles tool response serialization
- No structured logging, no log levels

## Comments

**When to Comment:**
- Module-level docstrings on all files (purpose + usage)
- Inline comments for complex logic (e.g., SQL building)
- Chinese comments acceptable (project is Chinese-oriented)

**Docstrings:**
- Present on all modules and major functions
- Format: Plain text, not Google/Numpy style
- Include usage examples for public APIs

## Function Design

**Size:** Varies widely — `server.py` has functions from 5 to 80+ lines

**Parameters:** Mix of positional and keyword arguments; `Optional[]` for optional params

**Return Values:** Dicts (tool responses), dataclass instances (internal), or raises exceptions

## Module Design

**Exports:** Each module exports classes/functions at module level

**Barrel Files:** `__init__.py` is empty — no barrel exports

---

*Convention analysis: 2026-04-30*
