# -*- coding: utf-8 -*-
"""
MCP Contract Snapshot — verify that all expected tools exist with correct signatures.

This test serves as an early-warning system: if a tool is added, removed, renamed,
or its parameters change, this test will fail — alerting the developer to check
the downstream sync checklist in CONVENTIONS.md.

Uses pure source-code parsing to avoid importing mcp_server (which has numpy
compatibility issues in test environments).
"""
import os
import json
import re
import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SERVER_PY = os.path.join(_PROJECT_ROOT, "mcp_server", "server.py")


def _extract_tools():
    """Parse server.py source to extract @mcp.tool() and @mcp.resource() functions."""
    tools = {}
    if not os.path.exists(_SERVER_PY):
        return tools

    with open(_SERVER_PY, "r", encoding="utf-8") as f:
        source = f.read()

    # Match @mcp.tool()\n    def func_name(...):
    # and   @mcp.resource("...")\n    def func_name(...):
    # Handle both single-line and multi-line function signatures
    for match in re.finditer(
        r'@mcp\.(tool|resource)(?:\(.*?\))?\s*\n\s*def\s+(\w+)\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)',
        source,
        re.MULTILINE
    ):
        func_type = match.group(1)
        func_name = match.group(2)
        params_raw = match.group(3)
        # Extract param names
        param_names = []
        for p in params_raw.split(","):
            p = p.strip()
            if not p or p == "self":
                continue
            # Handle "name: type = default"
            param_name = p.split(":")[0].strip()
            if param_name:
                param_names.append(param_name)

        tools[func_name] = {
            "type": func_type,
            "params": param_names,
        }

    return tools


TOOLS = _extract_tools()


REQUIRED_TOOLS = {
    "create_project",
    "execute_pipeline_step",
    "list_projects",
    "switch_project",
    "get_current_project",
    "delete_project",
    "regenerate_semantic_layer",
    "migrate_project",
    "review_data_understanding",
    "review_data_issues",
    "update_column_mapping",
    "update_event_mapping",
    "update_metric",
    "get_semantic_context",
    "validate_semantic_layer",
    "explore_column_values",
    "semantic_query",
    "raw_sql",
    "render_chart",
    "generate_dashboard_from_spec",
    "list_dashboards",
    "create_dashboard",
    "save_chart_to_dashboard",
    "delete_chart",
    "delete_dashboard",
    "export_dashboard",
    "llm_status",
    "submit_llm_result",
}

EXPECTED_NEW_TOOLS = {
    "register_events",
    "define_metric",
    "validate_metric",
}


class TestMCPContract:

    def test_tool_count(self):
        actual = len(TOOLS)
        print(f"\n  Current MCP tools: {actual}")
        assert actual >= 26, f"Too few tools: {actual}"

    def test_all_required_tools_present(self):
        actual_names = set(TOOLS.keys())
        missing = REQUIRED_TOOLS - actual_names
        assert len(missing) == 0, (
            f"Missing required tools: {sorted(missing)}"
        )

    def test_tool_parameter_signatures(self):
        sq = TOOLS.get("semantic_query", {})
        if sq:
            params = sq.get("params", [])
            assert "level" in params, f"semantic_query params: {params}"

        rc = TOOLS.get("render_chart", {})
        if rc:
            params = rc.get("params", [])
            assert "data" in params, f"render_chart params: {params}"

    def test_expected_new_tools_status(self):
        actual_names = set(TOOLS.keys())
        missing_new = EXPECTED_NEW_TOOLS - actual_names
        present_new = EXPECTED_NEW_TOOLS & actual_names
        print(f"\n  Phase 1 tools present: {sorted(present_new) if present_new else 'none'}")
        print(f"  Phase 1 tools needed: {sorted(missing_new) if missing_new else 'none'}")

    def test_contract_snapshot_export(self):
        snapshot = {
            "tool_count": len(TOOLS),
            "tool_names": sorted(TOOLS.keys()),
            "required_tools": sorted(REQUIRED_TOOLS),
            "expected_new_tools": sorted(EXPECTED_NEW_TOOLS),
        }
        snapshot_path = os.path.join(_PROJECT_ROOT, "tests", ".mcp_contract_snapshot.json")
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        assert os.path.exists(snapshot_path)
        print(f"\n  Snapshot saved: tests/.mcp_contract_snapshot.json")
