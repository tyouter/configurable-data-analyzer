# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import shutil
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.reference_parser import KPIValidator, ValidationResult, ValidationIssue

print("=" * 70)
print("AutoResearch KPI Validator — 4 项验收标准测试")
print("=" * 70)

RAW_COLUMNS = ["user_id", "event_name", "start_time", "duration", "page_url", "revenue"]

validator = KPIValidator(raw_schema_columns=RAW_COLUMNS)

# ─── 标准 1: 参考文件中的指标个数完全对齐 ─────────────────────────
print("\n[标准1] 指标个数完全对齐")

source_text = """指标名称 计算公式 口径说明
DAU COUNT(DISTINCT user_id) 每日活跃用户数
ARPU SUM(revenue)/COUNT(DISTINCT user_id) 每用户平均收入
转化率 购买用户数/总用户数*100% 从浏览到购买的转化率"""

complete_kpis = [
    {"name": "DAU", "formula": "COUNT(DISTINCT user_id)", "description": "每日活跃用户数", "params": ["user_id"]},
    {"name": "ARPU", "formula": "SUM(revenue)/COUNT(DISTINCT user_id)", "description": "每用户平均收入", "params": ["revenue", "user_id"]},
    {"name": "转化率", "formula": "COUNT(DISTINCT CASE WHEN event_name='purchase' THEN user_id END) / COUNT(DISTINCT user_id) * 100", "description": "从浏览到购买的转化率", "params": ["event_name", "user_id"]},
]

v1 = validator.validate(complete_kpis, source_text=source_text)
print(f"  完整指标 ({len(complete_kpis)}个): score={v1.score}, passed={v1.passed}")
assert v1.passed, f"完整指标应通过验证: score={v1.score}, issues={v1.issues}"

incomplete_kpis = [complete_kpis[0]]
v1b = validator.validate(incomplete_kpis, source_text=source_text)
print(f"  不完整指标 ({len(incomplete_kpis)}个, 缺少2个): score={v1b.score}, passed={v1b.passed}")
assert not v1b.passed, "不完整指标应验证失败"
has_completeness_issue = any(
    isinstance(i, ValidationIssue) and i.category == "completeness"
    for i in v1b.issues
)
assert has_completeness_issue, "应检测到 completeness 类型的错误"
print("  [OK] 标准1 通过: 指标个数检测正确")

# ─── 标准 2: 结构化指标理解，无残缺，每个指标有明确公式，计算参数可映射到 RAW ───
print("\n[标准2] 结构化指标理解 — 公式完整 + 参数可映射")

no_formula_kpi = [
    {"name": "DAU", "formula": "", "description": "每日活跃用户数"},
]
v2a = validator.validate(no_formula_kpi, source_text=source_text)
has_formula_error = any(
    isinstance(i, ValidationIssue) and i.category == "structure" and "缺少计算公式" in i.message
    for i in v2a.issues
)
print(f"  无公式指标: score={v2a.score}, has_formula_error={has_formula_error}")
assert has_formula_error, "应检测到缺少公式的错误"

unmapped_kpi = [
    {"name": "GMV", "formula": "SUM(gmv_amount) / COUNT(order_id)", "description": "成交总额", "params": ["gmv_amount", "order_id"]},
]
v2b = validator.validate(unmapped_kpi, source_text=source_text)
has_mapping_error = any(
    isinstance(i, ValidationIssue) and i.category == "mapping"
    for i in v2b.issues
)
print(f"  不可映射列名: score={v2b.score}, has_mapping_error={has_mapping_error}")
assert has_mapping_error, "应检测到列名不可映射的错误"
for i in v2b.issues:
    if isinstance(i, ValidationIssue) and i.category == "mapping":
        print(f"    → {i.message}")

correct_kpi = [
    {"name": "DAU", "formula": "COUNT(DISTINCT user_id)", "description": "每日活跃用户数", "params": ["user_id"]},
]
v2c = validator.validate(correct_kpi, source_text=source_text)
mapped_ok = not any(
    isinstance(i, ValidationIssue) and i.category == "mapping"
    for i in v2c.issues
)
print(f"  正确映射: score={v2c.score}, no_mapping_issues={mapped_ok}")
assert mapped_ok, "正确映射不应有 mapping 错误"
print("  [OK] 标准2 通过: 结构化检查正确")

# ─── 标准 3: 主动检测矛盾和不完善点 ─────────────────────────────
print("\n[标准3] 矛盾检测 — 重复指标 + 相同公式")

