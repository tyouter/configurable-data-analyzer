# -*- coding: utf-8 -*-
"""
Semantic Layer Generator: LLM-assisted generation of project semantic layer.

When a user imports data, this module:
1. Analyzes the schema (columns, types, sample values, statistics)
2. Sends schema to LLM for semantic interpretation
3. Generates a complete semantic layer (columns, metrics, event definitions, examples)
4. Supports multiple project types with type-specific templates
"""

import os
import sys
import json
import re

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.project_model import Project, ProjectStore, ProjectDataManager

DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.environ.get("BI_MODEL", "deepseek-chat")

SCHEMA_ANALYSIS_PROMPT = """You are a senior data analyst. Analyze the following dataset schema and generate a comprehensive semantic layer definition.

## Dataset Schema
Table name: {table_name}
Project type: {project_type}
Total rows: {total_rows}
Total columns: {total_columns}

## Column Details
{columns_detail}

## Sample Data (first 3 rows)
{sample_data}

## Basic Statistics
{statistics}

## Task
Generate a semantic layer definition in YAML format with the following sections:

1. **table_name**: A descriptive table name
2. **columns**: For each column, provide:
   - business_name: Chinese business name (中文业务名称)
   - type: data type (string/integer/float/date/timestamp/boolean)
   - role: dimension or measure
   - description: Chinese description of what this column means
   - derived: true if this is a computed column (set to false for raw columns)
   - enum: list of possible values if cardinality < 20 (optional)

3. **metrics**: Define 5-15 key business metrics. For each:
   - business_name: Chinese metric name
   - sql: DuckDB SQL expression for this metric
   - keywords: Chinese keywords that users might use to ask about this metric
   - description: How this metric is calculated (Chinese)

4. **event_definitions** (only for behavior_analysis type): If the data contains event-like rows with an event name column, define each event type:
   - business_name: Chinese event name
   - description: What this event means
   - category: Event category
   - aliases: Alternative names users might use

5. **examples**: 5-10 example natural language queries that users might ask about this data, in Chinese.

6. **rules**: Data analysis rules and constraints (e.g., "Only SELECT queries allowed", "Column X is often NULL for event type Y")

7. **project_type_suggestion**: Based on the data, suggest the most appropriate project type from: behavior_analysis, business_report, time_series, generic

## Important Guidelines
- All business names and descriptions should be in Chinese
- Metrics should cover common analytical patterns: counts, averages, rates, trends
- For event data, identify the event name column and enumerate event types
- Consider date/time columns for trend analysis
- Consider user ID columns for DAU/retention analysis
- If there's a column that looks like a duration or time span, suggest avg/percentile metrics
- Keywords should include both Chinese and English terms users might use

Respond with valid YAML only, no markdown fences."""

SCHEMA_ANALYSIS_PROMPT_WITH_REFS = """You are a senior data analyst. Analyze the following dataset schema and generate a comprehensive semantic layer definition.

## Dataset Schema
Table name: {table_name}
Project type: {project_type}
Total rows: {total_rows}
Total columns: {total_columns}

## Column Details
{columns_detail}

## Sample Data (first 3 rows)
{sample_data}

## Basic Statistics
{statistics}

## Reference Documents (IMPORTANT - use these as constraints)
{reference_context}

## Task
Generate a semantic layer definition in YAML format with the following sections:

1. **table_name**: A descriptive table name
2. **columns**: For each column, provide:
   - business_name: Chinese business name
   - type: data type (string/integer/float/date/timestamp/boolean)
   - role: dimension or measure
   - description: Chinese description (prefer definitions from reference documents)
   - derived: true if this is a computed column
   - enum: list of possible values if cardinality < 20

3. **metrics**: Define metrics based on BOTH the data schema AND the KPI definitions from reference documents. For each metric:
   - business_name: Chinese metric name (use names from KPI definitions if available)
   - sql: DuckDB SQL expression (MUST use column names from the schema above)
   - keywords: Chinese keywords for this metric
   - description: How this metric is calculated (include KPI caliber/口径 from reference docs)

4. **event_definitions** (only for behavior_analysis type): Define events based on the event definitions from reference documents.

5. **examples**: 5-10 example queries users might ask, in Chinese.

6. **rules**: Data analysis rules including any business rules from reference documents.

## Critical Rules
- You MUST use the KPI definitions from reference documents as the primary source for metrics
- Each metric's SQL formula MUST use actual column names from the schema (not descriptions)
- If a KPI definition references an event name, use it in a CASE WHEN or FILTER clause
- Preserve the exact business names and caliber descriptions from the reference documents
- All business names and descriptions should be in Chinese

Respond with valid YAML only, no markdown fences."""


