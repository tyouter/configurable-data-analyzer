# -*- coding: utf-8 -*-
"""
Chart Renderer: Generate ECharts option JSON from query results.
Also supports Playwright-based screenshot rendering for image output.
"""

import copy
import json
from typing import Optional

from mcp_server.themes import load_theme, deep_merge, list_themes

DEFAULT_THEME = "ggplot2_minimal"

CHART_TEMPLATES = {
    "line": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 32, "left": "right"},
        "grid": {"top": 60, "bottom": 24, "left": 16, "right": 16, "containLabel": True},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "series": [],
    },
    "bar": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 32, "left": "right"},
        "grid": {"top": 60, "bottom": 24, "left": 16, "right": 16, "containLabel": True},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "series": [],
    },
    "pie": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "item"},
        "legend": {"orient": "vertical", "left": "left", "top": 50},
        "series": [{"type": "pie", "radius": ["35%", "65%"], "center": ["55%", "55%"], "data": [], "label": {"formatter": "{b}: {d}%"}, "emphasis": {"label": {"show": True, "fontSize": 14, "fontWeight": "bold"}}}],
    },
    "funnel": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c} ({d}%)"},
        "series": [{"type": "funnel", "left": "10%", "top": 40, "width": "80%", "sort": "descending", "gap": 4, "data": [], "label": {"show": True, "position": "inside", "formatter": "{b}\n{c}", "fontSize": 12, "color": "#fff"}, "labelLine": {"show": True}, "itemStyle": {"borderColor": "#fff", "borderWidth": 1}}],
    },
    "scatter": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "item"},
        "legend": {"top": 32, "left": "right"},
        "grid": {"top": 60, "bottom": 24, "left": 16, "right": 16, "containLabel": True},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "value"},
        "series": [{"type": "scatter", "data": []}],
    },
    "bar_line": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 32, "left": "right"},
        "grid": {"top": 60, "bottom": 24, "left": 16, "right": 60, "containLabel": True},
        "xAxis": {"type": "category", "data": []},
        "yAxis": [{"type": "value"}, {"type": "value"}],
        "series": [],
    },
    "boxplot": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "item"},
        "grid": {"top": 60, "bottom": 24, "left": 16, "right": 16, "containLabel": True},
        "xAxis": {"type": "category", "data": []},
        "yAxis": {"type": "value"},
        "series": [{"type": "boxplot", "data": []}],
    },
    "ranking_bar": {
        "title": {"left": "left", "top": 5},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"top": 32, "left": "right"},
        "grid": {"top": 60, "bottom": 24, "left": "30%", "right": "10%", "containLabel": False},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "category", "data": [], "inverse": True},
        "series": [{"type": "bar", "data": []}],
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


def _apply_theme_to_option(option: dict, theme_name: str) -> dict:
    theme = load_theme(theme_name)
    if not theme:
        return option

    series_type = None
    for s in option.get("series", []):
        series_type = s.get("type")
        break

    merged = deep_merge(theme, option)

    if series_type and series_type in theme:
        series_theme = theme[series_type]
        for s in merged.get("series", []):
            if s.get("type") == series_type:
                s = deep_merge(s, series_theme)

    axis_type_map = {}
    if "xAxis" in merged:
        x_axis = merged["xAxis"]
        if isinstance(x_axis, dict):
            if x_axis.get("type") == "category" and "categoryAxis" in theme:
                axis_type_map["xAxis"] = "categoryAxis"
            elif "valueAxis" in theme:
                axis_type_map["xAxis"] = "valueAxis"
    if "yAxis" in merged:
        y_axis = merged["yAxis"]
        if isinstance(y_axis, dict):
            if "valueAxis" in theme:
                axis_type_map["yAxis"] = "valueAxis"
        elif isinstance(y_axis, list):
            if "valueAxis" in theme:
                axis_theme = theme["valueAxis"]
                merged["yAxis"] = [deep_merge(axis_theme, ax) if isinstance(ax, dict) else ax for ax in y_axis]

    for axis_key, theme_key in axis_type_map.items():
        axis_theme = theme[theme_key]
        merged[axis_key] = deep_merge(axis_theme, merged[axis_key])

    return merged


