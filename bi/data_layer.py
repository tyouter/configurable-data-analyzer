# -*- coding: utf-8 -*-
"""
Data Layer: DuckDB in-memory analytics engine
Loads Excel → detects V1/V2 schema → unifies columns → registers DuckDB table
"""

import os
import glob
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path


class DataManager:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(__file__), '..', 'data', 'rednote'
        )
        self.con = duckdb.connect(database=":memory:")
        self.df = None
        self.meta = {}

    def load(self) -> dict:
        """Load Excel data, unify schema, register DuckDB table."""
        xlsx_files = glob.glob(os.path.join(self.data_dir, "*.xlsx"))
        # Prefer the larger V2 file, fall back to any xlsx
        data_file = None
        for f in xlsx_files:
            if "20260319-20260412" in f:
                data_file = f
                break
        if not data_file and xlsx_files:
            data_file = xlsx_files[0]
        if not data_file:
            raise FileNotFoundError(f"No xlsx files found in {self.data_dir}")

        print(f"[DataLayer] Loading {data_file} ...")
        df = pd.read_excel(data_file)
        print(f"[DataLayer] Raw shape: {df.shape[0]:,} rows x {df.shape[1]} cols")

        # Detect V1 vs V2
        is_v1 = "span_nm" in df.columns
        is_v2 = "span_name" in df.columns
        print(f"[DataLayer] Schema: {'V1' if is_v1 else 'V2'}")

        # Unify column names
        if is_v1:
            rename_map = {
                "strt_time_nano": "start_time",
                "end_time_nano": "end_time",
                "span_nm": "event_name",
            }
        else:
            rename_map = {
                "start_time_nano": "start_time",
                "end_time_nano": "end_time",
                "span_name": "event_name",
            }
        df = df.rename(columns=rename_map)

        # Filter out test events: akimbo(西丽店) in rednote_poi_title
        poi_col = "rednote_poi_title"
        if poi_col in df.columns:
            before = len(df)
            df = df[~df[poi_col].astype(str).str.contains("akimbo", case=False, na=False)]
            filtered = before - len(df)
            if filtered > 0:
                print(f"[DataLayer] Filtered {filtered} test events (akimbo POI)")

        # Store reverse mapping: unified_name -> original_name (for audit)
        self.raw_column_map = {v: k for k, v in rename_map.items()}
        # Keep original sample values for audit display
        self.raw_sample = {}
        for orig_col, unified_col in rename_map.items():
            if unified_col in df.columns:
                vals = df[unified_col].dropna().head(3).tolist()
                self.raw_sample[unified_col] = [str(v) for v in vals]

        # Parse timestamps
        df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
        if "end_time" in df.columns:
            df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")
            df["duration_sec"] = (df["end_time"] - df["start_time"]).dt.total_seconds()
            df.loc[df["duration_sec"] < 0, "duration_sec"] = np.nan

        # Computed columns — also record their origin for audit
        df["event_date"] = df["start_time"].dt.date
        df["event_hour"] = df["start_time"].dt.hour
        df["event_weekday"] = df["start_time"].dt.dayofweek  # 0=Mon
        df["is_weekend"] = df["event_weekday"].isin([5, 6]).astype(int)

        parts = df["event_name"].str.split("_")
        df["page_root"] = parts.str[0]
        df["page"] = parts.str[:2].str.join("_")
        df["action"] = parts.str[-1]
        df["is_click"] = df["action"].str.contains("click", case=False, na=False).astype(int)

        # Computed column → raw column mapping (for audit trail)
        computed_map = {
            "event_date": {"raw_col": "start_time_nano", "logic": "取 start_time_nano 的日期部分"},
            "event_hour": {"raw_col": "start_time_nano", "logic": "取 start_time_nano 的小时部分"},
            "event_weekday": {"raw_col": "start_time_nano", "logic": "取 start_time_nano 的星期几(0=周一)"},
            "is_weekend": {"raw_col": "start_time_nano", "logic": "判断 event_weekday 是否为周末(5,6)"},
            "page_root": {"raw_col": "span_name", "logic": "取 span_name 下划线分隔的第1段"},
            "page": {"raw_col": "span_name", "logic": "取 span_name 下划线分隔的前2段"},
            "action": {"raw_col": "span_name", "logic": "取 span_name 下划线分隔的最后1段"},
            "is_click": {"raw_col": "span_name", "logic": "判断 span_name 最后一段是否包含 click"},
            "duration_sec": {"raw_col": "start_time_nano, end_time_nano", "logic": "end_time_nano - start_time_nano 的秒数"},
        }
        self.raw_column_map.update(computed_map)

        # Register in DuckDB
        self.con.execute("DROP TABLE IF EXISTS events")
        self.con.register("events", df)
        self.df = df

        # Build metadata
        valid = df[df["start_time"].notna()]
        self.meta = {
            "file": os.path.basename(data_file),
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "total_users": int(df["reduser_id"].nunique()) if "reduser_id" in df.columns else 0,
            "total_devices": int(df["device_id"].nunique()) if "device_id" in df.columns else 0,
            "event_types": int(df["event_name"].nunique()) if "event_name" in df.columns else 0,
            "date_range": [
                str(valid["event_date"].min()),
                str(valid["event_date"].max()),
            ] if len(valid) > 0 else [],
            "columns": list(df.columns),
        }
        print(f"[DataLayer] {self.meta['total_rows']:,} events, {self.meta['total_users']} users, "
              f"{self.meta['date_range']}")
        return self.meta

    def execute(self, sql: str) -> list[dict]:
        """Execute SQL and return list of dicts."""
        result = self.con.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def get_schema_info(self) -> list[dict]:
        """Return column info for the events table."""
        if self.df is None:
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


# Singleton
_data_manager: DataManager | None = None

def get_data_manager() -> DataManager:
    global _data_manager
    if _data_manager is None:
        base = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base, "..", "data", "rednote")
        _data_manager = DataManager(data_dir)
        _data_manager.load()
    return _data_manager
