# -*- coding: utf-8 -*-
import re
from typing import Optional

from mcp_server.project_model import ProjectSession, Project, ProjectDataManager, PROJECTS_DIR
from mcp_server.semantic_query import validate_raw_sql
from mcp_server.analysis_templates import ANALYSIS_TEMPLATES

_SQL_EXPR_PATTERN = re.compile(r'[\(\),\+\-\*/\.]', re.ASCII)
_SQL_AGG_PATTERN = re.compile(r'^\s*(COUNT|SUM|AVG|MIN|MAX|CAST|COALESCE|NULLIF|CASE|EXTRACT|DATE_TRUNC|SUBSTRING|TRIM|UPPER|LOWER|LENGTH|CONCAT|ROUND|FLOOR|CEIL|ABS|ROW_NUMBER|RANK|DENSE_RANK|LAG|LEAD|FIRST_VALUE|LAST_VALUE)\s*\(', re.IGNORECASE)


def _is_sql_expression(dim: str) -> bool:
    if _SQL_AGG_PATTERN.match(dim):
        return True
    if "(" in dim and ")" in dim:
        return True
    if any(op in dim for op in [" + ", " - ", " * ", " / "]):
        return True
    if "::" in dim:
        return True
    return False


def _derive_alias(dim: str) -> str:
    m = _SQL_AGG_PATTERN.match(dim)
    if m:
        func = m.group(1).lower()
        rest = dim[m.end():]
        inner_match = re.match(r'\s*["\']?(\w+)', rest)
        inner = inner_match.group(1) if inner_match else ""
        return f"{func}_{inner}" if inner else func
    alias = re.sub(r'[^a-zA-Z0-9_]', '_', dim)
    alias = re.sub(r'_+', '_', alias).strip("_")
    return alias or "expr"


def require_project(session: ProjectSession) -> tuple[Project, ProjectDataManager]:
    project = session.get_current_project()
    if not project:
        raise ValueError(
            "No active project. Call switch_project(project_id) first, "
            "or create_project(name, data_files) to create one."
        )
    dm = session.get_current_dm()
    if not dm:
        raise ValueError("Project data manager not loaded. Try switch_project again.")
    return project, dm


def serialize_data(data: list[dict]) -> list[dict]:
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


def build_dynamic_l1_query(
    semantic_layer: dict,
    metric: str,
    dimensions: list[str],
    filters: list[dict],
    order_by: Optional[str] = None,
    limit: int = 500,
) -> tuple[str, Optional[str]]:
    table_name = semantic_layer.get("table_name", "events")
    metrics = semantic_layer.get("metrics", {})
    columns = semantic_layer.get("columns", {})

    metric_def = metrics.get(metric)
    if not metric_def:
        available = sorted(metrics.keys())
        return "", f"Unknown metric: {metric}. Available: {available}"

    metric_sql = metric_def.get("sql", "")

    dim_expressions = []
    for dim in dimensions:
        if dim in columns:
            dim_expressions.append({"expr": dim, "alias": dim})
        elif _is_sql_expression(dim):
            alias = _derive_alias(dim)
            dim_expressions.append({"expr": dim, "alias": alias})
        else:
            available = sorted(columns.keys())
            return "", f"Invalid dimension: {dim}. Available: {available}"

    select_parts = [f"{d['expr']} AS {d['alias']}" for d in dim_expressions] + [f"{metric_sql} AS {metric}"]
    select_clause = ", ".join(select_parts)

    group_clause = ""
    if dim_expressions:
        group_clause = f"GROUP BY {', '.join(d['alias'] for d in dim_expressions)}"

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
    elif dim_expressions:
        order_clause = f"ORDER BY {dim_expressions[0]['alias']}"

    limit_clause = f"LIMIT {min(limit, 2000)}"

    parts = [f"SELECT {select_clause}", f"FROM {table_name}"]
    if where_clause:
        parts.append(where_clause)
    if group_clause:
        parts.append(group_clause)
    if order_clause:
        parts.append(order_clause)
    parts.append(limit_clause)
    sql = "\n".join(parts)
    return re.sub(r'\n\s+', '\n', sql), None


def build_dynamic_l2_query(
    semantic_layer: dict,
    analysis_type: str,
    params: dict,
) -> tuple[str, Optional[str]]:
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


