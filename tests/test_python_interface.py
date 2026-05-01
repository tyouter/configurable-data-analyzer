# -*- coding: utf-8 -*-
"""
测试1: 纯Python库层面 — 创建项目 + 实现Dashboard需求
只使用 mcp_server.* 的Python API，不修改任何项目源码。
"""
import os, sys, json, traceback
from datetime import datetime

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.project_model import ProjectStore, ProjectSession, ProjectDataManager, PROJECTS_DIR
from mcp_server.semantic_generator import generate_semantic_layer, detect_project_type
from mcp_server.semantic_query import validate_raw_sql
from mcp_server.chart_renderer import build_echarts_option, suggest_chart_type
from mcp_server import dashboard_store

DATA_DIR = os.path.join(_PROJECT_ROOT, "projects", "rednote", "data")
DATA_FILE = os.path.join(DATA_DIR, "rednote20260319-20260412.xlsx")
PROJECT_NAME = "小红书分析-python"

results = {
    "project_name": PROJECT_NAME,
    "interface": "python_library",
    "timestamp": datetime.now().isoformat(),
    "steps": [],
    "failures": [],
    "dashboard_charts": [],
}

session = ProjectSession()
store = session.store

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

# ─── Step 1: Create project ───
def create_project():
    proj = store.create_project(name=PROJECT_NAME, data_files=[DATA_FILE], project_type="behavior_analysis")
    dm = session.get_dm(proj.id)
    semantic = generate_semantic_layer(dm, project_type="behavior_analysis", use_llm=False)
    proj.semantic_layer = semantic
    store.save_project(proj)
    session.switch_project(proj.id)
    return {"id": proj.id, "metrics": len(semantic.get("metrics", {})), "events": len(semantic.get("event_definitions", {}))}

