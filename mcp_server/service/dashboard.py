# -*- coding: utf-8 -*-
import os
import json
from typing import Optional

from mcp_server.project_model import ProjectSession, PROJECTS_DIR
from mcp_server import dashboard_store
from mcp_server.chart_renderer import build_echarts_option, suggest_chart_type
from mcp_server.chart_selector import resolve_chart_type
from mcp_server.semantic_query import validate_raw_sql
from mcp_server.service.query import require_project, serialize_data, build_dynamic_l2_query


def list_dashboards(session: ProjectSession) -> dict:
    project, _ = require_project(session)
    dashboards = dashboard_store.list_dashboards(PROJECTS_DIR, project.id)
    result = []
    for d in dashboards:
        full = dashboard_store.get_dashboard(PROJECTS_DIR, project.id, d["id"])
        if full:
            result.append(full)
    return {"dashboards": result}


def create_dashboard(session: ProjectSession, name: str) -> dict:
    project, _ = require_project(session)
    result = dashboard_store.create_dashboard(PROJECTS_DIR, project.id, name)
    return result


def save_chart_to_dashboard(session: ProjectSession, dashboard_name: str, chart: dict) -> dict:
    project, _ = require_project(session)

    if not chart.get("business_domain"):
        full = project.get_full_semantic_layer(PROJECTS_DIR)
        metrics = full.get("metrics", {})
        chart_title = chart.get("title", "")
        if not chart_title:
            opt = chart.get("chart_option", {})
            if isinstance(opt, dict):
                t = opt.get("title", {})
                if isinstance(t, dict):
                    chart_title = t.get("text", "")
                elif isinstance(t, str):
                    chart_title = t
        for m_name, m_def in metrics.items():
            if m_def.get("business_name") == chart_title or m_name == chart_title:
                chart["business_domain"] = m_def.get("business_domain", "")
                chart["business_domain_label"] = m_def.get("business_domain_label", "")
                break

    result = dashboard_store.save_chart(PROJECTS_DIR, project.id, dashboard_name, chart)
    return result


def delete_chart(session: ProjectSession, dashboard_id: str, chart_id: str) -> dict:
    project, _ = require_project(session)
    ok = dashboard_store.delete_chart(PROJECTS_DIR, project.id, dashboard_id, chart_id)
    if not ok:
        return {"error": "Dashboard or chart not found"}
    return {"ok": True}


def delete_dashboard(session: ProjectSession, dashboard_id: str) -> dict:
    project, _ = require_project(session)
    dash = dashboard_store.get_dashboard(PROJECTS_DIR, project.id, dashboard_id)
    if not dash:
        return {"error": "Dashboard not found"}
    ok = dashboard_store.delete_dashboard(PROJECTS_DIR, project.id, dashboard_id)
    if not ok:
        return {"error": "Failed to delete dashboard"}
    return {"ok": True, "deleted_id": dashboard_id, "deleted_name": dash.get("name")}


