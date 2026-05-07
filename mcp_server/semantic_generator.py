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
import uuid
from typing import Optional

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.project_model import Project, ProjectStore, ProjectDataManager
from mcp_server import llm_client

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

## Low-Cardinality Column Values (IMPORTANT - use these for SQL patterns)
{low_card_values}

## Task
Generate a semantic layer definition in JSON format with the following sections:

1. **table_name**: A descriptive table name
2. **columns**: For each column, provide:
   - column_name: The EXACT original column name from the schema (e.g., "reduser_id", "span_name", "start_time")
   - business_name: Chinese business name (中文业务名称)
   - type: data type (string/integer/float/date/timestamp/boolean)
   - role: dimension or measure
   - description: Chinese description of what this column means
   - derived: true if this is a computed column (set to false for raw columns)
   - enum: list of possible values if cardinality < 20 (optional)

3. **metrics**: Define 15-35 key business metrics covering all analytical dimensions. For each:
   - name: A short English identifier (e.g., "dau", "total_events", "porsche_conversion_rate")
   - business_name: Chinese metric name
   - metric_type: One of "count" (absolute count), "rate" (percentage/ratio), "duration" (time), "distribution" (breakdown), "ranking" (top-N)
   - business_domain: Business domain this metric belongs to. Group related metrics into domains like: "overview" (总览), "engagement" (互动), "retention" (留存), "conversion" (转化), "revenue" (收入), "feature_X" (功能X), "distribution" (分布). Use English identifiers. Metrics about the same feature/page should share the same domain.
   - sql: DuckDB SQL AGGREGATE expression for this metric. CRITICAL: You MUST use the EXACT values from the Low-Cardinality Column Values section above for ILIKE patterns. For example, if the event names contain "porsche_page_Map_POI_Category_click", use ILIKE '%porsche%' NOT ILIKE '%porsche_plus%'. Do NOT invent event name patterns - only use patterns that match the actual values listed. Do NOT use subqueries, placeholders like {{date}}, or reference the table name. Use only column names from the schema.
   - keywords: Chinese keywords that users might use to ask about this metric
   - description: How this metric is calculated (Chinese)
   - visualization_goal: What the user wants to see when querying this metric, described in natural language (Chinese). Focus on the intent/goal, NOT a chart type. Examples: "展示总量的单一数值", "展示指标随时间的变化趋势和绝对值", "展示不同类别之间的占比构成", "展示Top N的排名对比", "展示数值的分布区间和集中趋势", "展示多个指标在不同时间段的对比". This helps the rendering layer choose the best visualization dynamically.

4. **event_definitions** (only for behavior_analysis type): If the data contains event-like rows with an event name column, define each event type:
   - event_name: The EXACT event name value from the data (e.g., "discovery_page_post_card_click")
   - business_name: Chinese event name
   - description: What this event means
   - category: Event category
   - aliases: Alternative names users might use

5. **examples**: 5-10 example natural language queries that users might ask about this data, in Chinese.

6. **rules**: Data analysis rules and constraints (e.g., "Only SELECT queries allowed", "Column X is often NULL for event type Y")

7. **project_type_suggestion**: Based on the data, suggest the most appropriate project type from: behavior_analysis, business_report, time_series, generic

8. **semantic_config** (only for behavior_analysis type): If the data has an event name column with underscore-separated names (e.g., "page_element_action"), provide a mapping configuration:
   - page_map: Map page identifiers to Chinese names (e.g., {"discovery": "发现页", "post_detail": "帖子详情页"})
   - element_map: Map element identifiers to Chinese names (e.g., {"card": "卡片", "ai_travel_guide": "AI路书"})
   - composite_pages: Multi-segment page names (e.g., {"post_detail": "帖子详情页", "search_homepage": "搜索首页"})
   - composite_elements: Multi-segment element names (e.g., {"post_card": "帖子卡片", "ai_travel_guide": "AI路书"})
   - alias_rules: Alias generation rules, each with "condition" ({"all_of": [...]} or {"contains": "..."}) and "aliases" (list of Chinese names)

## Important Guidelines
- All business names and descriptions should be in Chinese
- Metrics should cover common analytical patterns: counts, averages, rates, trends
- For event data, identify the event name column and enumerate event types
- Consider date/time columns for trend analysis
- Consider user ID columns for DAU/retention analysis
- If there's a column that looks like a duration or time span, suggest avg/percentile metrics
- Keywords should include both Chinese and English terms users might use

