# Phase 1 Plan: 文件分类与预分析引擎

**Phase:** 1
**Goal:** 实现 `create_project` 的底层能力 — 自动文件分类、Schema 提取、参考文档解析
**Status:** Planned

---

## Overview

Phase 1 不修改 `create_project` MCP 工具本身（那是 Phase 2 的事），而是构建三个核心引擎类，为 Phase 2 的状态机提供底层能力。

**原则：** Phase 1 的产出是纯 Python 类 + 数据结构，不涉及 MCP 工具层改造。

---

## Architecture Decision

### 数据流

```
用户提供的文件路径列表
        ↓
  FileClassifier.classify()
        ↓
  List[FileClassification]  ← 每个文件的分类结果
        ↓
  DataAuditor.audit()       ← 仅对 RAW_DATA 类文件
        ↓
  ReferenceParser.parse()   ← 仅对 REFERENCE 类文件
        ↓
  DataAuditReport           ← 汇总报告（Phase 2 用于用户对齐）
```

### 文件分类策略

LLM 分类（有 API Key 时）：
1. 读取文件名 + 扩展名
2. 读取前 N 行内容（CSV/Excel 都转文本样本）
3. 尝试 pd.read_csv/read_excel 提取列名
4. 发送 LLM prompt 判断文件类型

规则兜底（无 API Key 时）：
1. 扩展名启发式：`.pdf`, `.docx`, `.md` → REFERENCE
2. 列名启发式：检测是否含 KPI/指标/口径 等关键词
3. 行数启发式：< 20 行且含"定义"/"字典"/"KPI" → REFERENCE
4. 默认 → RAW_DATA

### 参考文档分类细类

```
REFERENCE_KPI     — KPI 定义文档（指标口径、计算公式）
REFERENCE_DICT    — 数据字典（字段定义、枚举说明）
REFERENCE_REQ     — 需求文档（分析目标、Dashboard 规划）
REFERENCE_OTHER   — 其他参考文档
```

---

## Plan 1.1: 新增数据结构

**File:** `mcp_server/project_model.py`

**What:**
在现有数据类（`ColumnDef`, `MetricDef` 等）之后新增：

```python
from enum import Enum

class FileCategory(str, Enum):
    RAW_DATA = "raw_data"
    REFERENCE_KPI = "reference_kpi"
    REFERENCE_DICT = "reference_dict"
    REFERENCE_REQ = "reference_req"
    REFERENCE_OTHER = "reference_other"
    UNKNOWN = "unknown"

@dataclass
class FileClassification:
    filename: str
    filepath: str
    category: FileCategory
    confidence: float          # 0.0 ~ 1.0
    reason: str                # LLM 或规则的判断理由
    columns: list[str]         # 列名（仅 RAW_DATA）
    row_count: int             # 行数（仅 RAW_DATA）
    encoding: str = "utf-8"
    format: str = "csv"        # csv / xlsx / parquet / other

@dataclass
class FileSchemaInfo:
    filename: str
    columns: list[dict]        # [{name, dtype, null_count, sample_values}]
    row_count: int
    numeric_columns: list[str]
    date_columns: list[str]
    category_columns: list[str]
    quality_score: float       # 0.0 ~ 1.0
    quality_issues: list[str]  # ["高空值率: col_x (45%)", "全唯一列可能是ID: col_y"]

@dataclass
class ReferenceContent:
    filename: str
    category: FileCategory
    raw_text: str              # 提取的文本内容
    kpi_definitions: list[dict]    # [{name, formula, description}]
    field_definitions: list[dict]   # [{field, meaning, enum_values}]
    analysis_goals: list[str]       # 提取的分析目标

@dataclass
class DataAuditReport:
    project_name: str
    created_at: str
    file_classifications: list[FileClassification]
    raw_data_schemas: list[FileSchemaInfo]
    reference_contents: list[ReferenceContent]
    summary: dict              # {raw_files: N, ref_files: N, total_rows: N, ...}
```

