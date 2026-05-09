# -*- coding: utf-8 -*-
"""
Dashboard HTML Renderer: Generate self-contained HTML dashboard from stored JSON.

Design principle: chart_option stores DATA only; all styling comes from ECharts theme.
This ensures theme switching works correctly and HTML size stays small.
"""

import json
import os
from typing import Optional

from mcp_server.themes import load_theme, list_themes
from mcp_server.echarts_inline import get_echarts_js as _get_inline_echarts

_STYLE_KEYS = frozenset({
    "color", "backgroundColor", "textStyle",
    "title", "tooltip", "grid",
    "categoryAxis", "valueAxis", "logAxis", "timeAxis",
    "line", "bar", "pie", "scatter", "funnel",
    "radar", "gauge", "map", "sankey", "boxplot",
})

_DATA_KEYS_TO_KEEP_IN_SERIES = frozenset({
    "type", "name", "data", "smooth", "stack", "areaStyle",
    "step", "encode", "datasetIndex", "seriesLayoutBy",
    "yAxisIndex",
})


def _strip_style_from_option(option: dict) -> dict:
    """Remove style-only top-level keys from chart option, keeping data/layout."""
    cleaned = {}
    for k, v in option.items():
        if k in _STYLE_KEYS:
            continue
        if k == "series":
            cleaned["series"] = _strip_series_style(v)
        elif k in ("xAxis", "yAxis"):
            cleaned[k] = _strip_axis_style(v)
        elif k == "legend":
            cleaned["legend"] = _strip_legend_style(v)
        else:
            cleaned[k] = v
    return cleaned


def _strip_series_style(series_list: list) -> list:
    result = []
    for s in series_list:
        if isinstance(s, dict):
            item = {k: v for k, v in s.items() if k in _DATA_KEYS_TO_KEEP_IN_SERIES}
            if "type" in s and s["type"] == "pie":
                item["radius"] = s.get("radius", ["35%", "65%"])
                item["center"] = s.get("center", ["55%", "55%"])
                item["label"] = s.get("label")
                item["emphasis"] = s.get("emphasis")
            if "type" in s and s["type"] == "funnel":
                item["left"] = s.get("left", "10%")
                item["top"] = s.get("top", 40)
                item["width"] = s.get("width", "80%")
                item["sort"] = s.get("sort", "descending")
                item["gap"] = s.get("gap", 4)
                item["label"] = s.get("label")
                item["labelLine"] = s.get("labelLine")
                item["itemStyle"] = s.get("itemStyle")
                if "data" in s:
                    item["data"] = _strip_funnel_data_style(s["data"])
            result.append(item)
        else:
            result.append(s)
    return result


def _strip_axis_style(axis) -> dict | list:
    if isinstance(axis, list):
        return [_strip_axis_style(a) for a in axis]
    if not isinstance(axis, dict):
        return axis
    data_keys = {"type", "data", "name", "min", "max", "splitNumber", "boundaryGap", "inverse"}
    return {k: v for k, v in axis.items() if k in data_keys}


def _strip_legend_style(legend) -> dict:
    if not isinstance(legend, dict):
        return legend
    data_keys = {"data", "selected", "selectable", "orient"}
    return {k: v for k, v in legend.items() if k in data_keys}


def _strip_funnel_data_style(data_list: list) -> list:
    result = []
    for item in data_list:
        if not isinstance(item, dict):
            result.append(item)
            continue
        clean = {"name": item.get("name"), "value": item.get("value")}
        if "label" in item:
            clean["label"] = item["label"]
        result.append(clean)
    return result


