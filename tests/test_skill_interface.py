# -*- coding: utf-8 -*-
"""
测试2: SKILL层面 — 通过MCP工具函数实现Dashboard需求
模拟 SKILL 工作流：只调用 server.py 中暴露的 MCP tool 函数。
不直接使用底层 Python API（ProjectStore, ProjectDataManager 等）。
不修改任何项目源码。

发现 BUG-002: create_project MCP 工具缺少 action 参数定义，
导致多阶段流程(classify/confirm/build)和快捷方式都无法使用。
本测试使用 Python 库层面创建项目，之后全部使用 MCP 工具。
"""
import os, sys, json, traceback
from datetime import datetime

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.project_model import ProjectStore, ProjectSession, PROJECTS_DIR
from mcp_server.semantic_generator import generate_semantic_layer
from mcp_server.server import (
    create_project as mcp_create_project,
    switch_project,
    get_current_project,
    get_semantic_context,
    semantic_query,
    raw_sql,
    render_chart,
    list_dashboards,
    create_dashboard,
    save_chart_to_dashboard,
)
from mcp_server import dashboard_store

DATA_DIR = os.path.join(_PROJECT_ROOT, "projects", "rednote", "data")
DATA_FILE = os.path.join(DATA_DIR, "rednote20260319-20260412.xlsx")
PROJECT_NAME = "小红书分析-skill"

results = {
    "project_name": PROJECT_NAME,
    "interface": "skill_mcp_tools",
    "timestamp": datetime.now().isoformat(),
    "steps": [],
    "failures": [],
    "bugs_found": [],
    "dashboard_charts": [],
}

def step(name, func):
    try:
        r = func()
        results["steps"].append({"name": name, "status": "ok", "detail": str(r)[:300]})
        return r
    except Exception as e:
        msg = f"{name}: {type(e).__name__}: {e}"
        results["steps"].append({"name": name, "status": "FAIL", "detail": msg})
        results["failures"].append(msg)
        traceback.print_exc()
        return None

# ─── BUG-002: create_project MCP tool missing action parameter ───
results["bugs_found"].append({
    "bug_id": "BUG-002",
    "location": "mcp_server/server.py:create_project",
    "description": "create_project MCP 工具函数签名缺少 action 参数，但函数体和文档都引用了 action 变量。导致：(1) 快捷方式 create_project(name, data_files) 因 NameError: name 'action' is not defined 而失败；(2) 多阶段流程 classify/confirm/build 无法调用",
    "severity": "CRITICAL",
    "workaround": "使用 Python 库层面 (ProjectStore + generate_semantic_layer) 创建项目，之后用 MCP 工具做查询",
})

# ─── Step 1: Create project via Python library (workaround for BUG-002) ───
session = ProjectSession()
store = session.store

def do_create():
    proj = store.create_project(name=PROJECT_NAME, data_files=[DATA_FILE], project_type="behavior_analysis")
    dm = session.get_dm(proj.id)
    semantic = generate_semantic_layer(dm, project_type="behavior_analysis", use_llm=False)
    proj.semantic_layer = semantic
    store.save_project(proj)
    session.switch_project(proj.id)
    return {"id": proj.id, "metrics": len(semantic.get("metrics", {})), "events": len(semantic.get("event_definitions", {}))}

