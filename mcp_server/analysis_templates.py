# -*- coding: utf-8 -*-
"""
L2 Analysis Templates: Retention, Funnel, Period-over-Period
These templates encapsulate complex analytical patterns so that Hermes
only needs to fill in parameters, not write SQL.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RetentionParams:
    anchor_event: str
    return_event: str
    day_offsets: list[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    event_column: str = "span_name"

    def __post_init__(self):
        if self.day_offsets is None:
            self.day_offsets = [1, 3, 7, 14, 30]


@dataclass
class FunnelParams:
    steps: list[str]
    within_days: int = 7
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    event_column: str = "span_name"


@dataclass
class PeriodOverPeriodParams:
    metric: str
    dimension: str
    period_type: str = "wow"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def build_retention_sql(params: RetentionParams, table: str = "events") -> str:
    """
    Build retention analysis SQL.
    Day-N retention = users active on day 0 AND still active on day N / users active on day 0.
    Uses self-join on reduser_id.
    """
    day_offsets = params.day_offsets or [1, 3, 7, 14, 30]

    date_filter_parts = []
    if params.start_date:
        date_filter_parts.append(f"a.event_date >= '{params.start_date}'")
    if params.end_date:
        date_filter_parts.append(f"a.event_date <= '{params.end_date}'")
    date_filter = " AND ".join(date_filter_parts)
    if date_filter:
        date_filter = "AND " + date_filter

    cohort_cte = f"""
    cohort AS (
        SELECT
            reduser_id,
            event_date AS cohort_date
        FROM {table}
        WHERE {params.event_column} = '{params.anchor_event}'
        {date_filter}
        GROUP BY reduser_id, event_date
    )"""

    retention_parts = []
    for n in day_offsets:
        retention_parts.append(f"""
        DAY_{n} AS (
            SELECT
                c.cohort_date,
                COUNT(DISTINCT c.reduser_id) AS day_{n}_retained
            FROM cohort c
            INNER JOIN {table} e
                ON c.reduser_id = e.reduser_id
                AND e.event_date = c.cohort_date + INTERVAL '{n}' DAY
                AND e.{params.event_column} = '{params.return_event}'
            GROUP BY c.cohort_date
        )""")

    cohort_size = f"""
    cohort_size AS (
        SELECT
            cohort_date,
            COUNT(DISTINCT reduser_id) AS cohort_users
        FROM cohort
        GROUP BY cohort_date
    )"""

    join_parts = ["cs.cohort_date", "cs.cohort_users"]
    join_clauses = []
    for n in day_offsets:
        join_parts.append(f"d{n}.day_{n}_retained")
        join_clauses.append(f"LEFT JOIN DAY_{n} d{n} ON cs.cohort_date = d{n}.cohort_date")

    select_clause = ", ".join(join_parts)
    from_clause = "\n".join(join_clauses)

    final_select = f"""
    SELECT
        {select_clause}
        {', ' + ', '.join([f"ROUND(CAST(day_{n}_retained AS DOUBLE) / NULLIF(cohort_users, 0) * 100, 2) AS day_{n}_rate" for n in day_offsets])}
    FROM cohort_size cs
    {from_clause}
    ORDER BY cs.cohort_date
    """

    ctes = [cohort_cte] + retention_parts + [cohort_size]
    cte_clause = ",\n".join(ctes)

    sql = f"WITH {cte_clause}\n{final_select}"
    return sql


def build_funnel_sql(params: FunnelParams, table: str = "events") -> str:
    """
    Build funnel analysis SQL.
    Counts users who completed each step in order within a time window.
    """
    if len(params.steps) < 2:
        raise ValueError("Funnel requires at least 2 steps")

    date_filter_parts = []
    if params.start_date:
        date_filter_parts.append(f"event_date >= '{params.start_date}'")
    if params.end_date:
        date_filter_parts.append(f"event_date <= '{params.end_date}'")
    date_filter = " AND ".join(date_filter_parts)
    if date_filter:
        date_filter = "AND " + date_filter

    step_ctes = []
    for i, step in enumerate(params.steps):
        step_ctes.append(f"""
    step_{i} AS (
        SELECT
            reduser_id,
            MIN(event_date) AS step_{i}_date
        FROM {table}
        WHERE {params.event_column} = '{step}'
        {date_filter}
        GROUP BY reduser_id
    )""")

    join_chain = f"step_0 s0"
    for i in range(1, len(params.steps)):
        join_chain += f"""
    INNER JOIN step_{i} s{i}
        ON s{i-1}.reduser_id = s{i}.reduser_id
        AND s{i}.step_{i}_date >= s{i-1}.step_{i-1}_date
        AND s{i}.step_{i}_date <= s{i-1}.step_{i-1}_date + INTERVAL '{params.within_days}' DAY"""

    step_counts = []
    for i, step in enumerate(params.steps):
        if i == 0:
            step_counts.append(f"COUNT(DISTINCT s0.reduser_id) AS step_{i}_cnt")
        else:
            step_counts.append(f"COUNT(DISTINCT s{i}.reduser_id) AS step_{i}_cnt")

    conversion_parts = []
    for i in range(1, len(params.steps)):
        conversion_parts.append(
            f"ROUND(CAST(step_{i}_cnt AS DOUBLE) / NULLIF(step_{i-1}_cnt, 0) * 100, 2) AS step_{i-1}_to_{i}_rate"
        )

    final_select = f"""
    SELECT
        {', '.join(step_counts)}
        {', ' + ', '.join(conversion_parts) if conversion_parts else ''}
    FROM {join_chain}"""

    cte_clause = ",\n".join(step_ctes)
    sql = f"WITH {cte_clause}\n{final_select}"
    return sql


def build_period_over_period_sql(params: PeriodOverPeriodParams, table: str = "events") -> str:
    """
    Build period-over-period comparison SQL (WoW or YoY).
    Uses LAG() window function.
    """
    metric_map = {
        "dau": "COUNT(DISTINCT reduser_id)",
        "total_events": "COUNT(*)",
        "avg_events_per_user": "CAST(COUNT(*) AS DOUBLE) / COUNT(DISTINCT reduser_id)",
        "avg_duration": "AVG(duration_sec)",
        "active_rate": "ROUND(CAST(COUNT(DISTINCT reduser_id) AS DOUBLE) / NULLIF((SELECT COUNT(DISTINCT reduser_id) FROM events), 0) * 100, 2)",
    }

    metric_sql = metric_map.get(params.metric, params.metric)

    if params.period_type == "wow":
        lag_expr = "LAG(current_value, 7) OVER (ORDER BY period)"
        period_label = "周环比"
    elif params.period_type == "yoy":
        lag_expr = "LAG(current_value, 365) OVER (ORDER BY period)"
        period_label = "同比"
    else:
        lag_expr = "LAG(current_value, 1) OVER (ORDER BY period)"
        period_label = "环比"

    date_filter_parts = []
    if params.start_date:
        date_filter_parts.append(f"event_date >= '{params.start_date}'")
    if params.end_date:
        date_filter_parts.append(f"event_date <= '{params.end_date}'")
    date_filter = " AND ".join(date_filter_parts)
    if date_filter:
        date_filter = "AND " + date_filter

    sql = f"""
    WITH daily AS (
        SELECT
            {params.dimension} AS period,
            {metric_sql} AS current_value
        FROM {table}
        WHERE 1=1 {date_filter}
        GROUP BY {params.dimension}
    ),
    with_prev AS (
        SELECT
            period,
            current_value,
            {lag_expr} AS prev_value
        FROM daily
    )
    SELECT
        period,
        current_value,
        prev_value,
        ROUND((current_value - prev_value) / NULLIF(prev_value, 0) * 100, 2) AS change_pct
    FROM with_prev
    WHERE prev_value IS NOT NULL
    ORDER BY period
    """

    return sql


ANALYSIS_TEMPLATES = {
    "retention": {
        "description": "留存分析：追踪用户在首次触发锚点事件后的N天回访率",
        "params_schema": {
            "anchor_event": "string - 锚点事件名称（如 'discovery_page_pageshow'）",
            "return_event": "string - 回访事件名称（如 'discovery_page_pageshow'）",
            "day_offsets": "list[int] - 留存天数偏移（默认 [1,3,7,14,30]）",
            "start_date": "string? - 起始日期（可选）",
            "end_date": "string? - 结束日期（可选）",
        },
        "builder": build_retention_sql,
        "param_class": RetentionParams,
    },
    "funnel": {
        "description": "漏斗分析：按顺序追踪用户在多步骤流程中的转化率",
        "params_schema": {
            "steps": "list[string] - 漏斗步骤事件名称列表（至少2步）",
            "within_days": "int - 完成漏斗的时间窗口天数（默认7）",
            "start_date": "string? - 起始日期（可选）",
            "end_date": "string? - 结束日期（可选）",
        },
        "builder": build_funnel_sql,
        "param_class": FunnelParams,
    },
    "period_over_period": {
        "description": "同环比分析：对比当前周期与上一周期的指标变化",
        "params_schema": {
            "metric": "string - 指标名称（dau/total_events/avg_events_per_user/avg_duration/active_rate）",
            "dimension": "string - 时间维度（event_date）",
            "period_type": "string - 对比类型（wow=周环比, yoy=同比）",
            "start_date": "string? - 起始日期（可选）",
            "end_date": "string? - 结束日期（可选）",
        },
        "builder": build_period_over_period_sql,
        "param_class": PeriodOverPeriodParams,
    },
}
