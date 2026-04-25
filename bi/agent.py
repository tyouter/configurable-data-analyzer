# -*- coding: utf-8 -*-
"""
NL→SQL Agent: Uses Claude API to translate natural language to SQL,
executes against DuckDB, and builds ECharts chart options.
"""

import os
import sys
import re
import json
import anthropic
from datetime import datetime

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from bi.data_layer import DataManager

PROMPT_TEMPLATE = """You are a senior product data analyst for a Rednote (小红书) in-car (Porsche) application.

## Your Role
You receive a natural language question from a product manager. You must:
1. Deeply understand the analytical concept they're asking about (DAU, retention rate, activity rate, funnel conversion, etc.)
2. Determine the CORRECT formula for that concept based on statistical/data analysis principles
3. Translate it into SQL for the `events` table below
4. Choose an appropriate chart type

## Data Context
- This is user behavior tracking data from a Rednote app on Porsche car infotainment systems
- Total {total_users} unique users, {total_events} events, date range: {date_range}
- The table `events` has these columns:

{columns_desc}

## Key Analytical Concepts — Think Before You Write SQL

When the user asks about these concepts, you MUST apply the correct formula:

**日活 (DAU)**: COUNT(DISTINCT reduser_id) per day. Simple count.
**活跃率 (Activity Rate)**: 活跃率 = 当天DAU / 全量总用户数 × 100%. This is a PERCENTAGE. You need both numerator and denominator. Example: SELECT event_date, COUNT(DISTINCT reduser_id) as dau, (SELECT COUNT(DISTINCT reduser_id) FROM events) as total, ROUND(COUNT(DISTINCT reduser_id) * 100.0 / (SELECT COUNT(DISTINCT reduser_id) FROM events), 2) as rate_pct FROM events GROUP BY event_date
**留存率 (Retention Rate)**: Day-N retention = users who were active on day 0 AND still active on day N / users active on day 0 × 100%. Requires a self-join on reduser_id between first-use date and target date.
**转化率 (Conversion Rate)**: Users who completed step B / users who completed step A × 100%. For funnels, each step's conversion = current step count / previous step count.
**漏斗 (Funnel)**: Show absolute counts per step in order. Columns must be named "step" and "cnt".
**人均 (Per Capita)**: Total metric / COUNT(DISTINCT reduser_id).
**环比/同比**: Compare current period vs previous period. Use LAG() window function.

If the user asks about a concept NOT listed above, REASON about the correct formula yourself. Think about what numerator and denominator make sense.

## Example Queries (reference only — adapt to each question)

{examples_text}

## Rules
1. Only SELECT queries. Never INSERT/UPDATE/DELETE/DROP.
2. Use exact column names from the schema above.
3. Respond in JSON: {{ "sql": "...", "chart_type": "...", "summary": "...", "explanation": "..." }}
4. chart_type: line | bar | pie | funnel | scatter | table
5. summary: 1-2 sentence Chinese description of the result.
6. explanation: Step-by-step Chinese description of the calculation logic using BUSINESS terms, not SQL. Describe what the formula computes and why. For rates/percentages, explicitly state the numerator and denominator.
7. For rates, ALWAYS include both the raw counts AND the percentage in the result columns.

## User Question
{question}

Respond with valid JSON only, no markdown fences."""

CHART_TEMPLATES = {
    "line": lambda title, data: {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "series": [],
    },
    "bar": lambda title, data: {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "series": [],
    },
    "pie": lambda title, data: {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "legend": {"orient": "vertical", "left": "left", "top": "middle"},
        "series": [{"type": "pie", "radius": "50%", "data": []}],
    },
    "funnel": lambda title, data: {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "series": [{"type": "funnel", "left": "10%", "width": "80%", "data": []}],
    },
    "table": lambda title, data: {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
    },
    "scatter": lambda title, data: {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "value"},
        "series": [{"type": "scatter", "data": []}],
    },
}


