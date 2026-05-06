# -*- coding: utf-8 -*-
"""
ChatBI CLI — Command-line interface for project management and queries.

Usage:
  python mcp_server/cli.py create <name> <data_file> [--type TYPE] [--no-llm]
  python mcp_server/cli.py list
  python mcp_server/cli.py switch <project_id>
  python mcp_server/cli.py info [project_id]
  python mcp_server/cli.py delete <project_id>
  python mcp_server/cli.py query <metric> [--dims dim1,dim2] [--filters field=val] [--limit N]
  python mcp_server/cli.py sql <sql_statement>
  python mcp_server/cli.py context [section]
  python mcp_server/cli.py dashboard-list
  python mcp_server/cli.py dashboard-create <name>
  python mcp_server/cli.py dashboard-save-chart -d <dashboard> -t <title> [-c bar|line|pie|table] <sql>
  python mcp_server/cli.py dashboard-export -d <dashboard> [--theme ggplot2_minimal|ggplot2_dark] [--open]
  python mcp_server/cli.py serve [--transport stdio|sse] [--port PORT]
"""

import argparse
import json
import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.project_model import ProjectSession, PROJECTS_DIR
from mcp_server.semantic_query import validate_raw_sql
from mcp_server.service.project import create_project as svc_create_project
from mcp_server.service.query import (
    require_project,
    build_dynamic_l1_query,
    execute_raw_sql as svc_execute_raw_sql,
)
from mcp_server.service.dashboard import (
    render_chart as svc_render_chart,
)
from mcp_server import dashboard_store


_session = ProjectSession()


def cmd_create(args):
    data_files = args.data_files
    for f in data_files:
        if not os.path.exists(f):
            print(f"ERROR: File not found: {f}")
            return 1

    result = svc_create_project(
        session=_session,
        name=args.name,
        data_files=data_files,
        action="start",
        project_type=args.type or "generic",
        use_llm=not args.no_llm,
    )

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return 1

    if result.get("state") == "ALIGN":
        project_id = result["project_id"]
        audit = result.get("audit_report", {})
        summary = audit.get("summary", {})

        print(f"\n  Project pre-analysis complete!")
        print(f"  ID:       {project_id}")
        print(f"  Name:     {args.name}")
        print(f"  Raw files:  {summary.get('raw_files', 0)}")
        print(f"  Ref files:  {summary.get('ref_files', 0)}")
        print(f"  Total rows: {summary.get('total_rows', 0)}")
        print(f"\n  File classifications:")
        for fc in audit.get("file_classifications", []):
            print(f"    {fc['filename']}: {fc['category']} (confidence: {fc.get('confidence', 0):.0%})")
        print(f"\n  Auto-building project...")

        confirm_result = svc_create_project(
            session=_session,
            action="confirm",
            project_id=project_id,
        )

        if "error" in confirm_result:
            print(f"  ERROR in confirm: {confirm_result['error']}")
            return 1

        build_result = svc_create_project(
            session=_session,
            action="build",
            project_id=project_id,
            use_llm=not args.no_llm,
            project_type=args.type,
        )

        if "error" in build_result:
            print(f"  ERROR in build: {build_result['error']}")
            return 1

        if build_result.get("state") == "COMPLETED":
            print(f"\n  Project created successfully!")
            print(f"  ID:       {build_result.get('project_id', project_id)}")
            print(f"  Name:     {build_result.get('name', args.name)}")
            print(f"  Type:     {build_result.get('project_type', '?')}")
            print(f"  Metrics:  {build_result.get('metrics_count', 0)}")
            print(f"  Events:   {build_result.get('events_count', 0)}")
        else:
            print(f"  Build result: {json.dumps(build_result, indent=2, default=str)}")
    else:
        print(f"  Result: {json.dumps(result, indent=2, default=str)}")

    return 0


def cmd_list(args):
    projects = _session.store.list_projects()
    if not projects:
        print("  No projects found. Use 'create' to add one.")
        return 0

    current = _session.get_current_project()
    current_id = current.id if current else None

    print(f"  {'*':1} {'ID':<15} {'Name':<30} {'Type':<20} {'Files':>6}")
    print(f"  {'─'*1} {'─'*15} {'─'*30} {'─'*20} {'─'*6}")
    for p in projects:
        marker = "→" if p["id"] == current_id else " "
        print(f"  {marker} {p['id']:<15} {p['name']:<30} {p.get('project_type', '?'):<20} {p.get('data_files_count', 0):>6}")
    return 0