def execute_semantic_query(
    session: ProjectSession,
    level: str,
    metric: Optional[str] = None,
    dimensions: Optional[list[str]] = None,
    filters: Optional[list[dict]] = None,
    order_by: Optional[str] = None,
    limit: int = 500,
    analysis_type: Optional[str] = None,
    analysis_params: Optional[dict] = None,
) -> dict:
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    semantic_layer = project.get_full_semantic_layer(PROJECTS_DIR)

    if level == "L1":
        if not metric:
            return {"error": "L1 query requires 'metric' parameter"}
        dimensions = dimensions or []
        filters = filters or []

        sql, err = build_dynamic_l1_query(
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

        sql, err = build_dynamic_l2_query(
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
        data = serialize_data(data)

        result = {
            "project_id": project.id,
            "sql": sql,
            "data": data,
            "row_count": len(data),
        }

        if data:
            sample = data[:3]
            keys = list(data[0].keys())
            result["data_preview"] = sample
            result["columns"] = keys
            result["summary"] = (
                f"查询返回 {len(data)} 行 × {len(keys)} 列\n"
                f"列: {', '.join(keys)}\n"
                f"前3行: {sample}"
            )

        if metric and metric in semantic_layer.get("metrics", {}):
            m_info = semantic_layer["metrics"][metric]
            result["metric_type"] = m_info.get("metric_type", "")
            result["chart_hint"] = m_info.get("chart_hint", "")
            result["visualization_goal"] = m_info.get("visualization_goal", "")
            result["business_domain"] = m_info.get("business_domain", "")

        if analysis_type:
            result["analysis_type"] = analysis_type
            result["visualization_goal"] = (
                f"展示{analysis_type}分析结果"
            )

        if not data:
            result["data_quality_warning"] = (
                "Query returned 0 rows. The metric or filter may not match any data. "
                "Use 'get_semantic_context' to check available metrics, "
                "or 'explore_column_values' to check actual data values."
            )

        return result
    except Exception as e:
        return {
            "project_id": project.id,
            "sql": sql,
            "error": f"SQL execution failed: {str(e)}",
            "data": [],
        }


def execute_raw_sql(
    session: ProjectSession,
    sql: str,
    limit: int = 2000,
) -> dict:
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    try:
        sql = validate_raw_sql(sql)
    except ValueError as e:
        return {"error": str(e), "data": []}

    try:
        data = dm.execute(sql)
        data = serialize_data(data)

        result = {
            "project_id": project.id,
            "sql": sql,
            "data": data,
            "row_count": len(data),
        }

        if data:
            keys = list(data[0].keys())
            result["data_preview"] = data[:3]
            result["columns"] = keys
            result["summary"] = (
                f"查询返回 {len(data)} 行 × {len(keys)} 列\n"
                f"列: {', '.join(keys)}"
            )

        if not data:
            result["data_quality_warning"] = (
                "Query returned 0 rows. Your WHERE clause or LIKE pattern may not match any data. "
                "Use 'explore_column_values' tool to check actual values in your data."
            )
        else:
            all_null = all(
                v is None for row in data for v in (row.values() if isinstance(row, dict) else [row])
            )
            if all_null:
                result["data_quality_warning"] = (
                    "All returned values are NULL. This usually means your SQL filter "
                    "(e.g., LIKE pattern) does not match any actual data values. "
                    "Use 'explore_column_values' tool to check actual values."
                )

        return result
    except Exception as e:
        return {
            "project_id": project.id,
            "sql": sql,
            "error": f"SQL execution failed: {str(e)}",
            "data": [],
        }


def explore_column_values(
    session: ProjectSession,
    column: str,
    pattern: Optional[str] = None,
    limit: int = 50,
) -> dict:
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    table_name = project.get_full_semantic_layer(PROJECTS_DIR).get("table_name", "events")

    columns = project.get_full_semantic_layer(PROJECTS_DIR).get("columns", {})
    if column not in columns:
        available = sorted(columns.keys())
        return {"error": f"Column '{column}' not found. Available columns: {available[:30]}"}

    limit = min(limit, 200)

    try:
        if pattern:
            sql = (
                f'SELECT "{column}", COUNT(*) AS cnt '
                f'FROM {table_name} '
                f'WHERE "{column}" LIKE \'{pattern}\' '
                f'GROUP BY "{column}" '
                f'ORDER BY cnt DESC '
                f'LIMIT {limit}'
            )
        else:
            sql = (
                f'SELECT "{column}", COUNT(*) AS cnt '
                f'FROM {table_name} '
                f'GROUP BY "{column}" '
                f'ORDER BY cnt DESC '
                f'LIMIT {limit}'
            )

        data = dm.execute(sql)
        data = serialize_data(data)

        result = {
            "project_id": project.id,
            "column": column,
            "pattern": pattern,
            "values": data,
            "total_distinct": len(data),
        }

        if not data and pattern:
            sql_no_filter = (
                f'SELECT DISTINCT "{column}" FROM {table_name} '
                f'LIMIT 10'
            )
            suggestions = dm.execute(sql_no_filter)
            suggestions = serialize_data(suggestions)
            result["hint"] = (
                f"No values match pattern '{pattern}'. "
                f"Here are some actual values in this column for reference: "
                f"{[r.get(column, '') for r in suggestions[:10]]}"
            )

        return result
    except Exception as e:
        return {"error": f"Failed to explore column values: {str(e)}"}


def review_data_issues(
    session: ProjectSession,
    project_type: str = "",
) -> dict:
    try:
        project, dm = require_project(session)
    except ValueError as e:
        return {"error": str(e)}

    from mcp_server.data_auditor import DataAuditor

    table_name = "events"
    try:
        sample_sql = f"SELECT * FROM {table_name} LIMIT 1"
        dm.execute(sample_sql)
    except Exception:
        return {"error": f"Table '{table_name}' not found. Load data first."}

    schema_sql = f"SELECT * FROM {table_name} LIMIT 100"
    sample_data = dm.execute(schema_sql)

    columns = []
    if sample_data:
        keys = list(sample_data[0].keys())
        for col_name in keys:
            col_sql = f'SELECT COUNT(DISTINCT "{col_name}") AS unique_count, SUM(CASE WHEN "{col_name}" IS NULL THEN 1 ELSE 0 END) AS null_count, COUNT(*) AS total FROM {table_name}'
            stats = dm.execute(col_sql)
            row = stats[0] if stats else {}
            total = row.get("total", 0) or 1
            unique_count = row.get("unique_count", 0)
            null_count = row.get("null_count", 0)

            type_sql = f'SELECT "{col_name}" FROM {table_name} WHERE "{col_name}" IS NOT NULL LIMIT 5'
            samples = dm.execute(type_sql)
            sample_vals = [str(r.get(col_name, "")) for r in samples]

            is_numeric = False
            is_date = False
            for v in sample_vals:
                try:
                    float(v)
                    is_numeric = True
                    break
                except (ValueError, TypeError):
                    pass

            columns.append({
                "name": col_name,
                "unique_count": unique_count,
                "unique_rate": round(unique_count / total, 4),
                "null_count": null_count,
                "null_rate": round(null_count / total, 4),
                "is_numeric": is_numeric,
                "is_date": is_date,
                "sample_values": sample_vals,
            })

    auditor = DataAuditor()
    issues = auditor.deep_audit(
        execute_fn=dm.execute,
        table_name=table_name,
        columns=columns,
        project_type=project_type,
    )

    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]
    infos = [i for i in issues if i.get("severity") == "info"]

    summary = (
        f"数据质量检查完成。发现 {len(errors)} 个错误、{len(warnings)} 个警告、{len(infos)} 个建议。\n"
    )
    if errors:
        summary += f"\n⚠️ 错误（建议修复后再继续）:\n"
        for e in errors[:5]:
            summary += f"  - {e['name']}: {e['description']}\n"
    if warnings:
        summary += f"\n⚠ 警告（建议确认）:\n"
        for w in warnings[:5]:
            summary += f"  - {w['name']}: {w['description']}\n"

    derived = [i for i in issues if i.get("type") == "derived_column_suggestion"]
    rules = [i for i in issues if i.get("type") == "business_rule"]

    return {
        "project_id": project.id,
        "total_issues": len(issues),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "derived_column_suggestions": derived,
        "business_rules": rules,
        "summary": summary,
        "message": (
            "请向用户展示以上问题，逐个确认处理方式。"
            "对于错误级别问题，建议修复后再继续。"
            "对于派生列建议，确认是否需要添加。"
        ),
    }
