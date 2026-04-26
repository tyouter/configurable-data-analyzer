# -*- coding: utf-8 -*-
"""
Rednote 新用户增长分析报告
基于 rednote20260319-20260412.xlsx 数据

计算逻辑:
  新用户 = 在观测时间窗口内首次产生任意埋点事件的用户
  即 first_seen_date = min(date) per reduser_id
  当 first_seen_date 落在某天/某周时，该用户即为当天/当周的新用户

输出:
  - report/fulldata_v2/new_user_growth.json      (结构化数据)
  - report/fulldata_v2/new_user_growth_report.html (可视化报告)
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_PATH = r'C:\projects\rednote data analyzer\data\rednote\rednote20260319-20260412.xlsx'
OUTPUT_DIR = r'C:\projects\rednote data analyzer\report\fulldata_v2'


def to_serializable(obj):
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj) if not np.isnan(obj) else None
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, pd.Timestamp):
        return str(obj)
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        if isinstance(obj, pd.Series):
            return {str(k): to_serializable(v) for k, v in obj.items()}
        return obj.to_dict(orient='records')
    else:
        return obj


def load_data():
    print("=" * 70)
    print("Rednote 新用户增长分析")
    print(f"数据源: {DATA_PATH}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"原始数据: {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['timestamp'] = pd.to_datetime(df['start_time_nano'], errors='coerce')
    df['date'] = df['timestamp'].dt.date

    # 过滤无效时间
    df = df[df['timestamp'].notna()].copy()

    print(f"有效数据: {df.shape[0]:,} 行")
    print(f"时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"总用户数: {df['reduser_id'].nunique()}")

    return df


def compute_new_user_growth(df):
    """核心计算: 新用户增长"""

    # ============================================================
    # 计算公式说明
    # ============================================================
    # 1. 新用户定义:
    #    对于用户 u, 其首次出现日期 first_date(u) = min(event.date for event in user_u)
    #    若 first_date(u) == 某日 D, 则 u 是日期 D 的新用户
    #
    # 2. 日新增用户数 NewUsers(d):
    #    NewUsers(d) = |{ u : first_date(u) = d }|
    #
    # 3. 累计用户数 Cumulative(d):
    #    Cumulative(d) = sum(NewUsers(d') for d' <= d)
    #
    # 4. 日环比增长率 DoD_growth(d):
    #    DoD_growth(d) = (NewUsers(d) - NewUsers(d-1)) / NewUsers(d-1) * 100%
    #
    # 5. 周新增用户数 WeeklyNewUsers(w):
    #    WeeklyNewUsers(w) = |{ u : first_date(u) in week_w }|
    #
    # 6. 周环比增长率 WoW_growth(w):
    #    WoW_growth(w) = (WeeklyNewUsers(w) - WeeklyNewUsers(w-1)) / WeeklyNewUsers(w-1) * 100%
    # ============================================================

    # Step 1: 每个用户的首次出现日期
    user_first = df.groupby('reduser_id')['date'].min().reset_index()
    user_first.columns = ['reduser_id', 'first_date']
    user_first = user_first.dropna(subset=['first_date'])

    total_users = len(user_first)
    print(f"\n[计算] 总独立用户: {total_users}")

    # ============================================================
    # 日维度: Daily New Users
    # ============================================================
    daily_new = user_first.groupby('first_date').size().reset_index(name='new_users')
    daily_new = daily_new.sort_values('first_date').reset_index(drop=True)
    daily_new['date_str'] = daily_new['first_date'].apply(lambda x: str(x))

    # 累计用户数
    daily_new['cumulative_users'] = daily_new['new_users'].cumsum()

    # 日环比增长率
    daily_new['prev_day_new'] = daily_new['new_users'].shift(1)
    daily_new['dod_growth_rate'] = daily_new.apply(
        lambda r: round((r['new_users'] - r['prev_day_new']) / r['prev_day_new'] * 100, 2)
        if pd.notna(r['prev_day_new']) and r['prev_day_new'] > 0 else None, axis=1
    )

    # 累计渗透率 (占最终总用户数的比例)
    daily_new['cumulative_pct'] = round(daily_new['cumulative_users'] / total_users * 100, 2)

    print(f"[计算] 日新增用户: {len(daily_new)} 天有新用户")

    # ============================================================
    # 周维度: Weekly New Users (ISO周, 周一开始)
    # ============================================================
    user_first['first_date_dt'] = pd.to_datetime(user_first['first_date'])
    user_first['iso_year'] = user_first['first_date_dt'].dt.isocalendar().year.astype(int)
    user_first['iso_week'] = user_first['first_date_dt'].dt.isocalendar().week.astype(int)
    user_first['week_key'] = user_first['iso_year'].astype(str) + '-W' + user_first['iso_week'].astype(str).str.zfill(2)

    # 每周起始日期
    def week_start_date(row):
        dt = row['first_date_dt']
        return dt - timedelta(days=dt.weekday())  # 周一

    user_first['week_start'] = user_first.apply(week_start_date, axis=1)
    user_first['week_end'] = user_first['week_start'] + timedelta(days=6)

    weekly_new = user_first.groupby(['week_key', 'week_start', 'week_end']).agg(
        new_users=('reduser_id', 'nunique')
    ).reset_index().sort_values('week_key').reset_index(drop=True)

    weekly_new['week_start_str'] = weekly_new['week_start'].apply(lambda x: str(x.date()) if hasattr(x, 'date') else str(x))
    weekly_new['week_end_str'] = weekly_new['week_end'].apply(lambda x: str(x.date()) if hasattr(x, 'date') else str(x))

    # 累计
    weekly_new['cumulative_users'] = weekly_new['new_users'].cumsum()
    weekly_new['cumulative_pct'] = round(weekly_new['cumulative_users'] / total_users * 100, 2)

    # 周环比增长率
    weekly_new['prev_week_new'] = weekly_new['new_users'].shift(1)
    weekly_new['wow_growth_rate'] = weekly_new.apply(
        lambda r: round((r['new_users'] - r['prev_week_new']) / r['prev_week_new'] * 100, 2)
        if pd.notna(r['prev_week_new']) and r['prev_week_new'] > 0 else None, axis=1
    )

    # 周均新增
    avg_weekly_new = round(weekly_new['new_users'].mean(), 1)

    print(f"[计算] 周新增用户: {len(weekly_new)} 周, 周均新增 {avg_weekly_new}")

    return {
        'daily': daily_new,
        'weekly': weekly_new,
        'user_first': user_first,
        'total_users': total_users
    }


def compute_new_user_behavior(df, user_first):
    """新用户 vs 老用户行为对比"""

    first_date_map = user_first.set_index('reduser_id')['first_date'].to_dict()
    df_with_flag = df.copy()
    df_with_flag['first_date'] = df_with_flag['reduser_id'].map(first_date_map)
    df_with_flag['is_first_day'] = df_with_flag['date'] == df_with_flag['first_date']

    # 新用户首日行为
    first_day_df = df_with_flag[df_with_flag['is_first_day']]

    # 首日行为统计
    first_day_events = first_day_df.groupby('reduser_id').agg(
        event_count=('span_name', 'count'),
        event_types=('span_name', 'nunique')
    ).reset_index()

    # 首日行为分布
    first_day_top_events = first_day_df['span_name'].value_counts().head(15)

    # 后续留存: 首日之后是否还有活动
    user_last = df.groupby('reduser_id')['date'].max().reset_index()
    user_last.columns = ['reduser_id', 'last_date']
    user_behavior = user_first[['reduser_id', 'first_date']].merge(user_last, on='reduser_id')
    user_behavior['first_date_dt'] = pd.to_datetime(user_behavior['first_date'])
    user_behavior['last_date_dt'] = pd.to_datetime(user_behavior['last_date'])
    user_behavior['lifespan_days'] = (user_behavior['last_date_dt'] - user_behavior['first_date_dt']).dt.days

    # 按首日行为分类
    single_day_users = int((user_behavior['lifespan_days'] == 0).sum())
    multi_day_users = int((user_behavior['lifespan_days'] > 0).sum())

    print(f"\n[新用户行为]")
    print(f"  仅首日活跃: {single_day_users} ({round(single_day_users/len(user_behavior)*100, 1)}%)")
    print(f"  多日活跃: {multi_day_users} ({round(multi_day_users/len(user_behavior)*100, 1)}%)")
    print(f"  首日人均事件数: {round(first_day_events['event_count'].mean(), 1)}")

    return {
        'first_day_avg_events': round(first_day_events['event_count'].mean(), 1),
        'first_day_avg_event_types': round(first_day_events['event_types'].mean(), 1),
        'first_day_median_events': round(first_day_events['event_count'].median(), 1),
        'single_day_users': single_day_users,
        'multi_day_users': multi_day_users,
        'single_day_pct': round(single_day_users / len(user_behavior) * 100, 1),
        'first_day_top_events': {str(k): int(v) for k, v in first_day_top_events.items()},
        'lifespan_stats': {
            'mean_days': round(user_behavior['lifespan_days'].mean(), 1),
            'median_days': round(user_behavior['lifespan_days'].median(), 1),
            'max_days': int(user_behavior['lifespan_days'].max())
        }
    }


def get_trigger_events(df):
    """识别新用户首次触发的埋点事件类型"""
    user_first_dates = df.groupby('reduser_id')['date'].min()
    df_copy = df.copy()
    df_copy['first_date'] = df_copy['reduser_id'].map(user_first_dates.to_dict())
    df_copy['is_first_event'] = df_copy['date'] == df_copy['first_date']

    first_events = df_copy[df_copy['is_first_event']]

    # 按event_type分类统计首日事件
    event_type_dist = first_events['event_type'].value_counts()
    span_name_dist = first_events['span_name'].value_counts().head(20)

    # 首次触发路径: 用户第一个事件是什么
    first_event_per_user = df_copy[df_copy['is_first_event']].sort_values('timestamp').groupby('reduser_id').first()
    first_trigger_dist = first_event_per_user['span_name'].value_counts().head(15)

    print(f"\n[埋点Trigger]")
    print(f"  首次事件分布 (Top 5):")
    for evt, cnt in first_trigger_dist.head(5).items():
        print(f"    {evt}: {cnt}")

    return {
        'first_event_type_distribution': {str(k): int(v) for k, v in event_type_dist.items()},
        'first_trigger_event_distribution': {str(k): int(v) for k, v in first_trigger_dist.items()},
        'first_day_top_span_names': {str(k): int(v) for k, v in span_name_dist.items()},
        'note': 'first_trigger_event = 用户在APP中产生的第一个埋点事件(span_name), 代表用户的首次交互入口'
    }


def build_json_report(growth_data, behavior_data, trigger_data, df):
    """构建JSON报告"""

    daily = growth_data['daily']
    weekly = growth_data['weekly']

    report = {
        'meta': {
            'report_name': 'Rednote 新用户增长分析报告',
            'data_source': DATA_PATH,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_period': {
                'start': str(df['timestamp'].min()),
                'end': str(df['timestamp'].max()),
                'total_days': int((df['timestamp'].max() - df['timestamp'].min()).days + 1)
            },
            'total_users': growth_data['total_users']
        },

        'calculation_methodology': {
            'new_user_definition': (
                '在观测时间窗口内首次产生任意埋点事件的用户。'
                '即 first_seen_date = min(event.date) per reduser_id。'
                '当 first_seen_date 落在某天/某周时, 该用户即为当天/当周的新用户。'
            ),
            'formulas': {
                'daily_new_users': {
                    'formula': 'NewUsers(d) = |{ u : first_date(u) = d }|',
                    'description': '日期 d 的新增用户数 = 首次出现日期等于 d 的用户数量'
                },
                'cumulative_users': {
                    'formula': 'Cumulative(d) = Σ NewUsers(d\') for all d\' <= d',
                    'description': '截至日期 d 的累计用户数 = 所有 d 及之前日期的新增用户之和'
                },
                'dod_growth_rate': {
                    'formula': 'DoD(d) = (NewUsers(d) - NewUsers(d-1)) / NewUsers(d-1) × 100%',
                    'description': '日环比增长率'
                },
                'weekly_new_users': {
                    'formula': 'WeeklyNewUsers(w) = |{ u : first_date(u) ∈ week_w }|',
                    'description': '周新增用户数 = 首次出现日期落在该周内的用户数量 (ISO周, 周一至周日)'
                },
                'wow_growth_rate': {
                    'formula': 'WoW(w) = (WeeklyNewUsers(w) - WeeklyNewUsers(w-1)) / WeeklyNewUsers(w-1) × 100%',
                    'description': '周环比增长率'
                },
                'cumulative_pct': {
                    'formula': 'CumulativePct(d) = Cumulative(d) / TotalUsers × 100%',
                    'description': '累计渗透率 = 截至该日的累计用户数 / 总用户数'
                }
            },
            'user_identifier': 'reduser_id (用户唯一标识)',
            'time_field': 'start_time_nano (事件开始时间戳)',
            'trigger_definition': (
                '新用户判定的"首次使用"基于用户在APP中触发的任意一个埋点事件 (span_name)。'
                '不限定特定事件类型, 只要该 reduser_id 首次出现在数据集中即判定为新用户。'
                '数据通过APP SDK自动采集, 包含页面展示(SHOW)、点击(CLICK)、系统事件等。'
            )
        },

        'trigger_events': trigger_data,

        'summary': {
            'total_new_users': growth_data['total_users'],
            'avg_daily_new_users': round(daily['new_users'].mean(), 1),
            'max_daily_new_users': {
                'count': int(daily['new_users'].max()),
                'date': str(daily.loc[daily['new_users'].idxmax(), 'first_date'])
            },
            'min_daily_new_users': {
                'count': int(daily['new_users'].min()),
                'date': str(daily.loc[daily['new_users'].idxmin(), 'first_date'])
            },
            'avg_weekly_new_users': round(weekly['new_users'].mean(), 1),
            'max_weekly_new_users': {
                'count': int(weekly['new_users'].max()),
                'week': str(weekly.loc[weekly['new_users'].idxmax(), 'week_key'])
            }
        },

        'daily_data': [
            {
                'date': row['date_str'],
                'new_users': int(row['new_users']),
                'cumulative_users': int(row['cumulative_users']),
                'cumulative_pct': row['cumulative_pct'],
                'dod_growth_rate': row['dod_growth_rate']
            }
            for _, row in daily.iterrows()
        ],

        'weekly_data': [
            {
                'week': row['week_key'],
                'week_start': row['week_start_str'],
                'week_end': row['week_end_str'],
                'new_users': int(row['new_users']),
                'cumulative_users': int(row['cumulative_users']),
                'cumulative_pct': row['cumulative_pct'],
                'wow_growth_rate': row['wow_growth_rate']
            }
            for _, row in weekly.iterrows()
        ],

        'new_user_behavior': behavior_data
    }

    return report


def generate_html_report(report):
    """生成可视化HTML报告"""

    daily_data = report['daily_data']
    weekly_data = report['weekly_data']

    # 准备图表数据
    daily_dates = [d['date'] for d in daily_data]
    daily_new = [d['new_users'] for d in daily_data]
    daily_cum = [d['cumulative_users'] for d in daily_data]
    daily_pct = [d['cumulative_pct'] for d in daily_data]
    daily_dod = [d['dod_growth_rate'] if d['dod_growth_rate'] is not None else 0 for d in daily_data]

    weekly_labels = [f"{w['week_start']}<br>~{w['week_end']}" for w in weekly_data]
    weekly_new = [w['new_users'] for w in weekly_data]
    weekly_cum = [w['cumulative_users'] for w in weekly_data]
    weekly_pct = [w['cumulative_pct'] for w in weekly_data]
    weekly_wow = [w['wow_growth_rate'] if w['wow_growth_rate'] is not None else 0 for w in weekly_data]

    trigger_items = report['trigger_events']['first_trigger_event_distribution']
    trigger_labels = list(trigger_items.keys())
    trigger_values = list(trigger_items.values())

    # 首日行为数据
    behavior_events = report['new_user_behavior']['first_day_top_events']
    beh_labels = list(behavior_events.keys())[:10]
    beh_values = list(behavior_events.values())[:10]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rednote 新用户增长分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f7fa;
    color: #1a1a2e;
    line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
h1 {{
    text-align: center;
    font-size: 28px;
    color: #1a1a2e;
    margin: 30px 0 10px;
}}
h2 {{
    font-size: 20px;
    color: #2d3436;
    margin: 30px 0 15px;
    padding-left: 12px;
    border-left: 4px solid #ff2442;
}}
h3 {{ font-size: 16px; color: #636e72; margin: 15px 0 10px; }}
.subtitle {{ text-align: center; color: #636e72; font-size: 14px; margin-bottom: 30px; }}

/* KPI Cards */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 20px 0;
}}
.kpi-card {{
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    text-align: center;
    border-top: 3px solid #ff2442;
}}
.kpi-card .value {{ font-size: 32px; font-weight: 700; color: #ff2442; }}
.kpi-card .label {{ font-size: 13px; color: #636e72; margin-top: 6px; }}
.kpi-card .sub {{ font-size: 12px; color: #b2bec3; margin-top: 4px; }}

/* Chart Containers */
.chart-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin: 20px 0;
}}
.chart-box {{
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.chart-box.full {{ grid-column: 1 / -1; }}
.chart-box canvas {{ max-height: 320px; }}

/* Methodology */
.methodology {{
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin: 20px 0;
}}
.methodology .formula {{
    background: #f8f9fa;
    border-left: 3px solid #ff2442;
    padding: 10px 16px;
    margin: 8px 0;
    font-family: 'Courier New', monospace;
    font-size: 14px;
    border-radius: 0 6px 6px 0;
}}
.methodology .desc {{ font-size: 13px; color: #636e72; margin: 2px 0 12px 16px; }}

/* Tables */
.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin: 15px 0;
}}
.data-table th {{
    background: #f8f9fa;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid #e0e0e0;
    white-space: nowrap;
}}
.data-table td {{
    padding: 8px 12px;
    border-bottom: 1px solid #f0f0f0;
}}
.data-table tr:hover {{ background: #fff5f5; }}
.positive {{ color: #00b894; }}
.negative {{ color: #ff2442; }}

/* Section divider */
.divider {{
    height: 1px;
    background: linear-gradient(to right, transparent, #ddd, transparent);
    margin: 30px 0;
}}

/* Trigger list */
.trigger-list {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.trigger-item {{
    display: flex;
    justify-content: space-between;
    padding: 6px 12px;
    background: #f8f9fa;
    border-radius: 6px;
    font-size: 13px;
}}
.trigger-item .name {{ font-family: monospace; color: #2d3436; }}
.trigger-item .count {{ font-weight: 600; color: #ff2442; }}
</style>
</head>
<body>
<div class="container">

<h1>Rednote 新用户增长分析报告</h1>
<p class="subtitle">
    数据周期: {report['meta']['data_period']['start']} ~ {report['meta']['data_period']['end']} |
    共 {report['meta']['data_period']['total_days']} 天 |
    总用户 {report['meta']['total_users']} 人
</p>

<!-- KPI Cards -->
<div class="kpi-grid">
    <div class="kpi-card">
        <div class="value">{report['summary']['total_new_users']}</div>
        <div class="label">总新用户数</div>
        <div class="sub">观测期间内首次出现的用户</div>
    </div>
    <div class="kpi-card">
        <div class="value">{report['summary']['avg_daily_new_users']}</div>
        <div class="label">日均新增用户</div>
    </div>
    <div class="kpi-card">
        <div class="value">{report['summary']['max_daily_new_users']['count']}</div>
        <div class="label">单日最高新增</div>
        <div class="sub">{report['summary']['max_daily_new_users']['date']}</div>
    </div>
    <div class="kpi-card">
        <div class="value">{report['summary']['avg_weekly_new_users']}</div>
        <div class="label">周均新增用户</div>
    </div>
    <div class="kpi-card">
        <div class="value">{report['new_user_behavior']['first_day_avg_events']}</div>
        <div class="label">首日人均事件数</div>
    </div>
    <div class="kpi-card">
        <div class="value">{report['new_user_behavior']['single_day_pct']}%</div>
        <div class="label">仅首日活跃占比</div>
        <div class="sub">{report['new_user_behavior']['single_day_users']} 人</div>
    </div>
</div>

<!-- 计算方法 -->
<h2>计算方法与公式</h2>
<div class="methodology">
    <h3>新用户定义</h3>
    <p>{report['calculation_methodology']['new_user_definition']}</p>

    <h3 style="margin-top:16px">核心公式</h3>

    <div class="formula">NewUsers(d) = |{{ u : first_date(u) = d }}|</div>
    <div class="desc">日新增用户数 = 首次出现日期等于 d 的用户数量</div>

    <div class="formula">Cumulative(d) = Σ NewUsers(d') for all d' &lt;= d</div>
    <div class="desc">累计用户数 = 截至该日的所有新增用户之和</div>

    <div class="formula">DoD(d) = (NewUsers(d) - NewUsers(d-1)) / NewUsers(d-1) × 100%</div>
    <div class="desc">日环比增长率</div>

    <div class="formula">WeeklyNewUsers(w) = |{{ u : first_date(u) ∈ week_w }}|</div>
    <div class="desc">周新增用户数 = 首次出现日期落在该ISO周内的用户数量 (周一至周日)</div>

    <div class="formula">WoW(w) = (WeeklyNewUsers(w) - WeeklyNewUsers(w-1)) / WeeklyNewUsers(w-1) × 100%</div>
    <div class="desc">周环比增长率</div>

    <div class="formula">CumulativePct(d) = Cumulative(d) / TotalUsers × 100%</div>
    <div class="desc">累计渗透率 = 累计用户 / 总用户</div>

    <h3 style="margin-top:16px">埋点说明</h3>
    <p>用户标识: <code>reduser_id</code> (用户唯一标识)</p>
    <p>时间字段: <code>start_time_nano</code> (事件开始时间戳)</p>
    <p>事件名称: <code>span_name</code> (埋点事件名, 如 discovery_page_pageshow, post_card_click 等)</p>
    <p style="color:#636e72; font-size:13px; margin-top:8px">
        {report['calculation_methodology']['trigger_definition']}
    </p>
</div>

<!-- 日增长趋势 -->
<h2>日新增用户趋势</h2>
<div class="chart-row">
    <div class="chart-box">
        <canvas id="dailyNewChart"></canvas>
    </div>
    <div class="chart-box">
        <canvas id="dailyCumChart"></canvas>
    </div>
</div>
<div class="chart-row">
    <div class="chart-box full">
        <canvas id="dailyDodChart"></canvas>
    </div>
</div>

<!-- 周增长趋势 -->
<h2>周新增用户趋势</h2>
<div class="chart-row">
    <div class="chart-box">
        <canvas id="weeklyNewChart"></canvas>
    </div>
    <div class="chart-box">
        <canvas id="weeklyCumChart"></canvas>
    </div>
</div>

<!-- 日数据表 -->
<h2>日新增用户明细</h2>
<div class="chart-box">
<table class="data-table">
<thead>
<tr>
    <th>日期</th><th>新增用户</th><th>累计用户</th><th>累计渗透率</th><th>日环比增长率</th>
</tr>
</thead>
<tbody>
{''.join(f'''<tr>
    <td>{d['date']}</td>
    <td><strong>{d['new_users']}</strong></td>
    <td>{d['cumulative_users']}</td>
    <td>{d['cumulative_pct']}%</td>
    <td class="{'positive' if d['dod_growth_rate'] is not None and d['dod_growth_rate'] >= 0 else 'negative'}">
        {f"{d['dod_growth_rate']:.1f}%" if d['dod_growth_rate'] is not None else '-'}
    </td>
</tr>''' for d in daily_data)}
</tbody>
</table>
</div>

<!-- 周数据表 -->
<h2>周新增用户明细</h2>
<div class="chart-box">
<table class="data-table">
<thead>
<tr>
    <th>周</th><th>起始</th><th>结束</th><th>新增用户</th><th>累计用户</th><th>累计渗透率</th><th>周环比增长率</th>
</tr>
</thead>
<tbody>
{''.join(f'''<tr>
    <td>{w['week']}</td>
    <td>{w['week_start']}</td>
    <td>{w['week_end']}</td>
    <td><strong>{w['new_users']}</strong></td>
    <td>{w['cumulative_users']}</td>
    <td>{w['cumulative_pct']}%</td>
    <td class="{'positive' if w['wow_growth_rate'] is not None and w['wow_growth_rate'] >= 0 else 'negative'}">
        {f"{w['wow_growth_rate']:.1f}%" if w['wow_growth_rate'] is not None else '-'}
    </td>
</tr>''' for w in weekly_data)}
</tbody>
</table>
</div>

<!-- 新用户首次Trigger -->
<h2>新用户首次触发事件分布 (埋点Trigger)</h2>
<div class="chart-row">
    <div class="chart-box">
        <canvas id="triggerChart"></canvas>
    </div>
    <div class="chart-box">
        <h3>首次触发事件明细</h3>
        <div class="trigger-list">
{''.join(f'''<div class="trigger-item"><span class="name">{k}</span><span class="count">{v}</span></div>''' for k, v in trigger_items.items())}
        </div>
    </div>
</div>

<!-- 新用户首日行为 -->
<h2>新用户首日行为分析</h2>
<div class="chart-row">
    <div class="chart-box">
        <canvas id="behaviorChart"></canvas>
    </div>
    <div class="chart-box">
        <h3>首日行为概况</h3>
        <table class="data-table">
            <tr><td>首日人均事件数</td><td><strong>{report['new_user_behavior']['first_day_avg_events']}</strong></td></tr>
            <tr><td>首日中位数事件数</td><td><strong>{report['new_user_behavior']['first_day_median_events']}</strong></td></tr>
            <tr><td>首日人均事件类型</td><td><strong>{report['new_user_behavior']['first_day_avg_event_types']}</strong></td></tr>
            <tr><td>仅首日活跃用户</td><td><strong>{report['new_user_behavior']['single_day_users']}</strong> ({report['new_user_behavior']['single_day_pct']}%)</td></tr>
            <tr><td>多日活跃用户</td><td><strong>{report['new_user_behavior']['multi_day_users']}</strong></td></tr>
            <tr><td>平均生命周期</td><td><strong>{report['new_user_behavior']['lifespan_stats']['mean_days']}</strong> 天</td></tr>
            <tr><td>中位生命周期</td><td><strong>{report['new_user_behavior']['lifespan_stats']['median_days']}</strong> 天</td></tr>
        </table>
    </div>
</div>

</div>

<script>
// Common chart options
const commonOpts = {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'top' }} }}
}};

// Daily New Users Bar + Line
new Chart(document.getElementById('dailyNewChart'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(daily_dates)},
        datasets: [{{
            label: '日新增用户',
            data: {json.dumps(daily_new)},
            backgroundColor: 'rgba(255,36,66,0.7)',
            borderRadius: 4
        }}]
    }},
    options: {{ ...commonOpts, plugins: {{ ...commonOpts.plugins, title: {{ display: true, text: '日新增用户数' }} }} }}
}});

// Daily Cumulative
new Chart(document.getElementById('dailyCumChart'), {{
    type: 'line',
    data: {{
        labels: {json.dumps(daily_dates)},
        datasets: [
            {{
                label: '累计用户数',
                data: {json.dumps(daily_cum)},
                borderColor: '#ff2442',
                backgroundColor: 'rgba(255,36,66,0.1)',
                fill: true,
                tension: 0.3,
                yAxisID: 'y'
            }},
            {{
                label: '累计渗透率(%)',
                data: {json.dumps(daily_pct)},
                borderColor: '#636e72',
                borderDash: [5, 5],
                tension: 0.3,
                yAxisID: 'y1'
            }}
        ]
    }},
    options: {{
        ...commonOpts,
        plugins: {{ title: {{ display: true, text: '累计用户增长曲线' }} }},
        scales: {{
            y: {{ type: 'linear', position: 'left', title: {{ display: true, text: '累计用户数' }} }},
            y1: {{ type: 'linear', position: 'right', title: {{ display: true, text: '渗透率(%)' }}, min: 0, max: 100, grid: {{ drawOnChartArea: false }} }}
        }}
    }}
}});

// Daily DoD Growth Rate
new Chart(document.getElementById('dailyDodChart'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(daily_dates)},
        datasets: [{{
            label: '日环比增长率(%)',
            data: {json.dumps(daily_dod)},
            backgroundColor: daily_dod.map(v => v >= 0 ? 'rgba(0,184,148,0.7)' : 'rgba(255,36,66,0.7)'),
            borderRadius: 4
        }}]
    }},
    options: {{ ...commonOpts, plugins: {{ title: {{ display: true, text: '日环比增长率' }} }} }}
}});

// Weekly New Users
new Chart(document.getElementById('weeklyNewChart'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(weekly_labels)},
        datasets: [{{
            label: '周新增用户',
            data: {json.dumps(weekly_new)},
            backgroundColor: 'rgba(255,36,66,0.7)',
            borderRadius: 4
        }}]
    }},
    options: {{ ...commonOpts, plugins: {{ title: {{ display: true, text: '周新增用户数' }} }} }}
}});

// Weekly Cumulative
new Chart(document.getElementById('weeklyCumChart'), {{
    type: 'line',
    data: {{
        labels: {json.dumps(weekly_labels)},
        datasets: [
            {{
                label: '累计用户数',
                data: {json.dumps(weekly_cum)},
                borderColor: '#ff2442',
                backgroundColor: 'rgba(255,36,66,0.1)',
                fill: true,
                tension: 0.3,
                yAxisID: 'y'
            }},
            {{
                label: '累计渗透率(%)',
                data: {json.dumps(weekly_pct)},
                borderColor: '#636e72',
                borderDash: [5, 5],
                tension: 0.3,
                yAxisID: 'y1'
            }}
        ]
    }},
    options: {{
        ...commonOpts,
        plugins: {{ title: {{ display: true, text: '周累计用户增长' }} }},
        scales: {{
            y: {{ type: 'linear', position: 'left', title: {{ display: true, text: '累计用户数' }} }},
            y1: {{ type: 'linear', position: 'right', title: {{ display: true, text: '渗透率(%)' }}, min: 0, max: 100, grid: {{ drawOnChartArea: false }} }}
        }}
    }}
}});

// First Trigger Events
new Chart(document.getElementById('triggerChart'), {{
    type: 'doughnut',
    data: {{
        labels: {json.dumps(trigger_labels[:10])},
        datasets: [{{
            data: {json.dumps(trigger_values[:10])},
            backgroundColor: [
                '#ff2442', '#e17055', '#fdcb6e', '#00b894', '#0984e3',
                '#6c5ce7', '#a29bfe', '#fab1a0', '#55efc4', '#74b9ff'
            ]
        }}]
    }},
    options: {{ ...commonOpts, plugins: {{ title: {{ display: true, text: '首次触发事件分布' }} }} }}
}});

// First Day Behavior
new Chart(document.getElementById('behaviorChart'), {{
    type: 'bar',
    data: {{
        labels: {json.dumps(beh_labels)},
        datasets: [{{
            label: '首日事件次数',
            data: {json.dumps(beh_values)},
            backgroundColor: 'rgba(108,92,231,0.7)',
            borderRadius: 4
        }}]
    }},
    options: {{
        ...commonOpts,
        indexAxis: 'y',
        plugins: {{ title: {{ display: true, text: '新用户首日行为 Top 10' }} }}
    }}
}});
</script>
</body>
</html>"""

    return html


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 加载数据
    df = load_data()

    # 计算新用户增长
    growth_data = compute_new_user_growth(df)

    # 新用户行为分析
    behavior_data = compute_new_user_behavior(df, growth_data['user_first'])

    # 埋点Trigger分析
    trigger_data = get_trigger_events(df)

    # 构建JSON报告
    report = build_json_report(growth_data, behavior_data, trigger_data, df)

    # 保存JSON
    json_path = os.path.join(OUTPUT_DIR, 'new_user_growth.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(report), f, ensure_ascii=False, indent=2)
    print(f"\n[保存] JSON: {json_path}")

    # 保存HTML
    html = generate_html_report(report)
    html_path = os.path.join(OUTPUT_DIR, 'new_user_growth_report.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[保存] HTML: {html_path}")

    # 打印摘要
    print("\n" + "=" * 70)
    print("新用户增长分析完成!")
    print("=" * 70)
    print(f"  总新用户: {report['summary']['total_new_users']}")
    print(f"  日均新增: {report['summary']['avg_daily_new_users']}")
    print(f"  最高单日: {report['summary']['max_daily_new_users']['count']} ({report['summary']['max_daily_new_users']['date']})")
    print(f"  周均新增: {report['summary']['avg_weekly_new_users']}")


if __name__ == '__main__':
    main()
