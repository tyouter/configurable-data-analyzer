# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from mcp_server.file_classifier import FileClassifier
from mcp_server.data_auditor import DataAuditor
from mcp_server.reference_parser import ReferenceParser, KPIValidator
from mcp_server.project_model import DataAuditReport
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "rednote analysis")

if not os.path.exists(DATA_DIR):
    print(f"SKIP: {DATA_DIR} not found")
    sys.exit(0)

print("=" * 70)
print("Real Data E2E Test: rednote analysis")
print("=" * 70)

files = [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
print(f"\nFiles: {len(files)}")
for f in files:
    print(f"  {os.path.basename(f)} ({os.path.getsize(f)/1024:.1f} KB)")

# ─── Step 1: Classify ──────────────────────────────────────────
print("\n[Step 1] FileClassifier (rule-based)")
classifier = FileClassifier(llm_available=False)
classifications = classifier.classify_all(files)

raw_files = []
ref_files = []
for c in classifications:
    tag = "[DATA]" if c.is_raw_data() else ("[REF]" if c.is_reference() else "[???]")
    print(f"  {tag} {c.filename:55s} -> {c.category:20s} conf={c.confidence:.2f}")
    if c.is_raw_data():
        raw_files.append(c)
    elif c.is_reference():
        ref_files.append(c)

assert len(raw_files) >= 1, f"Expected at least 1 raw data file, got {len(raw_files)}"
assert len(ref_files) >= 1, f"Expected at least 1 reference file, got {len(ref_files)}"

# ─── Step 2: Audit raw data ───────────────────────────────────
print("\n[Step 2] DataAuditor")
auditor = DataAuditor()
schemas = auditor.audit_all(classifications)

for s in schemas:
    print(f"  {s.filename}: {s.row_count} rows, {len(s.columns)} cols, quality={s.quality_score:.3f}")
    if s.numeric_columns:
        print(f"    numeric: {s.numeric_columns[:5]}...")
    if s.quality_issues:
        for qi in s.quality_issues[:3]:
            print(f"    issue: {qi}")

assert len(schemas) >= 1, "Should have at least 1 schema"

raw_columns = []
if schemas:
    raw_columns = [c["name"] for c in schemas[0].columns]

print(f"\n  Raw data columns ({len(raw_columns)}): {raw_columns[:10]}...")

# ─── Step 3: Parse references with AutoResearch ────────────────
print("\n[Step 3] ReferenceParser (rule-based fallback)")
parser = ReferenceParser(llm_available=False, raw_schema_columns=raw_columns)
refs = parser.parse_all(classifications)

for r in refs:
    print(f"  {r.filename} ({r.category}):")
    print(f"    kpi_defs={len(r.kpi_definitions)}, field_defs={len(r.field_definitions)}, goals={len(r.analysis_goals)}")

kpi_ref = None
dict_ref = None
for r in refs:
    if r.category == "reference_kpi":
        kpi_ref = r
    if r.category == "reference_dict":
        dict_ref = r

# ─── Step 4: Validate KPI completeness ─────────────────────────
print("\n[Step 4] KPI Validation against real data")

if kpi_ref and kpi_ref.kpi_definitions:
    validator = KPIValidator(raw_schema_columns=raw_columns)
    kpi_text = kpi_ref.raw_text
    validation = validator.validate(kpi_ref.kpi_definitions, source_text=kpi_text)
    print(f"  KPI count: {len(kpi_ref.kpi_definitions)}")
    print(f"  Validation score: {validation.score}")
    print(f"  Passed: {validation.passed}")
    print(f"  Issues ({len(validation.issues)}):")
    for issue in validation.issues:
        if hasattr(issue, 'severity'):
            print(f"    [{issue.severity}] {issue.category}: {issue.message}")
        else:
            print(f"    {issue}")
else:
    print("  No KPI definitions extracted (rule-based)")
    print("  This is expected without LLM - rule-based extraction is limited for complex xlsx")

# ─── Step 5: Data dictionary coverage ─────────────────────────
print("\n[Step 5] Data dictionary coverage")

if dict_ref and dict_ref.field_definitions:
    dict_fields = {fd["field"] for fd in dict_ref.field_definitions}
    print(f"  Dict fields: {len(dict_fields)}")
    print(f"  Raw columns: {len(raw_columns)}")

    matched = dict_fields & set(raw_columns)
    unmatched_dict = dict_fields - set(raw_columns)
    unmatched_raw = set(raw_columns) - dict_fields

    print(f"  Matched: {len(matched)}")
    if unmatched_dict:
        print(f"  Dict fields not in raw (top 5): {list(unmatched_dict)[:5]}")
    if unmatched_raw:
        print(f"  Raw cols not in dict (top 5): {list(unmatched_raw)[:5]}")

    assert len(matched) > 0, "Should have some matched fields between dict and raw"
else:
    print("  No field definitions extracted (rule-based)")

# ─── Step 6: Assemble audit report ─────────────────────────────
print("\n[Step 6] Assemble DataAuditReport")
report = DataAuditReport(
    project_name="Rednote Analysis",
    created_at=datetime.now().isoformat(),
    file_classifications=classifications,
    raw_data_schemas=schemas,
    reference_contents=refs,
    summary={
        "raw_files": len(raw_files),
        "ref_files": len(ref_files),
        "total_rows": sum(s.row_count for s in schemas),
        "kpi_count": sum(len(r.kpi_definitions) for r in refs),
    },
)
print(f"  Summary: {report.summary}")

from mcp_server.project_model import ProjectStore
import tempfile, shutil

tmp_dir = tempfile.mkdtemp(prefix="test_real_")
try:
    store = ProjectStore(projects_dir=tmp_dir)
    os.makedirs(os.path.join(tmp_dir, "rednote"), exist_ok=True)
    path = store.save_audit_report("rednote", report)
    loaded = store.load_audit_report("rednote")
    assert loaded is not None
    assert loaded.project_name == "Rednote Analysis"
    assert loaded.summary["total_rows"] > 0
    print(f"  Persist OK: {loaded.summary}")
finally:
    shutil.rmtree(tmp_dir)

print("\n" + "=" * 70)
print("Real Data E2E Test PASSED [OK]")
print("=" * 70)