**Constraints:**
- 使用 `str, Enum` 确保 YAML 序列化兼容
- `FileClassification` 的 `columns` 和 `row_count` 对非数据文件为空/0
- `ReferenceContent.kpi_definitions` 等字段为可选，非 KPI 文档时为空列表

**Verification:**
- `python -c "from mcp_server.project_model import FileCategory, DataAuditReport; print('OK')"`
- 确认所有 dataclass 可实例化

---

## Plan 1.2: FileClassifier 实现

**File:** `mcp_server/file_classifier.py` (新建)

**What:**

```python
class FileClassifier:
    """文件分类器：区分原始数据文件和参考文档"""

    def __init__(self, llm_available: bool = True):
        self.llm_available = llm_available and bool(os.environ.get("DEEPSEEK_API_KEY"))

    def classify_all(self, file_paths: list[str]) -> list[FileClassification]:
        """批量分类文件"""
        results = []
        for fp in file_paths:
            results.append(self.classify_one(fp))
        return results

    def classify_one(self, filepath: str) -> FileClassification:
        """分类单个文件"""
        # 1. 基础信息提取（文件名、扩展名、大小）
        # 2. 尝试读取列名 + 前N行样本
        # 3. LLM 分类（如果可用）或规则兜底

    def _extract_file_info(self, filepath: str) -> dict:
        """提取文件基础信息：扩展名、大小、可读性"""

    def _read_data_sample(self, filepath: str, n_rows: int = 5) -> dict:
        """尝试用 pandas 读取文件，返回 {columns, sample_rows, row_count} 或 None"""

    def _classify_with_llm(self, filename: str, columns: list, sample: str, file_size: int) -> FileClassification:
        """LLM 分类：发送文件名+列名+样本给 LLM 判断"""

    def _classify_with_rules(self, filename: str, columns: list, row_count: int, sample: str) -> FileClassification:
        """规则兜底分类"""

    def _build_classification_prompt(self, filename: str, columns: list, sample: str) -> str:
        """构建 LLM 分类 prompt"""
```

**LLM Prompt 设计：**

```
你是一个数据分析专家。请判断以下文件是「原始数据文件」还是「参考文档」。

文件名：{filename}
列名：{columns}
前5行内容：
{sample}

参考文档类型包括：
- KPI定义文档：包含指标名称、计算公式、口径说明
- 数据字典：包含字段定义、枚举值说明
- 需求文档：包含分析目标、Dashboard规划

请以JSON格式返回：
{
  "category": "raw_data" | "reference_kpi" | "reference_dict" | "reference_req" | "reference_other",
  "confidence": 0.0-1.0,
  "reason": "判断理由"
}
```

**规则分类逻辑：**
1. 非数据格式（`.pdf`, `.docx`, `.md`, `.txt`）→ `REFERENCE_OTHER`
2. 文件名含 `kpi`/`指标`/`口径` → `REFERENCE_KPI`
3. 文件名含 `字典`/`dict`/`field`/`字段` → `REFERENCE_DICT`
4. 文件名含 `需求`/`requirement`/`PRD` → `REFERENCE_REQ`
5. 行数 < 20 且内容含 "定义"/"说明"/"口径" → `REFERENCE_OTHER`
6. 有多列 + 行数 > 20 + 含数值列 → `RAW_DATA`
7. 默认 → `UNKNOWN`

**Constraints:**
- `_read_data_sample` 对读取失败的文件不抛异常，返回 None
- Excel 文件尝试所有 sheet，取第一个成功的
- CSV 编码检测用 `chardet`（如果可用）或 utf-8/gbk 逐个尝试
- LLM 超时 30s，失败自动降级到规则分类

**Verification:**
- 单元测试：传入一个 CSV 数据文件，确认分类为 `RAW_DATA`
- 单元测试：传入一个含"KPI"的文件名，确认规则分类为 `REFERENCE_KPI`
- 集成测试：传入混合文件列表，确认批量分类结果