def render_dashboard_html(
    dashboard: dict,
    project_name: str = "",
    theme: str = "ggplot2_minimal",
    title: Optional[str] = None,
) -> str:
    theme_obj = load_theme(theme)
    is_dark = "dark" in theme
    bg_color = "#1a1a2e" if is_dark else "#f8f9fa"
    card_bg = "#16213e" if is_dark else "#ffffff"
    text_color = "#e0e0e0" if is_dark else "#1a1a1a"
    text_secondary = "#a0a0a0" if is_dark else "#666666"
    border_color = "#2a2a4a" if is_dark else "#e8e8e8"
    accent_color = "#4E79A7" if not is_dark else "#5B9BD5"
    domain_accent = "#59A14F" if not is_dark else "#8CD17D"

    theme_json = json.dumps(theme_obj, ensure_ascii=False) if theme_obj else "{}"
    dashboard_title = title or dashboard.get("name", "Dashboard")
    charts = dashboard.get("charts", [])

    DOMAIN_ORDER = [
        "overview", "porsche", "discovery", "ai_travel_guide",
        "share_code", "content_interaction", "retention", "poi",
        "distribution", "other",
    ]

    domain_groups = {}
    domain_labels = {}
    for i, chart in enumerate(charts):
        chart_type = chart.get("chart_type", "table")
        chart_option = chart.get("chart_option")
        chart_title = chart.get("title", "")
        if not chart_title and isinstance(chart_option, dict):
            opt_title = chart_option.get("title", {})
            if isinstance(opt_title, dict):
                chart_title = opt_title.get("text", "")
            elif isinstance(opt_title, str):
                chart_title = opt_title
        if not chart_title:
            chart_title = f"Chart {i + 1}"
        data_sample = chart.get("data_sample", [])
        domain = chart.get("business_domain", "other") or "other"
        domain_label = chart.get("business_domain_label", domain) or domain

        if domain not in domain_groups:
            domain_groups[domain] = []
            domain_labels[domain] = domain_label

        if chart_type == "kpi_card" and chart_option:
            kpi_val = chart_option.get("value")
            metric_type = chart_option.get("metric_type", "")
            domain_groups[domain].append({
                "kind": "kpi",
                "html": _render_kpi_card_from_option(
                    chart_title, kpi_val, metric_type, card_bg, text_color,
                    text_secondary, border_color, accent_color, is_dark,
                    sub_text=chart_option.get("sub_text", "")),
            })
        elif chart_type == "table" or chart_option is None:
            domain_groups[domain].append({
                "kind": "kpi",
                "html": _render_kpi_card(
                    chart_title, data_sample, card_bg, text_color,
                    text_secondary, border_color, accent_color, is_dark),
            })
        else:
            is_funnel = chart_type == "funnel"
            is_full_width = chart_type in ("funnel", "boxplot")
            clean_option = _strip_style_from_option(chart_option)
            domain_groups[domain].append({
                "kind": "chart",
                "html": _render_chart_card(
                    i, chart_title, clean_option, card_bg, text_color,
                    border_color, is_dark, is_funnel=is_funnel,
                    is_full_width=is_full_width),
            })

    ordered_domains = []
    for d in DOMAIN_ORDER:
        if d in domain_groups:
            ordered_domains.append(d)
    for d in domain_groups:
        if d not in ordered_domains:
            ordered_domains.append(d)

    domain_sections = []
    for domain in ordered_domains:
        items = domain_groups[domain]
        label = domain_labels[domain]
        kpi_items = [it for it in items if it["kind"] == "kpi"]
        chart_items = [it for it in items if it["kind"] == "chart"]

        kpi_html = ""
        if kpi_items:
            kpi_html = f'<div class="kpi-row">{"".join(it["html"] for it in kpi_items)}</div>'

        chart_html = ""
        if chart_items:
            chart_html = f'<div class="chart-grid">{"".join(it["html"] for it in chart_items)}</div>'

        domain_sections.append(f"""
        <section class="domain-section" data-domain="{_esc(domain)}" data-domain-label="{_esc(label)}">
            <div class="domain-header">
                <span class="domain-accent"></span>
                <h2 class="domain-title">{_esc(label)}</h2>
            </div>
            {kpi_html}
            {chart_html}
        </section>""")

    body_content = "\n".join(domain_sections)

    date_start_val = ""
    date_end_val = ""
    all_dates = []
    for chart in charts:
        opt = chart.get("chart_option")
        if isinstance(opt, dict):
            x_data = opt.get("xAxis", {})
            if isinstance(x_data, dict):
                x_data = x_data.get("data", [])
            if isinstance(x_data, list):
                for v in x_data:
                    s = str(v)
                    if len(s) >= 10 and s[:4].isdigit():
                        all_dates.append(s[:10])
    if all_dates:
        all_dates.sort()
        date_start_val = all_dates[0]
        date_end_val = all_dates[-1]

    date_range_label = ""
    if date_start_val and date_end_val:
        date_range_label = f"{date_start_val} ~ {date_end_val}"

    theme_switcher = ""
    available_themes = list_themes()
    if len(available_themes) > 1:
        options = []
        for t in available_themes:
            selected = " selected" if t == theme else ""
            label = t.replace("_", " ").title()
            options.append(f'<option value="{t}"{selected}>{label}</option>')
        theme_switcher = f"""
        <div class="theme-switcher">
            <label for="theme-select">Theme:</label>
            <select id="theme-select">{''.join(options)}</select>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(dashboard_title)} - {_esc(project_name)}</title>
<script>""" + _get_inline_echarts() + """</script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: {bg_color};
    color: {text_color};
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
}}
.dashboard {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px 32px;
}}
.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 28px;
    padding-bottom: 16px;
    border-bottom: 1px solid {border_color};
}}
.header h1 {{
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.3px;
}}
.header .subtitle {{
    font-size: 13px;
    color: {text_secondary};
    margin-top: 4px;
}}
.theme-switcher {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: {text_secondary};
}}
.theme-switcher select {{
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid {border_color};
    background: {card_bg};
    color: {text_color};
    font-size: 13px;
    cursor: pointer;
}}
.domain-section {{
    margin-bottom: 32px;
}}
.domain-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid {border_color};
}}
.domain-accent {{
    display: inline-block;
    width: 4px;
    height: 22px;
    border-radius: 2px;
    background: {domain_accent};
}}
.domain-title {{
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.2px;
}}
.kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
}}
.kpi-card {{
    background: {card_bg};
    border: 1px solid {border_color};
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    transition: box-shadow 0.2s;
}}
.kpi-card:hover {{
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}}
.kpi-card .kpi-title {{
    font-size: 12px;
    color: {text_secondary};
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}}
.kpi-card .kpi-value {{
    font-size: 28px;
    font-weight: 700;
    color: {accent_color};
    line-height: 1.2;
}}
.kpi-card .kpi-sub {{
    font-size: 11px;
    color: {text_secondary};
    margin-top: 4px;
}}
.chart-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}}
@media (max-width: 900px) {{
    .chart-grid {{ grid-template-columns: 1fr; }}
    .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
}}
.chart-card {{
    background: {card_bg};
    border: 1px solid {border_color};
    border-radius: 10px;
    padding: 16px;
    min-height: 320px;
    transition: box-shadow 0.2s;
}}
.chart-card:hover {{
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}}
.chart-card.chart-full-width {{
    grid-column: 1 / -1;
    min-height: 420px;
}}
.chart-card .chart-title {{
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 8px;
    color: {text_color};
}}
.chart-container {{
    width: 100%;
    height: 280px;
}}
.chart-full-width .chart-container {{
    height: 380px;
}}
.filter-bar {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding: 12px 16px;
    background: {card_bg};
    border: 1px solid {border_color};
    border-radius: 10px;
    flex-wrap: wrap;
}}
.filter-bar label {{
    font-size: 13px;
    color: {text_secondary};
    font-weight: 500;
}}
.filter-bar input[type="date"] {{
    padding: 4px 8px;
    border-radius: 6px;
    border: 1px solid {border_color};
    background: {bg_color};
    color: {text_color};
    font-size: 13px;
}}
.filter-bar .filter-btn {{
    padding: 4px 12px;
    border-radius: 6px;
    border: 1px solid {border_color};
    background: {card_bg};
    color: {text_color};
    font-size: 12px;
    cursor: pointer;
    transition: background 0.15s;
}}
.filter-bar .filter-btn:hover {{
    background: {border_color};
}}
.filter-bar .filter-btn.active {{
    background: {accent_color};
    color: #fff;
    border-color: {accent_color};
}}
</style>
</head>
<body>
<div class="dashboard">
    <div class="header">
        <div>
            <h1>{_esc(dashboard_title)}</h1>
            <div class="subtitle">{_esc(project_name)}{' | ' + _esc(date_range_label) if date_range_label else ''}</div>
        </div>
        {theme_switcher}
    </div>
    <div class="filter-bar" id="filter-bar">
        <label>时间范围</label>
        <input type="date" id="date-start" value="{_esc(date_start_val)}" />
        <span style="color:{text_secondary}">~</span>
        <input type="date" id="date-end" value="{_esc(date_end_val)}" />
        <button class="filter-btn" data-range="7">近7天</button>
        <button class="filter-btn" data-range="30">近30天</button>
        <button class="filter-btn active" data-range="all">全部</button>
    </div>
    {body_content}
</div>
<script>
(function() {{
    var themeData = {theme_json};
    echarts.registerTheme('dashboard-theme', themeData);
    var charts = [];
    var chartContainers = document.querySelectorAll('.chart-container');
    var originalOptions = [];
    chartContainers.forEach(function(el) {{
        var chart = echarts.init(el, 'dashboard-theme');
        charts.push(chart);
        var optionJson = el.getAttribute('data-option');
        var parsed = null;
        if (optionJson) {{
            try {{
                parsed = JSON.parse(optionJson);
                chart.setOption(parsed);
            }} catch(e) {{
                console.error('Chart option parse error:', e);
            }}
        }}
        originalOptions.push(parsed);
    }});
    window.addEventListener('resize', function() {{
        charts.forEach(function(c) {{ c.resize(); }});
    }});
    var themeSelect = document.getElementById('theme-select');
    if (themeSelect) {{
        themeSelect.addEventListener('change', function() {{
            var params = new URLSearchParams(window.location.search);
            params.set('theme', this.value);
            window.location.search = params.toString();
        }});
    }}

    function isDateString(s) {{
        if (typeof s !== 'string') return false;
        return /^\\d{{4}}[-/]\\d{{1,2}}[-/]\\d{{1,2}}/.test(s);
    }}

    function parseDate(s) {{
        if (!s) return null;
        var d = new Date(s.replace(/\\//g, '-'));
        return isNaN(d.getTime()) ? null : d;
    }}

    function applyDateFilter(startStr, endStr) {{
        var startDate = startStr ? parseDate(startStr) : null;
        var endDate = endStr ? parseDate(endStr) : null;
        if (endDate) endDate.setHours(23, 59, 59, 999);

        charts.forEach(function(chart, idx) {{
            var opt = originalOptions[idx];
            if (!opt) return;

            var xAxis = opt.xAxis;
            if (!xAxis || !xAxis.data || !Array.isArray(xAxis.data)) return;

            var hasDate = xAxis.data.some(function(v) {{ return isDateString(String(v)); }});
            if (!hasDate) return;

            var filteredIndices = [];
            xAxis.data.forEach(function(val, i) {{
                var d = parseDate(String(val));
                if (!d) {{ filteredIndices.push(i); return; }}
                if (startDate && d < startDate) return;
                if (endDate && d > endDate) return;
                filteredIndices.push(i);
            }});

            var newOpt = JSON.parse(JSON.stringify(opt));
            newOpt.xAxis.data = filteredIndices.map(function(i) {{ return xAxis.data[i]; }});
            if (newOpt.series) {{
                newOpt.series.forEach(function(s) {{
                    if (Array.isArray(s.data)) {{
                        s.data = filteredIndices.map(function(i) {{ return s.data[i]; }});
                    }}
                }});
            }}
            chart.setOption(newOpt, true);
        }});
    }}

    var dateStart = document.getElementById('date-start');
    var dateEnd = document.getElementById('date-end');
    var filterBtns = document.querySelectorAll('.filter-btn');

    filterBtns.forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            filterBtns.forEach(function(b) {{ b.classList.remove('active'); }});
            btn.classList.add('active');
            var range = btn.getAttribute('data-range');
            if (range === 'all') {{
                dateStart.value = '';
                dateEnd.value = '';
                charts.forEach(function(chart, idx) {{
                    if (originalOptions[idx]) {{
                        chart.setOption(originalOptions[idx], true);
                    }}
                }});
            }} else {{
                var end = new Date();
                var start = new Date();
                start.setDate(end.getDate() - parseInt(range));
                dateStart.value = start.toISOString().split('T')[0];
                dateEnd.value = end.toISOString().split('T')[0];
                applyDateFilter(dateStart.value, dateEnd.value);
            }}
        }});
    }});

    dateStart.addEventListener('change', function() {{
        filterBtns.forEach(function(b) {{ b.classList.remove('active'); }});
        applyDateFilter(dateStart.value, dateEnd.value);
    }});
    dateEnd.addEventListener('change', function() {{
        filterBtns.forEach(function(b) {{ b.classList.remove('active'); }});
        applyDateFilter(dateStart.value, dateEnd.value);
    }});
}})();
</script>
</body>
</html>"""
    return html