class Agent:
    def __init__(self, data_manager: DataManager, semantic_path: str = None):
        self.dm = data_manager
        self.semantic_path = semantic_path or os.path.join(
            os.path.dirname(__file__), "semantic.yaml"
        )
        self.semantic = self._load_semantic()
        self.client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
        self.model = os.environ.get("BI_MODEL", "claude-sonnet-4-20250514")

    def _load_semantic(self) -> dict:
        import yaml
        with open(self.semantic_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _build_prompt(self, question: str) -> str:
        # Columns description
        cols = self.semantic.get("columns", {})
        cols_desc_parts = []
        for name, info in cols.items():
            role = info.get("role", "dimension")
            desc = info.get("description", info.get("business_name", ""))
            dtype = info.get("type", "")
            enum_vals = info.get("enum", [])
            enum_str = f" (enum: {', '.join(enum_vals)})" if enum_vals else ""
            cols_desc_parts.append(f"- {name} ({dtype}, {role}): {desc}{enum_str}")
        columns_desc = "\n".join(cols_desc_parts)

        # Example queries
        examples = self.semantic.get("example_queries", [])
        examples_parts = []
        for i, ex in enumerate(examples, 1):
            examples_parts.append(f"{i}. Q: {ex['question']}\n   SQL: {ex['sql']}\n   Chart: {ex['chart_type']}")
        examples_text = "\n".join(examples_parts)

        # Data context
        total_users = self.dm.meta.get("total_users", "?")
        total_events = self.dm.meta.get("total_rows", "?")
        date_range = " ~ ".join(self.dm.meta.get("date_range", ["?", "?"]))

        return PROMPT_TEMPLATE.format(
            columns_desc=columns_desc,
            examples_text=examples_text,
            question=question,
            total_users=total_users,
            total_events=total_events,
            date_range=date_range,
        )

    def _call_claude(self, prompt: str) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)

    def _build_chart_option(self, chart_type: str, data: list[dict], title: str) -> dict:
        if chart_type not in CHART_TEMPLATES or chart_type == "table":
            return None

        option = CHART_TEMPLATES[chart_type](title, data)
        if not data:
            return option

        keys = list(data[0].keys())

        if chart_type in ("line", "bar"):
            x_key = keys[0]
            y_keys = keys[1:]
            option["xAxis"]["data"] = [str(row[x_key]) for row in data]
            option["series"] = []
            for yk in y_keys:
                series = {
                    "type": chart_type,
                    "name": yk,
                    "data": [row[yk] for row in data],
                }
                if chart_type == "line":
                    series["smooth"] = True
                option["series"].append(series)
            if len(y_keys) > 1:
                option["legend"] = {"top": 30}

        elif chart_type == "pie":
            name_key = keys[0]
            val_key = keys[1] if len(keys) > 1 else keys[0]
            option["series"][0]["data"] = [
                {"name": str(row[name_key]), "value": row[val_key]}
                for row in data
            ]

        elif chart_type == "funnel":
            name_key = None
            val_key = None
            for k in keys:
                if k.lower() in ("step", "name", "label"):
                    name_key = k
                elif k.lower() in ("cnt", "count", "value", "val"):
                    val_key = k
            if not name_key:
                name_key = keys[0]
            if not val_key:
                val_key = keys[1] if len(keys) > 1 else keys[0]
            option["series"][0]["data"] = [
                {"name": str(row[name_key]), "value": row[val_key]}
                for row in data
            ]

        elif chart_type == "scatter":
            x_key = keys[0]
            y_key = keys[1] if len(keys) > 1 else keys[0]
            option["series"][0]["data"] = [[row[x_key], row[y_key]] for row in data]

        return option

    def _build_audit(self, sql: str, data: list[dict]) -> dict:
        """Build audit info from SQL, data, and semantic layer."""
        semantic_cols = self.semantic.get("columns", {})
        semantic_metrics = self.semantic.get("metrics", {})

        # Extract column names from SQL — resolve to raw Excel column names
        sql_lower = sql.lower()
        raw_col_map = self.dm.raw_column_map  # unified → raw
        result_keys = list(data[0].keys()) if data else []

        # Extract WHERE clause to filter sample values contextually
        where_clause = ""
        where_match = re.search(r"WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()

        columns_used = []
        for col_name, col_info in semantic_cols.items():
            if col_name.lower() in sql_lower:
                entry = {
                    "column": col_name,
                    "business_name": col_info.get("business_name", col_name),
                    "role": col_info.get("role", "dimension"),
                }
                # Map to original raw Excel column name
                mapping = raw_col_map.get(col_name)
                if isinstance(mapping, dict):
                    entry["raw_column"] = mapping["raw_col"]
                    entry["raw_logic"] = mapping["logic"]
                elif isinstance(mapping, str):
                    entry["raw_column"] = mapping

                # Get sample values: from result if present, otherwise query DB
                if col_name in result_keys:
                    entry["sample_values"] = [str(row.get(col_name, "")) for row in data[:3]]
                else:
                    # Column used in WHERE/aggregate but not in SELECT — query for samples
                    try:
                        sample_sql = f"SELECT DISTINCT {col_name} FROM events"
                        if where_clause:
                            # Only use simple WHERE conditions that reference this column
                            sample_sql += f" WHERE {where_clause}"
                        sample_sql += f" LIMIT 3"
                        sample_rows = self.dm.execute(sample_sql)
                        vals = [str(r[col_name]) for r in sample_rows if r[col_name] is not None]
                        if vals:
                            entry["sample_values"] = vals
                    except Exception:
                        pass
                columns_used.append(entry)

        # Match metrics — use human-readable formula
        metrics_involved = []
        for metric_name, metric_info in semantic_metrics.items():
            keywords = metric_info.get("keywords", [])
            for kw in keywords:
                if kw.lower() in sql_lower:
                    metrics_involved.append({
                        "metric": metric_name,
                        "business_name": metric_info.get("business_name", metric_name),
                        "formula_human": metric_info.get("description", metric_info.get("sql", "")),
                    })
                    break

        # Extract WHERE filters as Chinese description
        filters_raw = []
        filters_human = []
        where_match = re.search(r"WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            raw_where = where_match.group(1).strip()
            filters_raw.append(raw_where)
            # Simple Chinese translation of common patterns
            human = raw_where
            human = re.sub(r"page_root\s*=\s*'(\w+)'", r"页面模块为「\1」", human, flags=re.IGNORECASE)
            human = re.sub(r"is_weekend\s*=\s*1", "仅周末", human, flags=re.IGNORECASE)
            human = re.sub(r"is_weekend\s*=\s*0", "仅工作日", human, flags=re.IGNORECASE)
            human = re.sub(r"is_click\s*=\s*1", "仅点击事件", human, flags=re.IGNORECASE)
            human = re.sub(r"event_name\s+LIKE\s+'([^']+)'", r"事件名称匹配「\1」", human, flags=re.IGNORECASE)
            human = re.sub(r"event_name\s+IN\s*\(([^)]+)\)", r"事件名称为\1", human, flags=re.IGNORECASE)
            human = re.sub(r"reduser_id\s+IS\s+NOT\s+NULL", "用户ID不为空", human, flags=re.IGNORECASE)
            human = re.sub(r"\bAND\b", "，且", human, flags=re.IGNORECASE)
            human = re.sub(r"\bOR\b", "，或", human, flags=re.IGNORECASE)
            filters_human.append(human)

        # Sample data (first 3 rows)
        sample = data[:3]
        for row in sample:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()

        # Build SQL explanation in Chinese
        sql_explanation = self._explain_sql(sql)

        return {
            "question": "",  # Filled by caller
            "generated_at": datetime.now().isoformat(),
            "data_source": {
                "file": self.dm.meta.get("file", ""),
                "table": "events",
                "date_range": self.dm.meta.get("date_range", []),
                "total_rows_scanned": self.dm.meta.get("total_rows", 0),
            },
            "sql": sql,
            "sql_explanation": sql_explanation,
            "columns_used": columns_used,
            "metrics_involved": metrics_involved,
            "filters_applied": filters_raw,
            "filters_human": filters_human,
            "calculation_logic": "",
            "sample_data": sample,
        }

    def _explain_sql(self, sql: str) -> str:
        """Generate a plain Chinese explanation of what the SQL does."""
        parts = []
        sql_upper = sql.upper()

        # SELECT
        if "COUNT(DISTINCT" in sql_upper:
            parts.append("统计不重复的计数")
        elif "COUNT(*)" in sql_upper:
            parts.append("统计总数量")
        elif "AVG(" in sql_upper:
            parts.append("计算平均值")
        elif "SUM(" in sql_upper:
            parts.append("计算总和")

        # GROUP BY
        gb_match = re.search(r"GROUP\s+BY\s+(.+?)(?:\s+ORDER|\s+HAVING|\s+LIMIT|$)", sql, re.IGNORECASE)
        if gb_match:
            gb_cols = gb_match.group(1).strip()
            col_names = [c.strip() for c in gb_cols.split(",")]
            readable = []
            for c in col_names:
                c_key = c.lower().strip()
                for col_name, col_info in self.semantic.get("columns", {}).items():
                    if col_name.lower() == c_key:
                        readable.append(col_info.get("business_name", c))
                        break
                else:
                    readable.append(c)
            parts.append(f"按「{'、'.join(readable)}」分组")

        # WHERE
        where_match = re.search(r"WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            parts.append("筛选条件: " + where_match.group(1).strip())

        # ORDER BY
        if "ORDER BY" in sql_upper:
            if "DESC" in sql_upper:
                parts.append("按降序排列")
            else:
                parts.append("按升序排列")

        # LIMIT
        lim_match = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
        if lim_match:
            parts.append(f"取前 {lim_match.group(1)} 条")

        return "；".join(parts) if parts else "查询数据"

        return {
            "question": "",  # Filled by caller
            "generated_at": datetime.now().isoformat(),
            "data_source": {
                "file": self.dm.meta.get("file", ""),
                "table": "events",
                "date_range": self.dm.meta.get("date_range", []),
                "total_rows_scanned": self.dm.meta.get("total_rows", 0),
            },
            "sql": sql,
            "columns_used": columns_used,
            "metrics_involved": metrics_involved,
            "filters_applied": filters,
            "calculation_logic": "",
            "sample_data": sample,
        }

    def query(self, question: str) -> dict:
        """Main entry: NL question → SQL → execute → chart + audit."""
        prompt = self._build_prompt(question)

        # Try up to 3 times (initial + 2 retries)
        last_error = None
        for attempt in range(3):
            try:
                result = self._call_claude(prompt)
                sql = result["sql"]
                chart_type = result.get("chart_type", "table")
                summary = result.get("summary", "")

                # Execute SQL
                data = self.dm.execute(sql)

                # Serialize any non-JSON-safe types
                for row in data:
                    for k, v in row.items():
                        if hasattr(v, "isoformat"):
                            row[k] = v.isoformat()
                        elif hasattr(v, "item"):
                            row[k] = v.item()

                # Build chart option
                chart_option = self._build_chart_option(chart_type, data, question)

                # Build audit
                audit = self._build_audit(sql, data)
                audit["question"] = question
                audit["calculation_logic"] = summary
                # Prefer Claude's explanation over auto-generated one
                explanation = result.get("explanation", "")
                if explanation:
                    audit["sql_explanation"] = explanation

                return {
                    "sql": sql,
                    "data": data,
                    "chart_type": chart_type,
                    "chart_option": chart_option,
                    "summary": summary,
                    "audit": audit,
                    "error": None,
                }

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {e}"
            except anthropic.APIError as e:
                last_error = f"Claude API error: {e}"
                break  # No point retrying API errors
            except Exception as e:
                last_error = str(e)
                # If SQL error, retry with error context
                if "SQL" in str(e).upper() or "Parser" in str(e):
                    prompt += f"\n\nPrevious SQL failed with error: {last_error}\nPlease fix and try again."
                    continue

        return {
            "sql": None,
            "data": [],
            "chart_type": "table",
            "chart_option": None,
            "summary": f"查询失败: {last_error}",
            "audit": None,
            "error": last_error,
        }