def build_echarts_option(
    chart_type: str,
    data: list[dict],
    title: str,
    theme: str = DEFAULT_THEME,
) -> Optional[dict]:
    """
    Build ECharts option dict from query result data.
    Returns None for 'table' type (no chart needed).
    """
    if chart_type == "table" or chart_type not in CHART_TEMPLATES:
        return None

    option = copy.deepcopy(CHART_TEMPLATES[chart_type])
    option["title"]["text"] = title

    if not data:
        option = _apply_theme_to_option(option, theme)
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
        funnel_data = []
        first_val = None
        for row in data:
            val = row[val_key]
            if first_val is None:
                first_val = val
            rate = (val / first_val * 100) if first_val and first_val != 0 else 0
            funnel_data.append({
                "name": str(row[name_key]),
                "value": val,
                "label": {
                    "formatter": f"{{b}}\n{{c}} ({rate:.1f}%)"
                }
            })
        option["series"][0]["data"] = funnel_data

    elif chart_type == "scatter":
        x_key = keys[0]
        y_key = keys[1] if len(keys) > 1 else keys[0]
        option["series"][0]["data"] = [
            [row[x_key], row[y_key]] for row in data
        ]

    elif chart_type == "bar_line":
        x_key = keys[0]
        y_keys = keys[1:]
        option["xAxis"]["data"] = [str(row[x_key]) for row in data]
        option["yAxis"] = [{"type": "value"} for _ in y_keys]
        option["series"] = []
        for i, yk in enumerate(y_keys):
            s_type = "bar" if i == 0 else "line"
            s = {
                "type": s_type,
                "name": yk,
                "data": [row.get(yk) for row in data],
                "yAxisIndex": i,
            }
            if s_type == "line":
                s["smooth"] = True
            option["series"].append(s)

    elif chart_type == "boxplot":
        if len(keys) >= 5:
            option["xAxis"]["data"] = [str(row[keys[0]]) for row in data]
            box_data = []
            for row in data:
                box_data.append([
                    row.get(keys[1], 0),
                    row.get(keys[2], 0),
                    row.get(keys[3], 0),
                    row.get(keys[4], 0),
                    row.get(keys[5], 0) if len(keys) > 5 else row.get(keys[4], 0),
                ])
            option["series"][0]["data"] = box_data
        elif len(keys) == 2:
            group_key = keys[0]
            val_key = keys[1]
            groups = {}
            for row in data:
                g = str(row[group_key])
                if g not in groups:
                    groups[g] = []
                v = row[val_key]
                if v is not None:
                    groups[g].append(v)
            option["xAxis"]["data"] = list(groups.keys())
            box_data = []
            for g_name, vals in groups.items():
                if not vals:
                    box_data.append([0, 0, 0, 0, 0])
                    continue
                sv = sorted(vals)
                n = len(sv)
                box_data.append([
                    sv[0],
                    sv[int(n * 0.25)],
                    sv[int(n * 0.5)],
                    sv[int(n * 0.75)],
                    sv[-1],
                ])
            option["series"][0]["data"] = box_data
        else:
            vals = []
            for row in data:
                for k in keys:
                    v = row.get(k)
                    if isinstance(v, (int, float)) and v is not None:
                        vals.append(v)
            if vals:
                sv = sorted(vals)
                n = len(sv)
                option["xAxis"]["data"] = ["Distribution"]
                option["series"][0]["data"] = [[
                    sv[0], sv[int(n * 0.25)], sv[int(n * 0.5)],
                    sv[int(n * 0.75)], sv[-1],
                ]]

    elif chart_type == "ranking_bar":
        if len(keys) >= 2:
            name_key = keys[0]
            val_key = keys[-1]
        else:
            name_key = keys[0]
            val_key = keys[0]
        sorted_data = sorted(data, key=lambda r: r.get(val_key, 0) or 0, reverse=True)[:10]
        option["yAxis"]["data"] = [str(r[name_key]) for r in reversed(sorted_data)]
        option["series"][0]["data"] = [r.get(val_key, 0) for r in reversed(sorted_data)]
        option["series"][0]["name"] = title

    option = _apply_theme_to_option(option, theme)
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
    if any(kw in ctx_lower for kw in ["排名", "排行", "top", "ranking"]):
        return "ranking_bar"
    if any(kw in ctx_lower for kw in ["箱线", "boxplot", "分位", "四分位"]):
        return "boxplot"
    if any(kw in ctx_lower for kw in ["柱线", "bar_line", "bar-line", "混合"]):
        return "bar_line"
    if any(kw in ctx_lower for kw in ["趋势", "变化", "时间", "每天", "trend", "line"]):
        return "line"

    if len(data) <= 8 and len(numeric_keys) <= 2:
        return "pie"
    if len(string_keys) >= 1 and len(numeric_keys) >= 1:
        if len(data) > 15:
            return "line"
        return "bar"

    return "table"


async def render_chart_to_image(option: dict, width: int = 800, height: int = 500, theme: str = DEFAULT_THEME) -> Optional[bytes]:
    """
    Render ECharts option to PNG image using Playwright.
    Requires: playwright install chromium
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    theme_obj = load_theme(theme)
    theme_json = json.dumps(theme_obj, ensure_ascii=False) if theme_obj else "{}"
    option_json = json.dumps(option, ensure_ascii=False)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    </head>
    <body style="margin:0;background:#fff;">
        <div id="chart" style="width:{width}px;height:{height}px;"></div>
        <script>
            echarts.registerTheme('custom', {theme_json});
            var chart = echarts.init(document.getElementById('chart'), 'custom');
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
