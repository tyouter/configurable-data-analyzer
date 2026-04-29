# -*- coding: utf-8 -*-
"""
ChatBI MCP Server — Project-agnostic data analysis platform.

Exposes data analysis capabilities as MCP tools with multi-project support:
  - Project management: create, list, switch, delete projects
  - semantic_query: L1 simple + L2 analysis templates (project-aware)
  - raw_sql: L3 fallback with safety limits
  - render_chart: ECharts chart generation
  - get_semantic_context: Expose project semantic layer metadata
  - dashboard CRUD: Create, list, save charts, delete

Architecture:
  User (multi-channel)
    ↓
  Hermes Agent (Docker/Linux, ReAct loop)
    ↓ MCP Protocol
  ChatBI MCP Server (project-agnostic)
    ↓
  Project { data files + semantic layer + DuckDB }

Run:
  python mcp_server/server.py              # stdio transport (default)
  python mcp_server/server.py --transport sse  # SSE transport
"""

import os
import sys
import json
import argparse
from typing import Optional

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP

from mcp_server.project_model import (
    Project,
    ProjectStore,
    ProjectSession,
    ProjectDataManager,
    PROJECTS_DIR,
)
from mcp_server.semantic_generator import (
    generate_semantic_layer,
    detect_project_type,
    TYPE_TEMPLATES,
)
from mcp_server.semantic_query import (
    validate_raw_sql,
)
from mcp_server.analysis_templates import ANALYSIS_TEMPLATES
from mcp_server.chart_renderer import build_echarts_option, suggest_chart_type
from mcp_server import dashboard_store

mcp = FastMCP(
    "ChatBI",
    instructions="""ChatBI MCP Server — 项目无关的数据分析平台。

支持多项目管理，每个项目拥有独立的数据文件、语义层和DuckDB实例。

使用流程：
1. create_project — 导入数据文件，自动生成语义层
2. switch_project — 切换到目标项目
3. get_semantic_context — 查看当前项目的语义层（指标、维度、事件定义）
4. semantic_query / raw_sql — 执行数据分析查询
5. render_chart — 生成图表
6. Dashboard CRUD — 管理图表看板

三级查询协议：
- L1 简单查询：通过 metric + dimensions + filters 结构化查询
- L2 分析模板：封装留存、漏斗、同环比等分析模式
- L3 原始SQL：只读SQL查询兜底
""",
)

_session = ProjectSession()


def _require_project() -> tuple[Project, ProjectDataManager]:
    project = _session.get_current_project()
    if not project:
        raise ValueError(
            "No active project. Call switch_project(project_id) first, "
            "or create_project(name, data_files) to create one."
        )
    dm = _session.get_current_dm()
    if not dm:
        raise ValueError("Project data manager not loaded. Try switch_project again.")
    return project, dm


def _serialize_data(data: list[dict]) -> list[dict]:
    result = []
    for row in data:
        serialized = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                serialized[k] = v.isoformat()
            elif hasattr(v, "item"):
                serialized[k] = v.item()
            else:
                serialized[k] = v
        result.append(serialized)
    return result