TYPE_TEMPLATES = {
    "behavior_analysis": {
        "description": "用户行为分析项目 — 适用于埋点数据、事件流数据",
        "required_columns": {
            "event_name_col": "事件名称列（如 span_name, event_type）",
            "user_id_col": "用户标识列（如 user_id, reduser_id）",
            "timestamp_col": "时间戳列（如 start_time, event_time）",
        },
        "default_metrics": {
            "dau": {"sql": "COUNT(DISTINCT {user_id_col})", "business_name": "日活用户"},
            "total_events": {"sql": "COUNT(*)", "business_name": "总事件数"},
            "avg_events_per_user": {"sql": "CAST(COUNT(*) AS DOUBLE) / COUNT(DISTINCT {user_id_col})", "business_name": "人均事件数"},
        },
        "analysis_templates": ["retention", "funnel", "period_over_period"],
    },
    "business_report": {
        "description": "业务报表项目 — 适用于销售数据、运营指标等",
        "required_columns": {
            "date_col": "日期列",
            "metric_cols": "指标列（金额、数量等）",
        },
        "default_metrics": {
            "total": {"sql": "SUM({metric_col})", "business_name": "总计"},
            "average": {"sql": "AVG({metric_col})", "business_name": "平均值"},
        },
        "analysis_templates": ["period_over_period"],
    },
    "time_series": {
        "description": "时序数据项目 — 适用于传感器数据、监控数据等",
        "required_columns": {
            "timestamp_col": "时间戳列",
            "value_col": "数值列",
        },
        "default_metrics": {
            "avg_value": {"sql": "AVG({value_col})", "business_name": "平均值"},
            "max_value": {"sql": "MAX({value_col})", "business_name": "最大值"},
            "min_value": {"sql": "MIN({value_col})", "business_name": "最小值"},
        },
        "analysis_templates": ["period_over_period"],
    },
    "generic": {
        "description": "通用数据项目 — 无特定类型假设",
        "required_columns": {},
        "default_metrics": {},
        "analysis_templates": [],
    },
}


def _analyze_schema(dm: ProjectDataManager) -> dict:
    schema_info = dm.get_schema_info()
    columns_detail = []
    for col in schema_info:
        line = f"- {col['column']} ({col['dtype']}, nulls={col['null_count']}): sample={col['sample']}"
        columns_detail.append(line)

    sample_data = ""
    if dm.df is not None:
        sample_rows = dm.df.head(3).to_dict(orient="records")
        sample_data = json.dumps(sample_rows, ensure_ascii=False, default=str, indent=2)

    statistics = ""
    if dm.df is not None:
        numeric_cols = dm.df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            stats = dm.df[numeric_cols].describe().to_string()
            statistics = stats

    return {
        "total_rows": dm.meta.get("total_rows", 0),
        "total_columns": dm.meta.get("total_columns", len(schema_info)),
        "columns_detail": "\n".join(columns_detail),
        "sample_data": sample_data,
        "statistics": statistics,
    }


