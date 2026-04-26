# -*- coding: utf-8 -*-
"""
NL→SQL Agent: Uses DeepSeek API (OpenAI-compatible) to translate natural language to SQL,
executes against DuckDB, and builds ECharts chart options.
"""

import os
import sys
import re
import json
import requests
from datetime import datetime

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from bi.data_layer import DataManager

# DeepSeek API configuration
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
# Use deepseek-v4-pro for intelligent reasoning
DEEPSEEK_MODEL = os.environ.get("BI_MODEL", "deepseek-v4-pro")

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
**活跃率 (Activity Rate)**: 活跃率 = 当天DAU / 全量总用户数 × 100%. This is a PERCENTAGE. You need both numerator and denominator.
**留存率 (Retention Rate)**: Day-N retention = users who were active on day 0 AND still active on day N / users active on day 0 × 100%. Requires a self-join.
**转化率 (Conversion Rate)**: Users who completed step B / users who completed step A × 100%. For funnels, each step's conversion = current step count / previous step count.
**漏斗 (Funnel)**: Show absolute counts per step in order. Columns must be named "step" and "cnt".
**人均 (Per Capita)**: Total metric / COUNT(DISTINCT reduser_id).
**环比/同比**: Compare current period vs previous period. Use LAG() window function.

If the user asks about a concept NOT listed above, REASON about the correct formula yourself.

## Example Queries (reference only — adapt to each question)

{examples_text}

