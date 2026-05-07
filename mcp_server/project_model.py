# -*- coding: utf-8 -*-
"""
Project Model & Storage Layer

A Project represents an imported dataset with its semantic layer,
DuckDB instance, and configuration. Projects are stored as:

  projects/
    {project_id}/
      project.yaml          # project config + semantic layer
      data/                 # original data files (copied or symlinked)
      {project_id}.duckdb   # persistent DuckDB database
"""

import os
import re
import json
import shutil
import uuid
import yaml
import duckdb
from datetime import datetime
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


PROJECTS_DIR = os.environ.get(
    "CHATBI_PROJECTS_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "projects")),
)


@dataclass
class ColumnDef:
    business_name: str = ""
    type: str = "string"
    role: str = "dimension"
    description: str = ""
    derived: bool = False
    derived_from: str = ""
    derivation_logic: str = ""
    enum: list = field(default_factory=list)
    available_events: list = field(default_factory=list)
    note: str = ""


@dataclass
class MetricDef:
    business_name: str = ""
    sql: str = ""
    keywords: list = field(default_factory=list)
    description: str = ""


@dataclass
class EventDef:
    business_name: str = ""
    description: str = ""
    category: str = ""
    aliases: list = field(default_factory=list)


class FileCategory(str, Enum):
    RAW_DATA = "raw_data"
    REFERENCE_KPI = "reference_kpi"
    REFERENCE_DICT = "reference_dict"
    REFERENCE_REQ = "reference_req"
    REFERENCE_OTHER = "reference_other"
    UNKNOWN = "unknown"


@dataclass
class FileClassification:
    filename: str = ""
    filepath: str = ""
    category: str = "unknown"
    confidence: float = 0.0
    reason: str = ""
    columns: list = field(default_factory=list)
    row_count: int = 0
    encoding: str = "utf-8"
    format: str = "csv"

    def category_enum(self) -> FileCategory:
        try:
            return FileCategory(self.category)
        except ValueError:
            return FileCategory.UNKNOWN

    def is_reference(self) -> bool:
        return self.category.startswith("reference")

    def is_raw_data(self) -> bool:
        return self.category == "raw_data"


@dataclass
class FileSchemaInfo:
    filename: str = ""
    columns: list = field(default_factory=list)
    row_count: int = 0
    numeric_columns: list = field(default_factory=list)
    date_columns: list = field(default_factory=list)
    category_columns: list = field(default_factory=list)
    quality_score: float = 0.0
    quality_issues: list = field(default_factory=list)


@dataclass
class ReferenceContent:
    filename: str = ""
    category: str = "reference_other"
    raw_text: str = ""
    kpi_definitions: list = field(default_factory=list)
    field_definitions: list = field(default_factory=list)
    analysis_goals: list = field(default_factory=list)


@dataclass
class DataAuditReport:
    project_name: str = ""
    created_at: str = ""
    file_classifications: list = field(default_factory=list)
    raw_data_schemas: list = field(default_factory=list)
    reference_contents: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "created_at": self.created_at,
            "file_classifications": [
                fc if isinstance(fc, dict) else {
                    "filename": fc.filename,
                    "filepath": fc.filepath,
                    "category": fc.category,
                    "confidence": fc.confidence,
                    "reason": fc.reason,
                    "columns": fc.columns,
                    "row_count": fc.row_count,
                    "encoding": fc.encoding,
                    "format": fc.format,
                }
                for fc in self.file_classifications
            ],
            "raw_data_schemas": [
                s if isinstance(s, dict) else {
                    "filename": s.filename,
                    "columns": s.columns,
                    "row_count": s.row_count,
                    "numeric_columns": s.numeric_columns,
                    "date_columns": s.date_columns,
                    "category_columns": s.category_columns,
                    "quality_score": s.quality_score,
                    "quality_issues": s.quality_issues,
                }
                for s in self.raw_data_schemas
            ],
            "reference_contents": [
                rc if isinstance(rc, dict) else {
                    "filename": rc.filename,
                    "category": rc.category,
                    "raw_text": rc.raw_text[:500],
                    "kpi_definitions": rc.kpi_definitions,
                    "field_definitions": rc.field_definitions,
                    "analysis_goals": rc.analysis_goals,
                }
                for rc in self.reference_contents
            ],
            "summary": self.summary,
        }