def _render_kpi_card(title, data_sample, card_bg, text_color, text_secondary, border_color, accent_color, is_dark):
    if not data_sample:
        value = "-"
        sub = ""
    else:
        row = data_sample[0]
        values = [v for v in row.values()]
        value = _format_number(values[0]) if values else "-"
        if len(values) > 1:
            sub = " | ".join(_format_number(v) for v in values[1:])
        else:
            sub = ""
    return f"""
            <div class="kpi-card">
                <div class="kpi-title">{_esc(title)}</div>
                <div class="kpi-value">{_esc(str(value))}</div>
                {f'<div class="kpi-sub">{_esc(sub)}</div>' if sub else ''}
            </div>"""


def _render_kpi_card_from_option(title, value, metric_type, card_bg, text_color, text_secondary, border_color, accent_color, is_dark, sub_text=""):
    formatted = _format_number(value)
    suffix = ""
    if metric_type == "rate" and value is not None:
        if isinstance(value, float) and abs(value) <= 1:
            formatted = f"{value * 100:.1f}%"
        elif isinstance(value, (int, float)):
            formatted = f"{value:.1f}%"
    elif metric_type == "duration" and value is not None:
        suffix = " 秒"
    sub_html = f'<div class="kpi-sub">{_esc(sub_text)}</div>' if sub_text else ""
    return f"""
            <div class="kpi-card">
                <div class="kpi-title">{_esc(title)}</div>
                <div class="kpi-value">{_esc(str(formatted))}{suffix}</div>
                {sub_html}
            </div>"""


