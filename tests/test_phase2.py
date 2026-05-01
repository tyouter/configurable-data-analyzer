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
    _get_create_status,
)
from mcp_server.project_model import ProjectStore, PROJECTS_DIR

print("=" * 70)
print("Phase 2 Integration Test: Multi-stage create_project")
print("=" * 70)

tmp_dir = tempfile.mkdtemp(prefix="test_phase2_")
tmp_data = os.path.join(tmp_dir, "data")
os.makedirs(tmp_data)

original_dir = PROJECTS_DIR

import mcp_server.server as srv
srv.PROJECTS_DIR = tmp_dir
srv._session = srv.ProjectSession(projects_dir=tmp_dir)

try:
    data_file = os.path.join(tmp_data, "events.csv")
    with open(data_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "event_name", "start_time", "duration"])
        for i in range(100):
            w.writerow([f"u{i}", ["click", "view", "share"][i % 3], f"2024-01-{(i % 28) + 1:02d}", str(i * 1.5)])

    kpi_file = os.path.join(tmp_data, "kpi_defs.csv")
    with open(kpi_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["指标名称", "计算公式", "口径说明"])
        w.writerow(["DAU", "COUNT(DISTINCT user_id)", "日活"])
        w.writerow(["转化率", "购买/总*100%", "转化率"])

    dict_file = os.path.join(tmp_data, "field_dict.csv")
    with open(dict_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["col_name", "comment"])
        w.writerow(["user_id", "用户ID"])
        w.writerow(["event_name", "事件名"])

    all_files = [data_file, kpi_file, dict_file]

    # ─── Step 1: action="start" (PRE_ANALYZE) ──────────────────
    print("\n[Step 1] action=start (PRE_ANALYZE)")
    r1 = _create_phase_start("Test Project", all_files, None)
    print(f"  state: {r1.get('state')}")
    print(f"  project_id: {r1.get('project_id')}")
    assert r1.get("state") == "ALIGN", f"Expected ALIGN, got {r1.get('state')}"
    assert "audit_report" in r1, "Should have audit_report"

    ar = r1["audit_report"]
    fc_list = ar.get("file_classifications", [])
    print(f"  classifications: {len(fc_list)} files")
    for fc in fc_list:
        print(f"    {fc['filename']:20s} -> {fc['category']}")

    summary = ar.get("summary", {})
    print(f"  summary: {summary}")
    pid = r1["project_id"]

    # ─── Step 2: action="classify" (ALIGN - correction) ────────
    print("\n[Step 2] action=classify (ALIGN - user correction)")
    corrections = {}
    for fc in fc_list:
        if "dict" in fc["filename"].lower():
            if fc["category"] != "reference_dict":
                corrections[fc["filename"]] = "reference_dict"

    if corrections:
        r2 = _create_phase_classify(pid, corrections, None)
        print(f"  state: {r2.get('state')}")
        print(f"  corrections_applied: {r2.get('corrections_applied')}")
        assert r2.get("state") == "ALIGN"
    else:
        print("  No corrections needed (already correct)")
        r2 = _create_phase_classify(pid, None, "有多少个KPI指标?")
        print(f"  state: {r2.get('state')}")
        assert r2.get("state") == "ALIGN"
        if r2.get("answer"):
            print(f"  answer: {r2['answer'][:100]}...")

    # ─── Step 3: action="confirm" (CONFIRM) ─────────────────────
    print("\n[Step 3] action=confirm (CONFIRM)")
    updated_cs = srv._session.store.load_create_state(pid)
    updated_ar = updated_cs.audit_report
    updated_fc = updated_ar.get("file_classifications", [])

    raw_files = [fc["filename"] for fc in updated_fc if fc["category"] == "raw_data"]
    ref_files = [fc["filename"] for fc in updated_fc if fc["category"].startswith("reference")]
    print(f"  raw_files: {raw_files}")
    print(f"  ref_files: {ref_files}")

    r3 = _create_phase_confirm(
        pid,
        confirmed_raw_files=raw_files,
        confirmed_ref_files=ref_files,
        analysis_goals=["User behavior analysis", "KPI monitoring"],
    )
    print(f"  state: {r3.get('state')}")
    assert r3.get("state") == "BUILD_READY", f"Expected BUILD_READY, got {r3.get('state')}"
    bp = r3.get("build_plan", {})
    print(f"  build_plan: raw={bp.get('raw_files_to_import')}, ref={bp.get('ref_files_for_context')}")
    assert len(bp.get("raw_files_to_import", [])) >= 1

    # ─── Step 4: action="build" (BUILD) ─────────────────────────
    print("\n[Step 4] action=build (BUILD)")
    r4 = _create_phase_build(pid, use_llm=False, project_type=None)
    print(f"  state: {r4.get('state')}")
    assert r4.get("state") == "COMPLETED", f"Expected COMPLETED, got {r4.get('state')}"
    print(f"  project_id: {r4.get('project_id')}")
    print(f"  name: {r4.get('name')}")
    print(f"  total_rows: {r4.get('total_rows')}")
    print(f"  metrics_count: {r4.get('metrics_count')}")
    assert r4.get("total_rows") == 100, f"Expected 100 rows, got {r4.get('total_rows')}"
    assert r4.get("metrics_count", 0) > 0, "Should have metrics"

    # ─── Step 5: State file cleaned up ──────────────────────────
    print("\n[Step 5] State cleanup verification")
    cs = srv._session.store.load_create_state(pid)
    assert cs is None, "State file should be deleted after build"
    print("  State file deleted OK")

    # ─── Step 6: Status check ───────────────────────────────────
    print("\n[Step 6] Status check")
    r_status = _get_create_status()
    print(f"  status: {r_status.get('state')}")
    assert r_status.get("state") == "NONE"

    # ─── Step 7: Error handling ─────────────────────────────────
    print("\n[Step 7] Error handling")
    r_err = _create_phase_classify("nonexistent_id", None, None)
    assert "error" in r_err
    print(f"  Invalid project_id: {r_err.get('error')[:60]}")

    r_err2 = _create_phase_build("nonexistent_id", False, None)
    assert "error" in r_err2
    print(f"  Build without state: {r_err2.get('error')[:60]}")

    print("\n" + "=" * 70)
    print("Phase 2 Integration Test PASSED [OK]")
    print("=" * 70)

finally:
    srv.PROJECTS_DIR = original_dir
    shutil.rmtree(tmp_dir)