def cmd_switch(args):
    project = _session.store.get_project(args.project_id)
    if not project:
        print(f"  ERROR: Project '{args.project_id}' not found")
        return 1
    _session.switch_project(args.project_id)
    print(f"  Switched to project: {project.name} ({project.id})")
    return 0


def cmd_info(args):
    project_id = args.project_id
    if project_id:
        project = _session.store.get_project(project_id)
    else:
        project = _session.get_current_project()

    if not project:
        print("  No active project. Use 'switch' or provide project_id.")
        return 1

    dm = _session.get_dm(project.id)
    semantic = project.get_full_semantic_layer(PROJECTS_DIR) or {}

    print(f"\n  Project: {project.name}")
    print(f"  ID:      {project.id}")
    print(f"  Type:    {project.project_type}")
    print(f"  Created: {project.created_at}")
    print(f"  Updated: {project.updated_at}")
    print(f"  Rows:    {dm.meta.get('total_rows', 0) if dm else 'N/A'}")
    print(f"  Columns: {dm.meta.get('total_columns', 0) if dm else 'N/A'}")

    metrics = semantic.get("metrics", {})
    if metrics:
        print(f"\n  Metrics ({len(metrics)}):")
        for name, defn in metrics.items():
            print(f"    {name:<25} {defn.get('business_name', '')}")

    events = semantic.get("event_definitions", {})
    if events:
        print(f"\n  Events ({len(events)}):")
        for name, defn in list(events.items())[:10]:
            print(f"    {name:<40} {defn.get('business_name', '')}")
        if len(events) > 10:
            print(f"    ... and {len(events) - 10} more")

    return 0


def cmd_delete(args):
    project = _session.store.get_project(args.project_id)
    if not project:
        print(f"  ERROR: Project '{args.project_id}' not found")
        return 1

    if not args.force:
        confirm = input(f"  Delete project '{project.name}' ({project.id})? [y/N] ")
        if confirm.lower() != "y":
            print("  Cancelled.")
            return 0

    _session.store.delete_project(args.project_id)
    print(f"  Deleted project: {project.name} ({project.id})")
    return 0


def cmd_query(args):
    try:
        project, dm = require_project(_session)
    except ValueError as e:
        print(f"  ERROR: {e}")
        return 1

    semantic = project.get_full_semantic_layer(PROJECTS_DIR)

    dimensions = args.dims.split(",") if args.dims else []
    filters = []
    if args.filters:
        for f in args.filters:
            if "=" in f:
                field, value = f.split("=", 1)
                filters.append({"field": field, "op": "eq", "value": value})

    sql, err = build_dynamic_l1_query(
        semantic_layer=semantic,
        metric=args.metric,
        dimensions=dimensions,
        filters=filters,
        limit=args.limit,
    )

    if err:
        print(f"  ERROR: {err}")
        return 1

    print(f"\n  SQL:\n  {sql}\n")

    data = dm.execute(sql)
    if not data:
        print("  (no results)")
        return 0

    cols = list(data[0].keys())
    col_widths = {c: max(len(str(c)), max(len(str(row.get(c, ""))) for row in data[:20])) for c in cols}

    header = " | ".join(c.ljust(col_widths[c]) for c in cols)
    print(f"  {header}")
    print(f"  {'─' * len(header)}")

    for row in data[:50]:
        line = " | ".join(str(row.get(c, "")).ljust(col_widths[c]) for c in cols)
        print(f"  {line}")

    if len(data) > 50:
        print(f"  ... {len(data) - 50} more rows")

    print(f"\n  Total: {len(data)} rows")
    return 0


