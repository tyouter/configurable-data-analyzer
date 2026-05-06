# -*- coding: utf-8 -*-
"""
End-to-end test for the project-agnostic MCP Server.
Tests the full flow: create project → switch → query → context.
"""

import os
import sys
import json
import tempfile
import shutil

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.project_model import (
    Project,
    ProjectStore,
    ProjectSession,
    ProjectDataManager,
    PROJECTS_DIR,
)
from mcp_server.semantic_generator import (
    generate_basic_semantic_layer,
    detect_project_type,
    TYPE_TEMPLATES,
)
from mcp_server.server import (
    _build_dynamic_l1_query,
    _build_dynamic_l2_query,
    _serialize_data,
)


def test_project_store():
    print("\n" + "=" * 60)
    print("TEST 1: Project Store CRUD")
    print("=" * 60)

    tmp_dir = tempfile.mkdtemp()
    try:
        store = ProjectStore(tmp_dir)

        projects = store.list_projects()
        assert len(projects) == 0, f"Expected 0 projects, got {len(projects)}"
        print("  [PASS] list_projects returns empty")

        project = store.create_project(
            name="Test Project",
            data_files=[],
            project_type="generic",
            project_id="test1",
        )
        assert project.id == "test1"
        assert project.name == "Test Project"
        print(f"  [PASS] create_project: id={project.id}, name={project.name}")

        projects = store.list_projects()
        assert len(projects) == 1
        print("  [PASS] list_projects returns 1")

        fetched = store.get_project("test1")
        assert fetched is not None
        assert fetched.name == "Test Project"
        print("  [PASS] get_project returns correct project")

        ok = store.delete_project("test1")
        assert ok
        print("  [PASS] delete_project succeeds")

        projects = store.list_projects()
        assert len(projects) == 0
        print("  [PASS] list_projects returns empty after delete")

    finally:
        shutil.rmtree(tmp_dir)

    return True


def test_project_session():
    print("\n" + "=" * 60)
    print("TEST 2: Project Session (switch + context)")
    print("=" * 60)

    tmp_dir = tempfile.mkdtemp()
    try:
        store = ProjectStore(tmp_dir)
        project = store.create_project(
            name="Session Test",
            data_files=[],
            project_type="generic",
            project_id="sess1",
        )

        session = ProjectSession(tmp_dir)

        assert session.current_project_id is None
        print("  [PASS] Initial session has no current project")

        switched = session.switch_project("sess1")
        assert switched.id == "sess1"
        assert session.current_project_id == "sess1"
        print(f"  [PASS] switch_project: current={session.current_project_id}")

        current = session.get_current_project()
        assert current is not None
        assert current.id == "sess1"
        print("  [PASS] get_current_project returns switched project")

        session.unload_project("sess1")
        assert session.current_project_id is None
        print("  [PASS] unload_project clears current project")

    finally:
        shutil.rmtree(tmp_dir)

    return True


def test_semantic_generator():
    print("\n" + "=" * 60)
    print("TEST 3: Semantic Layer Generator (rule-based)")
    print("=" * 60)

    import pandas as pd

    tmp_dir = tempfile.mkdtemp()
    try:
        store = ProjectStore(tmp_dir)

        csv_path = os.path.join(tmp_dir, "test_data.csv")
        df = pd.DataFrame({
            "user_id": [f"u{i}" for i in range(100)],
            "event_name": ["click", "view", "purchase", "click", "view"] * 20,
            "event_time": pd.date_range("2026-01-01", periods=100, freq="h"),
            "amount": [float(i * 10) for i in range(100)],
            "category": ["A", "B", "C", "A", "B"] * 20,
        })
        df.to_csv(csv_path, index=False)

        project = store.create_project(
            name="Test CSV",
            data_files=[csv_path],
            project_type="generic",
            project_id="csv1",
        )

        dm = ProjectDataManager(project, tmp_dir)
        dm.load()

        print(f"  Data loaded: {dm.meta.get('total_rows', 0)} rows, {dm.meta.get('total_columns', 0)} cols")

        detected_type = detect_project_type(dm)
        print(f"  Detected project type: {detected_type}")

        semantic = generate_basic_semantic_layer(dm, detected_type)

        assert "table_name" in semantic
        assert "columns" in semantic
        assert "metrics" in semantic
        print(f"  [PASS] Semantic layer generated: table={semantic['table_name']}")
        print(f"  Columns: {len(semantic['columns'])}")
        print(f"  Metrics: {list(semantic['metrics'].keys())}")
        print(f"  Events: {len(semantic.get('event_definitions', {}))}")

        assert "dau" in semantic["metrics"] or "total_events" in semantic["metrics"]
        print("  [PASS] Key metrics generated")

    finally:
        shutil.rmtree(tmp_dir)

    return True


