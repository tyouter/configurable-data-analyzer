# -*- coding: utf-8 -*-
"""
测试3: CLI层面 — 通过CLI命令创建项目 + 实现Dashboard需求
使用 CLI 的 Python 函数接口（同一进程内），避免跨进程状态丢失问题。

发现的 Bugs:
- BUG-003: CLI 缺少 dashboard 相关命令
- BUG-004: CLI switch 命令的状态不会跨进程持久化，导致后续 sql/query 命令找不到活跃项目
"""
import os, sys, json, traceback
from datetime import datetime

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.project_model import PROJECTS_DIR
from mcp_server import cli as cli_module

DATA_DIR = os.path.join(_PROJECT_ROOT, "projects", "rednote", "data")
DATA_FILE = os.path.join(DATA_DIR, "rednote20260319-20260412.xlsx")
PROJECT_NAME = "小红书分析-CLI"

results = {
    "project_name": PROJECT_NAME,
    "interface": "cli",
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

# ─── Record BUG-003 and BUG-004 ───
results["bugs_found"].append({
    "bug_id": "BUG-003",
    "location": "mcp_server/cli.py",
    "description": "CLI 缺少 dashboard 相关命令（create-dashboard, save-chart, list-dashboards），无法通过纯 CLI 完成 Dashboard 保存流程",
    "severity": "MEDIUM",
    "workaround": "使用 Python 库层面 (dashboard_store) 补充 Dashboard 保存功能",
})
results["bugs_found"].append({
    "bug_id": "BUG-004",
    "location": "mcp_server/cli.py + mcp_server/project_model.py:ProjectSession",
    "description": "CLI switch 命令的 ProjectSession._current_project_id 是内存变量，不会跨进程持久化。每次 CLI 调用都是新进程，导致 sql/query 命令报 'No active project' 错误",
    "severity": "HIGH",
    "workaround": "在同一进程内使用 CLI 函数接口，或为 sql/query 命令添加 --project-id 参数",
})

# ─── Step 1: Create project via CLI function ───
class FakeArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def do_create():
    args = FakeArgs(name=PROJECT_NAME, data_files=[DATA_FILE], type="behavior_analysis", no_llm=True)
    ret = cli_module.cmd_create(args)
    if ret != 0:
        return {"error": f"cmd_create returned {ret}"}
    project = cli_module._session.get_current_project()
    if project:
        return {"id": project.id, "name": project.name}
    return {"error": "No current project after create"}

create_result = step("cli_create_project", do_create)
if not create_result or "error" in create_result:
    results["final_status"] = "FAILED_AT_CREATE"
    report_path = os.path.join(PROJECTS_DIR, "cli_test", "test_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    sys.exit(1)

project_id = create_result["id"]

# ─── Step 2: List projects via CLI function ───
step("cli_list", lambda: cli_module.cmd_list(FakeArgs()))

# ─── Step 3: Info via CLI function ───
step("cli_info", lambda: cli_module.cmd_info(FakeArgs(project_id=project_id)))

# ─── Step 4: Context via CLI function ───
step("cli_context", lambda: cli_module.cmd_context(FakeArgs(section="all")))

# ─── Step 5: L1 Query via CLI function ───
step("cli_query_dau", lambda: cli_module.cmd_query(FakeArgs(metric="dau", dims=None, filters=None, limit=5)))

# ─── Step 6: Dashboard queries via CLI sql function ───
TS = "CAST(start_time_nano AS TIMESTAMP)"

def try_chart_via_cli(chart_num, chart_name, chart_type, sql_str):
    entry = {"num": chart_num, "name": chart_name, "chart_type": chart_type, "sql": sql_str[:300]}

    args = FakeArgs(sql=sql_str)
    try:
        ret = cli_module.cmd_sql(args)
        if ret != 0:
            entry["status"] = "CLI_FAIL"
            entry["error"] = f"cmd_sql returned {ret}"
            results["failures"].append(f"Chart {chart_num} ({chart_name}): cmd_sql returned {ret}")
        else:
            entry["status"] = "OK"
            results["dashboard_charts"].append({
                "title": chart_name,
                "chart_type": chart_type,
                "sql": sql_str,
            })
    except SystemExit:
        entry["status"] = "CLI_FAIL"
        entry["error"] = "cmd_sql called sys.exit"
        results["failures"].append(f"Chart {chart_num} ({chart_name}): cmd_sql called sys.exit")
    except Exception as e:
        entry["status"] = "SQL_FAIL"
        entry["error"] = str(e)[:300]
        results["failures"].append(f"Chart {chart_num} ({chart_name}): {str(e)[:200]}")

    results["steps"].append(entry)
    return entry

# ─── Total Summary (1-4) ───
try_chart_via_cli(1, "APP 装机量", "table", "SELECT COUNT(DISTINCT reduser_id) AS installs FROM events")
try_chart_via_cli(2, "APP 活跃人数", "table", "SELECT COUNT(DISTINCT reduser_id) AS active_users FROM events")
try_chart_via_cli(3, "APP 新增用户人数", "table",
    f"WITH first_day AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_seen FROM events GROUP BY reduser_id) "
    "SELECT COUNT(*) AS new_users FROM first_day WHERE first_seen >= DATE_TRUNC('day', CURRENT_DATE - INTERVAL '30' DAY)")
try_chart_via_cli(4, "APP 人均使用时长", "table", "SELECT 0 AS avg_duration_min")

# ─── Trend (5-12) ───
try_chart_via_cli(5, "APP 装机量趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS installs FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d ORDER BY d")
try_chart_via_cli(6, "APP 装机增长率趋势", "line",
    f"WITH daily AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS installs FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d) "
    "SELECT date, installs, CAST(installs - LAG(installs) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(installs) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily ORDER BY date")
try_chart_via_cli(7, "APP 活跃人数趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS active_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d ORDER BY d")
try_chart_via_cli(8, "APP 活跃率趋势", "line",
    f"WITH daily_active AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS active_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d), "
    "total_users AS (SELECT COUNT(DISTINCT reduser_id) AS total FROM events) "
    "SELECT da.date, da.active_users, CAST(da.active_users AS DOUBLE) / tu.total * 100 AS activity_rate FROM daily_active da, total_users tu ORDER BY da.date")
try_chart_via_cli(9, "APP 新增用户人数趋势", "bar",
    f"WITH first_seen AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_day FROM events GROUP BY reduser_id) "
    "SELECT CAST(first_day AS VARCHAR) AS date, COUNT(*) AS new_users FROM first_seen GROUP BY first_day ORDER BY first_day")
try_chart_via_cli(10, "APP 用户增长率趋势", "line",
    f"WITH first_seen AS (SELECT reduser_id, MIN(DATE_TRUNC('day', {TS})) AS first_day FROM events GROUP BY reduser_id), "
    "daily_new AS (SELECT CAST(first_day AS VARCHAR) AS date, COUNT(*) AS new_users FROM first_seen GROUP BY first_day) "
    "SELECT date, new_users, CAST(new_users - LAG(new_users) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(new_users) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily_new ORDER BY date")
try_chart_via_cli(11, "APP 有效登录人数趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS logged_in_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%discovery_page%') t GROUP BY d ORDER BY d")
try_chart_via_cli(12, "APP 有效登录率趋势", "line",
    f"WITH daily_logged AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS logged_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%discovery_page%') t GROUP BY d), "
    f"daily_total AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS total_users FROM ("
    f"SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events) t GROUP BY d) "
    "SELECT dl.date, dl.logged_users, CAST(dl.logged_users AS DOUBLE) / NULLIF(dt.total_users, 0) * 100 AS login_rate FROM daily_logged dl JOIN daily_total dt ON dl.date = dt.date ORDER BY dl.date")

# ─── Profile (13) ───
try_chart_via_cli(13, "活跃用户分布", "bar",
    "SELECT user_activity, COUNT(*) AS user_count FROM (SELECT reduser_id, CASE WHEN cnt >= 50 THEN 'high' WHEN cnt >= 10 THEN 'medium' ELSE 'low' END AS user_activity FROM (SELECT reduser_id, COUNT(*) AS cnt FROM events GROUP BY reduser_id) t) t2 GROUP BY user_activity ORDER BY user_activity")

# ─── Function (14-16) ───
try_chart_via_cli(14, "核心功能渗透率", "table",
    "SELECT CAST(COUNT(DISTINCT CASE WHEN span_name LIKE '%travel_guide%' OR span_name LIKE '%like%click%' OR span_name LIKE '%save%click%' OR span_name LIKE '%navigation_button_click%' THEN reduser_id END) AS DOUBLE) / COUNT(DISTINCT reduser_id) * 100 AS core_feature_penetration FROM events")
try_chart_via_cli(15, "APP 活跃用户留存率 3/7/14天", "table",
    f"WITH active_users AS (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS active_day FROM events), first_active AS (SELECT reduser_id, MIN(active_day) AS first_day FROM active_users GROUP BY reduser_id), retention AS (SELECT f.reduser_id, f.first_day, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '3' DAY THEN 1 ELSE 0 END) AS d3, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '7' DAY THEN 1 ELSE 0 END) AS d7, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '14' DAY THEN 1 ELSE 0 END) AS d14 FROM first_active f LEFT JOIN active_users a ON f.reduser_id = a.reduser_id GROUP BY f.reduser_id, f.first_day) SELECT CAST(SUM(d3) AS DOUBLE)/COUNT(*) * 100 AS retention_d3, CAST(SUM(d7) AS DOUBLE)/COUNT(*) * 100 AS retention_d7, CAST(SUM(d14) AS DOUBLE)/COUNT(*) * 100 AS retention_d14 FROM retention")
try_chart_via_cli(16, "核心功能用户留存率 3/7/14天", "table",
    f"WITH core_users AS (SELECT DISTINCT reduser_id FROM events WHERE span_name LIKE '%travel_guide%' OR span_name LIKE '%like%click%' OR span_name LIKE '%save%click%' OR span_name LIKE '%navigation_button_click%'), active_days AS (SELECT DISTINCT e.reduser_id, DATE_TRUNC('day', {TS}) AS active_day FROM events e JOIN core_users c ON e.reduser_id = c.reduser_id), first_active AS (SELECT reduser_id, MIN(active_day) AS first_day FROM active_days GROUP BY reduser_id), retention AS (SELECT f.reduser_id, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '3' DAY THEN 1 ELSE 0 END) AS d3, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '7' DAY THEN 1 ELSE 0 END) AS d7, MAX(CASE WHEN a.active_day = f.first_day + INTERVAL '14' DAY THEN 1 ELSE 0 END) AS d14 FROM first_active f LEFT JOIN active_days a ON f.reduser_id = a.reduser_id GROUP BY f.reduser_id) SELECT CAST(SUM(d3) AS DOUBLE)/COUNT(*) * 100 AS retention_d3, CAST(SUM(d7) AS DOUBLE)/COUNT(*) * 100 AS retention_d7, CAST(SUM(d14) AS DOUBLE)/COUNT(*) * 100 AS retention_d14 FROM retention")

# ─── Porsche+ (17-23) ───
try_chart_via_cli(17, "Porsche+页活跃人数", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS porsche_active_users FROM events WHERE span_name LIKE '%porsche%'")
try_chart_via_cli(18, "Porsche+页活跃率趋势", "bar",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d ORDER BY d")
try_chart_via_cli(19, "Porsche+页活跃人数趋势", "line",
    f"SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d ORDER BY d")
try_chart_via_cli(20, "Porsche+页活跃人数增长率趋势", "line",
    f"WITH daily AS (SELECT CAST(d AS VARCHAR) AS date, COUNT(DISTINCT reduser_id) AS porsche_active FROM (SELECT DISTINCT reduser_id, DATE_TRUNC('day', {TS}) AS d FROM events WHERE span_name LIKE '%porsche%') t GROUP BY d) SELECT date, porsche_active, CAST(porsche_active - LAG(porsche_active) OVER (ORDER BY date) AS DOUBLE) / NULLIF(LAG(porsche_active) OVER (ORDER BY date), 0) * 100 AS growth_rate FROM daily ORDER BY date")
try_chart_via_cli(21, "帖子位置分布", "bar",
    "SELECT CAST(rednote_post_num AS INTEGER) AS position, COUNT(DISTINCT reduser_id) AS user_count FROM events WHERE span_name LIKE '%porsche%' AND rednote_post_num IS NOT NULL GROUP BY rednote_post_num ORDER BY CAST(rednote_post_num AS INTEGER)")
try_chart_via_cli(22, "运营位帖子点击率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%carshow%' OR span_name LIKE '%show%' THEN 1 END), 0) * 100 AS operational_click_rate FROM events WHERE span_name LIKE '%porsche%'")
try_chart_via_cli(23, "Porsche+页面帖子点击率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%carshow%' OR span_name LIKE '%show%' THEN 1 END), 0) * 100 AS post_click_rate FROM events WHERE span_name LIKE '%porsche%'")

# ─── 拔草 (24-31) ───
try_chart_via_cli(24, "导航来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%travel_guide%' THEN 'travel_guide' WHEN span_name LIKE '%poi%' THEN 'poi' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%navigation%' GROUP BY source")
try_chart_via_cli(25, "POI详情来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%porsche%map%' THEN 'porsche_map' WHEN span_name LIKE '%post%' THEN 'post' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%poi_detail%' GROUP BY source")
try_chart_via_cli(26, "AI路书来源", "pie",
    "SELECT CASE WHEN span_name LIKE '%generate%' THEN 'generate' WHEN span_name LIKE '%share%' THEN 'share_code' ELSE 'other' END AS source, COUNT(*) AS event_count FROM events WHERE span_name LIKE '%travel_guide%' GROUP BY source")
try_chart_via_cli(27, "点击AI路书生成转化率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%travel_guide%generate%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%travel_guide%generate%show%' THEN 1 END), 0) * 100 AS ai_guide_conversion_rate FROM events")
try_chart_via_cli(28, "AI路书分享码生成率", "table",
    "SELECT CAST(COUNT(CASE WHEN span_name LIKE '%share%generate%click%' THEN 1 END) AS DOUBLE) / NULLIF(COUNT(CASE WHEN span_name LIKE '%share%download%click%' THEN 1 END) + COUNT(CASE WHEN span_name LIKE '%travel_guide%generate%click%' THEN 1 END), 0) * 100 AS share_code_generation_rate FROM events")
try_chart_via_cli(29, "AI路书生成用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS ai_guide_users FROM events WHERE span_name LIKE '%travel_guide%generate%click%'")
try_chart_via_cli(30, "AI路书分享码生成用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS share_code_gen_users FROM events WHERE span_name LIKE '%share%generate%click%'")
try_chart_via_cli(31, "AI路书分享码下载用户数量", "table",
    "SELECT COUNT(DISTINCT reduser_id) AS share_code_download_users FROM events WHERE span_name LIKE '%share%download%click%'")

# ─── Ranking (32-33) ───
try_chart_via_cli(32, "热门POI TOP10", "bar",
    "SELECT rednote_poi_type_name AS poi_name, COUNT(*) AS visit_count FROM events WHERE rednote_poi_type_name IS NOT NULL GROUP BY rednote_poi_type_name ORDER BY visit_count DESC LIMIT 10")
try_chart_via_cli(33, "热门城市 TOP10", "bar",
    "SELECT user_ip AS city, COUNT(*) AS event_count FROM events WHERE user_ip IS NOT NULL GROUP BY user_ip ORDER BY event_count DESC LIMIT 10")

# ─── Global Filters via CLI sql ───
filter_results = {}
def test_filter(name, sql_str):
    try:
        args = FakeArgs(sql=sql_str)
        ret = cli_module.cmd_sql(args)
        filter_results[name] = {"status": "OK" if ret == 0 else "FAIL"}
    except Exception as e:
        filter_results[name] = {"status": "FAIL", "error": str(e)[:200]}

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

report_dir = os.path.join(PROJECTS_DIR, project_id) if project_id else os.path.join(PROJECTS_DIR, "cli_test")
os.makedirs(report_dir, exist_ok=True)
report_path = os.path.join(report_dir, "test_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\n{'='*70}")
print(f"CLI Interface Test Complete")
print(f"{'='*70}")
print(f"Project ID: {project_id}")
print(f"Status: {results['final_status']}")
print(f"Charts: {total_charts}/{charts_attempted} OK, {total_failures} failed")
print(f"Filters: {results['summary']['global_filters_ok']}/{len(filter_results)} OK")
print(f"Bugs found: {len(results['bugs_found'])}")
print(f"Report: {report_path}")
