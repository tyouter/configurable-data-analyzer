# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import shutil
import csv
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.project_model import (
    ProjectStore, DataAuditReport, FileClassification,
)
from mcp_server.file_classifier import FileClassifier
from mcp_server.data_auditor import DataAuditor
from mcp_server.reference_parser import ReferenceParser

tmp_dir = tempfile.mkdtemp(prefix="test_phase1_")
data_dir = os.path.join(tmp_dir, "source_data")
os.makedirs(data_dir)
projects_dir = os.path.join(tmp_dir, "projects")

try:
    data_file = os.path.join(data_dir, "user_events.csv")
    with open(data_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "event_name", "start_time", "duration", "page"])
        for i in range(200):
            ev = ["click", "view", "share", "purchase"][i % 4]
            w.writerow([f"u{i}", ev, f"2024-01-{(i % 28) + 1:02d} 10:{i % 60:02d}:00", str(i * 1.5), f"/p/{i % 10}"])

    kpi_file = os.path.join(data_dir, "kpi_definitions.csv")
    with open(kpi_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["指标名称", "计算公式", "口径说明"])
        w.writerow(["DAU", "COUNT(DISTINCT user_id)", "每日活跃用户数"])
        w.writerow(["ARPU", "SUM(revenue)/COUNT(DISTINCT user_id)", "每用户平均收入"])
        w.writerow(["转化率", "购买用户数/总用户数*100%", "从浏览到购买的转化率"])

    dict_file = os.path.join(data_dir, "field_dictionary.csv")
    with open(dict_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["字段名", "含义", "枚举值"])
        w.writerow(["user_id", "用户唯一标识", ""])
        w.writerow(["event_name", "事件名称", "click,view,share,purchase"])
        w.writerow(["start_time", "事件发生时间", ""])
        w.writerow(["duration", "事件持续时间(秒)", ""])
        w.writerow(["page", "页面路径", ""])

    all_files = [data_file, kpi_file, dict_file]

    print("=" * 60)
    print("Phase 1 Integration Test")
    print("=" * 60)

    print("\n[Step 1] FileClassifier")
    classifier = FileClassifier(llm_available=False)
    classifications = classifier.classify_all(all_files)
    for c in classifications:
        tag = "[DATA]" if c.is_raw_data() else ("[REF]" if c.is_reference() else "[???]")
        print(f"  {tag} {c.filename:30s} -> {c.category:20s} (conf={c.confidence:.2f})")

    raw_count = sum(1 for c in classifications if c.is_raw_data())
    ref_count = sum(1 for c in classifications if c.is_reference())
    assert raw_count >= 1, f"Expected at least 1 raw data file, got {raw_count}"
    assert ref_count >= 1, f"Expected at least 1 reference file, got {ref_count}"
    print(f"  -> {raw_count} raw data, {ref_count} reference files")

    print("\n[Step 2] DataAuditor")
    auditor = DataAuditor()
    schemas = auditor.audit_all(classifications)
    for s in schemas:
        print(f"  {s.filename}: {s.row_count} rows, {len(s.columns)} cols, quality={s.quality_score:.3f}")
        print(f"    numeric={s.numeric_columns}")
        print(f"    category={s.category_columns}")
        if s.quality_issues:
            print(f"    issues={s.quality_issues}")
    assert len(schemas) >= 1, "Should have at least 1 schema"
    assert schemas[0].row_count == 200, f"Expected 200 rows, got {schemas[0].row_count}"

    print("\n[Step 3] ReferenceParser")
    parser = ReferenceParser(llm_available=False)
    refs = parser.parse_all(classifications)
    for r in refs:
        print(f"  {r.filename} ({r.category}):")
        print(f"    kpi_defs={len(r.kpi_definitions)}, field_defs={len(r.field_definitions)}, goals={len(r.analysis_goals)}")
    assert len(refs) >= 1, "Should have at least 1 reference content"

    print("\n[Step 4] Assemble DataAuditReport")
    report = DataAuditReport(
        project_name="Integration Test Project",
        created_at=datetime.now().isoformat(),
        file_classifications=classifications,
        raw_data_schemas=schemas,
        reference_contents=refs,
        summary={
            "raw_files": raw_count,
            "ref_files": ref_count,
            "total_rows": sum(s.row_count for s in schemas),
        },
    )
    print(f"  Summary: {report.summary}")

    print("\n[Step 5] Persist & Reload")
    store = ProjectStore(projects_dir=projects_dir)
    project_id = "test_project"
    os.makedirs(os.path.join(projects_dir, project_id), exist_ok=True)

    saved_path = store.save_audit_report(project_id, report)
    print(f"  Saved to: {saved_path}")

    loaded = store.load_audit_report(project_id)
    assert loaded is not None, "Should load report"
    assert loaded.project_name == "Integration Test Project"
    assert len(loaded.file_classifications) == len(classifications)
    assert len(loaded.raw_data_schemas) == len(schemas)
    assert loaded.summary["total_rows"] == 200

    print(f"  Reloaded: {loaded.project_name}")
    print(f"  Classifications: {len(loaded.file_classifications)}")
    print(f"  Schemas: {len(loaded.raw_data_schemas)}")
    print(f"  References: {len(loaded.reference_contents)}")
    print(f"  Total rows: {loaded.summary['total_rows']}")

    print("\n" + "=" * 60)
    print("All integration tests passed! Phase 1 Complete [OK]")
    print("=" * 60)

finally:
    shutil.rmtree(tmp_dir)