def cmd_sql(args):
    result = svc_execute_raw_sql(session=_session, sql=args.sql)

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return 1

    data = result.get("data", [])
    print(f"\n  SQL:\n  {result.get('sql', args.sql)}\n")

    if not data:
        print("  (no results)")
        return 0

    cols = list(data[0].keys())
    for row in data[:50]:
        print("  " + " | ".join(str(row.get(c, "")) for c in cols))

    if len(data) > 50:
        print(f"  ... {len(data) - 50} more rows")

    print(f"\n  Total: {len(data)} rows")
    return 0


def cmd_context(args):
    project = _session.get_current_project()
    if not project:
        print("  No active project. Use 'switch' first.")
        return 1

    semantic = project.get_full_semantic_layer(PROJECTS_DIR) or {}
    section = args.section or "all"

    if section in ("metrics", "all"):
        metrics = semantic.get("metrics", {})
        print(f"\n  Metrics ({len(metrics)}):")
        for name, defn in metrics.items():
            print(f"    {name:<25} {defn.get('business_name', '')} — {defn.get('sql', '')}")

    if section in ("dimensions", "all"):
        columns = semantic.get("columns", {})
        dims = {k: v for k, v in columns.items() if v.get("role") == "dimension"}
        print(f"\n  Dimensions ({len(dims)}):")
        for name, defn in dims.items():
            print(f"    {name:<25} {defn.get('business_name', '')} ({defn.get('type', '')})")

    if section in ("events", "all"):
        events = semantic.get("event_definitions", {})
        print(f"\n  Events ({len(events)}):")
        for name, defn in events.items():
            print(f"    {name:<40} {defn.get('business_name', '')}")

    return 0


def cmd_dashboard_list(args):
    project = _session.get_current_project()
    if not project:
        print("  ERROR: No active project. Use 'switch' or 'create' first.")
        return 1
    dashboards = dashboard_store.list_dashboards(PROJECTS_DIR, project.id)
    if not dashboards:
        print("  No dashboards found. Use 'dashboard-create' to add one.")
        return 0
    print(f"  {'ID':<15} {'Name':<30} {'Charts':>7} {'Updated':<20}")
    print(f"  {'─'*15} {'─'*30} {'─'*7} {'─'*20}")
    for d in dashboards:
        print(f"  {d['id']:<15} {d['name']:<30} {d['charts_count']:>7} {d.get('updated_at', '')[:19]:<20}")
    return 0


def cmd_dashboard_create(args):
    project = _session.get_current_project()
    if not project:
        print("  ERROR: No active project. Use 'switch' or 'create' first.")
        return 1
    result = dashboard_store.create_dashboard(PROJECTS_DIR, project.id, args.name)
    if result.get("exists"):
        print(f"  Dashboard already exists: {result['id']} ({args.name})")
    else:
        print(f"  Dashboard created: {result['id']} ({args.name})")
    return 0


def cmd_dashboard_save_chart(args):
    project = _session.get_current_project()
    if not project:
        print("  ERROR: No active project. Use 'switch' or 'create' first.")
        return 1
    dm = _session.get_current_dm()
    if not dm:
        print("  ERROR: Project data not loaded. Try 'switch' again.")
        return 1

    sql = args.sql
    try:
        sql = validate_raw_sql(sql)
    except ValueError as e:
        print(f"  ERROR: {e}")
        return 1

    data = dm.execute(sql)
    if not data:
        print("  (no results — chart not saved)")
        return 0

    from mcp_server.chart_renderer import build_echarts_option
    chart_option = build_echarts_option(data=data, chart_type=args.chart_type, title=args.title)
    chart_record = {
        "title": args.title,
        "chart_type": args.chart_type,
        "chart_option": chart_option,
        "sql": args.sql,
    }
    result = dashboard_store.save_chart(PROJECTS_DIR, project.id, args.dashboard, chart_record)
    print(f"  Chart saved: {result.get('chart_id', '?')} → dashboard '{args.dashboard}'")
    return 0


