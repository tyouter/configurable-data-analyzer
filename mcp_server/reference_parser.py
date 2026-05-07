# -*- coding: utf-8 -*-
import os
import re
import json
import pandas as pd
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from mcp_server.project_model import FileClassification, ReferenceContent
from mcp_server.file_classifier import _detect_encoding
from mcp_server import llm_client

MAX_ITERATIONS = 3
PASS_THRESHOLD = 0.85

EXTRACT_PROMPT = """你是资深数据分析师，正在从参考文档中提取 KPI 指标定义。

## 文档内容
{text}

## 原始数据文件的 Schema
{schema_context}

## 严格规则
1. 提取文档中 **所有** 指标，不要遗漏
2. 每个指标必须有明确的 name、formula、description
3. formula 必须是可以直接映射到原始数据列的计算表达式（SQL 或数学公式）
4. formula 中的字段名必须与 Schema 中的列名完全对应
5. 如果文档中的指标定义不完整，请根据上下文补充合理的公式，并在 description 中标注"[推断]"
6. 主动检测指标定义中的矛盾和不合理之处，在 contradictions 字段中报告

## 输出格式（JSON，不要 markdown 代码块）
{{"kpi_definitions": [{{"name": "指标名称", "formula": "SQL/数学公式", "description": "口径说明", "params": ["用到的列名列表"], "inferred": false}}], "contradictions": ["发现的矛盾点"], "analysis_goals": ["分析目标"]}}"""

REFINE_PROMPT = """你是资深数据分析师。上一次提取的指标经过自动化验证，发现以下问题：

## 验证失败项
{validation_errors}

## 上一次提取结果
{previous_result}

## 原始文档内容
{text}

## 原始数据文件的 Schema
{schema_context}

## 修正要求
请根据验证错误修正指标定义。确保：
1. 所有之前遗漏的指标都已补充
2. formula 中的列名与 Schema 完全对应
3. 消除所有逻辑矛盾
4. 每个指标的计算公式在统计学上合理

## 输出格式（JSON，不要 markdown 代码块）
{{"kpi_definitions": [{{"name": "指标名称", "formula": "SQL/数学公式", "description": "口径说明", "params": ["用到的列名列表"], "inferred": false}}], "contradictions": ["发现的矛盾点"], "analysis_goals": ["分析目标"]}}"""

DICT_PARSE_PROMPT = """你是数据分析专家。请从以下数据字典文档中提取所有字段定义。

文档内容：
{text}

请以JSON格式返回（不要markdown代码块）：
{{"field_definitions": [{{"field": "字段名", "meaning": "含义", "enum_values": []}}], "analysis_goals": ["分析目标1"]}}"""

GENERIC_PARSE_PROMPT = """你是数据分析专家。请从以下参考文档中提取关键信息。

文档内容：
{text}

请以JSON格式返回（不要markdown代码块）：
{{"kpi_definitions": [{{"name": "指标名称", "formula": "计算公式", "description": "口径说明", "params": [], "inferred": false}}], "field_definitions": [{{"field": "字段名", "meaning": "含义", "enum_values": []}}], "contradictions": [], "analysis_goals": ["提取的分析目标"]}}"""


@dataclass
class ValidationIssue:
    category: str = ""
    severity: str = "error"
    message: str = ""
    kpi_name: str = ""
    suggestion: str = ""


@dataclass
class ValidationResult:
    score: float = 0.0
    passed: bool = False
    issues: list = field(default_factory=list)
    iteration: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if isinstance(i, dict) and i.get("severity") == "error" or isinstance(i, ValidationIssue) and i.severity == "error"]


@dataclass
class ExtractionLog:
    iteration: int = 0
    timestamp: str = ""
    action: str = ""
    score: float = 0.0
    status: str = ""
    details: str = ""


