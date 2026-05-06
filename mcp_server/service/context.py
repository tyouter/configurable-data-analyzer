# -*- coding: utf-8 -*-
import os
import json
from typing import Optional

from mcp_server.project_model import ProjectSession, PROJECTS_DIR
from mcp_server.analysis_templates import ANALYSIS_TEMPLATES
from mcp_server.service.query import require_project


def get_semantic_context(session: ProjectSession, section: Optional[str] = None) -> dict:
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    semantic = project.get_full_semantic_layer(PROJECTS_DIR)
    section = section or "all"

    if section == "metrics":
        metrics = []
        for name, info in semantic.get("metrics", {}).items():
            metrics.append({
                "id": name,
                "business_name": info.get("business_name", name),
                "sql": info.get("sql", ""),
                "metric_type": info.get("metric_type", ""),
                "business_domain": info.get("business_domain", ""),
                "business_domain_label": info.get("business_domain_label", ""),
                "chart_hint": info.get("chart_hint", ""),
                "visualization_goal": info.get("visualization_goal", ""),
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
                "metric_type": info.get("metric_type", ""),
                "chart_hint": info.get("chart_hint", ""),
                "visualization_goal": info.get("visualization_goal", ""),
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


def review_data_understanding(session: ProjectSession, project_id: Optional[str] = None) -> dict:
    if project_id:
        session.switch_project(project_id)
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    full = project.get_full_semantic_layer(PROJECTS_DIR)
    columns = full.get("columns", {})
    events = full.get("event_definitions", {})
    metrics = full.get("metrics", {})

    column_summary = {}
    for col_name, col_def in columns.items():
        column_summary[col_name] = {
            "business_name": col_def.get("business_name", ""),
            "type": col_def.get("type", ""),
            "role": col_def.get("role", ""),
            "description": col_def.get("description", ""),
        }
        if col_def.get("derived"):
            column_summary[col_name]["derived"] = True
            column_summary[col_name]["derived_from"] = col_def.get("derived_from", "")

    event_summary = {}
    for evt_name, evt_def in events.items():
        event_summary[evt_name] = {
            "business_name": evt_def.get("business_name", evt_name),
            "sql_pattern": evt_def.get("sql_pattern", f"span_name = '{evt_name}'"),
        }

    metric_summary = {}
    for m_name, m_def in metrics.items():
        metric_summary[m_name] = {
            "business_name": m_def.get("business_name", ""),
            "sql": m_def.get("sql", ""),
            "metric_type": m_def.get("metric_type", ""),
            "description": m_def.get("description", ""),
        }

    validation = session.store.load_validation_report(project.id)

    result = {
        "project_id": project.id,
        "columns": column_summary,
        "events": event_summary,
        "metrics": metric_summary,
        "summary": {
            "columns_count": len(columns),
            "events_count": len(events),
            "metrics_count": len(metrics),
            "semantic_layer_dirty": project.semantic_layer_dirty,
        },
    }

    if validation:
        result["validation_summary"] = validation.get("summary", {})

    return result


def update_semantic_config(
    session: ProjectSession,
    project_id: str,
    section: str,
    updates: dict,
    deletes: list = None,
) -> dict:
    if project_id:
        session.switch_project(project_id)
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    config_path = os.path.join(PROJECTS_DIR, project.id, "semantic_config.json")
    if not os.path.exists(config_path):
        return {"error": f"semantic_config.json not found for project {project.id}"}

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if section not in config:
        config[section] = {}

    updated_keys = []
    for key, value in updates.items():
        if key in config[section]:
            if isinstance(value, dict) and isinstance(config[section][key], dict):
                config[section][key].update(value)
            else:
                config[section][key] = value
        else:
            config[section][key] = value
        updated_keys.append(key)

    deleted_keys = []
    if deletes:
        for key in deletes:
            if key in config[section]:
                del config[section][key]
                deleted_keys.append(key)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    project.semantic_layer_dirty = True
    session.store.save_project(project)
    dm.invalidate_semantic_cache()

    return {
        "project_id": project.id,
        "section": section,
        "updated": updated_keys,
        "deleted": deleted_keys,
        "semantic_layer_dirty": True,
    }


def validate_semantic_layer(
    session: ProjectSession,
    project_id: Optional[str] = None,
    checks: Optional[list] = None,
) -> dict:
    from mcp_server.semantic_validator import SemanticValidator

    if project_id:
        session.switch_project(project_id)
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    full = project.get_full_semantic_layer(PROJECTS_DIR)
    validator = SemanticValidator(dm, full)

    valid_checks = {"sql_executability", "data_quality", "kpi_coverage"}
    if checks:
        invalid = set(checks) - valid_checks
        if invalid:
            return {"error": f"Invalid checks: {sorted(invalid)}. Valid: {sorted(valid_checks)}"}
        active_checks = set(checks)
    else:
        active_checks = valid_checks

    results = {}

    if "sql_executability" in active_checks:
        results["sql_executability"] = validator.validate_sql_executability()

    if "data_quality" in active_checks:
        sql_result = results.get("sql_executability")
        results["data_quality"] = validator.validate_data_quality(sql_result)

    if "kpi_coverage" in active_checks:
        results["kpi_coverage"] = validator.validate_kpi_coverage()

    results["summary"] = validator._build_summary(results)

    report_path = os.path.join(PROJECTS_DIR, project.id, "validation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    return results