def _call_llm(prompt: str) -> str:
    import requests

    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY environment variable is required for semantic layer generation")

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a data analyst expert. Respond with valid YAML only."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise Exception(f"LLM API error: {response.status_code} - {response.text[:500]}")

    result = response.json()
    content = result["choices"][0]["message"]["content"]

    if content.startswith("```"):
        content = re.sub(r"^```(?:yaml)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)

    return content.strip()


def generate_basic_semantic_layer(dm: ProjectDataManager, project_type: str = "generic") -> dict:
    """
    Generate a basic semantic layer without LLM (rule-based).
    Used as fallback when LLM is not available.
    """
    schema_info = dm.get_schema_info()
    columns = {}
    metrics = {}
    event_definitions = {}

    event_name_col = None
    user_id_col = None
    timestamp_col = None
    date_cols = []
    numeric_cols = []
    category_cols = []

    for col in schema_info:
        name = col["column"]
        dtype = col["dtype"]
        samples = col["sample"]
        nulls = col["null_count"]
        total = dm.meta.get("total_rows", 1)

        name_lower = name.lower()
        col_def = {
            "business_name": name,
            "type": "string",
            "role": "dimension",
            "description": f"Column: {name}",
        }

        is_numeric = False
        if "int" in dtype.lower() or "float" in dtype.lower():
            col_def["type"] = "float" if "float" in dtype.lower() else "integer"
            is_numeric = True
            is_id_like = any(kw in name_lower for kw in [
                "id", "uid", "version", "flag", "kind", "code",
                "index", "seq", "order", "rank",
            ]) or name_lower.endswith("_num")
            if nulls < total * 0.5 and not is_id_like:
                col_def["role"] = "measure"
                numeric_cols.append(name)
            elif is_id_like:
                col_def["role"] = "dimension"
        elif "date" in dtype.lower() or "time" in dtype.lower():
            col_def["type"] = "timestamp"
            date_cols.append(name)
        elif "bool" in dtype.lower():
            col_def["type"] = "boolean"
        else:
            if isinstance(samples, list) and 0 < len(set(str(s) for s in samples if s)) < 20:
                col_def["enum"] = sorted(set(str(s) for s in samples if s))
                category_cols.append(name)

        if any(kw in name_lower for kw in ["event", "span", "action"]):
            if "name" in name_lower or "type" in name_lower:
                if event_name_col is None or "name" in name_lower:
                    event_name_col = name
        name_parts = set(name_lower.split("_"))
        if (any(p in name_parts for p in ["uid", "userid"])
            or ("user" in name_parts and "id" in name_parts)
            or name_lower.endswith("_uid")
            or name_lower.endswith("_customer_id") or name_lower.endswith("_member_id")
            or name_lower == "reduser_id"):
            user_id_col = name
        if any(kw in name_lower for kw in ["time", "timestamp", "date", "created_at", "order_date"]):
            if not timestamp_col:
                timestamp_col = name

        columns[name] = col_def

    if timestamp_col and timestamp_col not in date_cols:
        date_cols.append(timestamp_col)

    if user_id_col:
        metrics["dau"] = {
            "business_name": "日活用户",
            "sql": f"COUNT(DISTINCT {user_id_col})",
            "keywords": ["日活", "DAU", "活跃用户", "daily active"],
            "description": f"按天去重统计 {user_id_col} 数量",
        }
        metrics["total_users"] = {
            "business_name": "总用户数",
            "sql": f"COUNT(DISTINCT {user_id_col})",
            "keywords": ["总用户", "用户总数", "total users"],
            "description": f"全部去重 {user_id_col} 数量",
        }
        metrics["avg_events_per_user"] = {
            "business_name": "人均事件数",
            "sql": f"CAST(COUNT(*) AS DOUBLE) / COUNT(DISTINCT {user_id_col})",
            "keywords": ["人均", "平均", "per user"],
            "description": "总事件数 / 去重用户数",
        }

    metrics["total_events"] = {
        "business_name": "总事件数",
        "sql": "COUNT(*)",
        "keywords": ["事件数", "总数", "total", "count"],
        "description": "总行数",
    }

    if project_type == "behavior_analysis" and event_name_col:
        event_strs = []
        if dm.df is not None and event_name_col in dm.df.columns:
            event_strs = [str(e) for e in dm.df[event_name_col].dropna().unique()]
        elif dm.con is not None:
            try:
                table_name = dm.project.semantic_layer.get("table_name", "events")
                rows = dm.con.execute(
                    f'SELECT DISTINCT "{event_name_col}" FROM {table_name} WHERE "{event_name_col}" IS NOT NULL LIMIT 200'
                ).fetchall()
                event_strs = [str(r[0]) for r in rows]
            except Exception:
                pass

        if event_strs:
            page_show_events = [e for e in event_strs if "_pageshow" in e or "_pageview" in e]
            click_events = [e for e in event_strs if "_click" in e]
            card_show_events = [e for e in event_strs if "_cardshow" in e or "_carshow" in e]
            search_events = [e for e in event_strs if "search" in e.lower()]
            navigation_events = [e for e in event_strs if "navigation" in e.lower()]
            like_events = [e for e in event_strs if "like" in e.lower()]
            save_events = [e for e in event_strs if "save" in e.lower()]

            if page_show_events:
                metrics["page_views"] = {
                    "business_name": "页面浏览次数",
                    "sql": f"COUNT(*) FILTER (WHERE {event_name_col} IN ({', '.join(repr(e) for e in page_show_events)}))",
                    "keywords": ["页面浏览", "浏览", "PV", "页面展示"],
                    "description": "所有页面展示事件的次数",
                }
            if click_events:
                metrics["total_clicks"] = {
                    "business_name": "总点击次数",
                    "sql": f"COUNT(*) FILTER (WHERE {event_name_col} LIKE '%_click')",
                    "keywords": ["点击", "click", "总点击"],
                    "description": "所有点击事件的次数",
                }
            if card_show_events:
                metrics["card_impressions"] = {
                    "business_name": "卡片曝光次数",
                    "sql": f"COUNT(*) FILTER (WHERE {event_name_col} IN ({', '.join(repr(e) for e in card_show_events)}))",
                    "keywords": ["卡片曝光", "曝光", "card show"],
                    "description": "所有卡片曝光事件的次数",
                }
            if search_events:
                metrics["search_queries"] = {
                    "business_name": "搜索次数",
                    "sql": f"COUNT(*) FILTER (WHERE {event_name_col} LIKE '%search%')",
                    "keywords": ["搜索", "查询", "search"],
                    "description": "搜索相关事件的次数",
                }
            if navigation_events:
                nav_confirm_events = [e for e in navigation_events if "confirm" in e.lower()]
                if nav_confirm_events:
                    metrics["navigation_confirms"] = {
                        "business_name": "导航确认次数",
                        "sql": f"COUNT(*) FILTER (WHERE {event_name_col} LIKE '%navigation%confirm%')",
                        "keywords": ["导航确认", "确认导航", "navigation confirm"],
                        "description": "用户确认发起导航的次数",
                    }
                metrics["navigation_initiations"] = {
                    "business_name": "导航发起次数",
                    "sql": f"COUNT(*) FILTER (WHERE {event_name_col} LIKE '%navigation_button_click')",
                    "keywords": ["导航", "发起导航", "navigation"],
                    "description": "用户点击导航按钮的次数",
                }
            if like_events:
                metrics["post_likes"] = {
                    "business_name": "点赞次数",
                    "sql": f"COUNT(*) FILTER (WHERE {event_name_col} LIKE '%like%click')",
                    "keywords": ["点赞", "喜欢", "like"],
                    "description": "点赞事件的次数",
                }
            if save_events:
                metrics["post_saves"] = {
                    "business_name": "收藏次数",
                    "sql": f"COUNT(*) FILTER (WHERE {event_name_col} LIKE '%save%click')",
                    "keywords": ["收藏", "保存", "save"],
                    "description": "收藏事件的次数",
                }

            pages = set()
            for e in event_strs:
                parts = e.split("_")
                if len(parts) >= 2:
                    pages.add("_".join(parts[:2]))
            for page in sorted(pages)[:10]:
                safe_page = re.sub(r'[^a-zA-Z0-9_]', '_', page)
                page_events = [e for e in event_strs if e.startswith(page + "_")]
                if page_events:
                    metrics[f"{safe_page}_views"] = {
                        "business_name": f"{page}页浏览次数",
                        "sql": f"COUNT(*) FILTER (WHERE {event_name_col} LIKE '{page}%')",
                        "keywords": [page, f"{page}页", "浏览"],
                        "description": f"{page} 页面相关事件的次数",
                    }

    for nc in numeric_cols:
        if nc == user_id_col or any(kw in nc.lower() for kw in ["id", "uid"]):
            continue

        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', nc.lower())
        if any(kw in nc.lower() for kw in ["duration", "time_spent", "elapsed"]):
            metrics[f"avg_{safe_name}"] = {
                "business_name": f"平均{nc}",
                "sql": f"AVG({nc})",
                "keywords": ["平均", nc, "average"],
                "description": f"{nc} 的平均值",
            }
            metrics[f"median_{safe_name}"] = {
                "business_name": f"{nc}中位数",
                "sql": f"MEDIAN({nc})",
                "keywords": ["中位数", nc, "median"],
                "description": f"{nc} 的中位数",
            }
        elif any(kw in nc.lower() for kw in ["amount", "revenue", "price", "cost", "sales", "income", "payment"]):
            metrics[f"total_{safe_name}"] = {
                "business_name": f"{nc}总额",
                "sql": f"SUM({nc})",
                "keywords": ["总额", "总计", nc, "total", "sum"],
                "description": f"{nc} 的总和",
            }
            metrics[f"avg_{safe_name}"] = {
                "business_name": f"平均{nc}",
                "sql": f"AVG({nc})",
                "keywords": ["平均", nc, "average"],
                "description": f"{nc} 的平均值",
            }
        elif any(kw in nc.lower() for kw in ["quantity", "count", "num", "qty"]):
            metrics[f"total_{safe_name}"] = {
                "business_name": f"{nc}总计",
                "sql": f"SUM({nc})",
                "keywords": ["总计", nc, "total"],
                "description": f"{nc} 的总和",
            }
        elif any(kw in nc.lower() for kw in ["rate", "ratio", "pct", "percent"]):
            metrics[f"avg_{safe_name}"] = {
                "business_name": f"平均{nc}",
                "sql": f"AVG({nc})",
                "keywords": ["平均", nc, "average"],
                "description": f"{nc} 的平均值",
            }

    if len(numeric_cols) > 0 and user_id_col:
        main_metric_col = None
        for nc in numeric_cols:
            if nc != user_id_col and not any(kw in nc.lower() for kw in ["id", "uid"]):
                main_metric_col = nc
                break
        if main_metric_col:
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', main_metric_col.lower())
            metrics[f"avg_{safe_name}_per_user"] = {
                "business_name": f"人均{main_metric_col}",
                "sql": f"CAST(SUM({main_metric_col}) AS DOUBLE) / COUNT(DISTINCT {user_id_col})",
                "keywords": ["人均", main_metric_col, "per user"],
                "description": f"总{main_metric_col} / 去重用户数",
            }

    if event_name_col:
        unique_event_list = []
        if dm.df is not None and event_name_col in dm.df.columns:
            unique_event_list = dm.df[event_name_col].dropna().unique()[:50]
        elif dm.con is not None:
            try:
                table_name = dm.project.semantic_layer.get("table_name", "events")
                rows = dm.con.execute(
                    f'SELECT DISTINCT "{event_name_col}" FROM {table_name} WHERE "{event_name_col}" IS NOT NULL LIMIT 50'
                ).fetchall()
                unique_event_list = [r[0] for r in rows]
            except Exception:
                pass
        for evt in unique_event_list:
            evt_str = str(evt)
            event_definitions[evt_str] = {
                "business_name": evt_str,
                "description": f"事件类型: {evt_str}",
                "category": "auto_detected",
                "aliases": [],
            }

    examples = []
    if timestamp_col:
        examples.append(f"最近7天的趋势如何？")
    if user_id_col:
        examples.append(f"今天的日活用户有多少？")
    if event_name_col:
        examples.append(f"哪种事件发生最多？")
    if numeric_cols:
        examples.append(f"各维度的数值分布如何？")
    if category_cols:
        examples.append(f"按{category_cols[0]}分组，各项指标分别是多少？")

    rules = [
        "Only SELECT queries are allowed",
        "Always use exact column names from the schema",
    ]
    if user_id_col:
        rules.append(f"User identification column: {user_id_col}")
    if timestamp_col:
        rules.append(f"Time column: {timestamp_col}")

    table_name = "events"

    return {
        "table_name": table_name,
        "columns": columns,
        "metrics": metrics,
        "event_definitions": event_definitions,
        "examples": examples,
        "rules": rules,
    }


def generate_semantic_layer_with_llm(dm: ProjectDataManager, project_type: str = "generic", reference_context: str = "") -> dict:
    """
    Generate a comprehensive semantic layer using LLM analysis.
    Falls back to rule-based generation if LLM is unavailable.
    """
    schema = _analyze_schema(dm)

    if reference_context:
        prompt = SCHEMA_ANALYSIS_PROMPT_WITH_REFS.format(
            table_name=dm.project.semantic_layer.get("table_name", "events"),
            project_type=project_type,
            total_rows=schema["total_rows"],
            total_columns=schema["total_columns"],
            columns_detail=schema["columns_detail"],
            sample_data=schema["sample_data"],
            statistics=schema["statistics"],
            reference_context=reference_context,
        )
    else:
        prompt = SCHEMA_ANALYSIS_PROMPT.format(
            table_name=dm.project.semantic_layer.get("table_name", "events"),
            project_type=project_type,
            total_rows=schema["total_rows"],
            total_columns=schema["total_columns"],
            columns_detail=schema["columns_detail"],
            sample_data=schema["sample_data"],
            statistics=schema["statistics"],
        )

    try:
        yaml_content = _call_llm(prompt)
        import yaml
        semantic = yaml.safe_load(yaml_content)

        if not isinstance(semantic, dict):
            raise ValueError("LLM did not return a valid YAML dict")

        required_keys = ["table_name", "columns", "metrics"]
        for key in required_keys:
            if key not in semantic:
                raise ValueError(f"LLM output missing required key: {key}")

        return semantic

    except Exception as e:
        print(f"[SemanticGen] LLM generation failed: {e}")
        print("[SemanticGen] Falling back to rule-based generation")
        return generate_basic_semantic_layer(dm, project_type)


def generate_semantic_layer(
    dm: ProjectDataManager,
    project_type: str = "generic",
    use_llm: bool = True,
    reference_context: str = "",
) -> dict:
    """
    Generate semantic layer for a project.
    If use_llm=True and DEEPSEEK_API_KEY is available, uses LLM.
    Otherwise falls back to rule-based generation.
    """
    if use_llm and DEEPSEEK_API_KEY:
        return generate_semantic_layer_with_llm(dm, project_type, reference_context=reference_context)
    return generate_basic_semantic_layer(dm, project_type)


def detect_project_type(dm: ProjectDataManager) -> str:
    """
    Auto-detect project type based on data schema.
    """
    if dm.df is None:
        return "generic"

    cols_lower = {c.lower(): c for c in dm.df.columns}
    col_names = set(cols_lower.keys())

    has_event_col = any(kw in " ".join(col_names) for kw in ["event", "span", "action"])
    has_user_col = any(kw in " ".join(col_names) for kw in ["user", "uid", "reduser"])
    has_time_col = any(kw in " ".join(col_names) for kw in ["time", "timestamp", "date"])

    if has_event_col and has_user_col and has_time_col:
        return "behavior_analysis"

    numeric_ratio = len(dm.df.select_dtypes(include=["number"]).columns) / max(len(dm.df.columns), 1)
    if has_time_col and numeric_ratio > 0.5:
        return "time_series"

    if has_time_col:
        return "business_report"

    return "generic"