contradiction_kpis = [
    {"name": "DAU", "formula": "COUNT(DISTINCT user_id)", "description": "日活", "params": ["user_id"]},
    {"name": "DAU", "formula": "COUNT(user_id)", "description": "日活(另一版)", "params": ["user_id"]},
    {"name": "总事件", "formula": "COUNT(DISTINCT user_id)", "description": "总事件数", "params": ["user_id"]},
]

v3 = validator.validate(contradiction_kpis, source_text="")
has_dup_name = any(
    isinstance(i, ValidationIssue) and i.category == "contradiction" and "重复指标" in i.message
    for i in v3.issues
)
has_same_formula = any(
    isinstance(i, ValidationIssue) and i.category == "contradiction" and "公式完全相同" in i.message
    for i in v3.issues
)
print(f"  矛盾指标: score={v3.score}")
print(f"    重复名称检测: {has_dup_name}")
print(f"    相同公式检测: {has_same_formula}")
assert has_dup_name, "应检测到重复指标名称"
assert has_same_formula, "应检测到相同公式不同名称"

count_no_distinct = [
    {"name": "事件数", "formula": "COUNT(event_name)", "description": "总事件数", "params": ["event_name"]},
]
v3b = validator.validate(count_no_distinct, source_text="")
has_count_warning = any(
    isinstance(i, ValidationIssue) and i.category == "statistical" and "DISTINCT" in i.message
    for i in v3b.issues
)
print(f"    COUNT无DISTINCT检测: {has_count_warning}")
assert has_count_warning, "应检测到COUNT未加DISTINCT的统计警告"
print("  [OK] 标准3 通过: 矛盾和统计检测正确")

# ─── 标准 4: 统计学合规性 ─────────────────────────────────────
print("\n[标准4] 统计学合规性 — 率指标检查 + 百分比检查")

rate_no_division = [
    {"name": "点击率", "formula": "COUNT(event_name)", "description": "点击率", "params": ["event_name"]},
]
v4a = validator.validate(rate_no_division, source_text="")
has_rate_issue = any(
    isinstance(i, ValidationIssue) and i.category == "statistical" and "率" in i.message
    for i in v4a.issues
)
print(f"  率指标无除法: has_rate_issue={has_rate_issue}")
assert has_rate_issue, "应检测到率指标缺少除法运算"

correct_rate = [
    {"name": "转化率", "formula": "CAST(COUNT(DISTINCT CASE WHEN event_name='purchase' THEN user_id END) AS DOUBLE) / COUNT(DISTINCT user_id) * 100", "description": "转化率", "params": ["event_name", "user_id"]},
]
v4b = validator.validate(correct_rate, source_text="")
rate_ok = not any(
    isinstance(i, ValidationIssue) and i.category == "statistical"
    for i in v4b.issues
)
print(f"  正确率指标: no_stat_issues={rate_ok}, score={v4b.score}")
assert rate_ok, "正确的率指标不应有统计问题"
print("  [OK] 标准4 通过: 统计学合规检查正确")

# ─── 综合: 规则模式下的规则兜底 ─────────────────────────────────
print("\n[综合] 规则兜底模式 (LLM 不可用)")

from mcp_server.reference_parser import ReferenceParser
from mcp_server.project_model import FileClassification

parser = ReferenceParser(llm_available=False, raw_schema_columns=RAW_COLUMNS)

tmp_dir = tempfile.mkdtemp(prefix="test_kpi_")
try:
    kpi_file = os.path.join(tmp_dir, "kpi_test.csv")
    with open(kpi_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["指标名称", "计算公式", "口径说明"])
        w.writerow(["DAU", "COUNT(DISTINCT user_id)", "每日活跃用户数"])
        w.writerow(["ARPU", "SUM(revenue)/COUNT(DISTINCT user_id)", "每用户平均收入"])

    fc = FileClassification(
        filename="kpi_test.csv", filepath=kpi_file,
        category="reference_kpi", confidence=0.8,
    )
    result = parser.parse_one(fc)
    print(f"  规则模式提取: {len(result.kpi_definitions)} KPIs")
    for k in result.kpi_definitions:
        print(f"    {k['name']}: {k['formula']}")
    assert len(result.kpi_definitions) >= 1, "规则模式应至少提取1个KPI"

finally:
    shutil.rmtree(tmp_dir)

print("\n" + "=" * 70)
print("全部 4 项验收标准测试通过 [OK]")
print("=" * 70)
