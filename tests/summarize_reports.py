import json, os, sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _PROJECT_ROOT)
from mcp_server.project_model import ProjectStore

store = ProjectStore()
projects = store.list_projects()

reports = {}
for p in projects:
    report_path = os.path.join(_PROJECT_ROOT, "projects", p["id"], "test_report.json")
    if os.path.exists(report_path):
        with open(report_path, encoding="utf-8") as f:
            reports[p["id"]] = json.load(f)

print("=" * 80)
print("三接口测试结果汇总")
print("=" * 80)

all_bugs = []
for pid, r in reports.items():
    iface = r.get("interface", "unknown")
    name = r.get("project_name", "unknown")
    summary = r.get("summary", {})
    status = r.get("final_status", "unknown")
    bugs = r.get("bugs_found", [])
    all_bugs.extend(bugs)

    print(f"\n{'─'*60}")
    print(f"接口: {iface}")
    print(f"项目: {name} ({pid})")
    print(f"状态: {status}")
    print(f"图表: {summary.get('charts_ok', '?')}/{summary.get('total_charts_attempted', '?')} OK")
    print(f"筛选器: {summary.get('global_filters_ok', '?')}/{summary.get('global_filters_tested', '?')} OK")
    print(f"发现Bug: {len(bugs)}")
    for b in bugs:
        print(f"  [{b['bug_id']}] {b.get('severity', '?')}: {b['description'][:80]}")

print(f"\n{'='*80}")
print(f"全部发现的 Bug 汇总 ({len(all_bugs)} 个)")
print(f"{'='*80}")

seen = set()
for b in all_bugs:
    bid = b["bug_id"]
    if bid in seen:
        continue
    seen.add(bid)
    print(f"\n[{bid}] {b.get('severity', '?')}")
    print(f"  位置: {b['location']}")
    print(f"  描述: {b['description']}")
    if "workaround" in b:
        print(f"  规避: {b['workaround']}")