Respond with valid JSON only, no markdown fences."""

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

## Low-Cardinality Column Values (IMPORTANT - use these for SQL patterns)
{low_card_values}

## Reference Documents (IMPORTANT - use these as constraints)
{reference_context}

## Task
Generate a semantic layer definition in JSON format with the following sections:

1. **table_name**: A descriptive table name
2. **columns**: For each column, provide:
   - column_name: The EXACT original column name from the schema (e.g., "reduser_id", "span_name", "start_time")
   - business_name: Chinese business name
   - type: data type (string/integer/float/date/timestamp/boolean)
   - role: dimension or measure
   - description: Chinese description (prefer definitions from reference documents)
   - derived: true if this is a computed column
   - enum: list of possible values if cardinality < 20

3. **metrics**: Define 20-40 metrics based on BOTH the data schema AND the KPI definitions from reference documents. Cover ALL sections mentioned in the reference docs (summary, trends, function penetration, retention, Porsche+, conversion, ranking, etc.). For each metric:
   - name: A short English identifier (e.g., "dau", "porsche_active_rate", "ai_travel_guide_conversion")
   - business_name: Chinese metric name (use names from KPI definitions if available)
   - metric_type: One of "count" (absolute count), "rate" (percentage/ratio), "duration" (time), "distribution" (breakdown), "ranking" (top-N)
   - business_domain: Business domain this metric belongs to. Group related metrics into domains like: "overview" (总览), "engagement" (互动), "retention" (留存), "conversion" (转化), "revenue" (收入), "feature_X" (功能X), "distribution" (分布). Use English identifiers. Metrics about the same feature/page should share the same domain.
   - sql: DuckDB SQL AGGREGATE expression. CRITICAL: You MUST use the EXACT values from the Low-Cardinality Column Values section above for ILIKE patterns. For example, if the event names contain "porsche_page_Map_POI_Category_click", use ILIKE '%porsche%' NOT ILIKE '%porsche_plus%'. Do NOT invent event name patterns - only use patterns that match the actual values listed. Do NOT use subqueries, placeholders like {{date}}, or reference the table name.
   - keywords: Chinese keywords for this metric
   - description: How this metric is calculated (include KPI caliber/口径 from reference docs)
   - visualization_goal: What the user wants to see when querying this metric, described in natural language (Chinese). Focus on the intent/goal, NOT a chart type. Examples: "展示总量的单一数值", "展示指标随时间的变化趋势和绝对值", "展示不同类别之间的占比构成", "展示Top N的排名对比", "展示数值的分布区间和集中趋势", "展示多个指标在不同时间段的对比". This helps the rendering layer choose the best visualization dynamically.

4. **event_definitions** (only for behavior_analysis type): Define events based on the event definitions from reference documents. For each:
   - event_name: The EXACT event name value from the data (e.g., "discovery_page_post_card_click")

5. **examples**: 5-10 example queries users might ask, in Chinese.

6. **rules**: Data analysis rules including any business rules from reference documents.

7. **semantic_config** (only for behavior_analysis type): If the data has an event name column with underscore-separated names (e.g., "page_element_action"), provide a mapping configuration:
   - page_map: Map page identifiers to Chinese names (e.g., {"discovery": "发现页", "post_detail": "帖子详情页"})
   - element_map: Map element identifiers to Chinese names (e.g., {"card": "卡片", "ai_travel_guide": "AI路书"})
   - composite_pages: Multi-segment page names (e.g., {"post_detail": "帖子详情页", "search_homepage": "搜索首页"})
   - composite_elements: Multi-segment element names (e.g., {"post_card": "帖子卡片", "ai_travel_guide": "AI路书"})
   - alias_rules: Alias generation rules, each with "condition" ({"all_of": [...]} or {"contains": "..."}) and "aliases" (list of Chinese names)

## Critical Rules
- You MUST use the KPI definitions from reference documents as the primary source for metrics
- Each metric's SQL formula MUST use actual column names from the schema (not descriptions)
- If a KPI definition references an event name, use it in a CASE WHEN or FILTER clause
- Preserve the exact business names and caliber descriptions from the reference documents
- All business names and descriptions should be in Chinese

Respond with valid JSON only, no markdown fences."""


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
    low_card_uniques = {}

    for col in schema_info:
        col_name = col['column']
        sample_str = str(col['sample'])[:100]
        line = f"- {col_name} ({col['dtype']}, nulls={col['null_count']}): sample={sample_str}"
        columns_detail.append(line)

        if dm.con is not None:
            dtype_upper = col['dtype'].upper()
            is_varchar = "VARCHAR" in dtype_upper or col['dtype'] == 'object' or col['dtype'] == 'string'
            if is_varchar:
                try:
                    table_name = dm.get_full_semantic_layer().get("table_name", "events")
                    n_unique = dm.con.execute(
                        f'SELECT COUNT(DISTINCT "{col_name}") FROM {table_name} WHERE "{col_name}" IS NOT NULL'
                    ).fetchone()[0]
                    if 2 <= n_unique <= 200:
                        rows = dm.con.execute(
                            f'SELECT DISTINCT "{col_name}" FROM {table_name} WHERE "{col_name}" IS NOT NULL ORDER BY "{col_name}" LIMIT 200'
                        ).fetchall()
                        sorted_vals = sorted([str(r[0]) for r in rows])
                        low_card_uniques[col_name] = sorted_vals
                except Exception:
                    pass

    sample_data = ""
    if dm.con is not None:
        try:
            table_name = dm.get_full_semantic_layer().get("table_name", "events")
            sample_rows = dm.con.execute(f"SELECT * FROM {table_name} LIMIT 2").fetchall()
            col_names = [desc[0] for desc in dm.con.description]
            records = [dict(zip(col_names, row)) for row in sample_rows]
            sample_data = json.dumps(records, ensure_ascii=False, default=str, indent=2)
            if len(sample_data) > 3000:
                sample_data = sample_data[:3000] + "\n... (truncated)"
        except Exception:
            pass

    statistics = ""
    if dm.con is not None:
        try:
            table_name = dm.get_full_semantic_layer().get("table_name", "events")
            numeric_cols = dm.meta.get("numeric_columns", [])
            if numeric_cols:
                stat_parts = []
                for nc in numeric_cols:
                    row = dm.con.execute(
                        f'SELECT COUNT("{nc}"), AVG(CAST("{nc}" AS DOUBLE)), MIN(CAST("{nc}" AS DOUBLE)), MAX(CAST("{nc}" AS DOUBLE)), STDDEV(CAST("{nc}" AS DOUBLE)) FROM {table_name} WHERE "{nc}" IS NOT NULL'
                    ).fetchone()
                    stat_parts.append(f"{nc}: count={row[0]}, mean={row[1]:.4f}, min={row[2]}, max={row[3]}, std={row[4]:.4f}" if row[0] else f"{nc}: no data")
                statistics = "\n".join(stat_parts)
                if len(statistics) > 2000:
                    statistics = statistics[:2000] + "\n... (truncated)"
        except Exception:
            pass

    low_card_detail = ""
    if low_card_uniques:
        parts = []
        for col_name, vals in low_card_uniques.items():
            val_str = ", ".join(vals[:150])
            if len(vals) > 150:
                val_str += f", ... ({len(vals)} total)"
            parts.append(f"- {col_name} ({len(vals)} unique values): [{val_str}]")
        low_card_detail = "\n".join(parts)

    return {
        "total_rows": dm.meta.get("total_rows", 0),
        "total_columns": dm.meta.get("total_columns", len(schema_info)),
        "columns_detail": "\n".join(columns_detail),
        "sample_data": sample_data,
        "statistics": statistics,
        "low_cardinality_values": low_card_detail,
    }


