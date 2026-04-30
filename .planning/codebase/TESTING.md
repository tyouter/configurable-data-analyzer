# Testing Patterns

**Analysis Date:** 2026-04-30

## Test Framework

**Runner:**
- No test framework configured
- `test_project_system.py` uses bare `assert` statements (no pytest/unittest)

**Assertion Library:**
- Built-in `assert` only

**Run Commands:**
```bash
python mcp_server/test_project_system.py    # Run basic test
# No pytest, no coverage, no watch mode
```

## Test File Organization

**Location:**
- Single file: `mcp_server/test_project_system.py`
- Co-located with source (same directory as `server.py`)

**Naming:**
- `test_project_system.py` — only test file

**Structure:**
```
mcp_server/
├── test_project_system.py     # Only test file
├── server.py                  # Main server (no tests)
├── project_model.py           # No tests
├── semantic_generator.py      # No tests
└── ...                        # No tests
```

## Test Structure

**Suite Organization:**
- Single function-based test file
- No test classes, no fixtures

**Patterns:**
- Direct function calls with `assert`
- No setup/teardown
- No mocking

## Mocking

**Framework:** None

**What to Mock:**
- DeepSeek API calls (for semantic generator tests)
- File system operations (for project CRUD tests)
- DuckDB queries (for data layer tests)

**What NOT to Mock:**
- Currently nothing is mocked at all

## Fixtures and Factories

**Test Data:**
- None — tests likely depend on `projects/rednote/` existing

**Location:**
- No fixture directory

## Coverage

**Requirements:** None enforced

**View Coverage:**
- No coverage tool configured

## Test Types

**Unit Tests:**
- Minimal — only `test_project_system.py` exists
- No unit tests for: `semantic_generator.py`, `analysis_templates.py`, `chart_renderer.py`, `dashboard_store.py`

**Integration Tests:**
- `test_project_system.py` appears to test basic project creation flow
- No integration tests for MCP tool chain

**E2E Tests:**
- Not used

## Common Patterns

**Async Testing:**
- Not applicable (synchronous codebase)

**Error Testing:**
- Not present

---

*Testing analysis: 2026-04-30*