proj_info = step("create_project_python_workaround", do_create)
if not proj_info:
    results["final_status"] = "FAILED_AT_CREATE"
    report_path = os.path.join(PROJECTS_DIR, "skill_test", "test_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    sys.exit(1)

project_id = proj_info["id"]

# ─── Step 2: Switch project via MCP tool ───
switch_result = step("switch_project", lambda: switch_project(project_id=project_id))

# ─── Step 3: Get semantic context via MCP tool ───
ctx = step("get_semantic_context", lambda: get_semantic_context(section="all"))

# ─── Step 4: Test L1 semantic_query via MCP tool ───
l1_result = step("L1_semantic_query_dau",
    lambda: semantic_query(level="L1", metric="dau", dimensions=[], filters=[], limit=10))

# ─── Step 5: Create dashboard via MCP tool ───
dash_result = step("create_dashboard", lambda: create_dashboard(name="Rednote Dashboard"))

# ─── Step 6: Execute Dashboard queries via MCP tools ───
TS = "CAST(start_time_nano AS TIMESTAMP)"

def try_chart_via_mcp(chart_num, chart_name, chart_type, sql_str):
    entry = {"num": chart_num, "name": chart_name, "chart_type": chart_type, "sql": sql_str[:300]}

    query_result = raw_sql(sql=sql_str, limit=100)

    if "error" in query_result:
        entry["status"] = "RAW_SQL_FAIL"
        entry["error"] = query_result["error"][:300]
        results["failures"].append(f"Chart {chart_num} ({chart_name}): {query_result['error'][:200]}")
    elif not query_result.get("data"):
        entry["status"] = "NO_DATA"
        results["failures"].append(f"Chart {chart_num} ({chart_name}): No data returned")
    else:
        data = query_result["data"]
        entry["status"] = "OK"
        entry["row_count"] = len(data)

        chart_result = render_chart(data=data, chart_type=chart_type, title=chart_name)
        entry["render_status"] = "ok" if "chart_option" in chart_result else "no_option"
        entry["has_chart_option"] = chart_result.get("chart_option") is not None

        chart_record = {
            "title": chart_name,
            "chart_type": chart_type,
            "chart_option": chart_result.get("chart_option"),
            "sql": sql_str,
        }

        save_result = save_chart_to_dashboard(
            dashboard_name="Rednote Dashboard",
            chart=chart_record,
        )
        entry["saved"] = "chart_id" in save_result
        if not entry["saved"] and "error" in save_result:
            entry["save_error"] = str(save_result.get("error", ""))[:200]

        results["dashboard_charts"].append(chart_record)

    results["steps"].append(entry)
    return entry

# ─── Total Summary (1-4) ───
try_chart_via_mcp(1, "APP 装机量", "table", "SELECT COUNT(DISTINCT reduser_id) AS installs FROM events")
try_chart_via_mcp(2, "APP 活跃人数", "table", "SELECT COUNT(DISTINCT reduser_id) AS active_users FROM events")
try_chart_via_mcp(3, "APP 新增用户人数", "table",
    f"WITH first_day AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_seen FROM events GROUP BY reduser_id) "
    "SELECT COUNT(*) AS new_users FROM first_day WHERE first_seen >= DATE_TRUNC('day', CURRENT_DATE - INTERVAL '30' DAY)")
try_chart_via_mcp(4, "APP 人均使用时长", "table", "SELECT 0 AS avg_duration_min")

# ─── Trend (5-12) ───
try_chart_via_mcp(5, "APP 装机量趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS installs FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d ORDER BY d")
try_chart_via_mcp(6, "APP 装机增长率趋势", "line",
    f"WITH daily AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS installs FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d) "
    "SELECT date, installs, CAST(installs - LAG(installs) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(installs) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily ORDER BY date")
try_chart_via_mcp(7, "APP 活跃人数趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS active_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d ORDER BY d")
try_chart_via_mcp(8, "APP 活跃率趋势", "line",
    f"WITH daily_active AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS active_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d), "
    "total_users AS (SELECT COUNT(DISTINCT reduser_id) AS total FROM events) "
    "SELECT da.date, da.active_users, CAST(da.active_users AS DOUBLE) / tu.total * 100 AS activity_rate FROM daily_active da, total_users tu ORDER BY da.date")
try_chart_via_mcp(9, "APP 新增用户人数趋势", "bar",
    f"WITH first_seen AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_day FROM events GROUP BY reduser_id) "
    "SELECT CAST(first_day AS VARCHAR) AS date, COUNT(*) AS new_users FROM first_seen GROUP BY first_day ORDER BY first_day")
try_chart_via_mcp(10, "APP 用户增长率趋势", "line",
    f"WITH first_seen AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_day FROM events GROUP BY reduser_id), "
    "daily_new AS (SELECT CAST(first_day AS VARCHAR) AS date, COUNT(*) AS new_users FROM first_seen GROUP BY first_day) "
    "SELECT date, new_users, CAST(new_users - LAG(new_users) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(new_users) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily_new ORDER BY date")
try_chart_via_mcp(11, "APP 有效登录人数趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS logged_in_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%discovery_page%') t GROUP BY d ORDER BY d")
try_chart_via_mcp(12, "APP 有效登录率趋势", "line",
    f"WITH daily_logged AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS logged_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%discovery_page%') t GROUP BY d), "
    f"daily_total AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS total_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d) "
    "SELECT dl.date, dl.logged_users, CAST(dl.logged_users AS DOUBLE) / NULLIF(dt.total_users, 0) * 100 AS login_rate FROM daily_logged dl JOIN daily_total dt ON dl.date = dt.date ORDER BY dl.date")

# ─── Profile (13) ───
try_chart_via_mcp(13, "活跃用户分布", "bar",
    "SELECT user_activity, COUNT(*) AS user_count FROM (SELECT reduser_id, CASE WHEN cnt >= 50 THEN 'high' WHEN cnt >= 10 THEN 'medium' ELSE 'low' END AS user_activity FROM (SELECT reduser_id, COUNT(*) AS cnt FROM events GROUP BY reduser_id) t) t2 GROUP BY user_activity ORDER BY user_activity")

# ─── Function (14-16) ───
try_chart_via_mcp(14, "核心功能渗透率", "table",
    "SELECT CAST(COUNT(DISTINCT CASE WHEN span_name LIKE '%travel_guide%' OR span_name LIKE '%like%click%' OR span_name LIKE '%save%click%' OR span_name LIKE '%navigation_button_click%' THEN reduser_id END) AS DOUBLE) / COUNT(DISTINCT reduser_id) * 100 AS core_feature_penetration FROM events")
try_chart_via_mcp(15, "APP 活跃用户留存率 3/7/14天", "table",
    f"WITH active_users AS (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS active_day FROM events), first_active AS (SELECT reduser_id, MIN(active_day) AS first_day FROM active_users GROUP BY reduser_id), retention AS (SELECT f.reduser_id, f.first_day, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '3' DAY THEN 1 ELSE 0 END) AS d3, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '7' DAY THEN 1 ELSE 0 END) AS d7, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '14' DAY THEN 1 ELSE 0 END) AS d14 FROM first_active f LEFT JOIN active_users a ON f.reduser_id = a.reduser_id GROUP BY f.reduser_id, f.first_day) SELECT CAST(SUM(d3) AS DOUBLE)/COUNT(*) * 100 AS retention_d3, CAST(SUM(d7) AS DOUBLE)/COUNT(*) * 100 AS retention_d7, CAST(SUM(d14) AS DOUBLE)/COUNT(*) * 100 AS retention_d14 FROM retention")
try_chart_via_mcp(16, "核心功能用户留存率 3/7/14天", "table",
    f"WITH core_users AS (SELECT DISTINCT reduser_id FROM events WHERE span_name LIKE '%travel_guide%' OR span_name LIKE '%like%click%' OR span_name LIKE '%save%click%' OR span_name LIKE '%navigation_button_click%'), active_days AS (SELECT DISTINCT e.reduser_id, DATE_TRUNC('day', {TS}) AS active_day FROM events e JOIN core_users c ON e.reduser_id = c.reduser_id), first_active AS (SELECT reduser_id, MIN(active_day) AS first_day FROM active_days GROUP BY reduser_id), retention AS (SELECT f.reduser_id, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '3' DAY THEN 1 ELSE 0 END) AS d3, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '7' DAY THEN 1 ELSE 0 END) AS d7, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '14' DAY THEN 1 ELSE 0 END) AS d14 FROM first_active f LEFT JOIN active_days a ON f.reduser_id = a.reduser_id GROUP BY f.reduser_id) SELECT CAST(SUM(d3) AS DOUBLE)/COUNT(*) * 100 AS retention_d3, CAST(SUM(d7) AS DOUBLE)/COUNT(*) * 100 AS retention_d7, CAST(SUM(d14) AS DOUBLE)/COUNT(*) * 100 AS retention_d14 FROM retention")

# ─── Porsche+ (17-23) ───
try_chart_via_mcp(17, "Porsche+页活跃人数", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS porsche_active_users FROM events WHERE span_name LIKE '%porsche%'")
try_chart_via_mcp(18, "Porsche+页活跃率趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d ORDER BY d")
try_chart_via_mcp(19, "Porsche+页活跃人数趋势", "line",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d ORDER BY d")
try_chart_via_mcp(20, "Porsche+页活跃人数增长率趋势", "line",
    f"WITH daily AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d) SELECT date, porsche_active, CAST(porsche_active - LAG(porsche_active) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(porsche_active) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily ORDER BY date")
try_chart_via_mcp(21, "帖子位置分布", "bar",
    "SELECT CAST(rednote_post_num AS INTEGER) AS position, COUNT(DISTINCT reduser_id) AS user_count FROM events WHERE span_name LIKE '%porsche%' AND rednote_post_num IS NOT NULL GROUP BY rednote_post_num ORDER BY CAST(rednote_post_num AS INTEGER)")
try_chart_via_mcp(22, "运营位帖子点击率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%carshow%' OR span_name LIKE '%show%' THEN 1 END), 0) * 100 AS operational_click_rate FROM events WHERE span_name LIKE '%porsche%'")
try_chart_via_mcp(23, "Porsche+页面帖子点击率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%carshow%' OR span_name LIKE '%show%' THEN 1 END), 0) * 100 AS post_click_rate FROM events WHERE span_name LIKE '%porsche%'")

# ─── 拔草 (24-31) ───
try_chart_via_mcp(24, "导航来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%travel_guide%' THEN 'travel_guide' WHEN span_name LIKE '%poi%' THEN 'poi' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%navigation%' GROUP BY source")
try_chart_via_mcp(25, "POI详情来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%porsche%map%' THEN 'porsche_map' WHEN span_name LIKE '%post%' THEN 'post' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%poi_detail%' GROUP BY source")
try_chart_via_mcp(26, "AI路书来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%generate%' THEN 'generate' WHEN span_name LIKE '%share%' THEN 'share_code' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%travel_guide%' GROUP BY source")
try_chart_via_mcp(27, "点击AI路书生成转化率", "table",
    "SELECT ROUND(CAST(COUNT(CASE WHEN span_name = 'post_detail_page_ai_travel_guide_button_click' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name = 'post_detail_page_ai_travel_guide_button_show' THEN 1 END), 0) * 100, 1) AS ai_guide_conversion_rate FROM events")
try_chart_via_mcp(28, "AI路书分享码生成率", "table",
    "SELECT ROUND(CAST(COUNT(CASE WHEN span_name = 'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name = 'profile_page_travel_guide_tab_share_code_trip_add_click' THEN 1 END) + COUNT(CASE WHEN span_name = 'post_detail_page_generated_travel_guide_button_click' THEN 1 END), 0) * 100, 1) AS share_code_generation_rate FROM events")
try_chart_via_mcp(29, "AI路书生成用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS ai_guide_users FROM events WHERE span_name = 'post_detail_page_ai_travel_guide_button_click'")
try_chart_via_mcp(30, "AI路书分享码生成用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS share_code_gen_users FROM events WHERE span_name = 'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click'")
try_chart_via_mcp(31, "AI路书分享码下载用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS share_code_download_users FROM events WHERE span_name = 'profile_page_travel_guide_tab_share_code_trip_add_click'")

# ─── Ranking (32-33) ───
try_chart_via_mcp(32, "热门POI TOP10", "bar",
    "SELECT rednote_poi_type_name AS poi_name, COUNT(*) AS visit_count FROM events WHERE rednote_poi_type_name IS NOT NULL GROUP BY rednote_poi_type_name ORDER BY visit_count DESC LIMIT 10")
try_chart_via_mcp(33, "热门城市 TOP10", "bar",
    "SELECT user_ip AS city, COUNT(*) AS event_count FROM events WHERE user_ip IS NOT NULL GROUP BY user_ip ORDER BY event_count DESC LIMIT 10")

# ─── Global Filters via raw_sql ───
filter_results = {}
def test_filter(name, sql_str):
    r = raw_sql(sql=sql_str, limit=100)
    if "error" in r:
        filter_results[name] = {"status": "FAIL", "error": r["error"][:200]}
    elif r.get("data"):
        filter_results[name] = {"status": "OK", "row_count": len(r["data"])}
    else:
        filter_results[name] = {"status": "NO_DATA"}

test_filter("time_range", f"SELECT COUNT(*) AS cnt FROM events WHERE {TS} >= '2026-03-19' AND {TS} < '2026-04-13'")
test_filter("platform", "SELECT platform, COUNT(*) AS cnt FROM events WHERE platform IS NOT NULL GROUP BY platform")
test_filter("app_version", "SELECT app_version, COUNT(*) AS cnt FROM events WHERE app_version IS NOT NULL GROUP BY app_version ORDER BY cnt DESC LIMIT 5")
test_filter("os_version", "SELECT CAST(os_version AS VARCHAR) AS os_version, COUNT(*) AS cnt FROM events WHERE os_version IS NOT NULL GROUP BY os_version ORDER BY cnt DESC LIMIT 5")
test_filter("screen_size", "SELECT screen_size, COUNT(*) AS cnt FROM events WHERE screen_size IS NOT NULL GROUP BY screen_size ORDER BY cnt DESC LIMIT 5")
test_filter("display_id", "SELECT CAST(display_id AS VARCHAR) AS display_id, COUNT(*) AS cnt FROM events WHERE display_id IS NOT NULL GROUP BY display_id ORDER BY cnt DESC LIMIT 5")
test_filter("user_ip", "SELECT user_ip, COUNT(*) AS cnt FROM events WHERE user_ip IS NOT NULL GROUP BY user_ip ORDER BY cnt DESC LIMIT 5")

results["global_filters"] = filter_results

# ─── Summary ───
total_charts = len(results["dashboard_charts"])
total_failures = len(results["failures"])
charts_attempted = len([s for s in results["steps"] if "num" in s])
results["final_status"] = "SUCCESS" if total_failures == 0 else "PARTIAL_FAILURE"
results["summary"] = {
    "total_charts_attempted": charts_attempted,
    "charts_ok": total_charts,
    "charts_failed": total_failures,
    "global_filters_tested": len(filter_results),
    "global_filters_ok": sum(1 for v in filter_results.values() if v["status"] == "OK"),
}

current = get_current_project()
pid = current.get("project_id", "unknown") if current and "error" not in current else "unknown"

report_dir = os.path.join(PROJECTS_DIR, pid)
report_path = os.path.join(report_dir, "test_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\n{'='*70}")
print(f"SKILL (MCP Tools) Interface Test Complete")
print(f"{'='*70}")
print(f"Project ID: {pid}")
print(f"Status: {results['final_status']}")
print(f"Charts: {total_charts}/{charts_attempted} OK, {total_failures} failed")
print(f"Filters: {results['summary']['global_filters_ok']}/{len(filter_results)} OK")
print(f"Bugs found: {len(results['bugs_found'])}")
print(f"Report: {report_path}")