def cmd_dashboard_export(args):
    project = _session.get_current_project()
    if not project:
        print("  ERROR: No active project. Use 'switch' or 'create' first.")
        return 1

    from mcp_server.dashboard_html import export_dashboard_html
    from mcp_server.themes import list_themes

    theme = args.theme or "ggplot2_minimal"
    available = list_themes()
    if theme not in available:
        print(f"  ERROR: Unknown theme '{theme}'. Available: {available}")
        return 1

    try:
        html_path = export_dashboard_html(
            projects_dir=PROJECTS_DIR,
            project_id=project.id,
            dashboard_name=args.dashboard,
            theme=theme,
        )
        print(f"  Dashboard exported: {html_path}")
        if args.open:
            import webbrowser
            webbrowser.open(f"file://{os.path.abspath(html_path)}")
            print("  Opened in browser.")
        return 0
    except ValueError as e:
        print(f"  ERROR: {e}")
        return 1


def cmd_serve(args):
    from mcp_server.server import mcp
    mcp.run(transport=args.transport)
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="chatbi",
        description="ChatBI CLI — Project-agnostic data analysis platform",
    )
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Create a new project from data files")
    p_create.add_argument("name", help="Project name")
    p_create.add_argument("data_files", nargs="+", help="Data file paths (xlsx/csv/parquet)")
    p_create.add_argument("--type", "-t", help="Project type (behavior_analysis/business_report/time_series/generic)")
    p_create.add_argument("--no-llm", action="store_true", help="Skip LLM-assisted semantic generation")

    p_list = sub.add_parser("list", help="List all projects")

    p_switch = sub.add_parser("switch", help="Switch active project")
    p_switch.add_argument("project_id", help="Project ID to switch to")

    p_info = sub.add_parser("info", help="Show project details")
    p_info.add_argument("project_id", nargs="?", help="Project ID (default: current)")

    p_delete = sub.add_parser("delete", help="Delete a project")
    p_delete.add_argument("project_id", help="Project ID to delete")
    p_delete.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    p_query = sub.add_parser("query", help="Execute L1 structured query")
    p_query.add_argument("metric", help="Metric name from semantic layer")
    p_query.add_argument("--dims", "-d", help="Comma-separated dimensions")
    p_query.add_argument("--filters", "-f", nargs="*", help="Filters as field=value")
    p_query.add_argument("--limit", "-l", type=int, default=50, help="Row limit")

    p_sql = sub.add_parser("sql", help="Execute raw SQL query")
    p_sql.add_argument("sql", help="SQL statement")

    p_context = sub.add_parser("context", help="Show semantic layer context")
    p_context.add_argument("section", nargs="?", help="Section: metrics/dimensions/events/all")

    p_dash_list = sub.add_parser("dashboard-list", help="List dashboards for current project")
    p_dash_create = sub.add_parser("dashboard-create", help="Create a new dashboard")
    p_dash_create.add_argument("name", help="Dashboard name")
    p_dash_save = sub.add_parser("dashboard-save-chart", help="Execute SQL and save chart to dashboard")
    p_dash_save.add_argument("--dashboard", "-d", required=True, help="Dashboard name")
    p_dash_save.add_argument("--title", "-t", required=True, help="Chart title")
    p_dash_save.add_argument("--chart-type", "-c", default="bar", help="Chart type: bar/line/pie/table")
    p_dash_save.add_argument("sql", help="SQL query")

    p_dash_export = sub.add_parser("dashboard-export", help="Export dashboard to self-contained HTML")
    p_dash_export.add_argument("-d", "--dashboard", required=True, help="Dashboard name")
    p_dash_export.add_argument("--theme", "-t", default="ggplot2_minimal", help="Theme: ggplot2_minimal / ggplot2_dark")
    p_dash_export.add_argument("--open", action="store_true", help="Open in browser after export")

    p_serve = sub.add_parser("serve", help="Start MCP Server")
    p_serve.add_argument("--transport", "-t", default="stdio", choices=["stdio", "sse"])
    p_serve.add_argument("--port", "-p", type=int, default=8000)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "create": cmd_create,
        "list": cmd_list,
        "switch": cmd_switch,
        "info": cmd_info,
        "delete": cmd_delete,
        "query": cmd_query,
        "sql": cmd_sql,
        "context": cmd_context,
        "dashboard-list": cmd_dashboard_list,
        "dashboard-create": cmd_dashboard_create,
        "dashboard-save-chart": cmd_dashboard_save_chart,
        "dashboard-export": cmd_dashboard_export,
        "serve": cmd_serve,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