def export_dashboard(session: ProjectSession, dashboard_name: str, theme: str = "ggplot2_minimal") -> dict:
    from mcp_server.dashboard_html import export_dashboard_html
    from mcp_server.themes import list_themes

    project, _ = require_project(session)

    available = list_themes()
    if theme not in available:
        return {"error": f"Unknown theme '{theme}'. Available: {available}"}

    try:
        html_path = export_dashboard_html(
            projects_dir=PROJECTS_DIR,
            project_id=project.id,
            dashboard_name=dashboard_name,
            theme=theme,
        )
        return {
            "status": "exported",
            "html_path": html_path,
            "dashboard_name": dashboard_name,
            "theme": theme,
            "message": f"Dashboard 已导出为 HTML: {html_path}",
        }
    except ValueError as e:
        return {"error": str(e)}


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
    resolved = resolve_chart_type(
        data=data,
        title=title,
        intent=intent or chart_hint or "",
        user_chart_type=chart_type,
        use_llm=use_llm,
    )
    effective_type = resolved["chart_type"]

    if metric_type in ("rate", "count", "duration") and data and len(data) <= 1:
        effective_type = "kpi_card"
    elif not effective_type:
        if metric_type == "distribution":
            effective_type = "pie"
        elif metric_type == "ranking":
            effective_type = "ranking_bar"
        elif metric_type == "rate":
            effective_type = "line"
        else:
            effective_type = suggest_chart_type(data, title)

    render_spec = {
        "chart_type": effective_type,
        "reasoning": resolved.get("reasoning", ""),
        "alternatives": resolved.get("alternatives", []),
        "confidence": resolved.get("confidence", 0.5),
    }

    if confirm:
        return {
            "status": "confirm_required",
            "render_spec": render_spec,
            "data_preview": data[:5] if data else [],
            "message": (
                f"即将以 {effective_type} 类型绘制图表: {title}\n"
                f"原因: {render_spec['reasoning']}\n"
                f"备选: {render_spec['alternatives']}\n"
                "请确认或调整后再次调用 render_chart。"
            ),
        }

    if effective_type == "kpi_card":
        if data:
            keys = list(data[0].keys())
            rate_keys = [k for k in keys if "rate" in k.lower()]
            if rate_keys and len(data) > 1:
                best_row = None
                for row in reversed(data):
                    if any(row.get(rk) is not None for rk in rate_keys):
                        best_row = row
                        break
                if best_row is None:
                    best_row = data[-1]
                sub_parts = []
                for rk in rate_keys:
                    v = best_row.get(rk)
                    if v is not None:
                        if isinstance(v, float):
                            if abs(v) <= 1:
                                sub_parts.append(f"{rk}: {v * 100:.1f}%")
                            else:
                                sub_parts.append(f"{rk}: {v:.1f}%")
                        else:
                            sub_parts.append(f"{rk}: {v}")
                val_key = rate_keys[0]
                val = best_row.get(val_key)
                if isinstance(val, float):
                    val = round(val, 4)
                sub_text = " | ".join(sub_parts[1:]) if len(sub_parts) > 1 else ""
                return {
                    "chart_type": "kpi_card",
                    "chart_option": {
                        "title": {"text": title},
                        "value": val,
                        "metric_type": metric_type or "rate",
                        "sub_text": sub_text,
                    },
                    "render_spec": render_spec,
                }
            val_key = keys[-1] if len(keys) > 1 else keys[0]
            val = data[-1].get(val_key)
            if isinstance(val, float):
                val = round(val, 4)
            return {
                "chart_type": "kpi_card",
                "chart_option": {
                    "title": {"text": title},
                    "value": val,
                    "metric_type": metric_type,
                },
                "render_spec": render_spec,
            }
        return {"chart_type": "kpi_card", "chart_option": {"title": {"text": title}, "value": None}, "render_spec": render_spec}

    if effective_type == "table":
        return {"chart_type": "table", "chart_option": None, "data": data, "render_spec": render_spec}

    chart_option = build_echarts_option(effective_type, data, title)
    if chart_option is None:
        return {"error": f"Unsupported chart type: {effective_type}"}

    return {
        "chart_type": effective_type,
        "chart_option": chart_option,
        "render_spec": render_spec,
    }