def _build_dynamic_l1_query(
    semantic_layer: dict,
    metric: str,
    dimensions: list[str],
    filters: list[dict],
    order_by: Optional[str] = None,
    limit: int = 500,
) -> tuple[str, Optional[str]]:
    """
    Build L1 query SQL from project's semantic layer.
    Returns (sql, error_message). If error, sql is empty.
    """
    table_name = semantic_layer.get("table_name", "events")
    metrics = semantic_layer.get("metrics", {})
    columns = semantic_layer.get("columns", {})

    metric_def = metrics.get(metric)
    if not metric_def:
        available = sorted(metrics.keys())
        return "", f"Unknown metric: {metric}. Available: {available}"

    metric_sql = metric_def.get("sql", "")

    for dim in dimensions:
        if dim not in columns and dim not in [c for c in columns.keys()]:
            available = sorted(columns.keys())
            return "", f"Invalid dimension: {dim}. Available: {available}"

    select_parts = [f"{dim}" for dim in dimensions] + [f"{metric_sql} AS {metric}"]
    select_clause = ", ".join(select_parts)

    group_clause = ", ".join(dimensions)

    where_parts = []
    for f in filters:
        field = f.get("field", "")
        op = f.get("op", "eq")
        value = f.get("value")

        if field not in columns:
            return "", f"Filter field '{field}' not found in schema"

        if op == "eq":
            where_parts.append(f"{field} = '{value}'")
        elif op == "neq":
            where_parts.append(f"{field} != '{value}'")
        elif op == "gt":
            where_parts.append(f"{field} > '{value}'")
        elif op == "gte":
            where_parts.append(f"{field} >= '{value}'")
        elif op == "lt":
            where_parts.append(f"{field} < '{value}'")
        elif op == "lte":
            where_parts.append(f"{field} <= '{value}'")
        elif op == "like":
            where_parts.append(f"{field} LIKE '%{value}%'")
        elif op == "not_like":
            where_parts.append(f"{field} NOT LIKE '%{value}%'")
        elif op == "in":
            if isinstance(value, list):
                vals = ", ".join(f"'{v}'" for v in value)
                where_parts.append(f"{field} IN ({vals})")
        elif op == "not_in":
            if isinstance(value, list):
                vals = ", ".join(f"'{v}'" for v in value)
                where_parts.append(f"{field} NOT IN ({vals})")
        elif op == "is_null":
            where_parts.append(f"{field} IS NULL")
        elif op == "is_not_null":
            where_parts.append(f"{field} IS NOT NULL")

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    order_clause = ""
    if order_by:
        order_clause = f"ORDER BY {order_by}"
    elif dimensions:
        order_clause = f"ORDER BY {dimensions[0]}"

    limit_clause = f"LIMIT {min(limit, 2000)}"

    sql = f"SELECT {select_clause}\nFROM {table_name}\n{where_clause}\nGROUP BY {group_clause}\n{order_clause}\n{limit_clause}"
    import re
    return re.sub(r'\n\s+', '\n', sql), None


def _build_dynamic_l2_query(
    semantic_layer: dict,
    analysis_type: str,
    params: dict,
) -> tuple[str, Optional[str]]:
    """
    Build L2 analysis template SQL from project's semantic layer.
    Returns (sql, error_message).
    """
    if analysis_type not in ANALYSIS_TEMPLATES:
        available = sorted(ANALYSIS_TEMPLATES.keys())
        return "", f"Unknown analysis_type: {analysis_type}. Available: {available}"

    template = ANALYSIS_TEMPLATES[analysis_type]
    builder = template["builder"]
    param_class = template["param_class"]

    try:
        typed_params = param_class(**params)
    except Exception as e:
        return "", f"Invalid params for {analysis_type}: {e}"

    try:
        table_name = semantic_layer.get("table_name", "events")
        sql = builder(typed_params, table=table_name)
        return sql, None
    except Exception as e:
        return "", f"Failed to build {analysis_type} SQL: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Tools: Project Management
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_project(
    name: str,
    data_files: list[str],
    project_type: Optional[str] = None,
    use_llm: bool = True,
) -> dict:
    """
    创建新项目：导入数据文件，自动生成语义层。

    流程：
    1. 复制数据文件到项目目录
    2. 加载数据到DuckDB
    3. 自动检测项目类型（如未指定）
    4. 生成语义层（LLM辅助或规则推导）
    5. 保存项目配置

    Args:
        name: 项目名称，如 "小红书车载应用分析"
        data_files: 数据文件路径列表，支持 xlsx/csv/parquet
        project_type: 项目类型 behavior_analysis/business_report/time_series/generic（可选，自动检测）
        use_llm: 是否使用LLM辅助生成语义层（需要DEEPSEEK_API_KEY，默认True）
    """
    try:
        project = _session.store.create_project(
            name=name,
            data_files=data_files,
            project_type=project_type or "generic",
        )

        dm = _session.get_dm(project.id)

        if not project_type:
            detected = detect_project_type(dm)
            project.project_type = detected

        semantic = generate_semantic_layer(
            dm,
            project_type=project.project_type,
            use_llm=use_llm,
        )
        project.semantic_layer = semantic

        _session.store.save_project(project)

        _session.switch_project(project.id)

        return {
            "project_id": project.id,
            "name": project.name,
            "project_type": project.project_type,
            "data_files": project.data_source.get("files", []),
            "total_rows": dm.meta.get("total_rows", 0),
            "total_columns": dm.meta.get("total_columns", 0),
            "metrics_count": len(semantic.get("metrics", {})),
            "events_count": len(semantic.get("event_definitions", {})),
            "semantic_source": "llm" if (use_llm and os.environ.get("DEEPSEEK_API_KEY")) else "rule_based",
        }
    except Exception as e:
        return {"error": f"Failed to create project: {str(e)}"}


