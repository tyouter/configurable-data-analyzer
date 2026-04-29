# -*- coding: utf-8 -*-
"""
Chart Renderer: Generate ECharts option JSON from query results.
Also supports Playwright-based screenshot rendering for image output.
"""

import json
from typing import Optional


CHART_TEMPLATES = {
    "line": {
        "title": {"left": "center", "top": 10, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 35, "left": "center", "itemWidth": 15, "itemHeight": 10},
        "grid": {"top": 60, "bottom": 30, "left": 50, "right": 30},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "series": [],
    },
    "bar": {
        "title": {"left": "center", "top": 10, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 35, "left": "center", "itemWidth": 15, "itemHeight": 10},
        "grid": {"top": 60, "bottom": 30, "left": 50, "right": 30},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "series": [],
    },
    "pie": {
        "title": {"left": "center", "top": 10, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "legend": {"orient": "vertical", "left": "left", "top": 50},
        "series": [{"type": "pie", "radius": "45%", "center": ["55%", "55%"], "data": []}],
    },
    "funnel": {
        "title": {"left": "center", "top": 10, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "series": [{"type": "funnel", "left": "10%", "top": 40, "width": "80%", "sort": "none", "data": []}],
    },
    "scatter": {
        "title": {"left": "center", "top": 10, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "legend": {"top": 35, "left": "center", "itemWidth": 15, "itemHeight": 10},
        "grid": {"top": 60, "bottom": 30, "left": 50, "right": 30},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "value"},
        "series": [{"type": "scatter", "data": []}],
    },
}


def _serialize_row(row: dict) -> dict:
    result = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif hasattr(v, "item"):
            result[k] = v.item()
        else:
            result[k] = v
    return result


def build_echarts_option(
    chart_type: str,
    data: list[dict],
    title: str,
) -> Optional[dict]:
    """
    Build ECharts option dict from query result data.
    Returns None for 'table' type (no chart needed).
    """
    if chart_type == "table" or chart_type not in CHART_TEMPLATES:
        return None

    import copy
    option = copy.deepcopy(CHART_TEMPLATES[chart_type])
    option["title"]["text"] = title

    if not data:
        return option

    data = [_serialize_row(row) for row in data]
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


def suggest_chart_type(data: list[dict], query_context: str = "") -> str:
    """
    Heuristically suggest a chart type based on data shape and query context.
    """
    if not data:
        return "table"

    keys = list(data[0].keys())
    numeric_keys = []
    string_keys = []
    for k in keys:
        sample_vals = [row.get(k) for row in data[:5]]
        if all(isinstance(v, (int, float)) for v in sample_vals if v is not None):
            numeric_keys.append(k)
        else:
            string_keys.append(k)

    ctx_lower = query_context.lower()

    if any(kw in ctx_lower for kw in ["漏斗", "funnel", "转化步骤", "转化率"]):
        return "funnel"
    if any(kw in ctx_lower for kw in ["占比", "分布", "比例", "构成", "pie"]):
        return "pie"
    if any(kw in ctx_lower for kw in ["趋势", "变化", "时间", "每天", "trend", "line"]):
        return "line"

    if len(data) <= 8 and len(numeric_keys) <= 2:
        return "pie"
    if len(string_keys) >= 1 and len(numeric_keys) >= 1:
        if len(data) > 15:
            return "line"
        return "bar"

    return "table"


async def render_chart_to_image(option: dict, width: int = 800, height: int = 500) -> Optional[bytes]:
    """
    Render ECharts option to PNG image using Playwright.
    Requires: playwright install chromium
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    option_json = json.dumps(option, ensure_ascii=False)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    </head>
    <body>
        <div id="chart" style="width:{width}px;height:{height}px;"></div>
        <script>
            var chart = echarts.init(document.getElementById('chart'));
            chart.setOption({option_json});
        </script>
    </body>
    </html>
    """

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.set_content(html, wait_until="networkidle")
            await page.wait_for_timeout(500)
            screenshot = await page.locator("#chart").screenshot(type="png")
            await browser.close()
            return screenshot
    except Exception:
        return None
