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
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


PROJECTS_DIR = os.path.join(os.path.dirname(__file__), "..", "projects")


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