@mcp.tool()
def list_projects() -> dict:
    """列出所有已创建的项目及其基本信息。"""
    projects = _session.store.list_projects()
    current_id = _session.current_project_id
    for p in projects:
        p["is_current"] = (p["id"] == current_id)
    return {"projects": projects, "current_project_id": current_id}


@mcp.tool()
def switch_project(project_id: str) -> dict:
    """
    切换当前活跃项目。后续所有查询操作将针对此项目。

    Args:
        project_id: 项目ID
    """
    try:
        project = _session.switch_project(project_id)
        dm = _session.get_current_dm()
        return {
            "project_id": project.id,
            "name": project.name,
            "project_type": project.project_type,
            "total_rows": dm.meta.get("total_rows", 0) if dm else 0,
            "metrics_count": len(project.semantic_layer.get("metrics", {})),
        }
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
def get_current_project() -> dict:
    """获取当前活跃项目的详细信息。"""
    project = _session.get_current_project()
    if not project:
        return {"error": "No active project. Use switch_project() or create_project() first."}

    dm = _session.get_current_dm()
    return {
        "project_id": project.id,
        "name": project.name,
        "project_type": project.project_type,
        "data_source": project.data_source,
        "total_rows": dm.meta.get("total_rows", 0) if dm else 0,
        "total_columns": dm.meta.get("total_columns", 0) if dm else 0,
        "metrics_count": len(project.semantic_layer.get("metrics", {})),
        "events_count": len(project.semantic_layer.get("event_definitions", {})),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


@mcp.tool()
def delete_project(project_id: str) -> dict:
    """
    删除项目及其所有数据（DuckDB文件、数据副本、配置）。

    Args:
        project_id: 要删除的项目ID
    """
    _session.unload_project(project_id)
    ok = _session.store.delete_project(project_id)
    if not ok:
        return {"error": f"Project not found: {project_id}"}
    return {"ok": True, "deleted_project_id": project_id}


@mcp.tool()
def regenerate_semantic_layer(use_llm: bool = True) -> dict:
    """
    重新生成当前项目的语义层。当数据结构变化或语义层不准确时使用。

    Args:
        use_llm: 是否使用LLM辅助（需要DEEPSEEK_API_KEY，默认True）
    """
    try:
        project, dm = _require_project()
    except ValueError as e:
        return {"error": str(e)}

    try:
        semantic = generate_semantic_layer(
            dm,
            project_type=project.project_type,
            use_llm=use_llm,
        )
        project.semantic_layer = semantic
        _session.store.save_project(project)

        return {
            "project_id": project.id,
            "metrics_count": len(semantic.get("metrics", {})),
            "events_count": len(semantic.get("event_definitions", {})),
            "columns_count": len(semantic.get("columns", {})),
            "semantic_source": "llm" if (use_llm and os.environ.get("DEEPSEEK_API_KEY")) else "rule_based",
        }
    except Exception as e:
        return {"error": f"Failed to regenerate semantic layer: {str(e)}"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool: semantic_query (L1 + L2) — project-aware
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def semantic_query(
    level: str,
    metric: Optional[str] = None,
    dimensions: Optional[list[str]] = None,
    filters: Optional[list[dict]] = None,
    order_by: Optional[str] = None,
    limit: int = 500,
    analysis_type: Optional[str] = None,
    analysis_params: Optional[dict] = None,
) -> dict:
    """
    结构化语义查询，支持L1简单查询和L2分析模板。
    基于当前项目的语义层自动构建SQL。

    L1 简单查询：指定 metric + dimensions + filters，自动生成SQL。
    L2 分析模板：指定 analysis_type + analysis_params，使用预定义分析模式。

    Args:
        level: 查询级别 "L1" 或 "L2"
        metric: L1指标名称（来自当前项目语义层定义）
        dimensions: L1分组维度列表（来自当前项目schema列名）
        filters: L1筛选条件列表，每项 {field, op, value}，op支持 eq/neq/gt/gte/lt/lte/like/not_like/in/not_in/is_null/is_not_null
        order_by: L1排序字段
        limit: 返回行数上限（默认500，最大2000）
        analysis_type: L2分析类型：retention / funnel / period_over_period
        analysis_params: L2分析参数（JSON对象），不同类型参数不同：
            - retention: {anchor_event, return_event, day_offsets?, start_date?, end_date?}
            - funnel: {steps, within_days?, start_date?, end_date?}
            - period_over_period: {metric, dimension, period_type?, start_date?, end_date?}
    """
    try:
        project, dm = _require_project()
    except ValueError as e:
        return {"error": str(e)}

    semantic_layer = project.semantic_layer

    if level == "L1":
        if not metric:
            return {"error": "L1 query requires 'metric' parameter"}
        dimensions = dimensions or []
        filters = filters or []

        sql, err = _build_dynamic_l1_query(
            semantic_layer=semantic_layer,
            metric=metric,
            dimensions=dimensions,
            filters=filters,
            order_by=order_by,
            limit=limit,
        )
        if err:
            return {"error": err}

    elif level == "L2":
        if not analysis_type:
            return {"error": "L2 query requires 'analysis_type' parameter"}
        if not analysis_params:
            return {"error": "L2 query requires 'analysis_params' parameter"}

        sql, err = _build_dynamic_l2_query(
            semantic_layer=semantic_layer,
            analysis_type=analysis_type,
            params=analysis_params,
        )
        if err:
            return {"error": err}

    else:
        return {"error": f"Invalid level: {level}. Must be 'L1' or 'L2'"}

    try:
        data = dm.execute(sql)
        data = _serialize_data(data)

        chart_type = suggest_chart_type(data, f"{metric or ''} {analysis_type or ''}")
        chart_option = build_echarts_option(chart_type, data, metric or analysis_type or "Query Result")

        return {
            "project_id": project.id,
            "sql": sql,
            "data": data,
            "row_count": len(data),
            "chart_type": chart_type,
            "chart_option": chart_option,
        }
    except Exception as e:
        return {
            "project_id": project.id,
            "sql": sql,
            "error": f"SQL execution failed: {str(e)}",
            "data": [],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Tool: raw_sql (L3) — project-aware
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def raw_sql(sql: str, limit: int = 2000) -> dict:
    """
    L3原始SQL查询（只读，带安全限制）。
    仅用于L1/L2无法覆盖的复杂自定义查询。
    查询在当前项目的DuckDB实例上执行。

    安全限制：
    - 仅允许SELECT/WITH...SELECT
    - 禁止INSERT/UPDATE/DELETE/DROP/CREATE等DDL/DML
    - 强制LIMIT上限2000行

    Args:
        sql: SQL查询语句（使用当前项目的表名和列名）
        limit: 返回行数上限（默认2000）
    """
    try:
        project, dm = _require_project()
    except ValueError as e:
        return {"error": str(e)}

    try:
        sql = validate_raw_sql(sql)
    except ValueError as e:
        return {"error": str(e), "data": []}

    try:
        data = dm.execute(sql)
        data = _serialize_data(data)

        chart_type = suggest_chart_type(data)
        chart_option = build_echarts_option(chart_type, data, "Raw SQL Result")

        return {
            "project_id": project.id,
            "sql": sql,
            "data": data,
            "row_count": len(data),
            "chart_type": chart_type,
            "chart_option": chart_option,
        }
    except Exception as e:
        return {
            "project_id": project.id,
            "sql": sql,
            "error": f"SQL execution failed: {str(e)}",
            "data": [],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Tool: render_chart
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def render_chart(
    data: list[dict],
    chart_type: str,
    title: str,
) -> dict:
    """
    根据查询数据生成ECharts图表配置。

    Args:
        data: 查询结果数据（列表的字典）
        chart_type: 图表类型 line/bar/pie/funnel/scatter/table
        title: 图表标题
    """
    if chart_type == "table":
        return {"chart_type": "table", "chart_option": None, "data": data}

    chart_option = build_echarts_option(chart_type, data, title)
    if chart_option is None:
        return {"error": f"Unsupported chart type: {chart_type}"}

    return {
        "chart_type": chart_type,
        "chart_option": chart_option,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Tool: get_semantic_context — project-aware
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_semantic_context(section: Optional[str] = None) -> dict:
    """
    获取当前项目的语义层元数据，包括指标定义、维度列表、事件定义、分析模板等。
    Agent可据此理解数据上下文，构建正确的查询。

    Args:
        section: 可选，指定返回的节：metrics / dimensions / events / analysis_templates / schema / all（默认all）
    """
    try:
        project, dm = _require_project()
    except ValueError as e:
        return {"error": str(e)}

    semantic = project.semantic_layer
    section = section or "all"

    if section == "metrics":
        metrics = []
        for name, info in semantic.get("metrics", {}).items():
            metrics.append({
                "id": name,
                "business_name": info.get("business_name", name),
                "sql": info.get("sql", ""),
                "keywords": info.get("keywords", []),
                "description": info.get("description", ""),
            })
        return {"project_id": project.id, "metrics": metrics}

    elif section == "dimensions":
        dims = []
        for name, info in semantic.get("columns", {}).items():
            dims.append({
                "id": name,
                "business_name": info.get("business_name", name),
                "type": info.get("type", ""),
                "role": info.get("role", "dimension"),
                "description": info.get("description", ""),
            })
        return {"project_id": project.id, "dimensions": dims}

    elif section == "events":
        events = []
        for name, info in semantic.get("event_definitions", {}).items():
            events.append({
                "id": name,
                "business_name": info.get("business_name", name),
                "description": info.get("description", ""),
                "category": info.get("category", ""),
                "aliases": info.get("aliases", []),
            })
        return {"project_id": project.id, "events": events}

    elif section == "analysis_templates":
        templates = []
        for name, info in ANALYSIS_TEMPLATES.items():
            templates.append({
                "id": name,
                "description": info["description"],
                "params_schema": info["params_schema"],
            })
        return {"project_id": project.id, "analysis_templates": templates}

    elif section == "schema":
        schema_info = dm.get_schema_info()
        return {"project_id": project.id, "schema": schema_info}

    elif section == "all":
        metrics = []
        for name, info in semantic.get("metrics", {}).items():
            metrics.append({
                "id": name,
                "business_name": info.get("business_name", name),
                "keywords": info.get("keywords", []),
                "description": info.get("description", ""),
            })

        dims = []
        for name, info in semantic.get("columns", {}).items():
            dims.append({
                "id": name,
                "business_name": info.get("business_name", name),
                "type": info.get("type", ""),
                "role": info.get("role", "dimension"),
            })

        events = []
        for name, info in semantic.get("event_definitions", {}).items():
            events.append({
                "id": name,
                "business_name": info.get("business_name", name),
                "category": info.get("category", ""),
            })

        templates = []
        for name, info in ANALYSIS_TEMPLATES.items():
            templates.append({
                "id": name,
                "description": info["description"],
                "params_schema": info["params_schema"],
            })

        return {
            "project_id": project.id,
            "project_name": project.name,
            "project_type": project.project_type,
            "table": semantic.get("table_name", "events"),
            "data_meta": dm.meta,
            "available_metrics": metrics,
            "available_dimensions": dims,
            "event_definitions": events,
            "analysis_templates": templates,
            "examples": semantic.get("examples", []),
            "rules": semantic.get("rules", []),
        }

    else:
        return {"error": f"Unknown section: {section}. Valid: metrics, dimensions, events, analysis_templates, schema, all"}


# ═══════════════════════════════════════════════════════════════════════════
# Tools: Dashboard CRUD
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_dashboards() -> dict:
    """列出当前项目所有Dashboard及其包含的图表。"""
    project, _ = _require_project()
    dashboards = dashboard_store.list_dashboards(PROJECTS_DIR, project.id)
    result = []
    for d in dashboards:
        full = dashboard_store.get_dashboard(PROJECTS_DIR, project.id, d["id"])
        if full:
            result.append(full)
    return {"dashboards": result}


@mcp.tool()
def create_dashboard(name: str) -> dict:
    """
    在当前项目下创建新的空Dashboard。

    Args:
        name: Dashboard名称
    """
    project, _ = _require_project()
    result = dashboard_store.create_dashboard(PROJECTS_DIR, project.id, name)
    return result


@mcp.tool()
def save_chart_to_dashboard(dashboard_name: str, chart: dict) -> dict:
    """
    保存图表到当前项目的Dashboard。如果Dashboard不存在则自动创建。

    Args:
        dashboard_name: Dashboard名称
        chart: 图表数据，包含 chart_type, chart_option, title, sql 等
    """
    project, _ = _require_project()
    result = dashboard_store.save_chart(PROJECTS_DIR, project.id, dashboard_name, chart)
    return result


@mcp.tool()
def delete_chart(dashboard_id: str, chart_id: str) -> dict:
    """
    从Dashboard中删除指定图表。

    Args:
        dashboard_id: Dashboard ID
        chart_id: 图表ID
    """
    project, _ = _require_project()
    ok = dashboard_store.delete_chart(PROJECTS_DIR, project.id, dashboard_id, chart_id)
    if not ok:
        return {"error": "Dashboard or chart not found"}
    return {"ok": True}


@mcp.tool()
def delete_dashboard(dashboard_id: str) -> dict:
    """
    删除当前项目的整个Dashboard及其所有图表。

    Args:
        dashboard_id: Dashboard ID
    """
    project, _ = _require_project()
    dash = dashboard_store.get_dashboard(PROJECTS_DIR, project.id, dashboard_id)
    if not dash:
        return {"error": "Dashboard not found"}
    ok = dashboard_store.delete_dashboard(PROJECTS_DIR, project.id, dashboard_id)
    if not ok:
        return {"error": "Failed to delete dashboard"}
    return {"ok": True, "deleted_id": dashboard_id, "deleted_name": dash.get("name")}


# ═══════════════════════════════════════════════════════════════════════════
# Resource: project semantic layer
# ═══════════════════════════════════════════════════════════════════════════

@mcp.resource("semantic://current")
def get_current_semantic_layer() -> str:
    """获取当前项目的完整语义层配置（YAML格式）。"""
    project = _session.get_current_project()
    if not project:
        return "No active project. Use switch_project() or create_project() first."
    import yaml
    return yaml.dump(project.semantic_layer, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ═══════════════════════════════════════════════════════════════════════════
# Prompt: data_analysis
# ═══════════════════════════════════════════════════════════════════════════

@mcp.prompt()
def data_analysis(question: str) -> str:
    """
    数据分析提示模板：引导Agent使用三级查询协议分析数据。

    Args:
        question: 用户的自然语言分析问题
    """
    return f"""你是一个专业的数据分析助手。请使用ChatBI MCP Server的三级查询协议来回答以下问题：

用户问题：{question}

分析步骤：
1. 确认当前项目：调用 get_current_project() 确认活跃项目
2. 了解数据上下文：调用 get_semantic_context(section="all") 查看可用的指标、维度、事件定义
3. 判断问题属于哪个级别：
   - L1 简单查询：如果问题可以分解为 {{metric, dimensions, filters}}，使用 semantic_query(level="L1", ...)
   - L2 分析模板：如果问题涉及留存、漏斗、同环比等分析模式，使用 semantic_query(level="L2", ...)
   - L3 原始SQL：如果L1/L2无法覆盖，使用 raw_sql(sql="...")
4. 执行查询并分析结果
5. 如果需要可视化，调用 render_chart 生成图表
6. 用中文总结分析结论

注意事项：
- 优先使用L1/L2，L3仅作为兜底
- 指标名称和维度名称必须来自当前项目的语义层定义
- 留存分析用 analysis_type="retention"
- 漏斗分析用 analysis_type="funnel"
- 同环比用 analysis_type="period_over_period"
- 事件名称必须精确匹配 semantic context 中的定义
"""


# ═══════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChatBI MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Port for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "0.0.0.0"),
        help="Host for SSE transport (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    if args.transport == "sse":
        import uvicorn
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp._mcp_server.run(
                    streams[0], streams[1], mcp._mcp_server.create_initialization_options()
                )

        async def handle_messages(request):
            await sse.handle_post_message(request._receive, request._send)

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")