def generate_dashboard_from_spec(
    session: ProjectSession,
    spec_path: str = "",
    dashboard_name: str = "",
    theme: str = "ggplot2_minimal",
) -> dict:
    project, dm = require_project(session)
    if not dm.con:
        dm.load()
    semantic = project.get_full_semantic_layer(PROJECTS_DIR)
    metrics = semantic.get("metrics", {})
    table_name = semantic.get("table_name", "events")

    if not spec_path:
        spec_path = os.path.join(PROJECTS_DIR, project.id, "dashboard_spec.json")
    if not os.path.exists(spec_path):
        return {"error": f"dashboard_spec.json not found at {spec_path}"}

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    if not dashboard_name:
        dashboard_name = spec.get("name", "Dashboard")

    existing = dashboard_store.load_dashboard_by_name(PROJECTS_DIR, project.id, dashboard_name)
    if existing:
        dashboard_store.delete_dashboard(PROJECTS_DIR, project.id, existing["id"])

    categories = {c["id"]: c for c in spec.get("categories", [])}
    charts_spec = spec.get("charts", [])

    created_charts = []
    errors = []

    for chart_spec in charts_spec:
        chart_id = chart_spec.get("chart_id", "")
        chart_name = chart_spec.get("name", "")
        chart_type = chart_spec.get("chart_type", "")
        category_id = chart_spec.get("category", "")
        category_label = categories.get(category_id, {}).get("label", category_id)
        metric_ref = chart_spec.get("metric_ref", "")
        custom_sql = chart_spec.get("custom_sql", "")
        analysis_type = chart_spec.get("analysis_type", "")
        description = chart_spec.get("description", "")

        try:
            sql = ""
            y_axis = chart_spec.get("y_axis", [])
            x_axis = chart_spec.get("x_axis", {})

            if custom_sql:
                sql = custom_sql
            elif analysis_type:
                params = chart_spec.get("analysis_params", {})
                built_sql, err = build_dynamic_l2_query(semantic, analysis_type, params)
                if err:
                    errors.append({"chart_id": chart_id, "name": chart_name, "error": err})
                    continue
                sql = built_sql
            elif y_axis and isinstance(y_axis, list):
                y_metric_refs = [ya.get("metric_ref", "") for ya in y_axis if ya.get("metric_ref")]
                if not y_metric_refs and metric_ref:
                    y_metric_refs = [metric_ref]

                if y_metric_refs:
                    metric_sqls = []
                    metric_types = []
                    for mr in y_metric_refs:
                        mdef = metrics.get(mr)
                        if not mdef:
                            errors.append({"chart_id": chart_id, "name": chart_name, "error": f"Unknown metric: {mr}"})
                            break
                        metric_sqls.append(f"{mdef.get('sql', '')} AS {mr}")
                        metric_types.append(mdef.get("metric_type", ""))
                    else:
                        dimensions = chart_spec.get("dimensions", [])
                        if dimensions:
                            dim_clause = ", ".join(dimensions)
                            select_clause = f"{dim_clause}, " + ", ".join(metric_sqls)
                            sql = f"SELECT {select_clause} FROM {table_name} GROUP BY {dim_clause} ORDER BY {dim_clause}"
                        else:
                            select_clause = ", ".join(metric_sqls)
                            sql = f"SELECT {select_clause} FROM {table_name}"
                    if not sql and not y_metric_refs:
                        errors.append({"chart_id": chart_id, "name": chart_name, "error": "No valid metric_ref in y_axis"})
                        continue
                    elif not sql:
                        continue
                else:
                    errors.append({"chart_id": chart_id, "name": chart_name, "error": "No metric_ref in y_axis or chart_spec"})
                    continue
            elif metric_ref:
                dimensions = chart_spec.get("dimensions", [])
                metric_def = metrics.get(metric_ref)
                if not metric_def:
                    errors.append({"chart_id": chart_id, "name": chart_name, "error": f"Unknown metric: {metric_ref}"})
                    continue
                metric_sql = metric_def.get("sql", "")

                if not dimensions:
                    sql = f"SELECT {metric_sql} AS {metric_ref} FROM {table_name}"
                else:
                    dim_clause = ", ".join(dimensions)
                    sql = f"SELECT {dim_clause}, {metric_sql} AS {metric_ref} FROM {table_name} GROUP BY {dim_clause} ORDER BY {dim_clause}"
            else:
                errors.append({"chart_id": chart_id, "name": chart_name, "error": "No metric_ref, custom_sql, or analysis_type specified"})
                continue

            try:
                sql = validate_raw_sql(sql)
            except ValueError as sql_err:
                errors.append({"chart_id": chart_id, "name": chart_name, "error": f"SQL validation error: {sql_err}"})
                continue

            data = dm.execute(sql)
            data = serialize_data(data)

            metric_type = ""
            business_domain = ""
            business_domain_label = ""
            if metric_ref and metric_ref in metrics:
                metric_type = metrics[metric_ref].get("metric_type", "")
                business_domain = metrics[metric_ref].get("business_domain", "")
                business_domain_label = metrics[metric_ref].get("business_domain_label", "")

            if not business_domain and category_id:
                business_domain = category_id
                business_domain_label = category_label

            chart_result = render_chart(
                data=data,
                chart_type=chart_type,
                title=chart_name,
                metric_type=metric_type,
            )

            chart_data = {
                "title": chart_name,
                "chart_type": chart_result.get("chart_type", chart_type),
                "chart_option": chart_result.get("chart_option"),
                "sql": sql,
                "data_sample": data[:5],
                "business_domain": business_domain,
                "business_domain_label": business_domain_label,
                "spec_chart_id": chart_id,
                "spec_category": category_id,
                "spec_category_label": category_label,
                "description": description,
            }

            if chart_type == "kpi_card":
                kpi_format = chart_spec.get("kpi_format", "")
                chart_data["kpi_format"] = kpi_format
                if chart_result.get("chart_option"):
                    chart_data["chart_option"]["kpi_format"] = kpi_format

            save_result = dashboard_store.save_chart(PROJECTS_DIR, project.id, dashboard_name, chart_data)
            created_charts.append({
                "chart_id": chart_id,
                "name": chart_name,
                "chart_type": chart_type,
                "category": category_id,
                "saved_chart_id": save_result.get("chart_id"),
                "rows": len(data),
                "warnings": save_result.get("warnings", []),
            })

        except Exception as e:
            errors.append({"chart_id": chart_id, "name": chart_name, "error": str(e)})

    html_path = None
    try:
        from mcp_server.dashboard_html import export_dashboard_html
        html_path = export_dashboard_html(
            projects_dir=PROJECTS_DIR,
            project_id=project.id,
            dashboard_name=dashboard_name,
            theme=theme,
        )
    except Exception as e:
        errors.append({"chart_id": "_export", "name": "export_html", "error": str(e)})

    return {
        "status": "generated",
        "dashboard_name": dashboard_name,
        "total_specs": len(charts_spec),
        "charts_created": len(created_charts),
        "errors_count": len(errors),
        "charts": created_charts,
        "errors": errors,
        "html_path": html_path,
    }