@dataclass
class SemanticLayer:
    table_name: str = "events"
    columns: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    event_definitions: dict = field(default_factory=dict)
    examples: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    prompt_template: str = ""


@dataclass
class DataSource:
    files: list = field(default_factory=list)
    format: str = "xlsx"
    sheet_name: Optional[str] = None
    encoding: str = "utf-8"


PROJECT_TYPES = [
    "behavior_analysis",
    "business_report",
    "time_series",
    "generic",
]


@dataclass
class Project:
    id: str = ""
    name: str = ""
    project_type: str = "generic"
    data_source: dict = field(default_factory=dict)
    semantic_layer: dict = field(default_factory=dict)
    semantic_layer_dirty: bool = False
    created_at: str = ""
    updated_at: str = ""
    meta: dict = field(default_factory=dict)

    @staticmethod
    def generate_id(name: str = "") -> str:
        if name:
            slug = name.strip()
            slug = re.sub(r'[<>:"/\\|?*]', '', slug)
            slug = re.sub(r'\s+', '-', slug)
            slug = slug.strip('-.')
            if slug:
                return slug
        return str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "project_type": self.project_type,
            "data_source": self.data_source,
            "semantic_layer": self.semantic_layer,
            "semantic_layer_dirty": self.semantic_layer_dirty,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            project_type=d.get("project_type", "generic"),
            data_source=d.get("data_source", {}),
            semantic_layer=d.get("semantic_layer", {}),
            semantic_layer_dirty=d.get("semantic_layer_dirty", False),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            meta=d.get("meta", {}),
        )

    def get_full_semantic_layer(self, projects_dir: str = None) -> dict:
        sl = self.semantic_layer.copy()
        config_file = sl.get("config_file")

        if config_file and projects_dir:
            config_path = os.path.join(projects_dir, self.id, config_file)
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                for key in ("columns", "metrics", "dimensions",
                            "examples", "rules", "prompt_template",
                            "data_cleaning"):
                    if key in config and key not in sl:
                        sl[key] = config[key]
                if "event_definitions" in config and "event_definitions" not in sl:
                    sl["event_definitions"] = config["event_definitions"]
                elif "events" in config and "event_definitions" not in sl:
                    sl["event_definitions"] = config["events"]
                for key in ("page_map", "element_map", "composite_pages",
                            "composite_elements", "alias_rules", "category_rules",
                            "dedup_words", "action_type_map"):
                    if key in config:
                        sl.setdefault("semantic_config", {})[key] = config[key]

        return sl


class PipelineStep(str, Enum):
    LOAD_DATA = "load_data"
    CREATE_DERIVED = "create_derived"
    GEN_SEMANTIC = "gen_semantic"
    SAVE_SEMANTIC = "save_semantic"

    @classmethod
    def all_steps(cls) -> list[str]:
        return [s.value for s in cls]


@dataclass
class PipelineState:
    project_id: str = ""
    current_step: str = ""
    completed_steps: list = field(default_factory=list)
    step_results: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "step_results": self.step_results,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineState":
        return cls(
            project_id=d.get("project_id", ""),
            current_step=d.get("current_step", ""),
            completed_steps=d.get("completed_steps", []),
            step_results=d.get("step_results", {}),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )

    def advance(self, step: str, result: dict) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.current_step = step
        self.step_results[step] = result
        self.updated_at = datetime.now().isoformat()

    def next_step(self) -> Optional[str]:
        for s in PipelineStep.all_steps():
            if s not in self.completed_steps:
                return s
        return None

    def is_step_completed(self, step: str) -> bool:
        return step in self.completed_steps


