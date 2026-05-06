# -*- coding: utf-8 -*-
import os
import json
from typing import Optional
from datetime import datetime

from mcp_server.project_model import (
    Project,
    ProjectStore,
    ProjectSession,
    ProjectDataManager,
    CreateProjectState,
    DataAuditReport,
    PipelineState,
    PROJECTS_DIR,
)
from mcp_server.file_classifier import FileClassifier
from mcp_server.data_auditor import DataAuditor
from mcp_server.reference_parser import ReferenceParser
from mcp_server.semantic_generator import generate_semantic_layer, detect_project_type


def create_project(
    session: ProjectSession,
    name: str = "",
    data_files: list[str] = [],
    action: str = "start",
    project_id: Optional[str] = None,
    project_type: Optional[str] = None,
    corrections: Optional[dict] = None,
    questions: Optional[str] = None,
    confirmed_raw_files: Optional[list[str]] = None,
    confirmed_ref_files: Optional[list[str]] = None,
    analysis_goals: Optional[list[str]] = None,
    use_llm: bool = True,
) -> dict:
    try:
        effective_action = action
        if effective_action == "start" and data_files:
            pass
        elif effective_action == "start" and not data_files and not name:
            return get_create_status(session)

        if effective_action == "start":
            return _phase_start(session, name, data_files, project_type)
        elif effective_action == "classify":
            return _phase_classify(session, project_id, corrections, questions)
        elif effective_action == "confirm":
            return _phase_confirm(
                session, project_id, confirmed_raw_files,
                confirmed_ref_files, analysis_goals,
            )
        elif effective_action == "build":
            return _phase_build(session, project_id, use_llm, project_type)
        elif effective_action == "status":
            return get_create_status(session)
        else:
            return {"error": f"Unknown action: {effective_action}. Use start/classify/confirm/build/status"}
    except Exception as e:
        return {"error": f"create_project({action}) failed: {str(e)}"}


def _phase_start(session: ProjectSession, name: str, data_files: list[str], project_type: Optional[str]) -> dict:
    if not name:
        return {"error": "name is required for action=start"}
    if not data_files:
        return {"error": "data_files is required for action=start"}

    existing_files = [f for f in data_files if os.path.exists(f)]
    if not existing_files:
        return {"error": "No valid file paths found in data_files"}

    project_id = Project.generate_id(name)
    project_id = session.store._ensure_unique_id(project_id)
    now = datetime.now().isoformat()

    classifier = FileClassifier()
    classifications = classifier.classify_all(existing_files)

    raw_classifications = [c for c in classifications if c.is_raw_data()]
    raw_columns = []
    if raw_classifications:
        auditor = DataAuditor()
        schemas = auditor.audit_all(classifications)
        for s in schemas:
            raw_columns.extend([col["name"] for col in s.columns])
    else:
        schemas = []

    parser = ReferenceParser(raw_schema_columns=raw_columns)
    ref_contents = parser.parse_all(classifications)

    raw_count = sum(1 for c in classifications if c.is_raw_data())
    ref_count = sum(1 for c in classifications if c.is_reference())
    total_rows = sum(s.row_count for s in schemas)

    audit_report = DataAuditReport(
        project_name=name,
        created_at=now,
        file_classifications=[
            {
                "filename": c.filename,
                "filepath": c.filepath,
                "category": c.category,
                "confidence": c.confidence,
                "reason": c.reason,
                "columns": c.columns,
                "row_count": c.row_count,
                "format": c.format,
            }
            for c in classifications
        ],
        raw_data_schemas=[
            {
                "filename": s.filename,
                "row_count": s.row_count,
                "columns": s.columns,
                "quality_score": s.quality_score,
                "quality_issues": s.quality_issues,
            }
            for s in schemas
        ],
        reference_contents=[
            {
                "filename": r.filename,
                "category": r.category,
                "kpi_definitions": r.kpi_definitions,
                "field_definitions": r.field_definitions,
                "analysis_goals": r.analysis_goals,
            }
            for r in ref_contents
        ],
        summary={
            "raw_files": raw_count,
            "ref_files": ref_count,
            "total_rows": total_rows,
            "kpi_count": sum(len(r.kpi_definitions) for r in ref_contents),
            "field_definitions_count": sum(len(r.field_definitions) for r in ref_contents),
        },
    )

    create_state = CreateProjectState(
        state="ALIGN",
        project_id=project_id,
        name=name,
        data_files=existing_files,
        audit_report=audit_report.to_dict(),
        created_at=now,
        updated_at=now,
    )

    project_dir = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(project_dir, exist_ok=True)
    session.store.save_create_state(project_id, create_state)
    session.store.save_audit_report(project_id, audit_report)

    return {
        "state": "ALIGN",
        "project_id": project_id,
        "audit_report": audit_report.to_dict(),
        "message": "数据预分析完成。请审查文件分类和KPI定义，确认或修正后继续。",
        "next_actions": ["classify", "confirm"],
    }