def _repair_truncated_json(content: str) -> Optional[dict]:
    import re
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    s = content.rstrip()
    s = re.sub(r',\s*$', '', s)

    in_str = False
    escape = False
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str

    if in_str:
        last_quote = s.rfind('"')
        if last_quote > 0:
            s = s[:last_quote]
            in_str = False

    s = re.sub(r',\s*$', '', s)

    open_b = s.count('{') - s.count('}')
    open_br = s.count('[') - s.count(']')

    if open_br > 0:
        s += ']' * open_br
    if open_b > 0:
        s += '}' * open_b

    try:
        result = json.loads(s)
        return result
    except json.JSONDecodeError:
        pass

    last_brace = s.rfind('}')
    if last_brace > 0:
        candidate = s[:last_brace + 1]
        open_b2 = candidate.count('{') - candidate.count('}')
        open_br2 = candidate.count('[') - candidate.count(']')
        if open_br2 > 0:
            candidate += ']' * open_br2
        if open_b2 > 0:
            candidate += '}' * open_b2
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def _call_llm(prompt: str) -> str:
    return llm_client.call_llm(
        prompt=prompt,
        system_msg="You are a data analyst expert. Respond with valid JSON only, no markdown fences.",
        max_tokens=32768,
        temperature=0.3,
        timeout=180,
        strip_markdown=True,
    )


_DEFAULT_SEMANTIC_CONFIG = {
    "action_type_map": {
        "show": "曝光",
        "click": "点击",
        "cardshow": "卡片曝光",
        "carshow": "卡片曝光",
        "pageshow": "页面浏览",
        "pageview": "页面浏览",
        "pageslide": "页面滑动",
        "swipe": "滑动",
        "scroll": "滚动",
        "submit": "提交",
        "confirm": "确认",
        "cancel": "取消",
        "close": "关闭",
        "delete": "删除",
        "save": "保存",
        "share": "分享",
        "download": "下载",
        "upload": "上传",
        "play": "播放",
        "pause": "暂停",
        "refresh": "刷新",
        "search": "搜索",
        "generate": "生成",
        "add": "添加",
        "create": "创建",
        "edit": "编辑",
        "update": "更新",
        "select": "选择",
        "switch": "切换",
        "login": "登录",
        "logout": "登出",
        "register": "注册",
        "auth": "认证",
    },
    "page_map": {},
    "element_map": {
        "card": "卡片",
        "button": "按钮",
        "icon": "图标",
        "tab": "标签页",
        "link": "链接",
        "image": "图片",
        "video": "视频",
        "body": "内容区",
        "header": "头部",
        "footer": "底部",
        "sidebar": "侧边栏",
        "popup": "弹窗",
        "modal": "弹窗",
        "dialog": "对话框",
        "form": "表单",
        "input": "输入框",
        "map": "地图",
        "category": "分类",
        "account": "账号",
    },
    "composite_pages": {},
    "composite_elements": {},
    "dedup_words": ["卡片", "按钮", "图标", "标签", "弹窗", "链接"],
    "alias_rules": [],
    "category_rules": {
        "exposure": ["show", "cardshow", "carshow", "pageshow", "pageview"],
        "interaction": ["click", "confirm", "submit"],
        "navigation": ["pageslide", "swipe", "scroll", "pull_to_refresh"],
        "conversion": ["save", "share", "download", "generate", "create", "add"],
        "authentication": ["login", "register", "auth"],
    },
}


