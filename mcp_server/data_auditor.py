# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
from typing import Optional

from mcp_server.project_model import FileClassification, FileSchemaInfo
from mcp_server.file_classifier import _detect_encoding


class DataAuditor:
    def audit_all(self, classifications: list[FileClassification]) -> list[FileSchemaInfo]:
        results = []
        for fc in classifications:
            if fc.is_raw_data():
                results.append(self.audit_one(fc))
        return results

    def audit_one(self, classification: FileClassification) -> FileSchemaInfo:
        filepath = classification.filepath
        if not os.path.exists(filepath):
            return FileSchemaInfo(
                filename=classification.filename,
                quality_score=0.0,
                quality_issues=[f"文件不存在: {filepath}"],
            )

        try:
            schema = self._extract_full_schema(filepath, classification.format)
        except Exception as e:
            return FileSchemaInfo(
                filename=classification.filename,
                quality_score=0.0,
                quality_issues=[f"Schema提取失败: {str(e)}"],
            )

        quality_score, quality_issues = self._compute_quality_score(
            schema["columns"], schema["total_rows"]
        )

        numeric_cols = [
            c["name"] for c in schema["columns"]
            if c.get("is_numeric")
        ]
        date_cols = [
            c["name"] for c in schema["columns"]
            if c.get("is_date")
        ]
        category_cols = [
            c["name"] for c in schema["columns"]
            if c.get("is_category")
        ]

        return FileSchemaInfo(
            filename=classification.filename,
            columns=schema["columns"],
            row_count=schema["total_rows"],
            numeric_columns=numeric_cols,
            date_columns=date_cols,
            category_columns=category_cols,
            quality_score=quality_score,
            quality_issues=quality_issues,
        )

    def _extract_full_schema(self, filepath: str, fmt: str) -> dict:
        ext = os.path.splitext(filepath)[1].lower()

        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(filepath)
        elif ext == ".parquet":
            df = pd.read_parquet(filepath)
        elif ext in (".csv", ".tsv"):
            enc = _detect_encoding(filepath)
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(filepath, encoding=enc, sep=sep)
        else:
            enc = _detect_encoding(filepath)
            df = pd.read_csv(filepath, encoding=enc)

        total_rows = len(df)
        columns = []

        for col_name in df.columns:
            series = df[col_name]
            null_count = int(series.isnull().sum())
            null_rate = null_count / max(total_rows, 1)
            unique_count = series.nunique()
            unique_rate = unique_count / max(total_rows, 1)

            sample_values = series.dropna().head(5).tolist()
            sample_str = [str(v) for v in sample_values]

            dtype_str = str(series.dtype)
            is_numeric = pd.api.types.is_numeric_dtype(series)
            is_date = pd.api.types.is_datetime64_any_dtype(series)

            is_category = False
            if not is_numeric and not is_date:
                if 0 < unique_count < 20 and unique_rate < 0.5:
                    is_category = True

            col_info = {
                "name": col_name,
                "dtype": dtype_str,
                "null_count": null_count,
                "null_rate": round(null_rate, 4),
                "unique_count": unique_count,
                "unique_rate": round(unique_rate, 4),
                "sample_values": sample_str,
                "is_numeric": is_numeric,
                "is_date": is_date,
                "is_category": is_category,
            }
            columns.append(col_info)

        return {
            "columns": columns,
            "total_rows": total_rows,
        }

    def _compute_quality_score(
        self, columns: list[dict], total_rows: int
    ) -> tuple[float, list[str]]:
        if not columns or total_rows == 0:
            return 0.0, ["空数据集"]

        issues = []
        null_scores = []
        type_scores = []
        unique_scores = []

        for col in columns:
            name = col["name"]
            null_rate = col.get("null_rate", 0)

            if null_rate > 0.5:
                issues.append(f"高空值率: {name} ({null_rate:.0%})")
                null_scores.append(0.0)
            elif null_rate > 0.2:
                issues.append(f"中空值率: {name} ({null_rate:.0%})")
                null_scores.append(0.5)
            else:
                null_scores.append(1.0)

            if col.get("is_numeric"):
                type_scores.append(1.0)
            elif col.get("is_date"):
                type_scores.append(1.0)
            else:
                type_scores.append(0.8)

            unique_rate = col.get("unique_rate", 0)
            if unique_rate >= 1.0 and not col.get("is_numeric"):
                issues.append(f"全唯一列可能是ID: {name}")
                unique_scores.append(0.5)
            else:
                unique_scores.append(1.0)

        avg_null = sum(null_scores) / len(null_scores)
        avg_type = sum(type_scores) / len(type_scores)
        avg_unique = sum(unique_scores) / len(unique_scores)

        quality_score = round(avg_null * 0.4 + avg_type * 0.3 + avg_unique * 0.3, 4)
        return quality_score, issues
