# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import shutil
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.server import (
    _create_phase_start,
    _create_phase_classify,
    _create_phase_confirm,
    _create_phase_build,
    _build_reference_context,
)
from mcp_server.project_model import ProjectStore, PROJECTS_DIR, CreateProjectState
import mcp_server.server as srv

print("=" * 70)
print("AutoResearch: Phase 3 Reference Injection Validation")
print("=" * 70)

tmp_dir = tempfile.mkdtemp(prefix="test_autoresearch_p3_")
tmp_data = os.path.join(tmp_data_dir := os.path.join(tmp_dir, "data"), "")
os.makedirs(tmp_data_dir)

original_dir = PROJECTS_DIR
srv.PROJECTS_DIR = tmp_dir
srv._session = srv.ProjectSession(projects_dir=tmp_dir)

TOTAL_ISSUES = 0

def check(name, condition, detail=""):
    global TOTAL_ISSUES
    if condition:
        print(f"  [PASS] {name}")
    else:
        TOTAL_ISSUES += 1
        print(f"  [FAIL] {name} -- {detail}")

try:
    data_file = os.path.join(tmp_data, "events.csv")
    with open(data_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "event_name", "start_time", "duration"])
        for i in range(50):
            w.writerow([f"u{i}", ["click", "view", "share"][i % 3], f"2024-01-{(i % 28) + 1:02d}", str(i * 1.5)])

    kpi_file = os.path.join(tmp_data, "kpi_defs.csv")
    with open(kpi_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["指标名称", "计算公式", "口径说明"])
        w.writerow(["DAU", "COUNT(DISTINCT user_id)", "日活跃用户数"])
        w.writerow(["转化率", "购买/总*100%", "用户转化率"])
        w.writerow(["人均浏览", "AVG(views)", "人均浏览页面数"])

    dict_file = os.path.join(tmp_data, "field_dict.csv")
    with open(dict_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["col_name", "comment"])
        w.writerow(["user_id", "用户唯一标识"])
        w.writerow(["event_name", "事件名称"])
        w.writerow(["start_time", "事件开始时间"])
        w.writerow(["duration", "持续时长(秒)"])

    all_files = [data_file, kpi_file, dict_file]

    # ─── Criterion 1: _build_reference_context produces non-empty context ──
    print("\n[Criterion 1] Reference context generation")
    r1 = _create_phase_start("TestAR", all_files, None)
    pid = r1["project_id"]

    cs = srv._session.store.load_create_state(pid)
    ctx = _build_reference_context(cs)

    check("Context is non-empty", len(ctx) > 0, f"len={len(ctx)}")
    check("Contains KPI section", "KPI" in ctx, ctx[:200])
    check("Contains DAU definition", "DAU" in ctx)
    check("Contains data dictionary", "数据字典" in ctx)
    check("Contains field user_id comment", "用户唯一标识" in ctx)

    # ─── Criterion 2: Only confirmed ref files are included ──────────
    print("\n[Criterion 2] Confirmed ref files filter")
    cs2 = CreateProjectState(
        confirmed_ref_files=["kpi_defs.csv"],
        audit_report=cs.audit_report,
    )
    ctx2 = _build_reference_context(cs2)
    check("Only KPI file included", "kpi_defs.csv" in ctx2)
    check("Dict file excluded", "field_dict.csv" not in ctx2, ctx2[:300])
    check("DAU still present", "DAU" in ctx2)

    # ─── Criterion 3: Empty confirmed_ref produces empty context ─────
    print("\n[Criterion 3] Empty ref files -> empty context")
    cs3 = CreateProjectState(
        state="CONFIRM",
        confirmed_ref_files=[],
        audit_report=cs.audit_report,
    )
    ctx3 = _build_reference_context(cs3)
    check("Empty context when confirmed empty", ctx3 == "", f"len={len(ctx3)}")

    # ─── Criterion 4: Full pipeline end-to-end with refs ─────────────
    print("\n[Criterion 4] Full pipeline with reference injection")
    classifications = cs.audit_report.get("file_classifications", [])
    raw_files = [fc["filename"] for fc in classifications if fc["category"] == "raw_data"]
    ref_files = [fc["filename"] for fc in classifications if fc["category"].startswith("reference")]

    r3 = _create_phase_confirm(pid, raw_files, ref_files, ["KPI monitoring"])
    check("Confirm returns BUILD_READY", r3.get("state") == "BUILD_READY")

    r4 = _create_phase_build(pid, use_llm=False, project_type=None)
    check("Build returns COMPLETED", r4.get("state") == "COMPLETED")
    check("Has metrics", r4.get("metrics_count", 0) > 0)
    check("Has correct row count", r4.get("total_rows") == 50)

    # ─── Criterion 5: PROJECTS_DIR is absolute path ──────────────────
    print("\n[Criterion 5] PROJECTS_DIR is absolute")
    from mcp_server.project_model import PROJECTS_DIR as PD
    check("PROJECTS_DIR is absolute", os.path.isabs(PD), PD)

    # ─── Criterion 6: load_dotenv available ──────────────────────────
    print("\n[Criterion 6] load_dotenv import")
    try:
        from dotenv import load_dotenv
        check("dotenv importable", True)
    except ImportError:
        check("dotenv importable", False, "python-dotenv not installed")

    # ─── Criterion 7: generate_semantic_layer accepts reference_context ──
    print("\n[Criterion 7] generate_semantic_layer signature")
    import inspect
    from mcp_server.semantic_generator import generate_semantic_layer
    sig = inspect.signature(generate_semantic_layer)
    has_ref_ctx = "reference_context" in sig.parameters
    check("reference_context parameter exists", has_ref_ctx, str(sig))

    # ─── Criterion 8: SCHEMA_ANALYSIS_PROMPT_WITH_REFS exists ────────
    print("\n[Criterion 8] REF prompt template")
    from mcp_server.semantic_generator import SCHEMA_ANALYSIS_PROMPT_WITH_REFS
    check("Prompt template exists", len(SCHEMA_ANALYSIS_PROMPT_WITH_REFS) > 500)
    check("Contains reference_context placeholder", "{reference_context}" in SCHEMA_ANALYSIS_PROMPT_WITH_REFS)

    print("\n" + "=" * 70)
    if TOTAL_ISSUES == 0:
        print(f"AutoResearch Phase 3+4: ALL CRITERIA PASSED [0 issues]")
    else:
        print(f"AutoResearch Phase 3+4: {TOTAL_ISSUES} ISSUES FOUND")
    print("=" * 70)

finally:
    srv.PROJECTS_DIR = original_dir
    shutil.rmtree(tmp_dir)

if TOTAL_ISSUES > 0:
    sys.exit(1)
