import sys, os, json, time
sys.path.insert(0, ".")
from mcp_server.server import (
    create_project, switch_project, get_semantic_context,
    semantic_query, raw_sql, render_chart,
    create_dashboard, save_chart_to_dashboard, list_dashboards,
)

DATA_DIR = r"d:\projects\claude\configurable-data-analyzer\projects\rednote\data"
data_files = [
    os.path.join(DATA_DIR, "rednote20260319-20260412.xlsx"),
    os.path.join(DATA_DIR, "Rednote tracking data stracture_20260331.xlsx"),
    os.path.join(DATA_DIR, "rednote KPI definition_20260323.xlsx"),
    os.path.join(DATA_DIR, "Rednote dashboard V1.0 5-30 requirements.xlsx"),
]

print("=" * 60)
print("STEP 1: CREATE PROJECT (START)")
print("=" * 60)
result = create_project(
    name="小红书车载应用分析-全量测试",
    data_files=data_files,
    action="start",
)
pid = result.get("project_id")
print(f"project_id: {pid}, state: {result.get('state')}")

print("\n" + "=" * 60)
print("STEP 2: CONFIRM PROJECT")
print("=" * 60)
result2 = create_project(
    action="confirm",
    project_id=pid,
    confirmed_raw_files=["rednote20260319-20260412.xlsx"],
    confirmed_ref_files=[
        "Rednote tracking data stracture_20260331.xlsx",
        "rednote KPI definition_20260323.xlsx",
        "Rednote dashboard V1.0 5-30 requirements.xlsx",
    ],
    analysis_goals=[
        "小红书车载应用用户行为分析",
        "核心KPI指标监控（DAU、活跃率、留存率、转化率）",
        "Porsche+版块和发现页使用分析",
        "AI路书功能使用和转化分析",
        "分享码功能分析",
    ],
)
print(f"state: {result2.get('state')}")

print("\n" + "=" * 60)
print("STEP 3: BUILD PROJECT")
print("=" * 60)
result3 = create_project(action="build", project_id=pid)
print(json.dumps(result3, ensure_ascii=False, indent=2, default=str))

if result3.get("state") != "COMPLETED":
    print("BUILD FAILED! Exiting.")
    sys.exit(1)

print("\n" + "=" * 60)
print("STEP 4: SWITCH PROJECT & GET SEMANTIC CONTEXT")
print("=" * 60)
switch_project(project_id=pid)

ctx = get_semantic_context(section="all")
metrics = ctx.get("metrics", {})
events = ctx.get("event_definitions", {})
dimensions = ctx.get("dimensions", [])

metric_ids = [m["id"] for m in metrics] if isinstance(metrics, list) else list(metrics.keys())
print(f"Metrics: {len(metric_ids)}")
for mid in metric_ids:
    m = metrics[mid] if isinstance(metrics, dict) else next(m for m in metrics if m["id"] == mid)
    bname = m.get("business_name", mid) if isinstance(m, dict) else mid
    print(f"  {mid}: {bname}")

print(f"\nEvents: {len(events)}")
print(f"Dimensions: {len(dimensions)}")

print("\n" + "=" * 60)
print("STEP 5: QUERY ALL METRICS")
print("=" * 60)

chart_data = {}
for mid in metric_ids:
    print(f"\nQuerying: {mid}")
    try:
        result = semantic_query(level="L1", metric=mid, dimensions=["event_date"])
        if result.get("data") and len(result["data"]) > 0:
            chart_data[mid] = result
            print(f"  OK: {len(result['data'])} rows")
        elif result.get("error"):
            print(f"  ERR: {result['error'][:100]}")
        else:
            print(f"  NO DATA")
    except Exception as e:
        print(f"  EXC: {e}")

print(f"\nSuccessful queries: {len(chart_data)}/{len(metric_ids)}")

print("\n" + "=" * 60)
print("STEP 6: CREATE DASHBOARD & SAVE CHARTS")
print("=" * 60)

dash_result = create_dashboard(name="小红书车载应用KPI看板")
print(f"Dashboard: {json.dumps(dash_result, ensure_ascii=False, default=str)[:200]}")

for mid, result in chart_data.items():
    data = result.get("data", [])
    if not data:
        continue

    m_info = metrics[mid] if isinstance(metrics, dict) else next((m for m in metrics if m["id"] == mid), {})
    title = m_info.get("business_name", mid) if isinstance(m_info, dict) else mid

    if len(data) > 1:
        has_trend = any("date" in str(list(row.keys())) for row in data)
        chart_type = "line" if has_trend else "bar"
    else:
        chart_type = "gauge"

    try:
        chart = render_chart(data=data, chart_type=chart_type, title=title)
        save_result = save_chart_to_dashboard(
            dashboard_name="小红书车载应用KPI看板",
            chart=chart,
        )
        print(f"  Saved: {title} ({chart_type}) -> {save_result.get('chart_id', 'OK')}")
    except Exception as e:
        print(f"  Failed to save {mid}: {e}")

print("\n" + "=" * 60)
print("STEP 7: LIST DASHBOARDS")
print("=" * 60)
dashes = list_dashboards()
print(json.dumps(dashes, ensure_ascii=False, indent=2, default=str)[:500])

print("\n" + "=" * 60)
print("ALL DONE!")
print("=" * 60)
