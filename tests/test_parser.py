# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.project_model import FileClassification
from mcp_server.reference_parser import ReferenceParser

with tempfile.NamedTemporaryFile(mode='w', suffix='_kpi_defs.csv', delete=False, newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['指标名称', '计算公式', '口径说明'])
    w.writerow(['DAU', 'COUNT(DISTINCT user_id)', '每日活跃用户数'])
    w.writerow(['ARPU', 'SUM(revenue)/COUNT(DISTINCT user_id)', '每用户平均收入'])
    w.writerow(['转化率', '购买用户数/总用户数*100%', '从浏览到购买的转化率'])
    kpi_file = f.name

with tempfile.NamedTemporaryFile(mode='w', suffix='_数据字典.csv', delete=False, newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['字段名', '含义', '枚举值'])
    w.writerow(['user_id', '用户唯一标识', ''])
    w.writerow(['event_name', '事件名称', 'click,view,share,purchase'])
    w.writerow(['start_time', '事件发生时间', ''])
    dict_file = f.name

parser = ReferenceParser(llm_available=False)

fc_kpi = FileClassification(
    filename=os.path.basename(kpi_file),
    filepath=kpi_file,
    category='reference_kpi',
    confidence=0.8,
    reason='test',
)

fc_dict = FileClassification(
    filename=os.path.basename(dict_file),
    filepath=dict_file,
    category='reference_dict',
    confidence=0.8,
    reason='test',
)

results = parser.parse_all([fc_kpi, fc_dict])

for r in results:
    print(f'File: {r.filename} (category: {r.category})')
    print(f'  KPI defs: {r.kpi_definitions}')
    print(f'  Field defs: {r.field_definitions}')
    print(f'  Goals: {r.analysis_goals}')
    print()

kpi_result = results[0]
dict_result = results[1]

assert len(kpi_result.kpi_definitions) > 0, f'KPI defs should not be empty, got: {kpi_result.kpi_definitions}'
assert kpi_result.kpi_definitions[0]["name"] in ["指标名称", "DAU"], f'Unexpected KPI name: {kpi_result.kpi_definitions[0]["name"]}'

assert len(dict_result.field_definitions) > 0, f'Field defs should not be empty, got: {dict_result.field_definitions}'

for f in [kpi_file, dict_file]:
    os.unlink(f)

print('All assertions passed! Plan 1.4 OK')
