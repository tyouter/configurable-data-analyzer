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
  ChatBI MCP Server (thin wrapper)
    ↓
  Service Layer (single source of truth)
    ↓
  Project { data files + semantic layer + DuckDB }

Run:
  python mcp_server/server.py              # stdio transport (default)
  python mcp_server/server.py --transport sse  # SSE transport
"""

import os
import sys
import argparse
from typing import Optional

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mcp.server.fastmcp import FastMCP

from mcp_server.project_model import (
    ProjectSession,
    PROJECTS_DIR,
)
from mcp_server.semantic_generator import generate_semantic_layer
from mcp_server.service import (
    create_project as svc_create_project,
    execute_pipeline_step as svc_execute_pipeline_step,
    list_dashboards as svc_list_dashboards,
    create_dashboard as svc_create_dashboard,
    save_chart_to_dashboard as svc_save_chart_to_dashboard,
    delete_chart as svc_delete_chart,
    delete_dashboard as svc_delete_dashboard,
    export_dashboard as svc_export_dashboard,
    render_chart as svc_render_chart,
    generate_dashboard_from_spec as svc_generate_dashboard_from_spec,
    execute_semantic_query as svc_execute_semantic_query,
    execute_raw_sql as svc_execute_raw_sql,
    explore_column_values as svc_explore_column_values,
    get_semantic_context as svc_get_semantic_context,
    review_data_understanding as svc_review_data_understanding,
    update_semantic_config as svc_update_semantic_config,
    validate_semantic_layer as svc_validate_semantic_layer,
)

mcp = FastMCP(
    "ChatBI",
    instructions="""ChatBI MCP Server — 项目无关的数据分析平台。

支持多项目管理，每个项目拥有独立的数据文件、语义层和DuckDB实例。

创建项目流程（多阶段交互）：
1. create_project(action="start") — 提交数据文件，自动分类+审计+解析，返回审计报告
2. create_project(action="classify") — 用户修正文件分类，支持多轮交互
3. create_project(action="confirm") — 用户确认要导入的文件和分析目标
4. create_project(action="build") — 仅导入确认的文件，生成语义层

快捷流程：create_project(name, data_files) — 等同于 action="start"

查询流程：
5. switch_project — 切换到目标项目
6. get_semantic_context — 查看当前项目的语义层
7. semantic_query / raw_sql — 执行数据分析查询
8. render_chart — 生成图表
9. Dashboard CRUD — 管理图表看板