class ProjectStore:
    def __init__(self, projects_dir: str = None):
        self.projects_dir = projects_dir or PROJECTS_DIR
        os.makedirs(self.projects_dir, exist_ok=True)

    def _ensure_unique_id(self, project_id: str) -> str:
        if not os.path.exists(self._project_dir(project_id)):
            return project_id
        base = project_id
        counter = 2
        while os.path.exists(self._project_dir(f"{base}-{counter}")):
            counter += 1
        return f"{base}-{counter}"

    def _project_dir(self, project_id: str) -> str:
        return os.path.join(self.projects_dir, project_id)

    def _config_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "project.yaml")

    def _data_dir(self, project_id: str) -> str:
        d = os.path.join(self._project_dir(project_id), "data")
        os.makedirs(d, exist_ok=True)
        return d

    def _duckdb_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), f"{project_id}.duckdb")

    def list_projects(self) -> list[dict]:
        projects = []
        if not os.path.exists(self.projects_dir):
            return projects
        for entry in sorted(os.listdir(self.projects_dir)):
            config_path = os.path.join(self.projects_dir, entry, "project.yaml")
            if os.path.exists(config_path):
                try:
                    with open(config_path, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    projects.append({
                        "id": data.get("id", entry),
                        "name": data.get("name", entry),
                        "project_type": data.get("project_type", "generic"),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "has_duckdb": os.path.exists(self._duckdb_path(data.get("id", entry))),
                        "data_files_count": len(data.get("data_source", {}).get("files", [])),
                    })
                except Exception:
                    continue
        return projects

    def resolve_project_id(self, identifier: str) -> Optional[str]:
        config_path = self._config_path(identifier)
        if os.path.exists(config_path):
            return identifier
        for entry in sorted(os.listdir(self.projects_dir)):
            cp = os.path.join(self.projects_dir, entry, "project.yaml")
            if os.path.exists(cp):
                try:
                    with open(cp, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if data.get("name") == identifier or data.get("id") == identifier:
                        return data.get("id", entry)
                except Exception:
                    continue
        return None

    def get_project(self, project_id: str) -> Optional[Project]:
        resolved = self.resolve_project_id(project_id)
        if not resolved:
            return None
        config_path = self._config_path(resolved)
        if not os.path.exists(config_path):
            return None
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return Project.from_dict(data)

    def save_project(self, project: Project) -> str:
        project_dir = self._project_dir(project.id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(self._data_dir(project.id), exist_ok=True)

        project.updated_at = datetime.now().isoformat()
        config_path = self._config_path(project.id)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(project.to_dict(), f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return config_path

    def create_project(
        self,
        name: str,
        data_files: list[str],
        project_type: str = "generic",
        project_id: str = None,
    ) -> Project:
        if project_id:
            project_id = project_id
        else:
            project_id = Project.generate_id(name)
            project_id = self._ensure_unique_id(project_id)
        now = datetime.now().isoformat()

        data_dir = self._data_dir(project_id)
        copied_files = []
        for src in data_files:
            if not os.path.exists(src):
                continue
            dst = os.path.join(data_dir, os.path.basename(src))
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
            copied_files.append(os.path.basename(src))

        fmt = "csv"
        if any(f.endswith((".xlsx", ".xls")) for f in copied_files):
            fmt = "xlsx"

        project = Project(
            id=project_id,
            name=name,
            project_type=project_type,
            data_source={
                "files": copied_files,
                "format": fmt,
            },
            created_at=now,
            updated_at=now,
        )

        self.save_project(project)
        return project

    def delete_project(self, project_id: str) -> bool:
        project_dir = self._project_dir(project_id)
        if not os.path.exists(project_dir):
            return False
        shutil.rmtree(project_dir)
        return True

    def _audit_report_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "audit_report.yaml")

    def save_audit_report(self, project_id: str, report: DataAuditReport) -> str:
        report_path = self._audit_report_path(project_id)
        project_dir = self._project_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        data = report.to_dict()
        with open(report_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return report_path

    def load_audit_report(self, project_id: str) -> Optional[DataAuditReport]:
        report_path = self._audit_report_path(project_id)
        if not os.path.exists(report_path):
            return None
        with open(report_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return None
        return DataAuditReport(
            project_name=data.get("project_name", ""),
            created_at=data.get("created_at", ""),
            file_classifications=[
                FileClassification(**fc) if isinstance(fc, dict) else fc
                for fc in data.get("file_classifications", [])
            ],
            raw_data_schemas=[
                FileSchemaInfo(**s) if isinstance(s, dict) else s
                for s in data.get("raw_data_schemas", [])
            ],
            reference_contents=[
                ReferenceContent(**rc) if isinstance(rc, dict) else rc
                for rc in data.get("reference_contents", [])
            ],
            summary=data.get("summary", {}),
        )

    def _create_state_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), ".create_state.json")

    def save_create_state(self, project_id: str, state: "CreateProjectState") -> str:
        path = self._create_state_path(project_id)
        project_dir = self._project_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_create_state(self, project_id: str) -> Optional["CreateProjectState"]:
        path = self._create_state_path(project_id)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return CreateProjectState.from_dict(data)

    def delete_create_state(self, project_id: str) -> bool:
        path = self._create_state_path(project_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _pipeline_state_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), ".pipeline_state.json")

    def save_pipeline_state(self, project_id: str, state: PipelineState) -> str:
        path = self._pipeline_state_path(project_id)
        project_dir = self._project_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_pipeline_state(self, project_id: str) -> Optional[PipelineState]:
        path = self._pipeline_state_path(project_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PipelineState.from_dict(data)

    def delete_pipeline_state(self, project_id: str) -> bool:
        path = self._pipeline_state_path(project_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _semantic_config_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "semantic_config.json")

    def save_semantic_config(self, project_id: str, config: dict) -> str:
        config_path = self._semantic_config_path(project_id)
        project_dir = self._project_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return config_path

    def load_semantic_config(self, project_id: str) -> Optional[dict]:
        config_path = self._semantic_config_path(project_id)
        if not os.path.exists(config_path):
            return None
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def migrate_semantic_layer(self, project_id: str) -> dict:
        project = self.get_project(project_id)
        if not project:
            return {"error": f"Project {project_id} not found"}

        sl = project.semantic_layer
        if sl.get("config_file"):
            return {"status": "already_migrated", "project_id": project_id}

        if not sl.get("columns") and not sl.get("metrics"):
            return {"status": "no_semantic_layer", "project_id": project_id}

        config = {}
        config_path = self._semantic_config_path(project_id)
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

        if sl.get("columns"):
            config["columns"] = sl["columns"]
        if sl.get("event_definitions"):
            config["events"] = sl["event_definitions"]
        if sl.get("metrics"):
            config["metrics"] = sl["metrics"]

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        project.semantic_layer = {
            "table_name": sl.get("table_name", "events"),
            "config_file": "semantic_config.json",
        }
        self.save_project(project)

        return {
            "status": "migrated",
            "project_id": project_id,
            "config_file": "semantic_config.json",
            "columns_count": len(config.get("columns", {})),
            "metrics_count": len(config.get("metrics", {})),
        }

    def load_validation_report(self, project_id: str) -> Optional[dict]:
        report_path = os.path.join(self.projects_dir, project_id, "validation_report.json")
        if not os.path.exists(report_path):
            return None
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_validation_report(self, project_id: str, report: dict) -> None:
        report_path = os.path.join(self.projects_dir, project_id, "validation_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)


class CreateState(str, Enum):
    PRE_ANALYZE = "PRE_ANALYZE"
    ALIGN = "ALIGN"
    CONFIRM = "CONFIRM"
    BUILD = "BUILD"
    COMPLETED = "COMPLETED"


@dataclass
class CreateProjectState:
    state: str = "PRE_ANALYZE"
    project_id: str = ""
    name: str = ""
    data_files: list = field(default_factory=list)
    audit_report: dict = field(default_factory=dict)
    user_corrections: dict = field(default_factory=dict)
    confirmed_raw_files: list = field(default_factory=list)
    confirmed_ref_files: list = field(default_factory=list)
    analysis_goals: list = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "project_id": self.project_id,
            "name": self.name,
            "data_files": self.data_files,
            "audit_report": self.audit_report,
            "user_corrections": self.user_corrections,
            "confirmed_raw_files": self.confirmed_raw_files,
            "confirmed_ref_files": self.confirmed_ref_files,
            "analysis_goals": self.analysis_goals,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CreateProjectState":
        return cls(
            state=d.get("state", "PRE_ANALYZE"),
            project_id=d.get("project_id", ""),
            name=d.get("name", ""),
            data_files=d.get("data_files", []),
            audit_report=d.get("audit_report", {}),
            user_corrections=d.get("user_corrections", {}),
            confirmed_raw_files=d.get("confirmed_raw_files", []),
            confirmed_ref_files=d.get("confirmed_ref_files", []),
            analysis_goals=d.get("analysis_goals", []),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


class ProjectDataManager:
    def __init__(self, project: Project, projects_dir: str = None):
        self.project = project
        projects_dir = projects_dir or PROJECTS_DIR
        self.projects_dir = projects_dir
        self.project_dir = os.path.join(projects_dir, project.id)
        self.data_dir = os.path.join(self.project_dir, "data")
        self.duckdb_path = os.path.join(self.project_dir, f"{project.id}.duckdb")
        self.con = None
        self.df = None
        self.meta = {}
        self._full_semantic_layer = None

    def get_full_semantic_layer(self) -> dict:
        if self._full_semantic_layer is None:
            self._full_semantic_layer = self.project.get_full_semantic_layer(self.projects_dir)
        return self._full_semantic_layer

    def invalidate_semantic_cache(self):
        self._full_semantic_layer = None

    def load(self) -> dict:
        if self.con:
            self.con.close()

        self.con = duckdb.connect(database=self.duckdb_path)

        if self._is_duckdb_populated():
            self._load_meta_from_duckdb()
            self._ensure_clean_views()
            return self.meta

        ds = self.project.data_source
        if not ds.get("files"):
            self.meta = {
                "total_rows": 0,
                "total_columns": 0,
                "table_name": self.get_full_semantic_layer().get("table_name", "events"),
                "source": "no_data",
                "columns": [],
            }
            return self.meta

        self._load_from_source()
        return self.meta

    def _is_duckdb_populated(self) -> bool:
        try:
            tables = self.con.execute("SHOW TABLES").fetchall()
            return len(tables) > 0
        except Exception:
            return False

    def _load_meta_from_duckdb(self):
        table_name = self.get_full_semantic_layer().get("table_name", "events")
        try:
            count = self.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            self.meta = {
                "total_rows": count,
                "table_name": table_name,
                "source": "duckdb_persistent",
            }
            cols = self.con.execute(f"DESCRIBE {table_name}").fetchall()
            existing_cols = [c[0] for c in cols]
            self.meta["columns"] = existing_cols
            self.meta["total_columns"] = len(cols)

            numeric_cols, date_cols = self._infer_column_types(table_name, cols, count)
            self.meta["numeric_columns"] = numeric_cols
            self.meta["date_columns"] = date_cols

            self._ensure_derived_columns_in_duckdb(table_name, existing_cols)
        except Exception as e:
            self.meta = {"error": str(e)}

    def _infer_column_types(self, table_name: str, cols: list, total_rows: int) -> tuple[list[str], list[str]]:
        numeric_cols = []
        date_cols = []
        for c in cols:
            col_name = c[0]
            dtype = c[1].upper()
            if any(t in dtype for t in ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC", "SMALLINT", "TINYINT", "HUGEINT")):
                numeric_cols.append(col_name)
            elif any(t in dtype for t in ("TIMESTAMP", "DATE", "TIME")):
                date_cols.append(col_name)
            elif dtype == "VARCHAR":
                col_lower = col_name.lower()
                is_id_col = ("id" in col_lower or col_lower.endswith("_id") or col_lower == "id")
                if not is_id_col:
                    try:
                        unique_cnt = self.con.execute(
                            f'SELECT COUNT(DISTINCT "{col_name}") FROM {table_name}'
                        ).fetchone()[0]
                        unique_rate = unique_cnt / max(total_rows, 1)
                        if unique_rate > 0.8:
                            continue
                        numeric_check = self.con.execute(
                            f'SELECT COUNT(*) FROM {table_name} WHERE "{col_name}" IS NOT NULL AND TRY_CAST("{col_name}" AS DOUBLE) IS NOT NULL'
                        ).fetchone()[0]
                        non_null = total_rows - self.con.execute(
                            f'SELECT COUNT(*) FROM {table_name} WHERE "{col_name}" IS NULL'
                        ).fetchone()[0]
                        if non_null > 0 and numeric_check / non_null > 0.9:
                            numeric_cols.append(col_name)
                            continue
                        date_check = self.con.execute(
                            f'SELECT COUNT(*) FROM {table_name} WHERE "{col_name}" IS NOT NULL AND TRY_CAST("{col_name}" AS TIMESTAMP) IS NOT NULL'
                        ).fetchone()[0]
                        if non_null > 0 and date_check / non_null > 0.9:
                            date_cols.append(col_name)
                    except Exception:
                        pass
        return numeric_cols, date_cols

    def _ensure_derived_columns_in_duckdb(self, table_name: str, existing_cols: list):
        derived = self.get_full_semantic_layer().get("columns", {})
        for col_name, col_info in derived.items():
            if not col_info.get("derived"):
                continue
            if col_name in existing_cols:
                continue

            derived_from = col_info.get("derived_from", "")
            logic = col_info.get("derivation_logic", "")

            if derived_from not in existing_cols:
                continue

            try:
                if logic == "date" or (not logic and "日期" in (col_info.get("business_name", "") + col_info.get("description", ""))):
                    self.con.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} DATE"
                    )
                    self.con.execute(
                        f"UPDATE {table_name} SET {col_name} = CAST(TRY_CAST({derived_from} AS TIMESTAMP) AS DATE)"
                    )
                elif logic == "hour" or (not logic and "小时" in (col_info.get("business_name", "") + col_info.get("description", ""))):
                    self.con.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} INTEGER"
                    )
                    self.con.execute(
                        f"UPDATE {table_name} SET {col_name} = HOUR(TRY_CAST({derived_from} AS TIMESTAMP))"
                    )
                print(f"[ProjectDM] Added derived column {col_name} to DuckDB")
            except Exception as e:
                print(f"[ProjectDM] Failed to add derived column {col_name}: {e}")

    def _ensure_duckdb_excel(self):
        try:
            self.con.execute("SELECT 1 FROM duckdb_extensions() WHERE extension_name='excel' AND loaded=true").fetchone()
        except Exception:
            pass
        try:
            self.con.execute("LOAD excel")
        except Exception:
            self.con.execute("INSTALL excel")
            self.con.execute("LOAD excel")

    def _load_from_source(self):
        ds = self.project.data_source
        fmt = ds.get("format", "xlsx")
        files = ds.get("files", [])
        table_name = self.get_full_semantic_layer().get("table_name", "events")

        if not files:
            raise FileNotFoundError(f"No data files configured for project {self.project.id}")

        self.con.execute(f"DROP TABLE IF EXISTS {table_name}")

        first_file = True
        loaded_files = []
        for fname in files:
            fpath = os.path.join(self.data_dir, fname)
            if not os.path.exists(fpath):
                print(f"[ProjectDM] File not found: {fpath}, skipping")
                continue

            ext = os.path.splitext(fname)[1].lower()
            try:
                if ext in (".xlsx", ".xls"):
                    self._ensure_duckdb_excel()
                    read_sql = f"SELECT * FROM read_xlsx('{fpath}', all_varchar=true)"
                elif ext == ".parquet":
                    read_sql = f"SELECT * FROM read_parquet('{fpath}')"
                elif ext in (".csv", ".tsv"):
                    enc = ds.get("encoding", "utf-8")
                    sep = "\\t" if ext == ".tsv" else ","
                    read_sql = f"SELECT * FROM read_csv('{fpath}', delim='{sep}', encoding='{enc}')"
                else:
                    enc = ds.get("encoding", "utf-8")
                    read_sql = f"SELECT * FROM read_csv('{fpath}', encoding='{enc}')"
            except Exception as e:
                print(f"[ProjectDM] Failed to prepare read for {fpath}: {e}")
                continue

            if first_file:
                self.con.execute(f"CREATE TABLE {table_name} AS {read_sql}")
                first_file = False
            else:
                self.con.execute(f"INSERT INTO {table_name} {read_sql}")

            row_count = self.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            loaded_files.append(fname)
            print(f"[ProjectDM] Loaded {fpath} (total rows now: {row_count:,})")

        if not loaded_files:
            raise FileNotFoundError(f"No loadable data files found for project {self.project.id}")

        cols = self.con.execute(f"DESCRIBE {table_name}").fetchall()
        col_names = [c[0] for c in cols]
        total_rows = self.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

        numeric_cols, date_cols = self._infer_column_types(table_name, cols, total_rows)

        self.df = None

        self.meta = {
            "file": ", ".join(loaded_files),
            "total_rows": total_rows,
            "total_columns": len(col_names),
            "table_name": table_name,
            "source": "data_files",
            "columns": col_names,
            "numeric_columns": numeric_cols,
            "date_columns": date_cols,
        }

        return self.meta

    def create_derived_columns(self) -> dict:
        if not self.con:
            raise RuntimeError("Project data not loaded. Call load() first.")

        table_name = self.get_full_semantic_layer().get("table_name", "events")
        created = {}

        try:
            cols = self.con.execute(f"DESCRIBE {table_name}").fetchall()
        except Exception:
            return created

        existing = {c[0].lower() for c in cols}
        time_cols = []
        for c in cols:
            col_name = c[0]
            dtype = c[1].lower()
            if "time" in dtype or "timestamp" in dtype:
                time_cols.append(col_name)
            elif "time" in col_name.lower() or "时间" in col_name:
                time_cols.append(col_name)

        if not time_cols:
            return created

        src_col = time_cols[0]

        if "event_date" not in existing:
            try:
                self.con.execute(f"ALTER TABLE {table_name} ADD COLUMN event_date DATE")
                self.con.execute(
                    f'UPDATE {table_name} SET event_date = CAST(TRY_CAST("{src_col}" AS TIMESTAMP) AS DATE)'
                )
                created["event_date"] = {"derived_from": src_col, "logic": "date"}
                print(f"[ProjectDM] Created derived column event_date from {src_col}")
            except Exception as e:
                print(f"[ProjectDM] Failed to create event_date: {e}")

        if "event_hour" not in existing:
            try:
                self.con.execute(f"ALTER TABLE {table_name} ADD COLUMN event_hour INTEGER")
                self.con.execute(
                    f'UPDATE {table_name} SET event_hour = HOUR(TRY_CAST("{src_col}" AS TIMESTAMP))'
                )
                created["event_hour"] = {"derived_from": src_col, "logic": "hour"}
                print(f"[ProjectDM] Created derived column event_hour from {src_col}")
            except Exception as e:
                print(f"[ProjectDM] Failed to create event_hour: {e}")

        return created

    def _ensure_clean_views(self):
        cleaning = self.get_full_semantic_layer().get("data_cleaning", {})
        view_name = cleaning.get("clean_view")
        if not view_name:
            return
        exclude_users = cleaning.get("exclude_users", [])
        dedup_cols = cleaning.get("dedup_logic", "")
        try:
            self.con.execute(f"SELECT 1 FROM {view_name} LIMIT 1").fetchone()
            return
        except Exception:
            pass

        where_parts = []
        if exclude_users:
            users_str = ", ".join(f"'{u}'" for u in exclude_users)
            where_parts.append(f"reduser_id NOT IN ({users_str})")
        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        if dedup_cols and "PARTITION BY" in dedup_cols:
            dedup_expr = dedup_cols.split(" = ")[0].strip()
            self.con.execute(f"""
                CREATE VIEW {view_name} AS
                SELECT * EXCLUDE (_rn)
                FROM (
                    SELECT *, ROW_NUMBER() OVER ({dedup_expr}) AS _rn
                    FROM events
                    {where_clause}
                )
                WHERE _rn = 1
            """)
        elif where_clause:
            self.con.execute(f"CREATE VIEW {view_name} AS SELECT * FROM events {where_clause}")

    def execute(self, sql: str) -> list[dict]:
        if not self.con:
            raise RuntimeError("Project data not loaded. Call load() first.")
        result = self.con.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def get_schema_info(self) -> list[dict]:
        try:
            table_name = self.get_full_semantic_layer().get("table_name", "events")
            cols = self.con.execute(f"DESCRIBE {table_name}").fetchall()
            result = []
            for c in cols:
                col_name, dtype = c[0], c[1]
                null_count = 0
                sample = []
                try:
                    null_count = self.con.execute(
                        f"SELECT COUNT(*) FROM {table_name} WHERE \"{col_name}\" IS NULL"
                    ).fetchone()[0]
                except Exception:
                    pass
                try:
                    sample_rows = self.con.execute(
                        f'SELECT DISTINCT "{col_name}" FROM {table_name} WHERE "{col_name}" IS NOT NULL LIMIT 3'
                    ).fetchall()
                    sample = [str(r[0]) for r in sample_rows]
                except Exception:
                    pass
                result.append({
                    "column": col_name,
                    "dtype": dtype,
                    "null_count": null_count,
                    "sample": sample,
                })
            return result
        except Exception:
            return []

    def close(self):
        if self.con:
            self.con.close()
            self.con = None


class ProjectSession:
    _CURRENT_PROJECT_FILE = ".current_project"

    def __init__(self, projects_dir: str = None):
        self.store = ProjectStore(projects_dir)
        self.projects_dir = projects_dir or PROJECTS_DIR
        self._current_project_id: Optional[str] = None
        self._managers: dict[str, ProjectDataManager] = {}
        self._load_current_project_id()

    def _state_file(self) -> str:
        return os.path.join(self.projects_dir, self._CURRENT_PROJECT_FILE)

    def _load_current_project_id(self):
        try:
            fp = self._state_file()
            if os.path.exists(fp):
                pid = open(fp, encoding="utf-8").read().strip()
                if pid and self.store.get_project(pid):
                    self._current_project_id = pid
        except Exception:
            pass

    def _save_current_project_id(self):
        try:
            fp = self._state_file()
            if self._current_project_id:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(self._current_project_id)
            elif os.path.exists(fp):
                os.remove(fp)
        except Exception:
            pass

    @property
    def current_project_id(self) -> Optional[str]:
        return self._current_project_id

    def switch_project(self, project_id: str) -> Project:
        resolved = self.store.resolve_project_id(project_id)
        if not resolved:
            raise ValueError(f"Project not found: {project_id}")
        project = self.store.get_project(resolved)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        self._current_project_id = resolved
        self._save_current_project_id()
        if resolved not in self._managers:
            dm = ProjectDataManager(project, self.projects_dir)
            dm.load()
            self._managers[resolved] = dm
        return project

    def get_current_project(self) -> Optional[Project]:
        if not self._current_project_id:
            return None
        return self.store.get_project(self._current_project_id)

    def get_current_dm(self) -> Optional[ProjectDataManager]:
        if not self._current_project_id:
            return None
        if self._current_project_id not in self._managers:
            project = self.store.get_project(self._current_project_id)
            if project:
                dm = ProjectDataManager(project, self.projects_dir)
                dm.load()
                self._managers[self._current_project_id] = dm
        return self._managers.get(self._current_project_id)

    def get_dm(self, project_id: str) -> ProjectDataManager:
        resolved = self.store.resolve_project_id(project_id) or project_id
        if resolved not in self._managers:
            project = self.store.get_project(resolved)
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            dm = ProjectDataManager(project, self.projects_dir)
            dm.load()
            self._managers[resolved] = dm
        return self._managers[resolved]

    def unload_project(self, project_id: str):
        if project_id in self._managers:
            self._managers[project_id].close()
            del self._managers[project_id]
        if self._current_project_id == project_id:
            self._current_project_id = None
            self._save_current_project_id()