class KPIValidator:
    def __init__(self, raw_schema_columns: list[str] = None):
        self.raw_columns = set(raw_schema_columns or [])

    def validate(self, kpi_defs: list[dict], source_text: str = "") -> ValidationResult:
        issues = []

        if not kpi_defs:
            issues.append(ValidationIssue(
                category="completeness", severity="error",
                message="未提取到任何指标定义", suggestion="检查文档是否包含KPI指标",
            ))
            return ValidationResult(score=0.0, passed=False, issues=issues)

        expected_count = self._count_expected_kpis(source_text)
        if expected_count > 0 and len(kpi_defs) < expected_count:
            issues.append(ValidationIssue(
                category="completeness", severity="error",
                message=f"指标数量不完整：文档中包含 {expected_count} 个指标，仅提取 {len(kpi_defs)} 个",
                kpi_name="", suggestion="重新检查文档，补充遗漏的指标",
            ))

        for kpi in kpi_defs:
            name = kpi.get("name", "")
            formula = kpi.get("formula", "")
            desc = kpi.get("description", "")
            params = kpi.get("params", [])

            if not name:
                issues.append(ValidationIssue(
                    category="structure", severity="error",
                    message="存在无名称的指标", suggestion="补充指标名称",
                ))

            if not formula:
                issues.append(ValidationIssue(
                    category="structure", severity="error",
                    message=f"指标 '{name}' 缺少计算公式",
                    kpi_name=name, suggestion="补充计算公式",
                ))

            if formula and self.raw_columns:
                formula_cols = self._extract_columns_from_formula(formula)
                unmatched = [c for c in formula_cols if c not in self.raw_columns]
                if unmatched:
                    issues.append(ValidationIssue(
                        category="mapping", severity="error",
                        message=f"指标 '{name}' 公式引用了不存在的列: {unmatched}",
                        kpi_name=name,
                        suggestion=f"可用列: {sorted(self.raw_columns)}",
                    ))

            if formula and not desc:
                issues.append(ValidationIssue(
                    category="structure", severity="warning",
                    message=f"指标 '{name}' 缺少口径说明",
                    kpi_name=name, suggestion="补充口径说明",
                ))

            if formula:
                stat_issues = self._check_statistical_validity(name, formula, desc)
                issues.extend(stat_issues)

        contradiction_names = set()
        for i, kpi_a in enumerate(kpi_defs):
            for kpi_b in kpi_defs[i + 1:]:
                if kpi_a.get("name", "") == kpi_b.get("name", ""):
                    issues.append(ValidationIssue(
                        category="contradiction", severity="error",
                        message=f"重复指标名称: '{kpi_a['name']}'",
                        kpi_name=kpi_a["name"], suggestion="合并或去重",
                    ))
                    contradiction_names.add(kpi_a["name"])

                if (kpi_a.get("formula", "") and kpi_b.get("formula", "")
                        and kpi_a.get("name", "") != kpi_b.get("name", "")
                        and kpi_a["formula"].strip() == kpi_b["formula"].strip()):
                    issues.append(ValidationIssue(
                        category="contradiction", severity="warning",
                        message=f"指标 '{kpi_a['name']}' 和 '{kpi_b['name']}' 公式完全相同",
                        suggestion="检查是否为同一指标的不同表述",
                    ))

        for kpi in kpi_defs:
            if kpi.get("contradictions"):
                for c in kpi["contradictions"]:
                    issues.append(ValidationIssue(
                        category="contradiction", severity="warning",
                        message=f"LLM检测到矛盾: {c}",
                        kpi_name=kpi.get("name", ""),
                    ))

        score = self._compute_score(issues, len(kpi_defs), expected_count)
        passed = score >= PASS_THRESHOLD and not any(
            isinstance(i, ValidationIssue) and i.severity == "error" and i.category == "completeness"
            for i in issues
        )

        return ValidationResult(score=score, passed=passed, issues=issues)

    def _count_expected_kpis(self, text: str) -> int:
        if not text:
            return 0

        indicators = [
            r'(?:指标|KPI|度量|metric)\s*(?:名称|名|列表)?\s*[:：]?\s*\n',
            r'^\s*\d+[.、)]\s*.+',
        ]

        rows = [l for l in text.split("\n") if l.strip() and not l.strip().startswith(("指标", "KPI", "#", "-", "*", "名"))]

        if len(rows) <= 1:
            return 0

        kpi_keywords = {"DAU", "ARPU", "GMV", "CTR", "LTV", "ROI", "PV", "UV", "转化率", "留存率",
                        "点击率", "完成率", "增长率", "占比", "占比", "均值", "中位数", "百分位"}
        kpi_rows = sum(1 for r in rows if any(kw in r for kw in kpi_keywords))

        return max(kpi_rows, 0)

    def _extract_columns_from_formula(self, formula: str) -> list[str]:
        cols = re.findall(r'[a-zA-Z_]\w*', formula)
        sql_keywords = {"SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "HAVING", "LIMIT",
                        "COUNT", "SUM", "AVG", "MAX", "MIN", "DISTINCT", "CAST", "AS", "AND",
                        "OR", "NOT", "IN", "IS", "NULL", "JOIN", "ON", "LEFT", "RIGHT", "INNER",
                        "BETWEEN", "LIKE", "CASE", "WHEN", "THEN", "ELSE", "END", "OVER",
                        "PARTITION", "WITH", "DOUBLE", "FLOAT", "INT", "INTEGER", "STRING",
                        "DESCRIBE", "SHOW", "TABLES", "IF", "COALESCE", "ROUND", "ABS", "CEIL",
                        "FLOOR", "CONCAT", "SUBSTR", "UPPER", "LOWER", "TRIM", "LENGTH", "TRUE", "FALSE"}
        return [c for c in cols if c.upper() not in sql_keywords and len(c) > 1]

    def _check_statistical_validity(self, name: str, formula: str, desc: str) -> list[ValidationIssue]:
        issues = []
        f = formula.upper()

        if "AVG(" in f or "MEAN" in f:
            if "OUTLIER" not in f and "TRIM" not in f:
                pass

        if "RATE" in name.upper() or "率" in name:
            has_division = "/" in formula or "CAST" in f
            if not has_division and "COUNT" not in f:
                issues.append(ValidationIssue(
                    category="statistical", severity="warning",
                    message=f"指标 '{name}' 名称含'率'但公式可能缺少除法运算",
                    kpi_name=name, suggestion="确认分子/分母定义",
                ))

        if "%" in formula or "100" in formula:
            if "/" not in formula and "RATE" not in f:
                issues.append(ValidationIssue(
                    category="statistical", severity="warning",
                    message=f"指标 '{name}' 含百分号但公式可能缺少比率计算",
                    kpi_name=name, suggestion="确认百分比计算逻辑",
                ))

        if "COUNT(DISTINCT" in f:
            pass

        if "COUNT(" in f and "DISTINCT" not in f:
            issues.append(ValidationIssue(
                category="statistical", severity="warning",
                message=f"指标 '{name}' 使用COUNT但未加DISTINCT，可能存在重复计数",
                kpi_name=name, suggestion="确认是否需要COUNT(DISTINCT ...)",
            ))

        return issues

    def _compute_score(self, issues: list[ValidationIssue], kpi_count: int, expected_count: int) -> float:
        if not kpi_count:
            return 0.0

        error_count = sum(1 for i in issues if isinstance(i, ValidationIssue) and i.severity == "error")
        warning_count = sum(1 for i in issues if isinstance(i, ValidationIssue) and i.severity == "warning")

        completeness_penalty = 0.0
        if expected_count > 0 and kpi_count < expected_count:
            completeness_penalty = 0.3 * (1 - kpi_count / expected_count)

        error_penalty = min(error_count * 0.15, 0.6)
        warning_penalty = min(warning_count * 0.05, 0.2)

        score = max(0.0, 1.0 - completeness_penalty - error_penalty - warning_penalty)
        return round(score, 4)