def load_semantic_config(project_dir: str) -> dict:
    config_path = os.path.join(project_dir, "semantic_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            project_config = json.load(f)
        merged = json.loads(json.dumps(_DEFAULT_SEMANTIC_CONFIG))
        for key in ("action_type_map", "page_map", "element_map",
                     "composite_pages", "composite_elements",
                     "dedup_words", "alias_rules", "category_rules"):
            if key in project_config:
                if isinstance(merged.get(key), dict) and isinstance(project_config[key], dict):
                    merged[key].update(project_config[key])
                else:
                    merged[key] = project_config[key]
        return merged
    return json.loads(json.dumps(_DEFAULT_SEMANTIC_CONFIG))


def _parse_event_name(event_name: str, config: dict = None) -> dict:
    if config is None:
        config = _DEFAULT_SEMANTIC_CONFIG

    action_type_map = config.get("action_type_map", {})
    page_map = config.get("page_map", {})
    element_map = config.get("element_map", {})
    composite_pages = config.get("composite_pages", {})
    composite_elements = config.get("composite_elements", {})
    dedup_words = config.get("dedup_words", [])
    alias_rules = config.get("alias_rules", [])
    category_rules = config.get("category_rules", {})

    parts = event_name.split("_")
    parts_lower = [p.lower() for p in parts]

    action_type = ""
    page = ""
    element = ""

    for i, p in enumerate(parts_lower):
        if p in action_type_map:
            action_type = p

    for i, p in enumerate(parts_lower):
        if p in page_map and not page:
            page = p

    max_composite_len = max(
        max((k.count("_") + 1 for k in composite_pages), default=1),
        max((k.count("_") + 1 for k in composite_elements), default=1),
    )
    for seg_len in range(max_composite_len, 1, -1):
        for i in range(len(parts_lower) - seg_len + 1):
            composite = "_".join(parts_lower[i:i + seg_len])
            if composite in composite_pages and not page:
                page = composite

    for seg_len in range(max_composite_len, 1, -1):
        for i in range(len(parts_lower) - seg_len + 1):
            composite = "_".join(parts_lower[i:i + seg_len])
            if composite in composite_elements and not element:
                element = composite

    for i, p in enumerate(parts_lower):
        if p in element_map and not element:
            element = p

    action_cn = action_type_map.get(action_type, action_type)
    page_cn = page_map.get(page, page) or (parts_lower[0] if parts_lower else "")
    element_cn = element_map.get(element, element)

    if element_cn and action_cn and element_cn in action_cn:
        action_cn = action_cn.replace(element_cn, "")
    elif element_cn and action_cn:
        for word in dedup_words:
            if element_cn.endswith(word) and action_cn.startswith(word):
                action_cn = action_cn[len(word):]
                break
    if page_cn and element_cn and page_cn == element_cn:
        element_cn = ""

    if action_cn and page_cn and element_cn:
        business_name = f"{page_cn}{element_cn}{action_cn}"
    elif action_cn and page_cn:
        business_name = f"{page_cn}{action_cn}"
    elif action_cn and element_cn:
        business_name = f"{element_cn}{action_cn}"
    elif action_cn:
        business_name = action_cn
    else:
        business_name = event_name

    category = "unknown"
    for cat_name, action_list in category_rules.items():
        if action_type in action_list:
            category = cat_name
            break

    aliases = []
    name_lower = event_name.lower()
    for rule in alias_rules:
        cond = rule.get("condition", {})
        matched = True
        if "all_of" in cond:
            matched = all(w in parts_lower for w in cond["all_of"])
        if "contains" in cond:
            matched = cond["contains"] in name_lower
        if matched:
            aliases.extend(rule.get("aliases", []))

    description = f"{business_name}"
    if action_type and page_cn:
        description = f"在{page_cn}上的{element_cn or '元素'}{action_cn}事件"

    return {
        "business_name": business_name,
        "description": description,
        "category": category,
        "aliases": aliases,
        "action_type": action_type,
        "page": page,
        "element": element,
    }


def _generate_conversion_metrics(
    metrics: dict,
    event_name_col: str,
    event_list: list,
    event_definitions: dict,
) -> None:
    show_events = {}
    click_events = {}

    for evt in event_list:
        evt_str = str(evt)
        parsed = event_definitions.get(evt_str, {})
        action = parsed.get("action_type", "")
        category = parsed.get("category", "")
        page = parsed.get("page", "")
        element = parsed.get("element", "")

        if category == "exposure" and action in ("show", "cardshow", "carshow"):
            key = f"{page}_{element}" if element else page
            show_events[key] = evt_str
        elif category == "interaction" and action == "click":
            key = f"{page}_{element}" if element else page
            click_events[key] = evt_str

    matched_keys = set(show_events.keys()) & set(click_events.keys())

    for key in matched_keys:
        show_evt = show_events[key]
        click_evt = click_events[key]

        show_parsed = event_definitions.get(show_evt, {})
        click_parsed = event_definitions.get(click_evt, {})

        show_bn = show_parsed.get("business_name", show_evt)
        click_bn = click_parsed.get("business_name", click_evt)

        safe_key = re.sub(r'[^a-zA-Z0-9_]', '_', key.lower())
        metric_name = f"{safe_key}_conversion_rate"

        if metric_name in metrics:
            continue

        metrics[metric_name] = {
            "business_name": f"{click_bn}转化率",
            "sql": (
                f"CAST(COUNT(CASE WHEN {event_name_col} = '{click_evt}' THEN 1 END) AS DOUBLE)"
                f" / NULLIF(COUNT(CASE WHEN {event_name_col} = '{show_evt}' THEN 1 END), 0)"
                f" * 100"
            ),
            "keywords": ["转化率", click_bn, show_bn, "conversion"],
            "description": f"{click_bn}次数 / {show_bn}次数 × 100",
        }

    confirm_events = {}
    for evt in event_list:
        evt_str = str(evt)
        parsed = event_definitions.get(evt_str, {})
        action = parsed.get("action_type", "")
        if action == "confirm":
            page = parsed.get("page", "")
            element = parsed.get("element", "")
            key = f"{page}_{element}" if element else page
            confirm_events[key] = evt_str

    for key in set(click_events.keys()) & set(confirm_events.keys()):
        click_evt = click_events[key]
        confirm_evt = confirm_events[key]

        click_parsed = event_definitions.get(click_evt, {})
        confirm_parsed = event_definitions.get(confirm_evt, {})

        safe_key = re.sub(r'[^a-zA-Z0-9_]', '_', key.lower())
        metric_name = f"{safe_key}_confirm_rate"

        if metric_name in metrics:
            continue

        metrics[metric_name] = {
            "business_name": f"{confirm_parsed.get('business_name', confirm_evt)}确认率",
            "sql": (
                f"CAST(COUNT(CASE WHEN {event_name_col} = '{confirm_evt}' THEN 1 END) AS DOUBLE)"
                f" / NULLIF(COUNT(CASE WHEN {event_name_col} = '{click_evt}' THEN 1 END), 0)"
                f" * 100"
            ),
            "keywords": ["确认率", click_parsed.get("business_name", ""), "confirm rate"],
            "description": f"确认次数 / 点击次数 × 100",
        }


def _save_semantic_config(project_dir: str, llm_config: dict) -> None:
    existing = {}
    config_path = os.path.join(project_dir, "semantic_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    for key in ("page_map", "element_map", "composite_pages", "composite_elements", "alias_rules"):
        if key in llm_config:
            if isinstance(llm_config[key], dict) and isinstance(existing.get(key), dict):
                existing.setdefault(key, {}).update(llm_config[key])
            else:
                existing[key] = llm_config[key]

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"[SemanticGen] Saved semantic_config.json to {project_dir}")


def _extract_dimensions(columns: dict) -> dict:
    dimensions = {}
    for col_name, col_info in columns.items():
        if col_info.get("role") == "dimension" and not col_info.get("derived"):
            dimensions[col_name] = {
                "business_name": col_info.get("business_name", col_name),
                "type": col_info.get("type", "string"),
                "description": col_info.get("description", ""),
            }
    return dimensions


def _save_full_semantic_config(project_dir: str, semantic: dict) -> None:
    config = {}

    config_path = os.path.join(project_dir, "semantic_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

    if semantic.get("columns"):
        config["columns"] = semantic["columns"]
    if semantic.get("event_definitions"):
        config["events"] = semantic["event_definitions"]
    if semantic.get("metrics"):
        config["metrics"] = semantic["metrics"]
    if semantic.get("columns"):
        config["dimensions"] = _extract_dimensions(semantic["columns"])

    if "semantic_config" in semantic:
        for key in ("page_map", "element_map", "composite_pages",
                     "composite_elements", "alias_rules", "category_rules",
                     "dedup_words", "action_type_map"):
            if key in semantic["semantic_config"]:
                config[key] = semantic["semantic_config"][key]

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"[SemanticGen] Saved full semantic_config.json to {project_dir}")


def generate_basic_semantic_layer(dm: ProjectDataManager, project_type: str = "generic") -> dict:
    """
    Generate a basic semantic layer without LLM (rule-based).
    Used as fallback when LLM is not available.
    """
    config = load_semantic_config(dm.project_dir)

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
        if dm.con is not None:
            try:
                table_name = dm.get_full_semantic_layer().get("table_name", "events")
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
        if dm.con is not None:
            try:
                table_name = dm.get_full_semantic_layer().get("table_name", "events")
                rows = dm.con.execute(
                    f'SELECT DISTINCT "{event_name_col}" FROM {table_name} WHERE "{event_name_col}" IS NOT NULL LIMIT 50'
                ).fetchall()
                unique_event_list = [r[0] for r in rows]
            except Exception:
                pass
        for evt in unique_event_list:
            evt_str = str(evt)
            parsed = _parse_event_name(evt_str, config)
            event_definitions[evt_str] = {
                "business_name": parsed["business_name"],
                "description": parsed["description"],
                "category": parsed["category"],
                "aliases": parsed["aliases"],
                "action_type": parsed["action_type"],
                "page": parsed["page"],
                "element": parsed["element"],
            }

        if project_type == "behavior_analysis":
            _generate_conversion_metrics(
                metrics, event_name_col, unique_event_list, event_definitions
            )

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

    semantic = {
        "table_name": table_name,
        "columns": columns,
        "metrics": metrics,
        "event_definitions": event_definitions,
        "examples": examples,
        "rules": rules,
    }

    _save_full_semantic_config(dm.project_dir, semantic)
    semantic["config_file"] = "semantic_config.json"

    return semantic


def generate_semantic_layer_with_llm(dm: ProjectDataManager, project_type: str = "generic", reference_context: str = "") -> dict:
    """
    Generate a comprehensive semantic layer using LLM analysis.
    Falls back to rule-based generation if LLM is unavailable.
    """
    schema = _analyze_schema(dm)
    table_name = dm.get_full_semantic_layer().get("table_name", "events")

    low_card = schema.get("low_cardinality_values", "")

    if reference_context:
        prompt = SCHEMA_ANALYSIS_PROMPT_WITH_REFS.replace("{table_name}", table_name).replace("{project_type}", project_type).replace("{total_rows}", str(schema["total_rows"])).replace("{total_columns}", str(schema["total_columns"])).replace("{columns_detail}", schema["columns_detail"]).replace("{sample_data}", schema["sample_data"]).replace("{statistics}", schema["statistics"]).replace("{low_card_values}", low_card).replace("{reference_context}", reference_context)
    else:
        prompt = SCHEMA_ANALYSIS_PROMPT.replace("{table_name}", table_name).replace("{project_type}", project_type).replace("{total_rows}", str(schema["total_rows"])).replace("{total_columns}", str(schema["total_columns"])).replace("{columns_detail}", schema["columns_detail"]).replace("{sample_data}", schema["sample_data"]).replace("{statistics}", schema["statistics"]).replace("{low_card_values}", low_card)

    try:
        yaml_content = _call_llm(prompt)
        print(f"[SemanticGen] LLM returned {len(yaml_content)} chars")
        print(f"[SemanticGen] First 500 chars: {yaml_content[:500]}")

        content = yaml_content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
            content = content.strip()

        content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', content)

        try:
            semantic = json.loads(content)
        except json.JSONDecodeError as je:
            print(f"[SemanticGen] JSON parse failed: {je}")
            repaired = _repair_truncated_json(content)
            if repaired is not None:
                semantic = repaired
                print("[SemanticGen] JSON repaired from truncated output")
            else:
                for _ in range(3):
                    content += "}"
                    try:
                        semantic = json.loads(content)
                        print("[SemanticGen] JSON repaired by closing braces")
                        break
                    except json.JSONDecodeError:
                        continue
                else:
                    raise RuntimeError(f"[SemanticGen] JSON repair failed: {je}")

        if not isinstance(semantic, dict):
            print(f"[SemanticGen] Parsed type: {type(semantic)}, value: {str(semantic)[:200]}")
            raise ValueError("LLM did not return a valid JSON dict")

        required_keys = ["table_name", "columns", "metrics"]
        for key in required_keys:
            if key not in semantic:
                raise ValueError(f"LLM output missing required key: {key}")

        semantic["table_name"] = "events"

        if isinstance(semantic.get("columns"), list):
            cols_dict = {}
            for col in semantic["columns"]:
                col_name = col.pop("column_name", None) or col.pop("name", None) or col.get("business_name", "")
                if col_name:
                    cols_dict[col_name] = col
            semantic["columns"] = cols_dict

        if isinstance(semantic.get("metrics"), list):
            metrics_dict = {}
            for i, m in enumerate(semantic["metrics"]):
                metric_name = m.pop("name", None) or m.pop("metric_name", None) or m.get("business_name", "")
                safe_name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_]', '_', metric_name) if metric_name else f"metric_{i}"
                if safe_name in metrics_dict:
                    safe_name = f"{safe_name}_{i}"
                if safe_name:
                    metrics_dict[safe_name] = m
            semantic["metrics"] = metrics_dict

        if isinstance(semantic.get("event_definitions"), list):
            events_dict = {}
            for e in semantic["event_definitions"]:
                evt_name = e.pop("event_name", None) or e.pop("name", None) or e.get("business_name", "")
                if evt_name:
                    events_dict[evt_name] = e
            semantic["event_definitions"] = events_dict

        columns = semantic.get("columns", {})
        has_event_date = any("event_date" in str(k) or "日期" in str(v.get("business_name", "")) for k, v in (columns.items() if isinstance(columns, dict) else []))
        has_event_hour = any("event_hour" in str(k) or "小时" in str(v.get("business_name", "")) for k, v in (columns.items() if isinstance(columns, dict) else []))

        time_cols = [k for k, v in (columns.items() if isinstance(columns, dict) else []) if "time" in k.lower() or "时间" in str(v.get("business_name", ""))]
        if time_cols and not has_event_date:
            src_col = time_cols[0]
            columns["event_date"] = {
                "business_name": "事件日期",
                "type": "date",
                "role": "dimension",
                "description": f"从{src_col}提取的日期",
                "derived": True,
                "derived_from": src_col,
                "derivation_logic": "date",
            }
        if time_cols and not has_event_hour:
            src_col = time_cols[0]
            columns["event_hour"] = {
                "business_name": "事件小时",
                "type": "integer",
                "role": "dimension",
                "description": f"从{src_col}提取的小时",
                "derived": True,
                "derived_from": src_col,
                "derivation_logic": "hour",
            }
        semantic["columns"] = columns

        if "semantic_config" in semantic and project_type == "behavior_analysis":
            llm_config = semantic.pop("semantic_config")
            _save_semantic_config(dm.project_dir, llm_config)

        _save_full_semantic_config(dm.project_dir, semantic)

        semantic["config_file"] = "semantic_config.json"

        return semantic

    except Exception as e:
        raise RuntimeError(f"[SemanticGen] LLM generation failed: {e}") from e