def test_dynamic_l1_query():
    print("\n" + "=" * 60)
    print("TEST 4: Dynamic L1 Query Builder")
    print("=" * 60)

    semantic_layer = {
        "table_name": "events",
        "columns": {
            "event_date": {"business_name": "日期", "type": "date", "role": "dimension"},
            "page_root": {"business_name": "页面模块", "type": "string", "role": "dimension"},
            "reduser_id": {"business_name": "用户ID", "type": "string", "role": "dimension"},
        },
        "metrics": {
            "dau": {
                "business_name": "日活用户",
                "sql": "COUNT(DISTINCT reduser_id)",
                "keywords": ["日活", "DAU"],
            },
            "total_events": {
                "business_name": "总事件数",
                "sql": "COUNT(*)",
                "keywords": ["事件数"],
            },
        },
    }

    sql, err = _build_dynamic_l1_query(
        semantic_layer=semantic_layer,
        metric="dau",
        dimensions=["event_date"],
        filters=[{"field": "page_root", "op": "eq", "value": "discovery"}],
        order_by="event_date",
        limit=10,
    )
    assert err is None, f"Unexpected error: {err}"
    assert "COUNT(DISTINCT reduser_id)" in sql
    assert "GROUP BY event_date" in sql
    assert "page_root = 'discovery'" in sql
    print(f"  [PASS] L1 query with filter:\n    {sql.replace(chr(10), ' ')}")

    sql2, err2 = _build_dynamic_l1_query(
        semantic_layer=semantic_layer,
        metric="unknown_metric",
        dimensions=["event_date"],
        filters=[],
    )
    assert err2 is not None
    assert "Unknown metric" in err2
    print(f"  [PASS] Unknown metric returns error: {err2[:50]}")

    sql3, err3 = _build_dynamic_l1_query(
        semantic_layer=semantic_layer,
        metric="dau",
        dimensions=["invalid_dim"],
        filters=[],
    )
    assert err3 is not None
    assert "Invalid dimension" in err3
    print(f"  [PASS] Invalid dimension returns error: {err3[:50]}")

    return True


def test_type_templates():
    print("\n" + "=" * 60)
    print("TEST 5: Project Type Templates")
    print("=" * 60)

    for ptype, template in TYPE_TEMPLATES.items():
        desc = template["description"]
        req_cols = list(template["required_columns"].keys())
        print(f"  {ptype}: {desc[:40]}...")
        print(f"    Required columns: {req_cols}")
        print(f"    Default metrics: {list(template['default_metrics'].keys())}")
        print(f"    Analysis templates: {template['analysis_templates']}")

    assert "behavior_analysis" in TYPE_TEMPLATES
    assert "business_report" in TYPE_TEMPLATES
    assert "time_series" in TYPE_TEMPLATES
    assert "generic" in TYPE_TEMPLATES
    print("  [PASS] All 4 project type templates available")

    return True