def _render_chart_card(index, title, option, card_bg, text_color, border_color, is_dark, is_funnel=False, is_full_width=False):
    if isinstance(option, dict):
        option = {k: v for k, v in option.items() if k != "title"}
    option_json = json.dumps(option, ensure_ascii=False)
    full_width_class = " chart-full-width" if (is_funnel or is_full_width) else ""
    return f"""
            <div class="chart-card{full_width_class}">
                <div class="chart-title">{_esc(title)}</div>
                <div class="chart-container" id="chart-{index}" data-title="{_esc_attr(title)}" data-option='{_esc_attr(option_json)}'></div>
            </div>"""


def _format_number(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        if abs(v) >= 1_000:
            return f"{v / 1_000:.1f}K"
        if v == int(v):
            return str(int(v))
        return f"{v:.2f}"
    return str(v)


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;")


def export_dashboard_html(
    projects_dir: str,
    project_id: str,
    dashboard_name: str,
    theme: str = "ggplot2_minimal",
    output_path: Optional[str] = None,
) -> str:
    from mcp_server.dashboard_store import load_dashboard_by_name

    result = load_dashboard_by_name(projects_dir, project_id, dashboard_name)
    if not result:
        raise ValueError(f"Dashboard '{dashboard_name}' not found in project {project_id}")

    from mcp_server.project_model import ProjectStore
    store = ProjectStore(projects_dir)
    project = store.get_project(project_id)
    project_name = project.name if project else ""

    html = render_dashboard_html(result, project_name=project_name, theme=theme)

    if output_path is None:
        suffix = "_dark" if "dark" in theme else ""
        output_path = os.path.join(
            projects_dir, project_id, "dashboards",
            f"{dashboard_name}{suffix}.html",
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
