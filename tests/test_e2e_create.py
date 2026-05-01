# -*- coding: utf-8 -*-
import os, sys, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DATA_DIR = os.environ.get(
    "CHATBI_TEST_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "projects", "rednote", "data"),
)

if not os.path.exists(DATA_DIR):
    print(f"SKIP: {DATA_DIR} not found")
    sys.exit(0)

files = [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]

print("=" * 70)
print("E2E Test: Create New Rednote Project via MCP Server Internals")
print("=" * 70)
print(f"Data files found: {len(files)}")
for f in files:
    print(f"  {os.path.basename(f)} ({os.path.getsize(f)/1024:.1f} KB)")

from mcp_server.server import (
    switch_project,
    semantic_query,
    get_semantic_context,
    list_projects,
    raw_sql,
    delete_project,
    _create_phase_start,
    _create_phase_classify,
    _create_phase_confirm,
    _create_phase_build,
    _session,
)
from mcp_server.project_model import PROJECTS_DIR

print(f"\nPROJECTS_DIR: {PROJECTS_DIR}")

# === Phase 1: START ===
print("\n" + "-" * 60)
print("Phase 1: START (file classification + audit)")
print("-" * 60)
r1 = _create_phase_start(
    name="小红书分析v2",
    data_files=files,
    project_type="behavior_analysis",
)
if "error" in r1:
    print(f"ERROR: {r1['error']}")
    sys.exit(1)

print(f"State: {r1['state']}")
print(f"Project ID: {r1['project_id']}")
pid = r1["project_id"]
ar = r1["audit_report"]
print(f"Files classified: {len(ar['file_classifications'])}")
for fc in ar["file_classifications"]:
    print(f"  {fc['filename']:55s} -> {fc['category']:20s} conf={fc['confidence']:.2f}")
print(f"Summary: {ar['summary']}")

assert r1["state"] == "ALIGN", f"Expected ALIGN, got {r1['state']}"
assert len(ar["file_classifications"]) == 4, "Expected 4 file classifications"

# === Phase 2: CLASSIFY ===
print("\n" + "-" * 60)
print("Phase 2: CLASSIFY (user Q&A)")
print("-" * 60)
r2 = _create_phase_classify(
    project_id=pid,
    corrections=None,
    questions="这个数据集有多少原始数据文件？",
)
if "error" in r2:
    print(f"ERROR: {r2['error']}")
    sys.exit(1)

print(f"State: {r2['state']}")
if "answer" in r2:
    print(f"Answer: {r2['answer'][:200]}...")

assert r2["state"] == "ALIGN"

# === Phase 3: CONFIRM ===
print("\n" + "-" * 60)
print("Phase 3: CONFIRM (confirm files and goals)")
print("-" * 60)
raw_files = [fc["filename"] for fc in ar["file_classifications"] if fc["category"] == "raw_data"]
ref_files = [fc["filename"] for fc in ar["file_classifications"] if fc["category"].startswith("reference")]
print(f"Confirming raw files: {raw_files}")
print(f"Confirming ref files: {ref_files}")

r3 = _create_phase_confirm(
    project_id=pid,
    confirmed_raw_files=raw_files,
    confirmed_ref_files=ref_files,
    analysis_goals=["用户行为分析", "页面转化漏斗", "导航功能使用率"],
)
if "error" in r3:
    print(f"ERROR: {r3['error']}")
    sys.exit(1)

print(f"State: {r3['state']}")
bp = r3["build_plan"]
print(f"Build plan raw: {bp['raw_files_to_import']}")
print(f"Build plan ref: {bp['ref_files_for_context']}")
print(f"Build plan goals: {bp['analysis_goals']}")

assert r3["state"] == "BUILD_READY"

# === Phase 4: BUILD ===
print("\n" + "-" * 60)
print("Phase 4: BUILD (import data + generate semantic layer)")
print("-" * 60)
r4 = _create_phase_build(
    project_id=pid,
    use_llm=False,
    project_type="behavior_analysis",
)
if "error" in r4:
    print(f"ERROR: {r4['error']}")
    sys.exit(1)

print(f"State: {r4['state']}")
print(f"Name: {r4['name']}")
print(f"Type: {r4['project_type']}")
print(f"Rows: {r4['total_rows']}")
print(f"Columns: {r4['total_columns']}")
print(f"Metrics: {r4['metrics_count']}")
print(f"Events: {r4['events_count']}")
print(f"Semantic source: {r4['semantic_source']}")

assert r4["state"] == "COMPLETED"
assert r4["total_rows"] > 0
assert r4["metrics_count"] > 0

# === Verify: Switch & Query ===
print("\n" + "-" * 60)
print("Verify: Switch Project")
print("-" * 60)
sr = switch_project(pid)
print(f"Switched: {sr.get('project_id', 'ERROR')}")
assert sr.get("project_id") == pid

# === Verify: Semantic Context ===
print("\n" + "-" * 60)
print("Verify: Get Semantic Context")
print("-" * 60)
ctx = get_semantic_context(section="metrics")
metrics = ctx.get("metrics", [])
print(f"Metrics count: {len(metrics)}")
for m in metrics[:5]:
    print(f"  {m['id']}: {m['business_name']} (keywords: {m.get('keywords', [])[:3]})")
assert len(metrics) > 0

# === Verify: L1 Query ===
print("\n" + "-" * 60)
print("Verify: L1 Query (total_events)")
print("-" * 60)
qr = semantic_query(
    level="L1",
    metric="total_events",
    dimensions=[],
    limit=5,
)
if "error" in qr:
    print(f"Query error: {qr['error']}")
else:
    data = qr.get("data", [])
    print(f"Result rows: {len(data)}")
    for row in data[:3]:
        print(f"  {row}")

assert "error" not in qr
assert len(qr.get("data", [])) > 0

# === Verify: Raw SQL ===
print("\n" + "-" * 60)
print("Verify: Raw SQL")
print("-" * 60)
sql_r = raw_sql("SELECT COUNT(*) as cnt FROM events")
print(f"SQL result: {sql_r.get('data', [])}")
assert "error" not in sql_r

# === Verify: List Projects ===
print("\n" + "-" * 60)
print("Verify: List Projects")
print("-" * 60)
lp = list_projects()
print(f"Total projects: {len(lp.get('projects', []))}")
for p in lp.get("projects", []):
    print(f"  {p['id']}: {p['name']} ({p.get('project_type', '?')})")

# === Cleanup ===
print("\n" + "-" * 60)
print("Cleanup: Delete test project")
print("-" * 60)
dr = delete_project(pid)
print(f"Delete: {dr.get('status', dr.get('error', 'unknown'))}")

print("\n" + "=" * 70)
print("E2E New Project Creation Test PASSED [OK]")
print("=" * 70)