---

## Plan 1.3: DataAuditor 实现

**File:** `mcp_server/data_auditor.py` (新建)

**What:**

```python
class DataAuditor:
    """数据审计器：对 RAW_DATA 文件提取 Schema、统计信息、质量评估"""

    def audit_all(self, classifications: list[FileClassification]) -> list[FileSchemaInfo]:
        """批量审计所有 RAW_DATA 文件"""
        results = []
        for fc in classifications:
            if fc.category == FileCategory.RAW_DATA:
                results.append(self.audit_one(fc))
        return results

    def audit_one(self, classification: FileClassification) -> FileSchemaInfo:
        """审计单个文件：提取完整 Schema + 质量评估"""

    def _extract_full_schema(self, filepath: str, fmt: str) -> dict:
        """提取完整 Schema：列名、类型、空值率、唯一值数、样本值"""

    def _compute_quality_score(self, schema: dict, total_rows: int) -> tuple[float, list[str]]:
        """计算数据质量分数 (0.0~1.0) 和问题列表"""
```

**质量评估维度：**
- 空值率：列空值率 > 50% 扣分
- 唯一性：100% 唯一列可能是 ID，标记提醒
- 类型一致性：数值列含字符串的比例
- 行数合理性：0 行或 > 1000万行 标记警告

**Constraints:**
- 大文件只读取 schema + 前 100 行做质量评估（避免 OOM）
- `quality_score` 为加权平均：空值率(40%) + 类型一致性(30%) + 唯一性(30%)
- 使用 DuckDB 的 `DESCRIBE` 而非 pandas 的 `df.info()` 以获得更精确的类型

**Verification:**
- 对已知 CSV 文件执行 `audit_one()`，确认返回正确的 `FileSchemaInfo`
- 质量分数在合理范围内
- 空值列被正确标记

---

## Plan 1.4: ReferenceParser 实现

**File:** `mcp_server/reference_parser.py` (新建)

**What:**

```python
class ReferenceParser:
    """参考文档解析器：提取 KPI 定义、数据字典、分析目标"""

    def __init__(self, llm_available: bool = True):
        self.llm_available = llm_available and bool(os.environ.get("DEEPSEEK_API_KEY"))

    def parse_all(self, classifications: list[FileClassification]) -> list[ReferenceContent]:
        """批量解析所有 REFERENCE 类文件"""
        results = []
        for fc in classifications:
            if fc.category.startswith("reference"):
                results.append(self.parse_one(fc))
        return results

    def parse_one(self, classification: FileClassification) -> ReferenceContent:
        """解析单个参考文档"""

    def _extract_text(self, filepath: str) -> str:
        """从文件中提取纯文本（支持 csv/xlsx/txt/md）"""

    def _parse_with_llm(self, text: str, category: FileCategory, filename: str) -> ReferenceContent:
        """LLM 解析：提取结构化信息"""

    def _parse_kpi_document(self, text: str) -> list[dict]:
        """规则化 KPI 提取（兜底）"""

    def _parse_data_dictionary(self, text: str) -> list[dict]:
        """规则化数据字典提取（兜底）"""
```

**LLM Prompt 设计（KPI 类）：**

```
你是数据分析专家。请从以下文档中提取所有 KPI 指标定义。

文档内容：
{text}

请以 JSON 格式返回：
{
  "kpi_definitions": [
    {"name": "指标名称", "formula": "计算公式/SQL", "description": "口径说明"}
  ],
  "analysis_goals": ["分析目标1", "分析目标2"]
}
```

**Constraints:**
- 文本提取失败时返回空的 `ReferenceContent`（不抛异常）
- Excel 参考文档转为 CSV 文本后处理
- LLM 超时 45s，失败降级到规则提取
- 规则提取仅支持简单模式（表格型 KPI 定义）

