# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.file_classifier import FileClassifier

fc = FileClassifier(llm_available=False)

with tempfile.NamedTemporaryFile(mode='w', suffix='_kpi_definitions.csv', delete=False, newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['指标名称', '计算公式', '口径说明'])
    w.writerow(['DAU', 'COUNT(DISTINCT user_id)', '每日活跃用户数'])
    w.writerow(['ARPU', 'SUM(revenue)/DAU', '每用户平均收入'])
    kpi_file = f.name

with tempfile.NamedTemporaryFile(mode='w', suffix='_raw_events.csv', delete=False, newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['user_id', 'event_name', 'start_time', 'duration'])
    for i in range(100):
        w.writerow([f'u{i}', f'event_{i % 5}', f'2024-01-{(i % 28) + 1:02d}', str(i * 1.5)])
    data_file = f.name

with tempfile.NamedTemporaryFile(mode='w', suffix='_数据字典.csv', delete=False, newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['字段名', '含义', '枚举值'])
    w.writerow(['event_name', '事件名称', 'click,view,share'])
    dict_file = f.name

results = fc.classify_all([kpi_file, data_file, dict_file])
for r in results:
    print(f'{r.filename:40s} -> {r.category:20s} conf={r.confidence:.2f}  {r.reason}')

assert results[0].category.startswith('reference'), f'KPI file should be reference, got {results[0].category}'
assert results[1].category == 'raw_data', f'Data file should be raw_data, got {results[1].category}'
assert results[2].category.startswith('reference'), f'Dict file should be reference, got {results[2].category}'

for f in [kpi_file, data_file, dict_file]:
    os.unlink(f)

print('\nAll assertions passed! Plan 1.2 OK')
