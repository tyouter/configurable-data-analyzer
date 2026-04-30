# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.project_model import FileClassification
from mcp_server.data_auditor import DataAuditor

with tempfile.NamedTemporaryFile(mode='w', suffix='_events.csv', delete=False, newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['user_id', 'event_name', 'start_time', 'duration', 'page_url'])
    for i in range(100):
        ev = ['click', 'view', 'share', 'purchase'][i % 4]
        w.writerow([f'u{i}', ev, f'2024-01-{(i % 28) + 1:02d} 10:{i % 60:02d}:00', str(i * 1.5), f'/page/{i % 10}'])
    data_file = f.name

fc = FileClassification(
    filename=os.path.basename(data_file),
    filepath=data_file,
    category='raw_data',
    confidence=0.8,
    reason='test',
    columns=['user_id', 'event_name', 'start_time', 'duration', 'page_url'],
    row_count=100,
    format='csv',
)

auditor = DataAuditor()
result = auditor.audit_one(fc)

print(f'File: {result.filename}')
print(f'Row count: {result.row_count}')
print(f'Columns: {len(result.columns)}')
print(f'Numeric cols: {result.numeric_columns}')
print(f'Date cols: {result.date_columns}')
print(f'Category cols: {result.category_columns}')
print(f'Quality score: {result.quality_score}')
print(f'Quality issues: {result.quality_issues}')

print('\nColumn details:')
for c in result.columns:
    print(f'  {c["name"]:15s} dtype={c["dtype"]:15s} null={c["null_rate"]:.2f} unique={c["unique_count"]} numeric={c["is_numeric"]} cat={c["is_category"]}')

assert result.row_count == 100, f'Expected 100 rows, got {result.row_count}'
assert len(result.columns) == 5, f'Expected 5 columns, got {len(result.columns)}'
assert result.quality_score > 0.5, f'Quality score too low: {result.quality_score}'

os.unlink(data_file)

print('\nAll assertions passed! Plan 1.3 OK')
