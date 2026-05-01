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
import json
import shutil
import uuid
import yaml
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


PROJECTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "projects"))


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
    created_at: str = ""
    updated_at: str = ""
    meta: dict = field(default_factory=dict)

    @staticmethod
    def generate_id() -> str:
        return str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "project_type": self.project_type,
            "data_source": self.data_source,
            "semantic_layer": self.semantic_layer,
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
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            meta=d.get("meta", {}),
        )


class ProjectStore:
    def __init__(self, projects_dir: str = None):
        self.projects_dir = projects_dir or PROJECTS_DIR
        os.makedirs(self.projects_dir, exist_ok=True)

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

    def get_project(self, project_id: str) -> Optional[Project]:
        config_path = self._config_path(project_id)
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
        project_id = project_id or Project.generate_id()
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
        self.project_dir = os.path.join(projects_dir, project.id)
        self.data_dir = os.path.join(self.project_dir, "data")
        self.duckdb_path = os.path.join(self.project_dir, f"{project.id}.duckdb")
        self.con = None
        self.df = None
        self.meta = {}

    def load(self) -> dict:
        if self.con:
            self.con.close()

        self.con = duckdb.connect(database=self.duckdb_path)

        if self._is_duckdb_populated():
            self._load_meta_from_duckdb()
            return self.meta

        ds = self.project.data_source
        if not ds.get("files"):
            self.meta = {
                "total_rows": 0,
                "total_columns": 0,
                "table_name": self.project.semantic_layer.get("table_name", "events"),
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
        table_name = self.project.semantic_layer.get("table_name", "events")
        try:
            count = self.con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            self.meta = {
                "total_rows": count,
                "table_name": table_name,
                "source": "duckdb_persistent",
            }
            cols = self.con.execute(f"DESCRIBE {table_name}").fetchall()
            self.meta["columns"] = [c[0] for c in cols]
            self.meta["total_columns"] = len(cols)
        except Exception as e:
            self.meta = {"error": str(e)}

    def _load_from_source(self):
        ds = self.project.data_source
        fmt = ds.get("format", "xlsx")
        files = ds.get("files", [])
        table_name = self.project.semantic_layer.get("table_name", "events")

        if not files:
            raise FileNotFoundError(f"No data files configured for project {self.project.id}")

        dfs = []
        for fname in files:
            fpath = os.path.join(self.data_dir, fname)
            if not os.path.exists(fpath):
                print(f"[ProjectDM] File not found: {fpath}, skipping")
                continue

            if fmt == "xlsx":
                sheet = ds.get("sheet_name")
                df = pd.read_excel(fpath, sheet_name=sheet) if sheet else pd.read_excel(fpath)
            elif fmt == "csv":
                encoding = ds.get("encoding", "utf-8")
                df = pd.read_csv(fpath, encoding=encoding)
            elif fmt == "parquet":
                df = pd.read_parquet(fpath)
            else:
                raise ValueError(f"Unsupported format: {fmt}")

            dfs.append(df)
            print(f"[ProjectDM] Loaded {fpath}: {df.shape[0]:,} rows x {df.shape[1]} cols")

        if not dfs:
            raise FileNotFoundError(f"No loadable data files found for project {self.project.id}")

        combined = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        self.df = combined

        self._apply_derived_columns(combined)

        self.con.execute(f"DROP TABLE IF EXISTS {table_name}")
        self.con.register(table_name, combined)

        self.meta = {
            "file": ", ".join(files),
            "total_rows": len(combined),
            "total_columns": len(combined.columns),
            "table_name": table_name,
            "source": "data_files",
            "columns": list(combined.columns),
        }

        numeric_cols = combined.select_dtypes(include=[np.number]).columns.tolist()
        date_cols = combined.select_dtypes(include=["datetime64"]).columns.tolist()
        self.meta["numeric_columns"] = numeric_cols
        self.meta["date_columns"] = date_cols

        return self.meta

    def _apply_derived_columns(self, df: pd.DataFrame):
        derived = self.project.semantic_layer.get("columns", {})
        for col_name, col_info in derived.items():
            if not col_info.get("derived"):
                continue
            derived_from = col_info.get("derived_from", "")
            logic = col_info.get("derivation_logic", "")

            if "start_time" in derived_from and "日期" in (col_info.get("business_name", "") + col_info.get("description", "")):
                if "start_time" in df.columns:
                    df["event_date"] = pd.to_datetime(df["start_time"], errors="coerce").dt.date
            elif "start_time" in derived_from and "小时" in (col_info.get("business_name", "") + col_info.get("description", "")):
                if "start_time" in df.columns:
                    df["event_hour"] = pd.to_datetime(df["start_time"], errors="coerce").dt.hour

    def execute(self, sql: str) -> list[dict]:
        if not self.con:
            raise RuntimeError("Project data not loaded. Call load() first.")
        result = self.con.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def get_schema_info(self) -> list[dict]:
        if self.df is None:
            try:
                table_name = self.project.semantic_layer.get("table_name", "events")
                cols = self.con.execute(f"DESCRIBE {table_name}").fetchall()
                return [{"column": c[0], "dtype": c[1]} for c in cols]
            except Exception:
                return []
        info = []
        for col in self.df.columns:
            dtype = str(self.df[col].dtype)
            nulls = int(self.df[col].isnull().sum())
            sample = self.df[col].dropna().head(3).tolist()
            info.append({
                "column": col,
                "dtype": dtype,
                "null_count": nulls,
                "sample": [str(v) for v in sample[:3]],
            })
        return info

    def close(self):
        if self.con:
            self.con.close()
            self.con = None


class ProjectSession:
    def __init__(self, projects_dir: str = None):
        self.store = ProjectStore(projects_dir)
        self.projects_dir = projects_dir or PROJECTS_DIR
        self._current_project_id: Optional[str] = None
        self._managers: dict[str, ProjectDataManager] = {}

    @property
    def current_project_id(self) -> Optional[str]:
        return self._current_project_id

    def switch_project(self, project_id: str) -> Project:
        project = self.store.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        self._current_project_id = project_id
        if project_id not in self._managers:
            dm = ProjectDataManager(project, self.projects_dir)
            dm.load()
            self._managers[project_id] = dm
        return project

    def get_current_project(self) -> Optional[Project]:
        if not self._current_project_id:
            return None
        return self.store.get_project(self._current_project_id)

    def get_current_dm(self) -> Optional[ProjectDataManager]:
        if not self._current_project_id:
            return None
        return self._managers.get(self._current_project_id)

    def get_dm(self, project_id: str) -> ProjectDataManager:
        if project_id not in self._managers:
            project = self.store.get_project(project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            dm = ProjectDataManager(project, self.projects_dir)
            dm.load()
            self._managers[project_id] = dm
        return self._managers[project_id]

    def unload_project(self, project_id: str):
        if project_id in self._managers:
            self._managers[project_id].close()
            del self._managers[project_id]
        if self._current_project_id == project_id:
            self._current_project_id = None
