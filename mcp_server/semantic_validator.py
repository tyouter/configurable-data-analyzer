# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.project_model import ProjectDataManager


class SemanticValidator:
    def __init__(self, dm: ProjectDataManager, semantic_layer: dict):
        self.dm = dm
        self.semantic_layer = semantic_layer
        self.metrics = semantic_layer.get("metrics", {})
        self.events = semantic_layer.get("event_definitions", {})

    def validate_all(self) -> dict:
        sql_result = self.validate_sql_executability()
        quality_result = self.validate_data_quality(sql_result)
        coverage_result = self.validate_kpi_coverage()

        results = {
            "sql_executability": sql_result,
            "data_quality": quality_result,
            "kpi_coverage": coverage_result,
        }
        results["summary"] = self._build_summary(results)
        return results

    def validate_sql_executability(self) -> dict:
        pass_count = 0
        fail_count = 0
        details = {}

        for name, mdef in self.metrics.items():
            sql = mdef.get("sql", "")
            if not sql:
                details[name] = {"status": "fail", "error": "no SQL defined"}
                fail_count += 1
                continue

            try:
                test_sql = f"SELECT {sql} AS val FROM events LIMIT 1"
                self.dm.execute(test_sql)
                details[name] = {"status": "pass"}
                pass_count += 1
            except Exception as e:
                err_msg = str(e)
                if len(err_msg) > 200:
                    err_msg = err_msg[:200] + "..."
                details[name] = {"status": "fail", "error": err_msg}
                fail_count += 1

        return {
            "total": len(self.metrics),
            "pass": pass_count,
            "fail": fail_count,
            "details": details,
        }

    def validate_data_quality(self, sql_result: dict = None) -> dict:
        if sql_result is None:
            sql_result = self.validate_sql_executability()

        pass_count = 0
        warning_count = 0
        details = {}

        for name, mdef in self.metrics.items():
            sql_detail = sql_result.get("details", {}).get(name, {})
            if sql_detail.get("status") != "pass":
                details[name] = {"status": "skipped", "reason": "SQL execution failed"}
                continue

            sql = mdef.get("sql", "")
            metric_type = mdef.get("metric_type", "")

            try:
                rows = self.dm.execute(f"SELECT {sql} AS val FROM events LIMIT 1")
                if not rows:
                    details[name] = {"status": "warning", "reason": "no_result", "value": None}
                    warning_count += 1
                    continue

                val = rows[0].get("val")

                if val is None:
                    details[name] = {"status": "warning", "reason": "null_value", "value": None}
                    warning_count += 1
                elif val == 0 and metric_type in ("count", "rate"):
                    details[name] = {"status": "warning", "reason": "zero_data", "value": 0}
                    warning_count += 1
                else:
                    details[name] = {"status": "pass", "value": val}
                    pass_count += 1
            except Exception as e:
                details[name] = {"status": "warning", "reason": f"query_error: {str(e)[:100]}"}
                warning_count += 1

        return {
            "total": len(self.metrics),
            "pass": pass_count,
            "warning": warning_count,
            "skipped": len(self.metrics) - pass_count - warning_count,
            "details": details,
        }

    def validate_kpi_coverage(self) -> dict:
        audit_report = self.dm.project.meta.get("audit_report", {})
        file_classifications = audit_report.get("file_classifications", [])

        kpi_definitions = []
        for fc in file_classifications:
            if fc.get("category", "").startswith("reference"):
                kpi_defs = fc.get("kpi_definitions", [])
                for kd in kpi_defs:
                    name = kd.get("name", kd.get("kpi_name", ""))
                    if name:
                        kpi_definitions.append(name)

        if not kpi_definitions:
            return {
                "total_kpis": 0,
                "covered": 0,
                "coverage_rate": 1.0,
                "uncovered": [],
                "note": "No KPI definitions found in reference documents",
            }

        metric_names = set(self.metrics.keys())
        metric_keywords = {}
        for m_name, m_def in self.metrics.items():
            kw = m_def.get("keywords", "")
            biz = m_def.get("business_name", "")
            metric_keywords[m_name] = (kw.lower() + " " + biz.lower()).split()

        covered = []
        uncovered = []

        for kpi in kpi_definitions:
            kpi_lower = kpi.lower()
            found = False

            for m_name in metric_names:
                if m_name.lower() == kpi_lower:
                    found = True
                    break

            if not found:
                for m_name, keywords in metric_keywords.items():
                    for kw in keywords:
                        if kw and kw in kpi_lower:
                            found = True
                            break
                    if found:
                        break

            if found:
                covered.append(kpi)
            else:
                uncovered.append(kpi)

        total = len(kpi_definitions)
        rate = len(covered) / total if total > 0 else 1.0

        return {
            "total_kpis": total,
            "covered": len(covered),
            "coverage_rate": round(rate, 3),
            "uncovered": uncovered,
        }

    def _build_summary(self, results: dict) -> dict:
        sql = results.get("sql_executability", {})
        quality = results.get("data_quality", {})
        coverage = results.get("kpi_coverage", {})

        fail_count = sql.get("fail", 0)
        warning_count = quality.get("warning", 0)
        pass_count = quality.get("pass", 0)

        if fail_count > 0:
            overall = "fail"
        elif warning_count > 0:
            overall = "warning"
        else:
            overall = "pass"

        return {
            "overall_status": overall,
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "coverage_rate": coverage.get("coverage_rate", 1.0),
        }