def _phase_classify(
    session: ProjectSession,
    project_id: str,
    corrections: Optional[dict],
    questions: Optional[str],
) -> dict:
    if not project_id:
        return {"error": "project_id is required for action=classify"}

    create_state = session.store.load_create_state(project_id)
    if not create_state:
        return {"error": f"No create state found for project {project_id}. Start with action=start first."}

    if create_state.state not in ("ALIGN", "PRE_ANALYZE"):
        return {"error": f"Cannot classify in state {create_state.state}. Expected ALIGN."}

    audit_report = create_state.audit_report
    classifications = audit_report.get("file_classifications", [])

    if corrections:
        valid_categories = {"raw_data", "reference_kpi", "reference_dict", "reference_req", "reference_other"}
        for filename, new_cat in corrections.items():
            if new_cat not in valid_categories:
                return {"error": f"Invalid category '{new_cat}'. Valid: {sorted(valid_categories)}"}
            for fc in classifications:
                if fc["filename"] == filename:
                    fc["category"] = new_cat
                    fc["reason"] = "用户修正"
                    fc["confidence"] = 1.0
                    break

        create_state.user_corrections.update(corrections)

    answer = ""
    if questions:
        answer = _answer_alignment_question(questions, audit_report)

    create_state.state = "ALIGN"
    create_state.updated_at = datetime.now().isoformat()
    session.store.save_create_state(project_id, create_state)

    result = {
        "state": "ALIGN",
        "project_id": project_id,
        "file_classifications": classifications,
        "summary": audit_report.get("summary", {}),
    }
    if corrections:
        result["corrections_applied"] = list(corrections.keys())
    if answer:
        result["answer"] = answer
    result["message"] = "已更新。请继续修正或确认。"
    result["next_actions"] = ["classify", "confirm"]
    return result


def _phase_confirm(
    session: ProjectSession,
    project_id: str,
    confirmed_raw_files: Optional[list[str]],
    confirmed_ref_files: Optional[list[str]],
    analysis_goals: Optional[list[str]],
) -> dict:
    if not project_id:
        return {"error": "project_id is required for action=confirm"}

    create_state = session.store.load_create_state(project_id)
    if not create_state:
        return {"error": f"No create state found for project {project_id}."}

    if create_state.state not in ("ALIGN", "CONFIRM"):
        return {"error": f"Cannot confirm in state {create_state.state}. Expected ALIGN."}

    audit_report = create_state.audit_report
    classifications = audit_report.get("file_classifications", [])

    raw_names = {fc["filename"] for fc in classifications if fc["category"] == "raw_data"}
    ref_names = {fc["filename"] for fc in classifications if fc["category"].startswith("reference")}

    if confirmed_raw_files is not None:
        invalid = set(confirmed_raw_files) - raw_names
        if invalid:
            return {"error": f"These files are not classified as raw_data: {sorted(invalid)}"}
        create_state.confirmed_raw_files = confirmed_raw_files
    elif not create_state.confirmed_raw_files:
        create_state.confirmed_raw_files = sorted(raw_names)

    if confirmed_ref_files is not None:
        invalid = set(confirmed_ref_files) - ref_names
        if invalid:
            return {"error": f"These files are not classified as reference: {sorted(invalid)}"}
        create_state.confirmed_ref_files = confirmed_ref_files
    elif not create_state.confirmed_ref_files:
        create_state.confirmed_ref_files = sorted(ref_names)

    if analysis_goals:
        create_state.analysis_goals = analysis_goals

    if not create_state.confirmed_raw_files:
        return {"error": "At least 1 raw data file must be confirmed to build."}

    create_state.state = "CONFIRM"
    create_state.updated_at = datetime.now().isoformat()
    session.store.save_create_state(project_id, create_state)

    return {
        "state": "BUILD_READY",
        "project_id": project_id,
        "build_plan": {
            "raw_files_to_import": create_state.confirmed_raw_files,
            "ref_files_for_context": create_state.confirmed_ref_files,
            "analysis_goals": create_state.analysis_goals,
            "summary": audit_report.get("summary", {}),
        },
        "message": "确认后将开始构建语义层。调用 action=build 继续。",
        "next_actions": ["build"],
    }