def generate_semantic_layer(
    dm: ProjectDataManager,
    project_type: str = "generic",
    use_llm: bool = True,
    reference_context: str = "",
) -> dict:
    if use_llm:
        if llm_client.is_available():
            try:
                return generate_semantic_layer_with_llm(dm, project_type, reference_context=reference_context)
            except Exception as e:
                print(f"[SemanticGen] LLM generation failed: {e}, falling back to rules")
        else:
            schema = _analyze_schema(dm)
            table_name = dm.get_full_semantic_layer().get("table_name", "events")
            low_card = schema.get("low_cardinality_values", "")
            if reference_context:
                prompt = SCHEMA_ANALYSIS_PROMPT_WITH_REFS.replace("{table_name}", table_name).replace("{project_type}", project_type).replace("{total_rows}", str(schema["total_rows"])).replace("{total_columns}", str(schema["total_columns"])).replace("{columns_detail}", schema["columns_detail"]).replace("{sample_data}", schema["sample_data"]).replace("{statistics}", schema["statistics"]).replace("{low_card_values}", low_card).replace("{reference_context}", reference_context)
            else:
                prompt = SCHEMA_ANALYSIS_PROMPT.replace("{table_name}", table_name).replace("{project_type}", project_type).replace("{total_rows}", str(schema["total_rows"])).replace("{total_columns}", str(schema["total_columns"])).replace("{columns_detail}", schema["columns_detail"]).replace("{sample_data}", schema["sample_data"]).replace("{statistics}", schema["statistics"]).replace("{low_card_values}", low_card)
            raise llm_client.LlmDelegationNeeded(
                task_id=uuid.uuid4().hex[:12],
                prompt=prompt,
                system_msg="You are a data analyst expert. Respond with valid JSON only, no markdown fences.",
                max_tokens=32768,
            )

    return _generate_semantic_layer_rules(dm, project_type)