proj_info = step("create_project", create_project)
if not proj_info:
    results["final_status"] = "FAILED_AT_CREATE"
    report_path = os.path.join(PROJECTS_DIR, "python_test", "test_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    sys.exit(1)

project_id = proj_info["id"]
project = session.get_current_project()
dm = session.get_dm(project_id)

# ─── Step 2: Get semantic context ───
def get_context():
    semantic = project.semantic_layer
    metrics = list(semantic.get("metrics", {}).keys())
    events = list(semantic.get("event_definitions", {}).keys())
    return {"metrics_count": len(metrics), "events_count": len(events), "metrics": metrics, "events_sample": events[:10]}

ctx = step("get_semantic_context", get_context)

# ─── Step 3: Create dashboard ───
def create_dash():
    r = dashboard_store.create_dashboard(PROJECTS_DIR, project_id, "Rednote Dashboard")
    return r

dash_info = step("create_dashboard", create_dash)

# ─── Step 4: L1 semantic query test ───
def test_l1_query():
    from mcp_server.server import _build_dynamic_l1_query
    semantic = project.semantic_layer
    sql, err = _build_dynamic_l1_query(semantic_layer=semantic, metric="dau", dimensions=[], filters=[], limit=10)
    if err:
        return {"error": err}
    data = dm.execute(sql)
    return {"sql": sql[:200], "rows": len(data) if data else 0, "sample": data[:1] if data else []}

l1_result = step("L1_semantic_query_dau", test_l1_query)

# ─── Step 5: Execute Dashboard queries ───
def exec_query(sql_str):
    try:
        sql_str = validate_raw_sql(sql_str)
        data = dm.execute(sql_str)
        if data:
            data = _serialize(data)
        return data
    except Exception as e:
        return {"error": str(e)}

def _serialize(data):
    out = []
    for row in data:
        r = {}
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif hasattr(v, "item"):
                r[k] = v.item()
            else:
                r[k] = v
        out.append(r)
    return out

def try_chart(chart_num, chart_name, chart_type, sql_str):
    entry = {"num": chart_num, "name": chart_name, "chart_type": chart_type, "sql": sql_str[:300]}
    data = exec_query(sql_str)
    if isinstance(data, dict) and "error" in data:
        entry["status"] = "SQL_FAIL"
        entry["error"] = data["error"][:300]
        results["failures"].append(f"Chart {chart_num} ({chart_name}): SQL error - {data['error'][:200]}")
    elif not data:
        entry["status"] = "NO_DATA"
        results["failures"].append(f"Chart {chart_num} ({chart_name}): No data returned")
    else:
        entry["status"] = "OK"
        entry["row_count"] = len(data)
        chart_option = build_echarts_option(chart_type, data, chart_name)
        entry["has_chart_option"] = chart_option is not None
        chart_record = {
            "title": chart_name,
            "chart_type": chart_type,
            "chart_option": chart_option,
            "sql": sql_str,
            "data_sample": data[:3],
        }
        results["dashboard_charts"].append(chart_record)
        save_r = dashboard_store.save_chart(PROJECTS_DIR, project_id, "Rednote Dashboard", chart_record)
        entry["saved"] = save_r.get("chart_id") is not None
    results["steps"].append(entry)
    return entry

# start_time_nano is VARCHAR storing '2026-03-19 19:10:16' format
TS = "CAST(start_time_nano AS TIMESTAMP)"

# ─── Total Summary (1-4) ───
try_chart(1, "APP 装机量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS installs FROM events")
try_chart(2, "APP 活跃人数", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS active_users FROM events")
try_chart(3, "APP 新增用户人数", "table",
    f"WITH first_day AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_seen FROM events GROUP BY reduser_id) "
    "SELECT COUNT(*) AS new_users FROM first_day "
    "WHERE first_seen >= DATE_TRUNC('day', CURRENT_DATE - INTERVAL '30' DAY)")
try_chart(4, "APP 人均使用时长", "table",
    f"SELECT CAST(AVG(session_duration) AS INTEGER) AS avg_duration_min FROM ("
    f"SELECT reduser_id, SUM(CAST({TS} - CAST(end_time_nano AS TIMESTAMP) AS DOUBLE) * 24 * 60) AS session_duration "
    "FROM events WHERE start_time_nano IS NOT NULL AND end_time_nano IS NOT NULL "
    "GROUP BY reduser_id) t")

# ─── Trend (5-12) ───
try_chart(5, "APP 装机量趋势", "bar",
    f"SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS installs FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t "
    "GROUP BY d ORDER BY d")
try_chart(6, "APP 装机增长率趋势", "line",
    f"WITH daily AS (SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS installs FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d) "
    "SELECT date, installs, CAST(installs - LAG(installs) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(installs) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily ORDER BY date")
try_chart(7, "APP 活跃人数趋势", "bar",
    f"SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS active_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t "
    "GROUP BY d ORDER BY d")
try_chart(8, "APP 活跃率趋势", "line",
    f"WITH daily_active AS (SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS active_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d), "
    "total_users AS (SELECT COUNT(DISTINCT reduser_id) AS total FROM events) "
    "SELECT da.date, da.active_users, CAST(da.active_users AS DOUBLE) / tu.total * 100 AS activity_rate "
    "FROM daily_active da, total_users tu ORDER BY da.date")
try_chart(9, "APP 新增用户人数趋势", "bar",
    f"WITH first_seen AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_day FROM events GROUP BY reduser_id) "
    "SELECT CAST(first_day AS DATE) AS date, COUNT(*) AS new_users FROM first_seen GROUP BY first_day ORDER BY first_day")
try_chart(10, "APP 用户增长率趋势", "line",
    f"WITH first_seen AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_day FROM events GROUP BY reduser_id), "
    "daily_new AS (SELECT CAST(first_day AS DATE) AS date, COUNT(*) AS new_users FROM first_seen GROUP BY first_day) "
    "SELECT date, new_users, CAST(new_users - LAG(new_users) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(new_users) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily_new ORDER BY date")
try_chart(11, "APP 有效登录人数趋势", "bar",
    f"SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS logged_in_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d "
    "FROM events WHERE span_name LIKE '%discovery_page%') t GROUP BY d ORDER BY d")
try_chart(12, "APP 有效登录率趋势", "line",
    f"WITH daily_logged AS (SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS logged_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%discovery_page%') t GROUP BY d), "
    f"daily_total AS (SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS total_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d) "
    "SELECT dl.date, dl.logged_users, CAST(dl.logged_users AS DOUBLE) / NULLIF(dt.total_users, 0) * 100 AS login_rate "
    "FROM daily_logged dl JOIN daily_total dt ON dl.date = dt.date ORDER BY dl.date")

# ─── Profile (13) ───
try_chart(13, "活跃用户分布", "bar",
    "SELECT user_activity, COUNT(*) AS user_count FROM ("
    "SELECT reduser_id, CASE WHEN cnt >= 50 THEN 'high' WHEN cnt >= 10 THEN 'medium' ELSE 'low' END AS user_activity "
    "FROM (SELECT reduser_id, COUNT(*) AS cnt FROM events GROUP BY reduser_id) t) t2 "
    "GROUP BY user_activity ORDER BY user_activity")

# ─── Function (14-16) ───
try_chart(14, "核心功能渗透率", "table",
    "SELECT CAST(COUNT(DISTINCT CASE WHEN span_name LIKE '%travel_guide%' OR span_name LIKE '%like%click%' OR span_name LIKE '%save%click%' OR span_name LIKE '%navigation_button_click%' THEN reduser_id END) AS DOUBLE) / COUNT(DISTINCT reduser_id) * 100 AS core_feature_penetration FROM events")
try_chart(15, "APP 活跃用户留存率 3/7/14天", "table",
    f"WITH active_users AS (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS active_day FROM events), "
    f"first_active AS (SELECT reduser_id, MIN(active_day) AS first_day FROM active_users GROUP BY reduser_id), "
    "retention AS (SELECT f.reduser_id, f.first_day, "
    "MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '3' DAY THEN 1 ELSE 0 END) AS d3, "
    "MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '7' DAY THEN 1 ELSE 0 END) AS d7, "
    "MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '14' DAY THEN 1 ELSE 0 END) AS d14 "
    "FROM first_active f LEFT JOIN active_users a ON f.reduser_id = a.reduser_id GROUP BY f.reduser_id, f.first_day) "
    "SELECT CAST(SUM(d3) AS DOUBLE)/COUNT(*) * 100 AS retention_d3, CAST(SUM(d7) AS DOUBLE)/COUNT(*) * 100 AS retention_d7, CAST(SUM(d14) AS DOUBLE)/COUNT(*) * 100 AS retention_d14 FROM retention")
try_chart(16, "核心功能用户留存率 3/7/14天", "table",
    f"WITH core_users AS (SELECT DISTINCT reduser_id FROM events WHERE span_name LIKE '%travel_guide%' OR span_name LIKE '%like%click%' OR span_name LIKE '%save%click%' OR span_name LIKE '%navigation_button_click%'), "
    f"active_days AS (SELECT DISTINCT e.reduser_id, DATE_TRUNC('day', {TS}) AS active_day FROM events e JOIN core_users c ON e.reduser_id = c.reduser_id), "
    "first_active AS (SELECT reduser_id, MIN(active_day) AS first_day FROM active_days GROUP BY reduser_id), "
    "retention AS (SELECT f.reduser_id, "
    "MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '3' DAY THEN 1 ELSE 0 END) AS d3, "
    "MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '7' DAY THEN 1 ELSE 0 END) AS d7, "
    "MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '14' DAY THEN 1 ELSE 0 END) AS d14 "
    "FROM first_active f LEFT JOIN active_days a ON f.reduser_id = a.reduser_id GROUP BY f.reduser_id) "
    "SELECT CAST(SUM(d3) AS DOUBLE)/COUNT(*) * 100 AS retention_d3, CAST(SUM(d7) AS DOUBLE)/COUNT(*) * 100 AS retention_d7, CAST(SUM(d14) AS DOUBLE)/COUNT(*) * 100 AS retention_d14 FROM retention")

# ─── Porsche+ (17-23) ───
try_chart(17, "Porsche+页活跃人数", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS porsche_active_users FROM events WHERE span_name LIKE '%porsche%'")
try_chart(18, "Porsche+页活跃率趋势", "bar",
    f"SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d ORDER BY d")
try_chart(19, "Porsche+页活跃人数趋势", "line",
    f"SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d ORDER BY d")
try_chart(20, "Porsche+页活跃人数增长率趋势", "line",
    f"WITH daily AS (SELECT CAST(d AS DATE) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d) "
    "SELECT date, porsche_active, CAST(porsche_active - LAG(porsche_active) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(porsche_active) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily ORDER BY date")
try_chart(21, "帖子位置分布", "bar",
    "SELECT CAST(rednote_post_num AS INTEGER) AS position, COUNT(DISTINCT reduser_id) AS user_count "
    "FROM events WHERE span_name LIKE '%porsche%' AND rednote_post_num IS NOT NULL "
    "GROUP BY rednote_post_num ORDER BY CAST(rednote_post_num AS INTEGER)")
try_chart(22, "运营位帖子点击率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%carshow%' OR span_name LIKE '%show%' THEN 1 END), 0) * 100 AS operational_click_rate FROM events WHERE span_name LIKE '%porsche%'")
try_chart(23, "Porsche+页面帖子点击率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%carshow%' OR span_name LIKE '%show%' THEN 1 END), 0) * 100 AS post_click_rate FROM events WHERE span_name LIKE '%porsche%'")

# ─── 拔草 (24-31) ───
try_chart(24, "导航来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%travel_guide%' THEN 'travel_guide' WHEN span_name LIKE '%poi%' THEN 'poi' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%navigation%' GROUP BY source")
try_chart(25, "POI详情来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%porsche%map%' THEN 'porsche_map' WHEN span_name LIKE '%post%' THEN 'post' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%poi_detail%' GROUP BY source")
try_chart(26, "AI路书来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%generate%' THEN 'generate' WHEN span_name LIKE '%share%' THEN 'share_code' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%travel_guide%' GROUP BY source")
try_chart(27, "点击AI路书生成转化率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%travel_guide%generate%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%travel_guide%generate%show%' THEN 1 END), 0) * 100 AS ai_guide_conversion_rate FROM events")
try_chart(28, "AI路书分享码生成率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%share%generate%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%share%download%click%' THEN 1 END) + COUNT(CASE WHEN span_name LIKE '%travel_guide%generate%click%' THEN 1 END), 0) * 100 AS share_code_generation_rate FROM events")
try_chart(29, "AI路书生成用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS ai_guide_users FROM events WHERE span_name LIKE '%travel_guide%generate%click%'")
try_chart(30, "AI路书分享码生成用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS share_code_gen_users FROM events WHERE span_name LIKE '%share%generate%click%'")
try_chart(31, "AI路书分享码下载用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS share_code_download_users FROM events WHERE span_name LIKE '%share%download%click%'")

# ─── Ranking (32-33) ───
try_chart(32, "热门POI TOP10", "bar",
    "SELECT rednote_poi_type_name AS poi_name, COUNT(*) AS visit_count FROM events WHERE rednote_poi_type_name IS NOT NULL GROUP BY rednote_poi_type_name ORDER BY visit_count DESC LIMIT 10")
try_chart(33, "热门城市 TOP10", "bar",
    "SELECT user_ip AS city, COUNT(*) AS event_count FROM events WHERE user_ip IS NOT NULL GROUP BY user_ip ORDER BY event_count DESC LIMIT 10")

# ─── Global Filters Test ───
filter_results = {}

def test_filter(name, sql_str):
    data = exec_query(sql_str)
    if isinstance(data, dict) and "error" in data:
        filter_results[name] = {"status": "FAIL", "error": data["error"][:200]}
    elif data:
        filter_results[name] = {"status": "OK", "row_count": len(data), "sample": data[:2]}
    else:
        filter_results[name] = {"status": "NO_DATA"}

test_filter("time_range",
    f"SELECT COUNT(*) AS cnt FROM events WHERE {TS} >= '2026-03-19' AND {TS} < '2026-04-13'")
test_filter("platform",
    "SELECT platform, COUNT(*) AS cnt FROM events WHERE platform IS NOT NULL GROUP BY platform")
test_filter("app_version",
    "SELECT app_version, COUNT(*) AS cnt FROM events WHERE app_version IS NOT NULL GROUP BY app_version ORDER BY cnt DESC LIMIT 5")
test_filter("os_version",
    "SELECT CAST(os_version AS VARCHAR) AS os_version, COUNT(*) AS cnt FROM events WHERE os_version IS NOT NULL GROUP BY os_version ORDER BY cnt DESC LIMIT 5")
test_filter("screen_size",
    "SELECT screen_size, COUNT(*) AS cnt FROM events WHERE screen_size IS NOT NULL GROUP BY screen_size ORDER BY cnt DESC LIMIT 5")
test_filter("display_id",
    "SELECT CAST(display_id AS VARCHAR) AS display_id, COUNT(*) AS cnt FROM events WHERE display_id IS NOT NULL GROUP BY display_id ORDER BY cnt DESC LIMIT 5")
test_filter("user_ip",
    "SELECT user_ip, COUNT(*) AS cnt FROM events WHERE user_ip IS NOT NULL GROUP BY user_ip ORDER BY cnt DESC LIMIT 5")

results["global_filters"] = filter_results

results["bugs_found"] = [
    {
        "bug_id": "BUG-001",
        "location": "mcp_server/dashboard_store.py:save_chart",
        "description": "save_chart 无法序列化 DuckDB 返回的 date/datetime 类型，导致 TypeError: Object of type date is not JSON serializable",
        "reproduction": "当 SQL 查询结果包含 DATE 类型列时，save_chart 调用 json.dumps 会失败",
        "workaround": "在调用 save_chart 前手动将 date/datetime 转换为字符串",
    },
]

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

report_dir = os.path.join(PROJECTS_DIR, project_id)
report_path = os.path.join(report_dir, "test_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\n{'='*70}")
print(f"Python Library Interface Test Complete")
print(f"{'='*70}")
print(f"Project ID: {project_id}")
print(f"Status: {results['final_status']}")
print(f"Charts: {total_charts}/{charts_attempted} OK, {total_failures} failed")
print(f"Filters: {results['summary']['global_filters_ok']}/{len(filter_results)} OK")
print(f"Report: {report_path}")