**Verification:**
- 对含 KPI 关键词的 CSV 文件执行 `parse_one()`，确认提取 `kpi_definitions`
- 对非参考文档返回空结果
- LLM 不可用时降级到规则提取

---

## Plan 1.5: DataAuditReport 组装 + 持久化

**File:** `mcp_server/project_model.py` (修改)

**What:**

在 `ProjectStore` 中新增方法：

```python
def save_audit_report(self, project_id: str, report: DataAuditReport) -> str:
    """持久化审计报告到 {project_id}/audit_report.yaml"""
    report_path = os.path.join(self._project_dir(project_id), "audit_report.yaml")
    # 将 DataAuditReport 转为 dict，处理 Enum 序列化
    data = self._report_to_dict(report)
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return report_path

def load_audit_report(self, project_id: str) -> Optional[DataAuditReport]:
    """加载已保存的审计报告"""

@staticmethod
def _report_to_dict(report: DataAuditReport) -> dict:
    """将 DataAuditReport 序列化为可 YAML dump 的 dict"""
```

**Constraints:**
- `FileCategory` Enum 需要转为字符串才能 YAML 序列化
- `FileSchemaInfo.columns` 中的 dict 直接保留
- 报告路径：`{project_id}/audit_report.yaml`

**Verification:**
- 创建一个 `DataAuditReport`，保存后重新加载，确认数据完整

---

## Plan 1.6: 集成验证

**What:**

1. 创建端到端验证脚本 `tests/test_phase1.py`：
   - 构造测试文件（1个 CSV 数据文件 + 1个 KPI 定义文件）
   - 调用 `FileClassifier.classify_all()`
   - 调用 `DataAuditor.audit_all()`
   - 调用 `ReferenceParser.parse_all()`
   - 组装 `DataAuditReport`
   - 保存并重新加载，验证完整性

2. 手动验证：
   - 用 `projects/rednote/data/` 下的实际文件测试
   - 确认文件分类准确
   - 确认审计报告生成正确

**Verification:**
- `python tests/test_phase1.py` 全部通过
- 实际数据文件分类结果人工审查

---

## Execution Order

```
Plan 1.1 (数据结构) → Plan 1.2 (FileClassifier) → Plan 1.3 (DataAuditor)
                                                          ↓
                                     Plan 1.4 (ReferenceParser) → Plan 1.5 (报告持久化)
                                                                          ↓
                                                                   Plan 1.6 (集成验证)
```

---

## Files Changed

| File | Action | Plans |
|------|--------|-------|
| `mcp_server/project_model.py` | 修改：新增 5 个 dataclass + 2 个方法 | 1.1, 1.5 |
| `mcp_server/file_classifier.py` | 新建 | 1.2 |
| `mcp_server/data_auditor.py` | 新建 | 1.3 |
| `mcp_server/reference_parser.py` | 新建 | 1.4 |
| `tests/test_phase1.py` | 新建 | 1.6 |

**不修改的文件：**
- `server.py` — Phase 2 才改
- `semantic_generator.py` — Phase 3 才改
- `cli.py` — 后续迭代

---

## Dependencies

- `chardet` (可选) — CSV 编码检测，无则 utf-8/gbk 逐试
- 现有 `DEEPSEEK_API_KEY` 环境变量 — LLM 分类/解析
- 现有 `_call_llm()` 函数 — 复用 `semantic_generator.py` 的 LLM 调用能力

---

## Risks

| Risk | Mitigation |
|------|------------|
| LLM 分类准确率不够 | 规则兜底 + confidence 阈值标记低置信度结果 |
| 大文件 OOM | 限制读取行数，pandas 只读前 N 行 |
| 参考文档格式多样 | 只支持 csv/xlsx/txt/md，PDF/Word 后续迭代 |
| 编码问题 | utf-8 → gbk → latin-1 逐个尝试 |

---
*Created: 2026-04-30*
