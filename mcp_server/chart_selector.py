# -*- coding: utf-8 -*-
import json
import logging
from typing import Optional

from mcp_server import llm_client
from mcp_server.chart_renderer import suggest_chart_type

logger = logging.getLogger(__name__)

_CHART_SELECTION_PROMPT = """You are a data visualization expert. Given the user's intent, data shape, and available chart library capabilities, select the best chart type and provide a render specification.

Available chart types (ECharts):
- kpi_card: Single value display with optional sub-metrics
- line: Trend over time or ordered dimension
- bar: Comparison across categories
- pie: Part-to-whole proportion
- funnel: Sequential conversion steps
- scatter: Correlation between two numeric dimensions
- bar_line: Dual-axis chart combining bars (primary) and lines (secondary)
- boxplot: Distribution with quartiles/outliers
- ranking_bar: Horizontal bar for Top-N rankings
- area: Filled area for cumulative trends
- radar: Multi-dimensional comparison
- gauge: Single value against a scale
- ring/doughnut: Pie variant with center hollow
- stackedBar/stackedLine: Stacked comparisons
- candlestick: Open-high-low-close financial data
- heatmap: 2D density/intensity
- treemap: Hierarchical proportions
- sankey: Flow between categories

User intent: {intent}
Data shape: {row_count} rows × {col_count} columns
Columns: {columns}
Sample data: {sample}
Title: {title}
User-specified chart type: {user_chart_type}

Respond with JSON only:
{{
  "chart_type": "best_chart_type",
  "x_axis_label": "label or empty",
  "y_axis_label": "label or empty",
  "reasoning": "Brief explanation of why this chart type best serves the user's intent",
  "alternatives": ["list", "of", "1-2", "alternative", "types"],
  "confidence": 0.0_to_1.0
}}

Rules:
- If user_chart_type is specified and makes sense for the data, use it but explain why
- If user_chart_type conflicts with the data shape (e.g., pie with 50 categories), suggest better alternatives
- For single-row data showing a single value, prefer kpi_card
- For trend over time with both absolute and rate values, prefer bar_line
- For proportion/composition with <=8 categories, prefer pie
- For proportion with >8 categories, prefer bar or treemap
- For ranking/top-N, prefer ranking_bar
- For distribution analysis, prefer boxplot or bar
"""


def resolve_chart_type(
    data: list[dict],
    title: str = "",
    intent: str = "",
    user_chart_type: str = "",
    use_llm: bool = True,
) -> dict:
    """
    Resolve the best chart type based on intent, data shape, and user preference.

    Priority:
      1. user_chart_type (explicit user request)
      2. LLM inference from intent + data shape
      3. Rule-based fallback (suggest_chart_type)

    Returns:
      {
        "chart_type": str,
        "x_axis_label": str,
        "y_axis_label": str,
        "reasoning": str,
        "alternatives": list[str],
        "confidence": float,
      }
    """
    if not data:
        return {
            "chart_type": user_chart_type or "table",
            "x_axis_label": "",
            "y_axis_label": "",
            "reasoning": "No data available",
            "alternatives": [],
            "confidence": 1.0,
        }

    keys = list(data[0].keys())
    sample = data[:3]

    rule_based = suggest_chart_type(data, f"{title} {intent}")

    if user_chart_type and not intent:
        return _build_spec(
            chart_type=user_chart_type,
            reasoning=f"User explicitly requested {user_chart_type}",
            alternatives=[rule_based] if rule_based != user_chart_type else [],
            confidence=0.9,
        )

    if use_llm and intent and llm_client.is_available():
        try:
            llm_result = _llm_resolve(intent, data, title, user_chart_type, keys, sample)
            if llm_result:
                return llm_result
        except Exception as e:
            logger.warning(f"LLM chart resolution failed, falling back to rules: {e}")

    effective_type = user_chart_type or rule_based
    return _build_spec(
        chart_type=effective_type,
        reasoning=f"Rule-based inference from data shape ({len(data)} rows, {len(keys)} cols) and intent keywords",
        alternatives=[],
        confidence=0.6,
    )


def _llm_resolve(
    intent: str,
    data: list[dict],
    title: str,
    user_chart_type: str,
    keys: list,
    sample: list,
) -> Optional[dict]:
    prompt = _CHART_SELECTION_PROMPT.format(
        intent=intent,
        row_count=len(data),
        col_count=len(keys),
        columns=keys,
        sample=sample,
        title=title,
        user_chart_type=user_chart_type or "(not specified)",
    )

    response = llm_client.call_llm(
        prompt=prompt,
        system_msg="You are a data visualization expert. Respond with valid JSON only.",
        max_tokens=512,
        temperature=0.1,
    )

    result = json.loads(response)
    return _build_spec(
        chart_type=result.get("chart_type", ""),
        reasoning=result.get("reasoning", ""),
        alternatives=result.get("alternatives", []),
        confidence=result.get("confidence", 0.5),
        x_axis_label=result.get("x_axis_label", ""),
        y_axis_label=result.get("y_axis_label", ""),
    )


def _build_spec(
    chart_type: str,
    reasoning: str,
    alternatives: list,
    confidence: float,
    x_axis_label: str = "",
    y_axis_label: str = "",
) -> dict:
    return {
        "chart_type": chart_type,
        "x_axis_label": x_axis_label,
        "y_axis_label": y_axis_label,
        "reasoning": reasoning,
        "alternatives": alternatives,
        "confidence": confidence,
    }