def _generate_semantic_layer_rules(dm: ProjectDataManager, project_type: str) -> dict:
    if dm.con is None:
        raise RuntimeError("Project data not loaded. Call load() first.")

    table_name = dm.get_full_semantic_layer().get("table_name", "events")
    cols = dm.con.execute(f"DESCRIBE {table_name}").fetchall()
    total_rows = dm.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    columns = {}
    metrics = {}
    event_definitions = {}
    examples = []

    for c in cols:
        col_name = c[0]
        dtype = c[1].upper()
        col_lower = col_name.lower()

        is_numeric = any(t in dtype for t in ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC"))
        is_date = any(t in dtype for t in ("TIMESTAMP", "DATE", "TIME"))
        is_id = "id" in col_lower or col_lower.endswith("_id") or col_lower == "id"

        if is_id:
            semantic_type = "dimension_id"
            role = "identifier"
        elif is_date or any(kw in col_lower for kw in ["time", "date", "timestamp"]):
            semantic_type = "dimension_time"
            role = "time_dimension"
        elif any(kw in col_lower for kw in ["event", "span", "action", "name"]):
            semantic_type = "dimension_event"
            role = "event_name"
        elif any(kw in col_lower for kw in ["user", "uid", "account"]):
            semantic_type = "dimension_user"
            role = "user_identifier"
        elif any(kw in col_lower for kw in ["version", "platform", "os", "env", "service", "language", "sdk"]):
            semantic_type = "dimension_attribute"
            role = "attribute"
        elif is_numeric:
            semantic_type = "measure"
            role = "measure"
        else:
            semantic_type = "dimension"
            role = "dimension"

        try:
            null_count = dm.con.execute(f'SELECT COUNT(*) FROM {table_name} WHERE "{col_name}" IS NULL').fetchone()[0]
            unique_count = dm.con.execute(f'SELECT COUNT(DISTINCT "{col_name}") FROM {table_name}').fetchone()[0]
        except Exception:
            null_count = 0
            unique_count = 0

        try:
            sample = dm.con.execute(
                f'SELECT DISTINCT "{col_name}" FROM {table_name} WHERE "{col_name}" IS NOT NULL LIMIT 5'
            ).fetchall()
            sample_values = [str(v[0]) for v in sample]
        except Exception:
            sample_values = []

        columns[col_name] = {
            "column_name": col_name,
            "dtype": dtype,
            "semantic_type": semantic_type,
            "role": role,
            "business_name": col_name,
            "description": f"Auto-detected {role}",
            "null_rate": round(null_count / max(total_rows, 1), 4),
            "unique_count": unique_count,
            "sample_values": sample_values,
        }

    time_cols = [cn for cn, ci in columns.items() if ci["semantic_type"] == "dimension_time"]
    event_cols = [cn for cn, ci in columns.items() if ci["semantic_type"] == "dimension_event"]
    user_cols = [cn for cn, ci in columns.items() if ci["semantic_type"] == "dimension_user"]
    numeric_cols = [cn for cn, ci in columns.items() if ci["semantic_type"] == "measure"]

    if event_cols and user_cols and time_cols:
        event_col = event_cols[0]
        user_col = user_cols[0]
        time_col = time_cols[0]

        try:
            top_events = dm.con.execute(
                f'SELECT "{event_col}", COUNT(*) as cnt FROM {table_name} GROUP BY "{event_col}" ORDER BY cnt DESC LIMIT 10'
            ).fetchall()
        except Exception:
            top_events = []

        for ev in top_events:
            ev_name = str(ev[0])
            ev_count = ev[1]
            event_definitions[ev_name] = {
                "event_name": ev_name,
                "description": f"Event: {ev_name} (count: {ev_count:,})",
                "sql_pattern": f'SELECT "{user_col}", "{time_col}" FROM {table_name} WHERE "{event_col}" = \'{ev_name}\'',
            }

        metrics["total_events"] = {
            "name": "total_events",
            "description": "Total event count",
            "sql": "COUNT(*)",
            "type": "count",
        }

        if user_cols:
            metrics["dau"] = {
                "name": "dau",
                "description": "Daily Active Users",
                "sql": f'COUNT(DISTINCT "{user_col}")',
                "type": "count_distinct",
            }

        if time_cols and user_cols:
            metrics["events_per_user"] = {
                "name": "events_per_user",
                "description": "Average events per user",
                "sql": f'CAST(COUNT(*) AS DOUBLE) / COUNT(DISTINCT "{user_col}")',
                "type": "ratio",
            }

    for nc in numeric_cols[:5]:
        col_info = columns[nc]
        metrics[f"avg_{nc}"] = {
            "name": f"avg_{nc}",
            "description": f"Average of {col_info.get('business_name', nc)}",
            "sql": f'AVG("{nc}")',
            "type": "average",
        }

    if time_cols:
        examples.append({
            "question": "Show daily event trend",
            "sql": f'SELECT CAST("{time_cols[0]}" AS DATE) as day, COUNT(*) as cnt FROM {table_name} GROUP BY day ORDER BY day',
            "visualization_goal": "Show daily event trend over time",
        })
    if event_cols and time_cols:
        examples.append({
            "question": "Top events by count",
            "sql": f'SELECT "{event_cols[0]}", COUNT(*) as cnt FROM {table_name} GROUP BY "{event_cols[0]}" ORDER BY cnt DESC LIMIT 10',
            "visualization_goal": "Compare event frequencies",
        })

    return {
        "table_name": table_name,
        "config_file": "semantic_config.json",
        "project_type": project_type,
        "columns": columns,
        "metrics": metrics,
        "event_definitions": event_definitions,
        "examples": examples,
        "generated_by": "rules_fallback",
    }


def detect_project_type(dm: ProjectDataManager) -> str:
    if dm.con is None:
        return "generic"

    try:
        table_name = dm.get_full_semantic_layer().get("table_name", "events")
        cols = dm.con.execute(f"DESCRIBE {table_name}").fetchall()
    except Exception:
        return "generic"

    cols_lower = {c[0].lower(): c[0] for c in cols}
    col_names = set(cols_lower.keys())

    has_event_col = any(kw in " ".join(col_names) for kw in ["event", "span", "action"])
    has_user_col = any(kw in " ".join(col_names) for kw in ["user", "uid", "reduser"])
    has_time_col = any(kw in " ".join(col_names) for kw in ["time", "timestamp", "date"])

    if has_event_col and has_user_col and has_time_col:
        return "behavior_analysis"

    numeric_cols = dm.meta.get("numeric_columns", [])
    numeric_ratio = len(numeric_cols) / max(len(cols), 1)
    if has_time_col and numeric_ratio > 0.5:
        return "time_series"

    if has_time_col:
        return "business_report"

    return "generic"