def _phase_build(
    session: ProjectSession,
    project_id: str,
    use_llm: bool,
    project_type: Optional[str],
) -> dict:
    r1 = pipeline_load_data(session, project_id, project_type)
    if "error" in r1:
        return r1

    r2 = pipeline_create_derived(session, project_id)
    if "error" in r2:
        return r2

    r3 = pipeline_gen_semantic(session, project_id, use_llm)
    if "error" in r3:
        return r3

    r4 = pipeline_save_semantic(session, project_id)
    return r4


def execute_pipeline_step(
    session: ProjectSession,
    project_id: str,
    step: str,
    use_llm: bool = True,
    project_type: Optional[str] = None,
) -> dict:
    valid_steps = {"load_data", "create_derived", "gen_semantic", "save_semantic"}
    if step not in valid_steps:
        return {"error": f"Invalid step '{step}'. Valid: {sorted(valid_steps)}"}

    if step == "load_data":
        return pipeline_load_data(session, project_id, project_type)
    elif step == "create_derived":
        return pipeline_create_derived(session, project_id)
    elif step == "gen_semantic":
        return pipeline_gen_semantic(session, project_id, use_llm)
    elif step == "save_semantic":
        return pipeline_save_semantic(session, project_id)


def pipeline_load_data(session: ProjectSession, project_id: str, project_type: Optional[str]) -> dict:
    if not project_id:
        return {"error": "project_id is required"}

    create_state = session.store.load_create_state(project_id)
    if not create_state:
        return {"error": f"No create state found for project {project_id}."}

    if create_state.state != "CONFIRM":
        return {"error": f"Cannot build in state {create_state.state}. Complete confirm first."}

    classifications = create_state.audit_report.get("file_classifications", [])
    raw_file_map = {}
    for fc in classifications:
        if fc["filename"] in create_state.confirmed_raw_files:
            raw_file_map[fc["filename"]] = fc["filepath"]

    raw_paths = [raw_file_map[name] for name in create_state.confirmed_raw_files if name in raw_file_map]

    if not raw_paths:
        return {"error": "No confirmed raw data files found to import."}

    project = session.store.create_project(
        name=create_state.name,
        data_files=raw_paths,
        project_type=project_type or "generic",
        project_id=project_id,
    )

    dm = session.get_dm(project.id)

    if not project_type:
        detected = detect_project_type(dm)
        project.project_type = detected

    pipeline_state = PipelineState(
        project_id=project_id,
        current_step="load_data",
        completed_steps=["load_data"],
        step_results={
            "load_data": {
                "tables": [project.semantic_layer.get("table_name", "events")],
                "rows": dm.meta.get("total_rows", 0),
                "columns": dm.meta.get("columns", []),
            }
        },
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    session.store.save_pipeline_state(project_id, pipeline_state)

    return {
        "step": "load_data",
        "status": "completed",
        "project_id": project.id,
        "total_rows": dm.meta.get("total_rows", 0),
        "total_columns": dm.meta.get("total_columns", 0),
        "next_step": "create_derived",
    }


def pipeline_create_derived(session: ProjectSession, project_id: str) -> dict:
    pipeline_state = session.store.load_pipeline_state(project_id)
    if not pipeline_state or not pipeline_state.is_step_completed("load_data"):
        return {"error": "load_data step must complete first"}

    dm = session.get_dm(project_id)
    created = dm.create_derived_columns()

    pipeline_state.advance("create_derived", {"derived_columns": list(created.keys())})
    session.store.save_pipeline_state(project_id, pipeline_state)

    return {
        "step": "create_derived",
        "status": "completed",
        "project_id": project_id,
        "derived_columns": created,
        "next_step": "gen_semantic",
    }


def pipeline_gen_semantic(session: ProjectSession, project_id: str, use_llm: bool) -> dict:
    pipeline_state = session.store.load_pipeline_state(project_id)
    if not pipeline_state or not pipeline_state.is_step_completed("create_derived"):
        return {"error": "create_derived step must complete first"}

    project = session.store.get_project(project_id)
    dm = session.get_dm(project_id)

    create_state = session.store.load_create_state(project_id)
    reference_context = _build_reference_context(create_state) if create_state else ""

    try:
        semantic = generate_semantic_layer(
            dm,
            project_type=project.project_type,
            use_llm=use_llm,
            reference_context=reference_context,
        )
    except RuntimeError as e:
        return {"step": "gen_semantic", "status": "failed", "error": str(e)}

    project.semantic_layer = {
        "table_name": semantic.get("table_name", "events"),
        "config_file": semantic.get("config_file", "semantic_config.json"),
    }
    session.store.save_project(project)

    dm.invalidate_semantic_cache()

    pipeline_state.advance("gen_semantic", {
        "metrics_count": len(semantic.get("metrics", {})),
        "events_count": len(semantic.get("event_definitions", {})),
        "columns_count": len(semantic.get("columns", {})),
    })
    session.store.save_pipeline_state(project_id, pipeline_state)

    from mcp_server.semantic_validator import SemanticValidator
    full_sl = project.get_full_semantic_layer(PROJECTS_DIR)
    validator = SemanticValidator(dm, full_sl)
    validation = validator.validate_all()

    report_path = os.path.join(PROJECTS_DIR, project.id, "validation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(validation, f, ensure_ascii=False, indent=2, default=str)

    return {
        "step": "gen_semantic",
        "status": "completed",
        "project_id": project_id,
        "metrics_count": len(semantic.get("metrics", {})),
        "events_count": len(semantic.get("event_definitions", {})),
        "validation_summary": validation.get("summary", {}),
        "next_step": "save_semantic",
    }


def pipeline_save_semantic(session: ProjectSession, project_id: str) -> dict:
    pipeline_state = session.store.load_pipeline_state(project_id)
    if not pipeline_state or not pipeline_state.is_step_completed("gen_semantic"):
        return {"error": "gen_semantic step must complete first"}

    project = session.store.get_project(project_id)
    create_state = session.store.load_create_state(project_id)

    if create_state:
        if create_state.analysis_goals:
            project.meta["analysis_goals"] = create_state.analysis_goals
        project.meta["confirmed_ref_files"] = create_state.confirmed_ref_files

    session.store.save_project(project)
    session.store.delete_create_state(project_id)
    session.store.delete_pipeline_state(project_id)

    session.unload_project(project.id)
    session.switch_project(project.id)

    full_sl = project.get_full_semantic_layer(PROJECTS_DIR)

    return {
        "step": "save_semantic",
        "status": "completed",
        "project_id": project.id,
        "name": project.name,
        "project_type": project.project_type,
        "data_files": project.data_source.get("files", []),
        "metrics_count": len(full_sl.get("metrics", {})),
        "events_count": len(full_sl.get("event_definitions", {})),
        "semantic_source": "llm",
        "state": "COMPLETED",
    }


def _build_reference_context(create_state: CreateProjectState) -> str:
    audit_report = create_state.audit_report
    ref_contents = audit_report.get("reference_contents", [])
    confirmed_ref = set(create_state.confirmed_ref_files)

    if create_state.state in ("CONFIRM", "BUILD", "COMPLETED") and not confirmed_ref:
        return ""

    parts = []
    for rc in ref_contents:
        if confirmed_ref and rc.get("filename") not in confirmed_ref:
            continue

        sections = []
        cat = rc.get("category", "")
        if cat == "reference_kpi":
            kpis = rc.get("kpi_definitions", [])
            if kpis:
                sections.append("### KPI 指标定义")
                for kpi in kpis:
                    name = kpi.get("name", "?")
                    desc = kpi.get("description", "")
                    formula = kpi.get("formula", "")
                    params = kpi.get("params", [])
                    line = f"- **{name}**: {desc}"
                    if formula:
                        line += f" (公式: {formula})"
                    if params:
                        line += f" [参数: {', '.join(params)}]"
                    sections.append(line)
        elif cat == "reference_dict":
            fields = rc.get("field_definitions", [])
            if fields:
                sections.append("### 数据字典")
                for fd in fields:
                    field = fd.get("field", "?")
                    meaning = fd.get("meaning", "")
                    enums = fd.get("enum_values", [])
                    line = f"- **{field}**: {meaning}"
                    if enums:
                        line += f" (枚举: {', '.join(str(e) for e in enums[:10])})"
                    sections.append(line)
        else:
            raw = rc.get("raw_text", "")
            if raw:
                sections.append(f"### 参考文档内容\n{raw[:1000]}")

        if sections:
            parts.append(f"## 文件: {rc['filename']} (类型: {cat})\n" + "\n".join(sections))

    if not parts:
        return ""

    return "\n\n".join(parts)


def _answer_alignment_question(question: str, audit_report: dict) -> str:
    summary = audit_report.get("summary", {})
    classifications = audit_report.get("file_classifications", [])
    ref_contents = audit_report.get("reference_contents", [])

    context_parts = [
        f"项目概况: {summary.get('raw_files', 0)} 个原始数据文件, {summary.get('ref_files', 0)} 个参考文档, 共 {summary.get('total_rows', 0)} 行数据",
        "文件分类:",
    ]
    for fc in classifications:
        context_parts.append(f"  - {fc['filename']}: {fc['category']} (置信度: {fc.get('confidence', 0):.0%})")

    for rc in ref_contents:
        if rc.get("kpi_definitions"):
            context_parts.append(f"\n{rc['filename']} 中的 KPI 定义 ({len(rc['kpi_definitions'])} 个):")
            for kpi in rc["kpi_definitions"][:10]:
                context_parts.append(f"  - {kpi.get('name', '?')}: {kpi.get('description', '')[:60]}")

    context = "\n".join(context_parts)
    return f"基于审计报告:\n{context}\n\n关于您的问题「{question}」，请参考以上信息。如需更详细的分析，请在确认后构建项目。"


def get_create_status(session: ProjectSession) -> dict:
    projects_dir = PROJECTS_DIR
    if not os.path.exists(projects_dir):
        return {"state": "NONE", "message": "No projects directory."}

    pending = []
    for entry in os.listdir(projects_dir):
        state_path = os.path.join(projects_dir, entry, ".create_state.json")
        if os.path.exists(state_path):
            try:
                cs = session.store.load_create_state(entry)
                if cs and cs.state not in ("COMPLETED",):
                    pending.append({
                        "project_id": cs.project_id,
                        "name": cs.name,
                        "state": cs.state,
                        "created_at": cs.created_at,
                    })
            except Exception:
                pass

    if not pending:
        return {"state": "NONE", "message": "No pending create_project flows."}

    return {
        "state": "PENDING",
        "pending_projects": pending,
        "message": f"Found {len(pending)} pending create flow(s). Use action=classify/confirm/build to continue.",
    }