三级查询协议：
- L1 简单查询：通过 metric + dimensions + filters 结构化查询
- L2 分析模板：封装留存、漏斗、同环比等分析模式
- L3 原始SQL：只读SQL查询兜底
""",
)

_session = ProjectSession()


# ═══════════════════════════════════════════════════════════════════════════
# Tools: Project Management
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_project(
    name: str = "",
    data_files: list[str] = [],
    action: str = "start",
    project_id: Optional[str] = None,
    project_type: Optional[str] = None,
    corrections: Optional[dict] = None,
    questions: Optional[str] = None,
    confirmed_raw_files: Optional[list[str]] = None,
    confirmed_ref_files: Optional[list[str]] = None,
    analysis_goals: Optional[list[str]] = None,
    use_llm: bool = True,
) -> dict:
    """
    创建新项目（多阶段交互流程）。

    阶段说明：
    - action="start": 提交数据文件，自动执行文件分类、Schema提取、参考文档解析，返回审计报告
    - action="classify": 修正文件分类或回答问题（可多轮）
    - action="confirm": 确认要导入的原始数据文件、参考文档和分析目标
    - action="build": 执行构建——仅导入确认的文件并生成语义层
    - action="status": 查询当前进行中的创建流程状态

    快捷方式：直接传 name + data_files 等同于 action="start"

    Args:
        action: 阶段操作 start/classify/confirm/build/status（默认 start）
        name: 项目名称（action=start 时必填）
        data_files: 数据文件路径列表（action=start 时必填）
        project_id: 项目ID（action=classify/confirm/build/status 时必填）
        project_type: 项目类型（可选，自动检测）
        corrections: 文件分类修正 {"filename": "new_category"}（action=classify）
        questions: 用户问题（action=classify）
        confirmed_raw_files: 确认导入的原始数据文件名列表（action=confirm）
        confirmed_ref_files: 确认作为参考的文件名列表（action=confirm）
        analysis_goals: 确认的分析目标列表（action=confirm）
        use_llm: 是否使用LLM辅助生成语义层（默认True）
    """
    return svc_create_project(
        session=_session,
        name=name,
        data_files=data_files,
        action=action,
        project_id=project_id,
        project_type=project_type,
        corrections=corrections,
        questions=questions,
        confirmed_raw_files=confirmed_raw_files,
        confirmed_ref_files=confirmed_ref_files,
        analysis_goals=analysis_goals,
        use_llm=use_llm,
    )


@mcp.tool()
def execute_pipeline_step(
    project_id: str,
    step: str,
    use_llm: bool = True,
    project_type: Optional[str] = None,
) -> dict:
    """
    执行 Pipeline 单个步骤。支持断点续做和独立重试。

    步骤顺序：load_data → create_derived → gen_semantic → save_semantic

    Args:
        project_id: 项目ID
        step: 要执行的步骤 (load_data/create_derived/gen_semantic/save_semantic)
        use_llm: 是否使用LLM（gen_semantic步骤有效）
        project_type: 项目类型（load_data步骤有效）
    """
    return svc_execute_pipeline_step(
        session=_session,
        project_id=project_id,
        step=step,
        use_llm=use_llm,
        project_type=project_type,
    )


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
            "metrics_count": len(project.get_full_semantic_layer(PROJECTS_DIR).get("metrics", {})),
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
        "metrics_count": len(project.get_full_semantic_layer(PROJECTS_DIR).get("metrics", {})),
        "events_count": len(project.get_full_semantic_layer(PROJECTS_DIR).get("event_definitions", {})),
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
    return {"status": "deleted", "deleted_project_id": project_id}


@mcp.tool()
def regenerate_semantic_layer(use_llm: bool = True) -> dict:
    """
    重新生成当前项目的语义层。当数据结构变化或语义层不准确时使用。

    Args:
        use_llm: 是否使用LLM辅助（需要DEEPSEEK_API_KEY，默认True）
    """
    try:
        from mcp_server.service.query import require_project
        project, dm = require_project(_session)
    except ValueError as e:
        return {"error": str(e)}

    try:
        semantic = generate_semantic_layer(
            dm,
            project_type=project.project_type,
            use_llm=use_llm,
        )
        project.semantic_layer = {
            "table_name": semantic.get("table_name", "events"),
            "config_file": semantic.get("config_file", "semantic_config.json"),
        }
        project.semantic_layer_dirty = False
        _session.store.save_project(project)

        dm.invalidate_semantic_cache()

        return {
            "project_id": project.id,
            "metrics_count": len(semantic.get("metrics", {})),
            "events_count": len(semantic.get("event_definitions", {})),
            "columns_count": len(semantic.get("columns", {})),
            "semantic_source": "llm",
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
    return svc_execute_semantic_query(
        session=_session,
        level=level,
        metric=metric,
        dimensions=dimensions,
        filters=filters,
        order_by=order_by,
        limit=limit,
        analysis_type=analysis_type,
        analysis_params=analysis_params,
    )


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
    return svc_execute_raw_sql(session=_session, sql=sql, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════
# Tool: render_chart
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def render_chart(
    data: list[dict],
    chart_type: str = "",
    title: str = "",
    metric_type: str = "",
    chart_hint: str = "",
    intent: str = "",
    confirm: bool = False,
    use_llm: bool = True,
) -> dict:
    """
    根据查询数据生成图表配置。支持意图驱动的智能图表选择。

    图表选择优先级：
      1. chart_type（用户显式指定，最高优先级）
      2. intent + LLM推断（根据可视化目标智能匹配最佳图表类型）
      3. chart_hint（语义层建议，作为intent的补充）
      4. metric_type + 数据形态规则推断（兜底）

    Args:
        data: 查询结果数据（列表的字典）
        chart_type: 用户指定的图表类型（如 line/bar/pie 等）。留空则自动推断。
        title: 图表标题
        metric_type: 指标类型 count/rate/duration/distribution/ranking
        chart_hint: 语义层建议（向后兼容）
        intent: 可视化目标描述（如"展示活跃用户随时间的变化趋势"），用于LLM智能选择图表类型
        confirm: 设为 True 时返回渲染规格供用户确认，不实际渲染
        use_llm: 是否使用LLM辅助推断图表类型（默认True，无API Key时自动降级为规则推断）
    """
    return svc_render_chart(
        data=data,
        chart_type=chart_type,
        title=title,
        metric_type=metric_type,
        chart_hint=chart_hint,
        intent=intent,
        confirm=confirm,
        use_llm=use_llm,
    )


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
    return svc_get_semantic_context(session=_session, section=section)


@mcp.tool()
def explore_column_values(
    column: str,
    pattern: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """
    探索某列的实际值分布，用于编写正确的 SQL 过滤条件。
    在编写 LIKE/IN 等 WHERE 子句前，务必先调用此工具确认实际值。

    Args:
        column: 列名（如 span_name, page_root, event_type）
        pattern: 可选的模糊搜索模式（SQL LIKE 语法，如 '%travel_guide%'）
        limit: 返回值数量上限（默认50，最大200）
    """
    return svc_explore_column_values(session=_session, column=column, pattern=pattern, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════
# Tools: Dashboard CRUD
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_dashboards() -> dict:
    """列出当前项目所有Dashboard及其包含的图表。"""
    return svc_list_dashboards(session=_session)


@mcp.tool()
def create_dashboard(name: str) -> dict:
    """
    在当前项目下创建新的空Dashboard。

    Args:
        name: Dashboard名称
    """
    return svc_create_dashboard(session=_session, name=name)


@mcp.tool()
def save_chart_to_dashboard(dashboard_name: str, chart: dict) -> dict:
    """
    保存图表到当前项目的Dashboard。如果Dashboard不存在则自动创建。

    Args:
        dashboard_name: Dashboard名称
        chart: 图表数据，包含 chart_type, chart_option, title, sql, business_domain 等
    """
    return svc_save_chart_to_dashboard(session=_session, dashboard_name=dashboard_name, chart=chart)


@mcp.tool()
def delete_chart(dashboard_id: str, chart_id: str) -> dict:
    """
    从Dashboard中删除指定图表。

    Args:
        dashboard_id: Dashboard ID
        chart_id: 图表ID
    """
    return svc_delete_chart(session=_session, dashboard_id=dashboard_id, chart_id=chart_id)


@mcp.tool()
def delete_dashboard(dashboard_id: str) -> dict:
    """
    删除当前项目的整个Dashboard及其所有图表。

    Args:
        dashboard_id: Dashboard ID
    """
    return svc_delete_dashboard(session=_session, dashboard_id=dashboard_id)


@mcp.tool()
def export_dashboard(
    dashboard_name: str,
    theme: str = "ggplot2_minimal",
) -> dict:
    """
    将当前项目的 Dashboard 导出为自包含 HTML 文件，可在浏览器中直接打开。

    Args:
        dashboard_name: Dashboard 名称
        theme: 主题名称，可选 ggplot2_minimal（亮色）或 ggplot2_dark（暗色）
    """
    return svc_export_dashboard(session=_session, dashboard_name=dashboard_name, theme=theme)


@mcp.tool()
def generate_dashboard_from_spec(
    spec_path: str = "",
    dashboard_name: str = "",
    theme: str = "ggplot2_minimal",
) -> dict:
    """
    根据 dashboard_spec.json 自动生成完整 Dashboard，逐个图表执行查询并渲染。
    这是项目配置注入的核心：spec 定义了需求，MCP server 负责执行查询和渲染。

    Args:
        spec_path: dashboard_spec.json 的路径（默认使用当前项目的 dashboard_spec.json）
        dashboard_name: Dashboard 名称（默认使用 spec 中的 name）
        theme: 主题名称，可选 ggplot2_minimal 或 ggplot2_dark
    """
    return svc_generate_dashboard_from_spec(
        session=_session,
        spec_path=spec_path,
        dashboard_name=dashboard_name,
        theme=theme,
    )


@mcp.resource("semantic://current")
def get_current_semantic_layer() -> str:
    """获取当前项目的完整语义层配置（YAML格式）。"""
    project = _session.get_current_project()
    if not project:
        return "No active project. Use switch_project() or create_project() first."
    import yaml
    return yaml.dump(project.get_full_semantic_layer(PROJECTS_DIR), allow_unicode=True, default_flow_style=False, sort_keys=False)


@mcp.tool()
def migrate_project(project_id: str) -> dict:
    """
    迁移旧项目格式：将 project.yaml 中的语义层数据导出到 semantic_config.json。
    迁移后项目功能不变，但语义层配置与元信息分离，支持模块化管理。

    Args:
        project_id: 要迁移的项目ID
    """
    return _session.store.migrate_semantic_layer(project_id)


# ═══════════════════════════════════════════════════════════════════════════
# Tools: Human-in-the-Loop Alignment (Phase 6)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def review_data_understanding(project_id: Optional[str] = None) -> dict:
    """
    生成当前项目的数据理解报告，包含列映射、事件解析和指标定义。
    用户可基于此报告决定需要修正的内容。

    Args:
        project_id: 项目ID（默认当前项目）
    """
    return svc_review_data_understanding(session=_session, project_id=project_id)


@mcp.tool()
def update_column_mapping(
    project_id: Optional[str] = None,
    columns: Optional[dict] = None,
) -> dict:
    """
    批量修正列映射。修正后标记 semantic_layer_dirty=True。

    Args:
        project_id: 项目ID（默认当前项目）
        columns: 修正内容，格式 {"col_name": {"business_name": "新名称", "role": "dimension"}}
                 仅需提供要修改的字段，未提供的字段保持不变
    """
    if not columns:
        return {"error": "columns is required"}
    return svc_update_semantic_config(session=_session, project_id=project_id or "", section="columns", updates=columns)


@mcp.tool()
def update_event_mapping(
    project_id: Optional[str] = None,
    updates: Optional[dict] = None,
    delete_events: Optional[list] = None,
) -> dict:
    """
    批量修正事件映射。修正后标记 semantic_layer_dirty=True。

    Args:
        project_id: 项目ID（默认当前项目）
        updates: 修正/新增事件，格式 {"event_name": {"business_name": "...", "sql_pattern": "..."}}
        delete_events: 要删除的事件名称列表
    """
    if not updates and not delete_events:
        return {"error": "At least one of updates or delete_events is required"}
    return svc_update_semantic_config(session=_session, project_id=project_id or "", section="events", updates=updates or {}, deletes=delete_events)


@mcp.tool()
def update_metric(
    project_id: Optional[str] = None,
    updates: Optional[dict] = None,
    delete_metrics: Optional[list] = None,
) -> dict:
    """
    批量修正指标定义。修正后标记 semantic_layer_dirty=True。

    Args:
        project_id: 项目ID（默认当前项目）
        updates: 修正/新增指标，格式 {"metric_name": {"business_name": "...", "sql": "..."}}
        delete_metrics: 要删除的指标名称列表
    """
    if not updates and not delete_metrics:
        return {"error": "At least one of updates or delete_metrics is required"}
    return svc_update_semantic_config(session=_session, project_id=project_id or "", section="metrics", updates=updates or {}, deletes=delete_metrics)


# ═══════════════════════════════════════════════════════════════════════════
# Tool: validate_semantic_layer (Phase 7)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def validate_semantic_layer(
    project_id: Optional[str] = None,
    checks: Optional[list] = None,
) -> dict:
    """
    验证当前项目的语义层。检查 SQL 可执行性、数据质量和 KPI 覆盖率。

    Args:
        project_id: 项目ID（默认当前项目）
        checks: 要执行的检查项，可选 "sql_executability"/"data_quality"/"kpi_coverage"
                默认全部执行
    """
    return svc_validate_semantic_layer(session=_session, project_id=project_id, checks=checks)


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
        choices=["stdio", "sse", "streamable-http"],
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
    elif args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.transport_security = None
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