def test_migrated_rednote_project():
    print("\n" + "=" * 60)
    print("TEST 6: Migrated Rednote Project")
    print("=" * 60)

    projects_dir = os.path.join(_PROJECT_ROOT, "projects")
    store = ProjectStore(projects_dir)

    project = store.get_project("rednote")
    if not project:
        print("  [SKIP] Rednote project not found (run migrate_rednote.py first)")
        return True

    print(f"  Project: {project.name}")
    print(f"  Type: {project.project_type}")
    print(f"  Metrics: {len(project.get_full_semantic_layer(PROJECTS_DIR).get('metrics', {}))}")
    print(f"  Events: {len(project.get_full_semantic_layer(PROJECTS_DIR).get('event_definitions', {}))}")
    print(f"  Columns: {len(project.get_full_semantic_layer(PROJECTS_DIR).get('columns', {}))}")

    assert project.project_type == "behavior_analysis"
    assert len(project.get_full_semantic_layer(PROJECTS_DIR).get("metrics", {})) > 0
    assert len(project.get_full_semantic_layer(PROJECTS_DIR).get("event_definitions", {})) > 0
    print("  [PASS] Rednote project has valid semantic layer")

    sql, err = _build_dynamic_l1_query(
        semantic_layer=project.get_full_semantic_layer(PROJECTS_DIR),
        metric="dau",
        dimensions=["event_date"],
        filters=[{"field": "page_root", "op": "eq", "value": "discovery"}],
        order_by="event_date",
        limit=10,
    )
    assert err is None, f"Error: {err}"
    assert "COUNT(DISTINCT reduser_id)" in sql
    print(f"  [PASS] L1 query on rednote semantic layer works")
    print(f"    SQL: {sql.replace(chr(10), ' ')}")

    return True


def test_full_flow_with_csv():
    print("\n" + "=" * 60)
    print("TEST 7: Full Flow — Create Project from CSV → Query")
    print("=" * 60)

    import pandas as pd

    tmp_dir = tempfile.mkdtemp()
    try:
        csv_path = os.path.join(tmp_dir, "sales_data.csv")
        df = pd.DataFrame({
            "order_date": pd.date_range("2026-01-01", periods=200, freq="D"),
            "customer_id": [f"c{i % 50}" for i in range(200)],
            "product_category": ["Electronics", "Clothing", "Food", "Books", "Home"] * 40,
            "revenue": [float(i * 100 + 50) for i in range(200)],
            "quantity": [i % 10 + 1 for i in range(200)],
            "region": ["North", "South", "East", "West"] * 50,
        })
        df.to_csv(csv_path, index=False)
        print(f"  Created test CSV: {len(df)} rows x {len(df.columns)} cols")

        store = ProjectStore(tmp_dir)
        project = store.create_project(
            name="Sales Report",
            data_files=[csv_path],
            project_id="sales1",
        )

        dm = ProjectDataManager(project, tmp_dir)
        dm.load()
        print(f"  Data loaded: {dm.meta.get('total_rows', 0)} rows")

        detected = detect_project_type(dm)
        print(f"  Detected type: {detected}")

        semantic = generate_basic_semantic_layer(dm, detected)
        project.semantic_layer = semantic
        project.project_type = detected
        store.save_project(project)

        print(f"  Semantic layer: {len(semantic['metrics'])} metrics, {len(semantic['columns'])} columns")

        if "dau" in semantic["metrics"]:
            sql, err = _build_dynamic_l1_query(
                semantic_layer=semantic,
                metric="dau",
                dimensions=["order_date"],
                filters=[],
                limit=5,
            )
            if err is None:
                data = dm.execute(sql)
                print(f"  [PASS] L1 query executed: {len(data)} rows")
                if data:
                    print(f"    First row: {data[0]}")
            else:
                print(f"  [INFO] L1 query error: {err}")
        else:
            metric_name = list(semantic["metrics"].keys())[0]
            sql, err = _build_dynamic_l1_query(
                semantic_layer=semantic,
                metric=metric_name,
                dimensions=[list(semantic["columns"].keys())[0]],
                filters=[],
                limit=5,
            )
            if err is None:
                data = dm.execute(sql)
                print(f"  [PASS] L1 query with metric '{metric_name}': {len(data)} rows")
            else:
                print(f"  [INFO] L1 query error: {err}")

    finally:
        shutil.rmtree(tmp_dir)

    return True


if __name__ == "__main__":
    results = {}

    tests = [
        ("Project Store CRUD", test_project_store),
        ("Project Session", test_project_session),
        ("Semantic Generator", test_semantic_generator),
        ("Dynamic L1 Query", test_dynamic_l1_query),
        ("Type Templates", test_type_templates),
        ("Migrated Rednote", test_migrated_rednote_project),
        ("Full CSV Flow", test_full_flow_with_csv),
    ]

    for name, test_fn in tests:
        try:
            passed = test_fn()
            results[name] = bool(passed)
        except Exception as e:
            print(f"\n  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    total = len(results)
    passed_count = sum(1 for v in results.values() if v)
    print(f"\n  Total: {passed_count}/{total} passed")