## Rules
1. Only SELECT queries. Never INSERT/UPDATE/DELETE/DROP.
2. Use exact column names from the schema above.
3. Respond in JSON: {{\"sql\": \"...\", \"chart_type\": \"...\", \"title\": \"...\", \"summary\": \"...\", \"explanation\": \"...\"}}
4. chart_type: line | bar | pie | funnel | scatter | table
5. **title**: A professional BI/statistical chart title in Chinese. Use standard terminology:
   - 趋势类: "XX时序趋势图" / "XX变化趋势" / "XX时间序列分析"
   - 分布类: "XX分布分析" / "XX占比分布" / "XX构成分析"
   - 对比类: "XX对比分析" / "XX差异对比"
   - 漏斗类: "XX转化漏斗" / "XX流程漏斗分析"
   - 排名类: "XX排名分析" / "Top N XX统计"
   - 用户类: "日活跃用户(DAU)趋势" / "用户活跃率分析" / "人均XX分析"
   Title should be concise (≤20 chars), professional, and describe the visualization accurately.
6. summary: 1-2 sentence Chinese description of the result.
7. explanation: Step-by-step Chinese description of the calculation logic.
8. For rates, ALWAYS include both the raw counts AND the percentage.
9. chart_type selection: Use "pie" for 占比/来源/分布 questions. Use "funnel" only for multi-step conversion. Use "line" for trends. Use "bar" for comparisons.
10. The column referer_page is often NULL. Prefer page or page_root for source analysis.

## Conversation History (if any)
{conversation_history}

## User Question
{question}

Respond with valid JSON only, no markdown fences."""

# Prompt for LLM to autonomously decide if clarification is needed
CLARIFICATION_PROMPT = """You are an intelligent data analyst assistant. Analyze the user's question and decide if it needs clarification.

## Decision Logic
- Clear enough → {{\"action\": \"proceed\"}}
- Ambiguous → {{\"action\": \"clarify\", \"question\": \"中文澄清问题\", \"options\": [{{\"label\": \"选项\", \"value\": \"值\"}}]}}

## When to Clarify
1. Broad category (导航、搜索、页面) matching multiple event types — ask which specific type
2. Unclear time range (最近、这个月) — ask for specific dates
3. Ambiguous metric (用户数 — DAU vs total vs active)
4. Unclear aggregation (分析用户 — per-user vs daily vs overall)
5. Multiple interpretations

## When NOT to Clarify
1. Question is specific enough (每天的日活趋势, Porsche+页面访问量)
2. Conversation history makes it clear
3. Reasonable default exists

## Data Context
- {total_users} users, {total_events} events, {date_range}
- Columns: event_name, page, page_root, event_date, reduser_id, action, duration_sec

## Conversation History
{conversation_history}

## Current Question
{question}

## Available Event Types
{event_types_sample}

Respond in JSON:
- Proceed: {{\"action\": \"proceed\"}}
- Clarify: {{\"action\": \"clarify\", \"question\": \"友好的中文问题\", \"options\": [{{\"label\": \"...\", \"value\": \"...\"}}]}}

Only JSON, no markdown."""


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
        "series": [{"type": "pie", "radius": "50%", "center": ["60%", "50%"], "data": []}],
    },
    "funnel": lambda title, data: {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "series": [{"type": "funnel", "left": "10%", "width": "80%", "sort": "none", "data": []}],
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

        # DeepSeek API config
        self.base_url = DEEPSEEK_BASE_URL
        self.api_key = DEEPSEEK_API_KEY
        self.model = DEEPSEEK_MODEL

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is required")

        # Conversation history for multi-turn clarification
        self.conversation_history: list[dict] = []
        # Cache event types
        self._event_types_cache = None

    def _load_semantic(self) -> dict:
        import yaml
        with open(self.semantic_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _get_event_types_sample(self) -> str:
        """Get top event types with business semantics for clarification context."""
        if self._event_types_cache:
            return self._event_types_cache
        try:
            results = self.dm.execute(
                "SELECT event_name, COUNT(*) as cnt FROM events "
                "GROUP BY event_name ORDER BY cnt DESC LIMIT 50"
            )
            # Get event definitions from semantic layer
            event_defs = self.semantic.get("event_definitions", {})
            lines = []
            for r in results:
                event_name = r['event_name']
                cnt = r['cnt']
                # Look up business semantics
                def_info = event_defs.get(event_name, {})
                business_name = def_info.get("business_name", "")
                description = def_info.get("description", "")
                category = def_info.get("category", "")
                if business_name:
                    lines.append(f"- {event_name} ({business_name}): {cnt}次 — {description[:50] if description else ''}")
                else:
                    # Generate heuristic description for unknown events
                    parts = event_name.replace("_click", "").replace("_show", "").split("_")
                    heuristic = " ".join(parts[:3])
                    lines.append(f"- {event_name}: {cnt}次")
            self._event_types_cache = "\n".join(lines)
            return self._event_types_cache
        except Exception:
            return "Unable to load event types"

    def _build_clarification_prompt(self, question: str) -> str:
        """Build prompt for LLM to decide if clarification is needed."""
        total_users = self.dm.meta.get("total_users", "?")
        total_events = self.dm.meta.get("total_rows", "?")
        date_range = " ~ ".join(self.dm.meta.get("date_range", ["?", "?"]))
        event_types_sample = self._get_event_types_sample()

        history_text = ""
        if self.conversation_history:
            lines = []
            for h in self.conversation_history[-10:]:
                # Ensure h is a dict
                if isinstance(h, dict):
                    if h.get("role") == "user":
                        lines.append(f"用户: {h.get('content', '')}")
                    elif h.get("role") == "assistant":
                        content = h.get('content', '')
                        if content:
                            lines.append(f"AI: {content}")
                elif isinstance(h, str):
                    lines.append(f"历史: {h}")
            history_text = "\n".join(lines)

        return CLARIFICATION_PROMPT.format(
            total_users=total_users,
            total_events=total_events,
            date_range=date_range,
            conversation_history=history_text or "无",
            question=question,
            event_types_sample=event_types_sample,
        )

    def _build_prompt(self, question: str) -> str:
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

        examples = self.semantic.get("example_queries", [])
        examples_parts = []
        for i, ex in enumerate(examples, 1):
            examples_parts.append(f"{i}. Q: {ex['question']}\n   SQL: {ex['sql']}\n   Chart: {ex['chart_type']}")
        examples_text = "\n".join(examples_parts)

        total_users = self.dm.meta.get("total_users", "?")
        total_events = self.dm.meta.get("total_rows", "?")
        date_range = " ~ ".join(self.dm.meta.get("date_range", ["?", "?"]))

        history_text = ""
        if self.conversation_history:
            lines = []
            for h in self.conversation_history[-10:]:
                # Ensure h is a dict
                if isinstance(h, dict):
                    if h.get("role") == "user":
                        lines.append(f"用户: {h.get('content', '')}")
                    elif h.get("role") == "assistant":
                        content = h.get('content', '')
                        if content:
                            lines.append(f"AI: {content}")
                elif isinstance(h, str):
                    lines.append(f"历史: {h}")
            history_text = "\n".join(lines)

        return PROMPT_TEMPLATE.format(
            columns_desc=columns_desc,
            examples_text=examples_text,
            question=question,
            total_users=total_users,
            total_events=total_events,
            date_range=date_range,
            conversation_history=history_text or "无",
        )

    def _call_deepseek(self, prompt: str) -> dict:
        """Call DeepSeek V4 Pro API with thinking enabled."""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful data analyst assistant."},
                {"role": "user", "content": prompt}
            ],
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "max_tokens": 4096,
            "stream": False,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code} - {response.text[:500]}")

        data = response.json()

        # Extract content from OpenAI-compatible response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # For V4 Pro with thinking, reasoning may be in reasoning_content or embedded in content
        reasoning_content = message.get("reasoning_content", "")

        if not content and not reasoning_content:
            raise Exception("Empty response from DeepSeek")

        # Strip markdown fences if present
        content = content.strip() if content else ""
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)

        # Parse JSON
        try:
            result = json.loads(content) if content else {}
        except json.JSONDecodeError as e:
            raise Exception(f"JSON parse error: {e}. Content: {content[:200]}")

        # Ensure result is a dict
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except:
                raise Exception(f"DeepSeek returned a string: {result[:100]}")

        if not isinstance(result, dict):
            raise Exception(f"Expected dict, got {type(result).__name__}: {str(result)[:100]}")

        # Return both result and reasoning_content for display
        result["_reasoning_content"] = reasoning_content
        return result

    def _call_deepseek_stream(self, prompt: str):
        """Call DeepSeek V4 Pro API with streaming (SSE). Yields chunks including reasoning."""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful data analyst assistant."},
                {"role": "user", "content": prompt}
            ],
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "max_tokens": 4096,
            "stream": True,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120, stream=True)

        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code} - {response.text[:500]}")

        full_content = ""
        reasoning_content = ""

        for line in response.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    # Content chunk - may be None
                    content_chunk = delta.get("content")
                    if content_chunk:
                        full_content += content_chunk
                        yield {"type": "content", "text": content_chunk}
                    # Reasoning chunk (for V4 Pro with thinking) - may be None
                    reasoning_chunk = delta.get("reasoning_content")
                    if reasoning_chunk:
                        reasoning_content += reasoning_chunk
                        yield {"type": "reasoning", "text": reasoning_chunk}
                except json.JSONDecodeError:
                    continue

        # Final yield with full content
        yield {"type": "done", "content": full_content, "reasoning": reasoning_content}

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
            name_key = keys[0]
            val_key = keys[1] if len(keys) > 1 else keys[0]
            option["series"][0]["data"] = [
                {"name": str(row[name_key]), "value": row[val_key]}
                for row in data
            ]

        elif chart_type == "scatter":
            x_key = keys[0]
            y_key = keys[1] if len(keys) > 1 else keys[0]
            option["series"][0]["data"] = [
                [row[x_key], row[y_key]] for row in data
            ]

        return option

    def _build_audit(self, sql: str, data: list[dict]) -> dict:
        """Build audit trail for the query."""
        raw_col_map = self.dm.raw_column_map if hasattr(self.dm, "raw_column_map") else {}

        # Extract columns from SQL
        col_pattern = r"(?:SELECT|GROUP BY|ORDER BY|WHERE|AND|OR)[\s\S]*?(\b[a-z_][a-z0-9_]*\b)"
        sql_lower = sql.lower()
        cols_found = set(re.findall(r"\b([a-z_][a-z0-9_]*\b)", sql_lower))

        columns_used = []
        for col in cols_found:
            if col in ("select", "from", "where", "group", "order", "by", "and", "or", "as", "count", "distinct", "sum", "avg", "filter", "limit", "like", "is", "not", "null", "desc", "asc", "round", "over", "partition", "lag", "date", "events"):
                continue
            col_info = self.semantic.get("columns", {}).get(col, {})
            if col_info:
                entry = {
                    "column": col,
                    "business_name": col_info.get("business_name", col),
                    "role": col_info.get("role", "dimension"),
                }
                # Resolve to raw Excel column
                if col in raw_col_map:
                    raw_info = raw_col_map[col]
                    # raw_info can be either a string or a dict
                    if isinstance(raw_info, str):
                        entry["raw_column"] = raw_info
                    elif isinstance(raw_info, dict):
                        entry["raw_column"] = raw_info.get("raw_col", col)
                        if raw_info.get("logic"):
                            entry["raw_logic"] = raw_info["logic"]
                columns_used.append(entry)

        # Match metrics
        metrics_involved = []
        semantic_metrics = self.semantic.get("metrics", {})
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

        # Extract WHERE filters
        filters_raw = []
        filters_human = []
        where_match = re.search(r"WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            raw_where = where_match.group(1).strip()
            filters_raw.append(raw_where)
            human = raw_where
            human = re.sub(r"page_root\s*=\s*'(\w+)'", r"页面模块为「\1」", human, flags=re.IGNORECASE)
            human = re.sub(r"is_weekend\s*=\s*1", "仅周末", human, flags=re.IGNORECASE)
            human = re.sub(r"is_weekend\s*=\s*0", "仅工作日", human, flags=re.IGNORECASE)
            human = re.sub(r"is_click\s*=\s*1", "仅点击事件", human, flags=re.IGNORECASE)
            human = re.sub(r"event_name\s+LIKE\s+'([^']+)'", r"事件名称匹配「\1」", human, flags=re.IGNORECASE)
            human = re.sub(r"\bAND\b", "，且", human, flags=re.IGNORECASE)
            human = re.sub(r"\bOR\b", "，或", human, flags=re.IGNORECASE)
            filters_human.append(human)

        sample = data[:3]
        for row in sample:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()

        sql_explanation = self._explain_sql(sql)

        return {
            "question": "",
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
        """Generate a plain Chinese explanation."""
        parts = []
        sql_upper = sql.upper()

        if "COUNT(DISTINCT" in sql_upper:
            parts.append("统计不重复的计数")
        elif "COUNT(*)" in sql_upper:
            parts.append("统计总数量")
        elif "AVG(" in sql_upper:
            parts.append("计算平均值")
        elif "SUM(" in sql_upper:
            parts.append("计算总和")

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

        where_match = re.search(r"WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            parts.append("筛选条件: " + where_match.group(1).strip())

        if "ORDER BY" in sql_upper:
            if "DESC" in sql_upper:
                parts.append("按降序排列")
            else:
                parts.append("按升序排列")

        lim_match = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
        if lim_match:
            parts.append(f"取前 {lim_match.group(1)} 条")

        return "；".join(parts) if parts else "查询数据"

    def query(self, question: str, skip_clarification: bool = False) -> dict:
        """Main entry: NL question → (clarification loop) → SQL → chart + audit."""
        # Record user question
        self.conversation_history.append({"role": "user", "content": question})

        # Step 1: Ask LLM if clarification needed
        if not skip_clarification:
            clarification_prompt = self._build_clarification_prompt(question)
            try:
                clarification_result = self._call_deepseek(clarification_prompt)

                if isinstance(clarification_result, dict) and clarification_result.get("action") == "clarify":
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": clarification_result.get("question", ""),
                        "type": "clarification",
                    })
                    return {
                        "need_clarification": True,
                        "message": clarification_result.get("question", "请问您能提供更多信息吗？"),
                        "options": clarification_result.get("options", []),
                        "original_question": question,
                    }
            except Exception as e:
                # Log clarification error but continue to SQL generation
                print(f"Clarification check failed: {e}")
                pass

        # Step 2: Generate SQL
        prompt = self._build_prompt(question)

        last_error = None
        for attempt in range(3):
            try:
                result = self._call_deepseek(prompt)

                # Ensure result is a dict
                if not isinstance(result, dict):
                    raise Exception(f"Expected JSON object, got: {type(result).__name__}")

                sql = result.get("sql")
                if not sql:
                    raise Exception("No SQL in response")

                chart_type = result.get("chart_type", "table")
                summary = result.get("summary", "")
                title = result.get("title", question)  # Use LLM-generated title, fallback to question

                data = self.dm.execute(sql)

                for row in data:
                    for k, v in row.items():
                        if hasattr(v, "isoformat"):
                            row[k] = v.isoformat()
                        elif hasattr(v, "item"):
                            row[k] = v.item()

                chart_option = self._build_chart_option(chart_type, data, title)

                audit = self._build_audit(sql, data)
                audit["question"] = question
                audit["calculation_logic"] = summary
                explanation = result.get("explanation", "")
                if explanation:
                    audit["sql_explanation"] = explanation

                self.conversation_history.append({
                    "role": "assistant",
                    "content": summary,
                    "type": "result",
                })

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
                print(f"[Agent] JSON decode error: {e}")
            except Exception as e:
                last_error = str(e)
                print(f"[Agent] Error: {e}")
                if "SQL" in str(e).upper() or "Parser" in str(e):
                    prompt += f"\n\nPrevious SQL failed: {last_error}\nFix and try again."
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

    def query_stream(self, question: str, skip_clarification: bool = False, clear_history: bool = False):
        """Stream-based query with real-time reasoning display."""
        # Clear history if requested (for fresh start)
        if clear_history:
            self.conversation_history = []

        # Limit history to prevent context pollution
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

        self.conversation_history.append({"role": "user", "content": question})

        # Step 1: Stream clarification check - show reasoning immediately
        if not skip_clarification:
            clarification_prompt = self._build_clarification_prompt(question)
            clarification_reasoning = ""
            clarification_content = ""
            needs_clarification = False
            clarification_data = None

            try:
                for chunk in self._call_deepseek_stream(clarification_prompt):
                    if chunk["type"] == "reasoning":
                        clarification_reasoning += chunk["text"]
                        # Immediately yield reasoning so user sees progress
                        yield {"type": "reasoning", "text": chunk["text"]}
                    elif chunk["type"] == "content":
                        clarification_content += chunk["text"]
                    elif chunk["type"] == "done":
                        # Parse clarification result
                        content = clarification_content.strip()
                        if content.startswith("```"):
                            content = re.sub(r"^```(?:json)?\s*\n?", "", content)
                            content = re.sub(r"\n?```\s*$", "", content)
                        try:
                            clarification_data = json.loads(content)
                            if isinstance(clarification_data, dict) and clarification_data.get("action") == "clarify":
                                needs_clarification = True
                        except:
                            pass

                # If needs clarification, return with options
                if needs_clarification:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": clarification_data.get("question", ""),
                        "type": "clarification",
                    })
                    yield {
                        "type": "clarification",
                        "message": clarification_data.get("question", "请问您能提供更多信息吗？"),
                        "options": clarification_data.get("options", []),
                        "reasoning": clarification_reasoning,
                        "original_question": question,
                    }
                    return  # Stop here, wait for user clarification

            except Exception as e:
                print(f"[Agent] Clarification check failed: {e}")
                pass

        # Step 2: Stream SQL generation
        prompt = self._build_prompt(question)
        full_reasoning = ""
        full_content = ""

        try:
            for chunk in self._call_deepseek_stream(prompt):
                if chunk["type"] == "reasoning":
                    full_reasoning += chunk["text"]
                    yield {"type": "reasoning", "text": chunk["text"]}
                elif chunk["type"] == "content":
                    full_content += chunk["text"]
                    yield {"type": "content", "text": chunk["text"]}
                elif chunk["type"] == "done":
                    # Parse final JSON
                    content = full_content.strip()
                    if content.startswith("```"):
                        content = re.sub(r"^```(?:json)?\s*\n?", "", content)
                        content = re.sub(r"\n?```\s*$", "", content)
                    try:
                        result = json.loads(content)
                    except json.JSONDecodeError:
                        yield {"type": "error", "message": f"JSON parse failed: {content[:100]}"}
                        return

                    sql = result.get("sql")
                    chart_type = result.get("chart_type", "table")
                    summary = result.get("summary", "")
                    title = result.get("title", question)  # Use LLM-generated title, fallback to question

                    # Execute SQL
                    try:
                        data = self.dm.execute(sql)
                        for row in data:
                            for k, v in row.items():
                                if hasattr(v, "isoformat"):
                                    row[k] = v.isoformat()
                                elif hasattr(v, "item"):
                                    row[k] = v.item()
                    except Exception as e:
                        yield {"type": "error", "message": f"SQL execution failed: {e}"}
                        return

                    chart_option = self._build_chart_option(chart_type, data, title)
                    audit = self._build_audit(sql, data)
                    audit["question"] = question
                    audit["calculation_logic"] = summary
                    explanation = result.get("explanation", "")
                    if explanation:
                        audit["sql_explanation"] = explanation

                    self.conversation_history.append({
                        "role": "assistant",
                        "content": summary,
                        "type": "result",
                    })

                    yield {
                        "type": "result",
                        "sql": sql,
                        "data": data,
                        "chart_type": chart_type,
                        "chart_option": chart_option,
                        "summary": summary,
                        "audit": audit,
                        "reasoning": full_reasoning,
                    }

        except Exception as e:
            yield {"type": "error", "message": str(e)}