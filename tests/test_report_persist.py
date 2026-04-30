# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.project_model import (
    ProjectStore, DataAuditReport, FileClassification,
    FileSchemaInfo, ReferenceContent,
)

tmp_dir = tempfile.mkdtemp(prefix="test_audit_")
try:
    store = ProjectStore(projects_dir=tmp_dir)

    project_id = "testproj"
    project_dir = os.path.join(tmp_dir, project_id)
    os.makedirs(project_dir, exist_ok=True)

    report = DataAuditReport(
        project_name="Test Project",
        created_at="2026-04-30T12:00:00",
        file_classifications=[
            FileClassification(
                filename="events.csv",
                filepath="/data/events.csv",
                category="raw_data",
                confidence=0.9,
                reason="LLM classified",
                columns=["user_id", "event_name", "start_time"],
                row_count=1000,
                format="csv",
            ),
            FileClassification(
                filename="kpi_defs.csv",
                filepath="/data/kpi_defs.csv",
                category="reference_kpi",
                confidence=0.85,
                reason="LLM classified",
                columns=[],
                row_count=5,
                format="csv",
            ),
        ],
        raw_data_schemas=[
            FileSchemaInfo(
                filename="events.csv",
                columns=[
                    {"name": "user_id", "dtype": "object", "null_rate": 0.0},
                    {"name": "event_name", "dtype": "object", "null_rate": 0.01},
                ],
                row_count=1000,
                numeric_columns=[],
                quality_score=0.92,
                quality_issues=["全唯一列可能是ID: user_id"],
            ),
        ],
        reference_contents=[
            ReferenceContent(
                filename="kpi_defs.csv",
                category="reference_kpi",
                raw_text="DAU,COUNT...",
                kpi_definitions=[{"name": "DAU", "formula": "COUNT(DISTINCT user_id)", "description": "日活"}],
                field_definitions=[],
                analysis_goals=["用户行为分析"],
            ),
        ],
        summary={"raw_files": 1, "ref_files": 1, "total_rows": 1000},
    )

    path = store.save_audit_report(project_id, report)
    print(f"Saved to: {path}")
    assert os.path.exists(path), "Report file should exist"

    loaded = store.load_audit_report(project_id)
    assert loaded is not None, "Should load report"
    assert loaded.project_name == "Test Project", f"Name mismatch: {loaded.project_name}"
    assert len(loaded.file_classifications) == 2, f"Expected 2 classifications, got {len(loaded.file_classifications)}"
    assert loaded.file_classifications[0].category == "raw_data"
    assert loaded.file_classifications[1].category == "reference_kpi"
    assert len(loaded.raw_data_schemas) == 1
    assert loaded.raw_data_schemas[0].quality_score == 0.92
    assert len(loaded.reference_contents) == 1
    assert loaded.reference_contents[0].kpi_definitions[0]["name"] == "DAU"
    assert loaded.summary["total_rows"] == 1000

    print(f"Loaded report: {loaded.project_name}")
    print(f"  Classifications: {len(loaded.file_classifications)}")
    print(f"  Schemas: {len(loaded.raw_data_schemas)}")
    print(f"  References: {len(loaded.reference_contents)}")
    print(f"  Summary: {loaded.summary}")

    print("\nAll assertions passed! Plan 1.5 OK")

finally:
    shutil.rmtree(tmp_dir)
