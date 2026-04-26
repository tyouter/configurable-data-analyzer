# -*- coding: utf-8 -*-
"""
诊断时间戳字段格式 - 用于修复 C-001
"""

import pandas as pd
import numpy as np

df = pd.read_excel(r'c:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx')
print('=' * 80)
print('原始数据时间戳字段诊断')
print('=' * 80)
print(f'\n总行数: {len(df):,}')
print(f'\n时间戳相关列:')
time_cols = [c for c in df.columns if 'time' in c.lower() or 'nano' in c.lower() or 'strt' in c.lower() or 'end_' in c.lower()]
for col in time_cols:
    print(f'  - {col}: dtype={df[col].dtype}')

print('\n--- strt_time_nano 样例 (前10行) ---')
if 'strt_time_nano' in df.columns:
    print(df['strt_time_nano'].head(10))
    col_name = 'strt_time_nano'
    print(f'\n类型: {df[col_name].dtype}')
    print(f'非空数: {df[col_name].notna().sum()}')

    sample = df[col_name].dropna().iloc[0]
    print(f'\n第一个非空值: {sample}')
    print(f'值类型: {type(sample)}')
    if isinstance(sample, (int, float)):
        val_str = str(int(sample))
        print(f'数值长度: {len(val_str)} 位')
        if sample > 1e18:
            print('-> 这是纳秒级时间戳 (19位)')
        elif sample > 1e15:
            print('-> 这是毫秒级时间戳 (16位)')
        elif sample > 1e12:
            print('-> 这是秒级时间戳 (13位)')

print('\n--- end_time_nano 样例 (前10行) ---')
if 'end_time_nano' in df.columns:
    print(df['end_time_nano'].head(10))

print('\n--- 尝试解析为datetime ---')
df_test = df.head(100).copy()
df_test['strt_dt'] = pd.to_datetime(df_test['strt_time_nano'], errors='coerce')
df_test['end_dt'] = pd.to_datetime(df_test['end_time_nano'], errors='coerce')
strt_success = df_test['strt_dt'].notna().sum() / len(df_test) * 100
end_success = df_test['end_dt'].notna().sum() / len(df_test) * 100
print(f'strt_time_nano -> datetime 成功率: {strt_success:.1f}%')
print(f'end_time_nano -> datetime 成功率: {end_success:.1f}%')

if df_test['strt_dt'].notna().sum() > 0:
    valid = df_test[df_test['strt_dt'].notna()].head(5)
    print('\n成功解析的样例:')
    for idx, row in valid.iterrows():
        dur = (row['end_dt'] - row['strt_dt']).total_seconds()
        print(f'  [{idx}] strt={row["strt_dt"]} | end={row["end_dt"]} | duration={dur:.2f}s')

print('\n--- 检查是否有其他可能的时间字段 ---')
all_cols = df.columns.tolist()
for col in all_cols:
    if any(kw in col.lower() for kw in ['time', 'date', 'ts', 'timestamp']):
        print(f'  可能的时间字段: {col} | 样例: {df[col].iloc[0]}')