def _call_llm(prompt: str, system_msg: str = "You are a data analyst expert. Respond with valid JSON only.") -> str:
    return llm_client.call_llm(
        prompt=prompt,
        system_msg=system_msg,
        max_tokens=4096,
        temperature=0.2,
        timeout=45,
        strip_markdown=False,
    )


def _extract_text(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()

    if ext in (".csv", ".tsv"):
        enc = _detect_encoding(filepath)
        sep = "\t" if ext == ".tsv" else ","
        try:
            df = pd.read_csv(filepath, encoding=enc, sep=sep)
            return df.to_string(index=False, max_colwidth=50)
        except Exception:
            with open(filepath, "r", encoding=enc, errors="replace") as f:
                return f.read()

    if ext in (".xlsx", ".xls"):
        try:
            from mcp_server.excel_utils import read_excel_filled
            return read_excel_filled(filepath, max_colwidth=80)
        except Exception:
            try:
                xls = pd.ExcelFile(filepath)
                all_text = []
                for sheet in xls.sheet_names:
                    df = pd.read_excel(filepath, sheet_name=sheet)
                    text = df.to_string(index=False, max_colwidth=80)
                    if text.strip():
                        all_text.append(f"=== Sheet: {sheet} ===\n{text}")
                return "\n\n".join(all_text)
            except Exception:
                return ""

    if ext in (".txt", ".md"):
        enc = _detect_encoding(filepath)
        with open(filepath, "r", encoding=enc, errors="replace") as f:
            return f.read()

    return ""


def _parse_json_response(content: str) -> dict:
    content = re.sub(r"^```(?:json)?\s*\n?", "", content)
    content = re.sub(r"\n?```\s*$", "", content)
    return json.loads(content)


def _format_validation_errors(issues: list[ValidationIssue]) -> str:
    lines = []
    for i, issue in enumerate(issues):
        if isinstance(issue, ValidationIssue):
            lines.append(f"{i + 1}. [{issue.severity.upper()}] {issue.message}")
            if issue.suggestion:
                lines.append(f"   → 建议: {issue.suggestion}")
        elif isinstance(issue, dict):
            lines.append(f"{i + 1}. [{issue.get('severity', 'ERROR').upper()}] {issue.get('message', '')}")
    return "\n".join(lines)


class ReferenceParser:
    def __init__(self, llm_available: bool = True, raw_schema_columns: list[str] = None):
        self.llm_available = llm_available and llm_client.is_available()
        self.raw_schema_columns = raw_schema_columns or []
        self.extraction_log: list[ExtractionLog] = []

    def parse_all(self, classifications: list[FileClassification]) -> list[ReferenceContent]:
        results = []
        for fc in classifications:
            if fc.is_reference():
                results.append(self.parse_one(fc))
        return results

    def parse_one(self, classification: FileClassification) -> ReferenceContent:
        filepath = classification.filepath
        if not os.path.exists(filepath):
            return ReferenceContent(filename=classification.filename, category=classification.category)

        text = _extract_text(filepath)
        if not text.strip():
            return ReferenceContent(filename=classification.filename, category=classification.category)

        if self.llm_available:
            try:
                result = self._autoresearch_parse(text, classification.category, classification.filename)
                return result
            except Exception as e:
                print(f"[ReferenceParser] AutoResearch parse failed for {classification.filename}: {e}")
                print("[ReferenceParser] Falling back to rules")

        return self._parse_with_rules(text, classification.category, classification.filename)

    def _autoresearch_parse(self, text: str, category: str, filename: str) -> ReferenceContent:
        self.extraction_log = []
        schema_ctx = ", ".join(self.raw_schema_columns) if self.raw_schema_columns else "(未提供)"
        truncated = text[:4000]
        validator = KPIValidator(raw_schema_columns=self.raw_schema_columns)

        best_result = None
        best_score = 0.0
        previous_result_str = ""

        for iteration in range(1, MAX_ITERATIONS + 1):
            if iteration == 1:
                if category == "reference_kpi":
                    prompt = EXTRACT_PROMPT.format(text=truncated, schema_context=schema_ctx)
                elif category == "reference_dict":
                    prompt = DICT_PARSE_PROMPT.format(text=truncated)
                else:
                    prompt = GENERIC_PARSE_PROMPT.format(text=truncated)
            else:
                prompt = REFINE_PROMPT.format(
                    validation_errors=previous_result_str,
                    previous_result=json.dumps(best_result or {}, ensure_ascii=False, indent=2)[:2000],
                    text=truncated,
                    schema_context=schema_ctx,
                )

            raw = _call_llm(prompt)
            parsed = _parse_json_response(raw)

            kpi_defs = parsed.get("kpi_definitions", [])
            field_defs = parsed.get("field_definitions", [])
            goals = parsed.get("analysis_goals", [])

            if category == "reference_kpi" and kpi_defs:
                validation = validator.validate(kpi_defs, source_text=text)
            elif category == "reference_dict" and field_defs:
                validation = ValidationResult(score=1.0, passed=True, issues=[])
            else:
                validation = ValidationResult(score=0.8, passed=True, issues=[])

            log_entry = ExtractionLog(
                iteration=iteration,
                timestamp=datetime.now().isoformat(),
                action="extract" if iteration == 1 else "refine",
                score=validation.score,
                status="KEEP" if validation.passed else "DISCARD",
                details=f"kpi_count={len(kpi_defs)}, issues={len(validation.issues)}",
            )
            self.extraction_log.append(log_entry)

            if validation.score > best_score:
                best_score = validation.score
                best_result = {
                    "kpi_definitions": kpi_defs,
                    "field_definitions": field_defs,
                    "analysis_goals": goals,
                    "validation_score": validation.score,
                    "validation_issues": [
                        {"category": i.category, "severity": i.severity, "message": i.message}
                        if isinstance(i, ValidationIssue) else i
                        for i in validation.issues
                    ],
                }

            if validation.passed:
                log_entry.status = "KEEP (PASSED)"
                break

            previous_result_str = _format_validation_errors(validation.issues)

        if best_result is None:
            return ReferenceContent(filename=filename, category=category, raw_text=text[:2000])

        return ReferenceContent(
            filename=filename,
            category=category,
            raw_text=text[:2000],
            kpi_definitions=best_result.get("kpi_definitions", []),
            field_definitions=best_result.get("field_definitions", []),
            analysis_goals=best_result.get("analysis_goals", []),
        )

    def _parse_with_rules(self, text: str, category: str, filename: str) -> ReferenceContent:
        kpi_defs = []
        field_defs = []
        goals = []

        if category == "reference_kpi":
            kpi_defs = self._extract_kpi_rules(text)
        elif category == "reference_dict":
            field_defs = self._extract_dict_rules(text)
        else:
            kpi_defs = self._extract_kpi_rules(text)
            field_defs = self._extract_dict_rules(text)

        goals = self._extract_goals(text)

        return ReferenceContent(
            filename=filename,
            category=category,
            raw_text=text[:2000],
            kpi_definitions=kpi_defs,
            field_definitions=field_defs,
            analysis_goals=goals,
        )

    def _extract_kpi_rules(self, text: str) -> list[dict]:
        results = []
        lines = text.strip().split("\n")
        header_idx = -1
        title_col = -1
        desc_col = -1
        event_col = -1

        for idx, line in enumerate(lines):
            parts = re.split(r"[|\t,，]+|\s{2,}", line.strip())
            parts = [p.strip() for p in parts if p.strip()]
            for ci, p in enumerate(parts):
                pl = p.lower()
                if pl in ("指标标题", "指标名称", "指标", "kpi", "metric"):
                    header_idx = idx
                    title_col = ci
                if pl in ("描述", "口径说明", "口径", "description", "计算公式"):
                    desc_col = ci
                if pl in ("埋点事件", "事件", "event"):
                    event_col = ci

        if header_idx >= 0 and title_col >= 0:
            for line in lines[header_idx + 1:]:
                parts = re.split(r"[|\t,，]+|\s{2,}", line.strip())
                parts = [p.strip() for p in parts if p.strip()]
                if len(parts) > title_col:
                    title = parts[title_col]
                    if title and title.lower() not in ("nan", "none", ""):
                        desc = parts[desc_col] if desc_col >= 0 and desc_col < len(parts) else ""
                        event = parts[event_col] if event_col >= 0 and event_col < len(parts) else ""
                        desc_text = str(desc)[:200] if desc and str(desc).lower() != "nan" else ""
                        if event and str(event).lower() not in ("nan", "none"):
                            desc_text = f"[事件: {event}] {desc_text}" if desc_text else f"[事件: {event}]"
                        results.append({
                            "name": title,
                            "formula": "",
                            "description": desc_text,
                        })
            if results:
                return results

        for line in lines:
            parts = re.split(r"[|\t,，]+|\s{2,}", line.strip())
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                name = parts[0]
                if any(kw in name for kw in ["指标", "KPI", "DAU", "ARPU", "GMV", "CTR", "转化率", "留存率", "PV", "UV", "活跃率", "留存率", "使用率", "路书"]):
                    formula = parts[1] if len(parts) > 1 else ""
                    desc = parts[2] if len(parts) > 2 else ""
                    results.append({
                        "name": name,
                        "formula": formula,
                        "description": desc,
                    })
        return results

    def _extract_dict_rules(self, text: str) -> list[dict]:
        results = []
        lines = text.strip().split("\n")
        for line in lines:
            parts = re.split(r"[|\t,，]+|\s{2,}", line.strip())
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                field_name = parts[0]
                if re.match(r'^[a-zA-Z_]\w*$', field_name):
                    meaning = parts[1] if len(parts) > 1 else ""
                    results.append({
                        "field": field_name,
                        "meaning": meaning,
                        "enum_values": [],
                    })
        return results

    def _extract_goals(self, text: str) -> list[str]:
        goals = []
        goal_patterns = [
            r'(?:分析目标|目标|需求)[:：]\s*(.+)',
            r'(?:需要|希望|要求)(?:分析|统计|查看|了解)(.+)',
        ]
        for pattern in goal_patterns:
            matches = re.findall(pattern, text)
            goals.extend(m.strip() for m in matches)
        return goals[:10]

    def get_extraction_log(self) -> list[dict]:
        return [
            {
                "iteration": log.iteration,
                "timestamp": log.timestamp,
                "action": log.action,
                "score": log.score,
                "status": log.status,
                "details": log.details,
            }
            for log in self.extraction_log
        ]
