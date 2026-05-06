# -*- coding: utf-8 -*-
import os
import re
import json
import pandas as pd
from typing import Optional

from mcp_server.project_model import FileClassification
from mcp_server import llm_client

CLASSIFICATION_PROMPT = """你是一个数据分析专家。请判断以下文件是「原始数据文件」还是「参考文档」。

文件名：{filename}
列名：{columns}
行数：{row_count}
前5行内容：
{sample}

参考文档类型包括：
- KPI定义文档：包含指标名称、计算公式、口径说明
- 数据字典：包含字段定义、枚举值说明
- 需求文档：包含分析目标、Dashboard规划

请以JSON格式返回（不要markdown代码块）：
{{"category": "raw_data" | "reference_kpi" | "reference_dict" | "reference_req" | "reference_other", "confidence": 0.0-1.0, "reason": "判断理由"}}"""

_DATA_EXTENSIONS = {".csv", ".xlsx", ".xls", ".parquet", ".tsv"}
_TEXT_EXTENSIONS = {".md", ".txt", ".doc", ".docx", ".pdf"}
_KPI_KEYWORDS = ["kpi", "指标", "口径", "metric"]
_DICT_KEYWORDS = ["字典", "dict", "field", "字段定义", "数据说明", "埋点", "stracture", "structure", "架构", "structure", "tracking", "schema"]
_REQ_KEYWORDS = ["需求", "requirement", "prd", "规划", "目标"]


def _call_llm(prompt: str) -> str:
    return llm_client.call_llm(
        prompt=prompt,
        system_msg="You are a data classification expert. Respond with valid JSON only.",
        max_tokens=256,
        temperature=0.1,
        timeout=30,
        strip_markdown=False,
    )


def _detect_encoding(filepath: str) -> str:
    try:
        import chardet
        with open(filepath, "rb") as f:
            raw = f.read(8192)
        result = chardet.detect(raw)
        return result.get("encoding", "utf-8") or "utf-8"
    except ImportError:
        pass

    for enc in ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


def _read_data_sample(filepath: str, n_rows: int = 5) -> Optional[dict]:
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(filepath, nrows=n_rows)
        elif ext == ".parquet":
            df = pd.read_parquet(filepath)
            if len(df) > n_rows:
                df = df.head(n_rows)
        elif ext in (".csv", ".tsv"):
            enc = _detect_encoding(filepath)
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(filepath, encoding=enc, sep=sep, nrows=n_rows)
        else:
            return None

        sample_text = df.head(n_rows).to_string(index=False, max_colwidth=30)

        total_row_path = filepath
        try:
            if ext in (".xlsx", ".xls"):
                total_df = pd.read_excel(filepath)
            elif ext == ".parquet":
                total_df = pd.read_parquet(filepath)
            else:
                total_df = pd.read_csv(filepath, encoding=_detect_encoding(filepath), sep=sep if ext == ".tsv" else ",")
            total_rows = len(total_df)
            del total_df
        except Exception:
            total_rows = len(df)

        return {
            "columns": list(df.columns),
            "sample_text": sample_text,
            "row_count": total_rows,
            "format": ext.lstrip("."),
        }
    except Exception:
        return None


