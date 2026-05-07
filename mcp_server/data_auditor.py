# -*- coding: utf-8 -*-
import os
import duckdb
from typing import Optional

from mcp_server.project_model import FileClassification, FileSchemaInfo
from mcp_server.file_classifier import _detect_encoding


_DUCKDB_EXCEL_LOADED = False


def _ensure_duckdb_excel(con: duckdb.DuckDBPyConnection):
    global _DUCKDB_EXCEL_LOADED
    if not _DUCKDB_EXCEL_LOADED:
        con.execute("INSTALL excel")
        con.execute("LOAD excel")
        _DUCKDB_EXCEL_LOADED = True


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
        con = duckdb.connect(":memory:")

        try:
            if ext in (".xlsx", ".xls"):
                _ensure_duckdb_excel(con)
                from mcp_server.excel_utils import prepare_xlsx
                effective_path, was_filled = prepare_xlsx(filepath)
                con.execute(
                    f"CREATE TABLE _audit AS SELECT * FROM read_xlsx('{effective_path}', all_varchar=true)"
                )
                if was_filled:
                    try:
                        os.unlink(effective_path)
                    except OSError:
                        pass
            elif ext == ".parquet":
                con.execute(
                    f"CREATE TABLE _audit AS SELECT * FROM read_parquet('{filepath}')"
                )
            elif ext in (".csv", ".tsv"):
                enc = _detect_encoding(filepath)
                sep = "\\t" if ext == ".tsv" else ","
                con.execute(
                    f"CREATE TABLE _audit AS SELECT * FROM read_csv('{filepath}', delim='{sep}', encoding='{enc}')"
                )
            else:
                enc = _detect_encoding(filepath)
                con.execute(
                    f"CREATE TABLE _audit AS SELECT * FROM read_csv('{filepath}', encoding='{enc}')"
                )
        except Exception:
            con.close()
            raise

        total_rows = con.execute("SELECT COUNT(*) FROM _audit").fetchone()[0]
        describe_rows = con.execute("DESCRIBE _audit").fetchall()

        columns = []
        for desc in describe_rows:
            col_name = desc[0]
            duckdb_type = desc[1].upper()

            null_count = con.execute(
                f'SELECT COUNT(*) FROM _audit WHERE "{col_name}" IS NULL'
            ).fetchone()[0]
            unique_count = con.execute(
                f'SELECT COUNT(DISTINCT "{col_name}") FROM _audit'
            ).fetchone()[0]

            null_rate = null_count / max(total_rows, 1)
            unique_rate = unique_count / max(total_rows, 1)

            sample_rows = con.execute(
                f'SELECT DISTINCT "{col_name}" FROM _audit WHERE "{col_name}" IS NOT NULL LIMIT 5'
            ).fetchall()
            sample_str = [str(v[0]) for v in sample_rows]

            is_numeric = any(
                t in duckdb_type
                for t in ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "NUMERIC", "SMALLINT", "TINYINT", "HUGEINT")
            )
            is_date = any(
                t in duckdb_type
                for t in ("TIMESTAMP", "DATE", "TIME", "INTERVAL")
            )

            if duckdb_type == "VARCHAR" and not is_numeric and not is_date:
                col_lower = col_name.lower()
                is_id_col = (
                    "id" in col_lower
                    or col_lower.endswith("_id")
                    or col_lower == "id"
                    or unique_rate > 0.8
                )

                if not is_id_col:
                    try:
                        numeric_check = con.execute(
                            f'SELECT COUNT(*) FROM _audit WHERE "{col_name}" IS NOT NULL AND TRY_CAST("{col_name}" AS DOUBLE) IS NOT NULL'
                        ).fetchone()[0]
                        non_null = total_rows - null_count
                        if non_null > 0 and numeric_check / non_null > 0.9:
                            is_numeric = True
                    except Exception:
                        pass

                if not is_numeric and not is_id_col:
                    try:
                        date_check = con.execute(
                            f'SELECT COUNT(*) FROM _audit WHERE "{col_name}" IS NOT NULL AND TRY_CAST("{col_name}" AS TIMESTAMP) IS NOT NULL'
                        ).fetchone()[0]
                        non_null = total_rows - null_count
                        if non_null > 0 and date_check / non_null > 0.9:
                            is_date = True
                    except Exception:
                        pass

            is_category = False
            if not is_numeric and not is_date:
                if 0 < unique_count < 20 and unique_rate < 0.5:
                    is_category = True

            col_info = {
                "name": col_name,
                "dtype": duckdb_type,
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

        con.close()
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

    def deep_audit(
        self,
        execute_fn,
        table_name: str,
        columns: list[dict],
        project_type: str = "",
    ) -> list[dict]:
        from mcp_server.data_skills import get_rules_for_type

        skills = get_rules_for_type(project_type)
        issues = []
        col_names = [c["name"] for c in columns]
        date_cols = [c["name"] for c in columns if c.get("is_date")]
        numeric_cols = [c["name"] for c in columns if c.get("is_numeric")]

        for skill in skills:
            for check in skill.get("checks", []):
                sql_template = check.get("sql_template")
                if not sql_template:
                    detect = check.get("detect", "")
                    if detect and "unique_rate" in detect:
                        for col in columns:
                            if col.get("unique_rate", 0) > 0.95 and not col.get("is_numeric"):
                                issues.append(self._format_issue(check, col["name"]))
                    continue

                if "{col}" in sql_template:
                    target_cols = numeric_cols if check.get("id") in ("negative_values",) else col_names
                    for col in target_cols:
                        sql = sql_template.replace("{table}", table_name)
                        all_cols_str = ', '.join(f'"{c}"' for c in col_names)
                        sql = sql.replace("{all_cols}", all_cols_str)
                        sql = sql.replace("{col}", col)
                        if "{date_col}" in sql:
                            sql = sql.replace("{date_col}", date_cols[0] if date_cols else "1")
                        if "{ts_col}" in sql:
                            sql = sql.replace("{ts_col}", date_cols[0] if date_cols else "1")
                        if "{val_col}" in sql:
                            sql = sql.replace("{val_col}", numeric_cols[0] if numeric_cols else "1")
                        try:
                            result = execute_fn(sql)
                            if result and len(result) > 0:
                                issues.append(self._format_issue(
                                    check,
                                    col_name=col,
                                    extra_data=result[:5],
                                    affected_count=len(result),
                                ))
                        except Exception:
                            pass
                else:
                    sql = self._render_sql(sql_template, table_name, col_names, date_cols, numeric_cols)
                    if not sql:
                        continue
                    try:
                        result = execute_fn(sql)
                        if result and len(result) > 0:
                            issues.append(self._format_issue(
                                check,
                                extra_data=result[:5],
                                affected_count=len(result),
                            ))
                    except Exception:
                        pass

            for rule in skill.get("business_rules", []):
                issues.append({
                    "type": "business_rule",
                    "severity": "info",
                    "message": rule,
                    "suggestion": "请在生成语义层时确保此规则被遵守。",
                })

        for dc in self._collect_derived_suggestions(skills, col_names, date_cols, numeric_cols):
            issues.append(dc)

        return issues

    def _render_sql(
        self,
        template: str,
        table_name: str,
        col_names: list[str],
        date_cols: list[str],
        numeric_cols: list[str],
    ) -> Optional[str]:
        if "{col}" in template and not numeric_cols:
            return None
        if "{date_col}" in template and not date_cols:
            return None
        if "{ts_col}" in template and not date_cols:
            return None
        if "{val_col}" in template and not numeric_cols:
            return None

        all_cols = ', '.join(f'"{c}"' for c in col_names)
        sql = template.replace("{table}", table_name)
        sql = sql.replace("{all_cols}", all_cols)

        if "{col}" in template:
            col = numeric_cols[0]
            sql = sql.replace("{col}", col)
        if "{date_col}" in template:
            sql = sql.replace("{date_col}", date_cols[0])
        if "{ts_col}" in template:
            sql = sql.replace("{ts_col}", date_cols[0])
        if "{val_col}" in template:
            sql = sql.replace("{val_col}", numeric_cols[0])

        return sql

    def _format_issue(
        self,
        check: dict,
        col_name: str = "",
        extra_data: list = None,
        affected_count: int = 0,
    ) -> dict:
        issue = {
            "type": "data_quality",
            "check_id": check["id"],
            "severity": check["severity"],
            "name": check["name"],
            "description": check["description"],
            "suggestion": check.get("suggestion", ""),
        }
        if col_name:
            issue["column"] = col_name
        if affected_count:
            issue["affected_count"] = affected_count
        if extra_data:
            issue["sample_data"] = extra_data
        return issue

    def _collect_derived_suggestions(
        self,
        skills: list[dict],
        col_names: list[str],
        date_cols: list[str],
        numeric_cols: list[str],
    ) -> list[dict]:
        suggestions = []
        for skill in skills:
            for dc in skill.get("derived_columns", []):
                suggestions.append({
                    "type": "derived_column_suggestion",
                    "severity": "info",
                    "name": dc["name"],
                    "description": dc["description"],
                    "example": dc.get("example", ""),
                    "suggestion": f"建议添加派生列 {dc['name']}：{dc.get('example', dc['description'])}",
                })
        return suggestions