DASHBOARD_SPEC_SCHEMA_VERSION = "0.1.0"


def save_dashboard_as_spec(
    session: ProjectSession,
    dashboard_name: str,
    output_path: str = "",
) -> dict:
    """Export the current dashboard as a dashboard_spec.json file."""
    project, _ = require_project(session)

    dashboard = dashboard_store.load_dashboard_by_name(PROJECTS_DIR, project.id, dashboard_name)
    if not dashboard:
        return {"error": f"Dashboard '{dashboard_name}' not found"}

    charts = dashboard.get("charts", [])
    domains = {}
    chart_specs = []

    for c in charts:
        domain = c.get("business_domain", "other") or "other"
        domain_label = c.get("business_domain_label", domain) or domain
        if domain not in domains:
            domains[domain] = {"id": domain, "label": domain_label}

        chart_specs.append({
            "chart_id": c.get("spec_chart_id", c.get("id", "")),
            "name": c.get("title", ""),
            "description": c.get("description", ""),
            "chart_type": c.get("chart_type", ""),
            "category": domain,
            "custom_sql": c.get("sql", ""),
        })

    from datetime import datetime
    spec = {
        "version": DASHBOARD_SPEC_SCHEMA_VERSION,
        "name": dashboard_name,
        "description": f"Dashboard spec exported from {project.name}",
        "meta": {
            "created_at": dashboard.get("created_at", ""),
            "updated_at": datetime.now().isoformat(),
            "tags": [],
            "parameters": {},
        },
        "categories": list(domains.values()),
        "charts": chart_specs,
    }

    if not output_path:
        output_path = os.path.join(PROJECTS_DIR, project.id, "dashboard_spec.json")
    elif not os.path.isabs(output_path):
        output_path = os.path.join(PROJECTS_DIR, project.id, output_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    return {
        "status": "saved",
        "spec_path": output_path,
        "version": DASHBOARD_SPEC_SCHEMA_VERSION,
        "charts_count": len(chart_specs),
        "categories_count": len(domains),
    }


def validate_dashboard_spec(
    session: ProjectSession,
    spec_path: str = "",
) -> dict:
    """Validate a dashboard_spec.json for structure and metric references."""
    project, dm = require_project(session)
    semantic = project.get_full_semantic_layer(PROJECTS_DIR)
    metrics = semantic.get("metrics", {})

    if not spec_path:
        spec_path = os.path.join(PROJECTS_DIR, project.id, "dashboard_spec.json")
    if not os.path.exists(spec_path):
        return {"status": "fail", "reason": f"Spec file not found: {spec_path}"}

    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    issues = []
    warnings = []

    if not spec.get("name"):
        issues.append("Missing required field: name")
    if not spec.get("charts"):
        issues.append("Missing required field: charts")
    if not isinstance(spec.get("charts"), list):
        issues.append("charts must be a list")

    for cs in spec.get("charts", []):
        chart_id = cs.get("chart_id", "?")
        mr = cs.get("metric_ref", "")
        if mr and mr not in metrics:
            issues.append(f"Chart '{chart_id}': metric_ref '{mr}' not in semantic layer")
        at = cs.get("analysis_type", "")
        if at and at not in ("retention", "funnel", "period_over_period"):
            issues.append(f"Chart '{chart_id}': unknown analysis_type '{at}'")

    sv = spec.get("version", "0.0.0")
    if sv != DASHBOARD_SPEC_SCHEMA_VERSION:
        warnings.append(f"Spec version {sv} != current {DASHBOARD_SPEC_SCHEMA_VERSION}")

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "charts_count": len(spec.get("charts", [])),
        "spec_version": sv,
        "current_version": DASHBOARD_SPEC_SCHEMA_VERSION,
    }