class FileClassifier:
    def __init__(self, llm_available: bool = True):
        self.llm_available = llm_available and llm_client.is_available()

    def classify_all(self, file_paths: list[str]) -> list[FileClassification]:
        results = []
        for fp in file_paths:
            if os.path.isdir(fp):
                continue
            results.append(self.classify_one(fp))
        return results

    def classify_one(self, filepath: str) -> FileClassification:
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()

        info = self._extract_file_info(filepath)
        sample = _read_data_sample(filepath)

        columns = sample["columns"] if sample else []
        row_count = sample["row_count"] if sample else 0
        sample_text = sample["sample_text"] if sample else ""
        fmt = sample["format"] if sample else "other"
        enc = "utf-8"

        if ext in (".csv", ".tsv"):
            enc = _detect_encoding(filepath)

        if self.llm_available and (columns or sample_text):
            try:
                result = self._classify_with_llm(filename, columns, row_count, sample_text)
                return FileClassification(
                    filename=filename,
                    filepath=filepath,
                    category=result["category"],
                    confidence=result["confidence"],
                    reason=result["reason"],
                    columns=columns,
                    row_count=row_count,
                    encoding=enc,
                    format=fmt,
                )
            except Exception as e:
                print(f"[FileClassifier] LLM failed for {filename}: {e}, falling back to rules")

        return self._classify_with_rules(filename, filepath, columns, row_count, sample_text, enc, fmt)

    def _extract_file_info(self, filepath: str) -> dict:
        try:
            size = os.path.getsize(filepath)
        except OSError:
            size = 0
        return {"size": size}

    def _classify_with_llm(self, filename: str, columns: list, row_count: int, sample_text: str) -> dict:
        prompt = CLASSIFICATION_PROMPT.format(
            filename=filename,
            columns=", ".join(columns) if columns else "(无法读取列名)",
            row_count=row_count,
            sample=sample_text[:1500] if sample_text else "(无样本数据)",
        )

        content = _call_llm(prompt)

        content = re.sub(r"^```(?:json)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)

        result = json.loads(content)

        valid_categories = {"raw_data", "reference_kpi", "reference_dict", "reference_req", "reference_other"}
        if result.get("category") not in valid_categories:
            result["category"] = "unknown"
        if not isinstance(result.get("confidence"), (int, float)):
            result["confidence"] = 0.5
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
        if not result.get("reason"):
            result["reason"] = "LLM classified"

        return result

    def _classify_with_rules(
        self,
        filename: str,
        filepath: str,
        columns: list,
        row_count: int,
        sample_text: str,
        encoding: str,
        fmt: str,
    ) -> FileClassification:
        name_lower = filename.lower()
        ext = os.path.splitext(filename)[1].lower()

        if ext in _TEXT_EXTENSIONS and ext not in _DATA_EXTENSIONS:
            category, reason = self._match_text_extension(name_lower)
            return FileClassification(
                filename=filename, filepath=filepath, category=category,
                confidence=0.7, reason=reason, columns=[], row_count=0,
                encoding=encoding, format="other",
            )

        name_hit = self._match_filename_keywords(name_lower)
        if name_hit:
            return FileClassification(
                filename=filename, filepath=filepath, category=name_hit[0],
                confidence=name_hit[1], reason=name_hit[2],
                columns=columns, row_count=row_count, encoding=encoding, format=fmt,
            )

        if columns:
            column_hit = self._match_column_pattern(columns)
            if column_hit:
                return FileClassification(
                    filename=filename, filepath=filepath, category=column_hit[0],
                    confidence=column_hit[1], reason=column_hit[2],
                    columns=columns, row_count=row_count, encoding=encoding, format=fmt,
                )

        if sample_text and row_count < 20:
            content_hit = self._match_content_keywords(sample_text)
            if content_hit:
                return FileClassification(
                    filename=filename, filepath=filepath, category=content_hit[0],
                    confidence=content_hit[1], reason=content_hit[2],
                    columns=columns, row_count=row_count, encoding=encoding, format=fmt,
                )

        if columns and row_count >= 20:
            has_numeric = False
            try:
                df_sample = pd.read_csv(filepath, nrows=5, encoding=encoding) if ext == ".csv" else None
                if df_sample is not None:
                    has_numeric = len(df_sample.select_dtypes(include="number").columns) > 0
            except Exception:
                pass

            if has_numeric or len(columns) >= 3:
                return FileClassification(
                    filename=filename, filepath=filepath, category="raw_data",
                    confidence=0.8,
                    reason=f"数据文件特征：{len(columns)}列，{row_count}行，含数值列",
                    columns=columns, row_count=row_count, encoding=encoding, format=fmt,
                )

        if columns and row_count > 0:
            return FileClassification(
                filename=filename, filepath=filepath, category="raw_data",
                confidence=0.5,
                reason=f"默认分类为数据文件（{len(columns)}列，{row_count}行）",
                columns=columns, row_count=row_count, encoding=encoding, format=fmt,
            )

        return FileClassification(
            filename=filename, filepath=filepath, category="unknown",
            confidence=0.3, reason="无法确定文件类型",
            columns=[], row_count=0, encoding=encoding, format=fmt,
        )

    def _match_text_extension(self, name_lower: str) -> tuple[str, str]:
        for kw in _KPI_KEYWORDS:
            if kw in name_lower:
                return "reference_kpi", f"文件名含KPI关键词: {kw}"
        for kw in _REQ_KEYWORDS:
            if kw in name_lower:
                return "reference_req", f"文件名含需求关键词: {kw}"
        for kw in _DICT_KEYWORDS:
            if kw in name_lower:
                return "reference_dict", f"文件名含字典关键词: {kw}"
        return "reference_other", "非数据格式文件（文档类型）"

    def _match_column_pattern(self, columns: list) -> Optional[tuple]:
        cols_lower = {c.lower() for c in columns}
        dict_patterns = [
            {"col_name", "comment"}, {"field", "meaning"}, {"field_name", "description"},
            {"column", "description"}, {"字段名", "含义"}, {"字段", "说明"},
            {"name", "comment"}, {"field", "type"},
        ]
        for pat in dict_patterns:
            if pat.issubset(cols_lower):
                return ("reference_dict", 0.8, f"列名模式匹配数据字典: {pat}")

        kpi_patterns = [
            {"指标名称", "计算公式"}, {"指标", "公式"}, {"metric", "formula"},
            {"name", "formula"}, {"指标名称", "计算公式", "口径说明"},
        ]
        for pat in kpi_patterns:
            if pat.issubset(cols_lower):
                return ("reference_kpi", 0.8, f"列名模式匹配KPI定义: {pat}")

        return None

    def _match_filename_keywords(self, name_lower: str) -> Optional[tuple]:
        for kw in _KPI_KEYWORDS:
            if kw in name_lower:
                return ("reference_kpi", 0.75, f"文件名含KPI关键词: {kw}")
        for kw in _DICT_KEYWORDS:
            if kw in name_lower:
                return ("reference_dict", 0.75, f"文件名含字典关键词: {kw}")
        for kw in _REQ_KEYWORDS:
            if kw in name_lower:
                return ("reference_req", 0.75, f"文件名含需求关键词: {kw}")
        return None

    def _match_content_keywords(self, sample_text: str) -> Optional[tuple]:
        text_lower = sample_text.lower()
        kpi_hits = sum(1 for kw in ["口径", "指标定义", "计算公式", "KPI", "度量"] if kw.lower() in text_lower)
        dict_hits = sum(1 for kw in ["字段说明", "数据字典", "枚举值", "field definition"] if kw.lower() in text_lower)
        req_hits = sum(1 for kw in ["分析目标", "需求", "Dashboard规划", "PRD"] if kw.lower() in text_lower)

        if kpi_hits >= 2:
            return ("reference_kpi", 0.65, f"内容含{kpi_hits}个KPI相关关键词")
        if dict_hits >= 2:
            return ("reference_dict", 0.65, f"内容含{dict_hits}个数据字典相关关键词")
        if req_hits >= 2:
            return ("reference_req", 0.65, f"内容含{req_hits}个需求相关关键词")

        total = kpi_hits + dict_hits + req_hits
        if total >= 2:
            return ("reference_other", 0.55, f"内容含{total}个参考文档相关关键词")

        return None
