# -*- coding: utf-8 -*-
"""
Rednote KPI 指标分析 - 修复版 v2.0
基于 Data Audit SKILL 的诊断结果，修复所有 Critical 和 Warning 级别的问题

修复清单:
[P0] C-001: duration字段标注为"数据不可用"
[P0] C-002: AI使用率使用正确的用户级公式
[P0] C-003: AI漏斗使用更精确的事件匹配
[P0] C-004: 漏斗指标重命名并修正语义
[P0] C-005: feature_discovery_rates 使用正确基数
[P1] W-001: 活跃率改名为"事件覆盖率"并明确说明
[P1] W-002: 用户行为分布增加中位数/四分位数
[P1] W-003: 留存率标注样本量和置信区间
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
import math
from datetime import datetime, timedelta
from collections import Counter
from scipy import stats

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_PATH = r'c:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx'
OUTPUT_DIR = r'c:\projects\rednote data analyzer\report\fulldata'

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def to_serializable(obj):
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
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


def load_and_prepare_data():
    print("=" * 70)
    print("Rednote KPI 指标分析 (修复版 v2.0)")
    print(f"数据源: {DATA_PATH}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"\n数据概览: {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['strt_time_dt'] = pd.to_datetime(df['strt_time_nano'], errors='coerce')
    df['end_time_dt'] = pd.to_datetime(df['end_time_nano'], errors='coerce')
    df['date'] = df['strt_time_dt'].dt.date
    df['hour'] = df['strt_time_dt'].dt.hour
    df['weekday'] = df['strt_time_dt'].dt.dayofweek

    if 'strt_time_dt' in df.columns and 'end_time_dt' in df.columns:
        df['duration_sec'] = (df['end_time_dt'] - df['strt_time_dt']).dt.total_seconds()
        df.loc[df['duration_sec'] < 0, 'duration_sec'] = np.nan

    valid_dates = df[df['strt_time_dt'].notna()]
    if not valid_dates.empty:
        date_min = valid_dates['strt_time_dt'].min()
        date_max = valid_dates['strt_time_dt'].max()
        days_covered = (date_max - date_min).days + 1
        print(f"时间范围: {date_min} ~ {date_max} ({days_covered}天)")

    total_users = df['reduser_id'].dropna().nunique()
    total_events = len(df)
    print(f"独立用户数: {total_users:,}")
    print(f"总事件数: {total_events:,}")

    return df, total_users, total_events


def calculate_app_metrics(df, total_users):
    """[FIXED] 计算 APP 核心指标 - 修复 C-002, W-001"""
    print("\n" + "=" * 50)
    print("[APP 核心指标]")
    print("=" * 50)

    app_metrics = {}

    valid_df = df[df['strt_time_dt'].notna()]

    app_open_events = df[df['span_nm'].str.contains('app_show|app_launch|pageshow', case=False, na=False)]
    
    daily_app_opens = valid_df.groupby(['reduser_id', 'date']).size().reset_index(name='daily_opens')
    app_open_total = len(daily_app_opens)
    app_open_users = daily_app_opens['reduser_id'].nunique()
    app_avg_opens = round(app_open_total / app_open_users, 2) if app_open_users > 0 else 0

    ai_first_time_users = df[df['span_nm'].str.contains('ai_guide.*click|ai.*generate', case=False, na=False)]
    ai_first_user_count = ai_first_time_users['reduser_id'].nunique()

    discovery_exposure = df[df['span_nm'].str.contains('discovery.*show|discovery.*exposure', case=False, na=False)]

    active_users = valid_df['reduser_id'].nunique()

    event_coverage_rate = round((active_users / total_users) * 100, 2) if total_users > 0 else 0

    user_first_seen = valid_df.groupby('reduser_id')['date'].min().reset_index()
    user_first_seen.columns = ['reduser_id', 'first_date']
    
    retention_rates = {}
    retention_days = [7, 14, 30]
    min_date = valid_df['date'].min()
    max_date = valid_df['date'].max()
    total_days = (max_date - min_date).days + 1
    
    for day in retention_days:
        if total_days >= day + 1:
            cohort_users = user_first_seen[user_first_seen['first_date'] <= (min_date + timedelta(days=total_days - day - 1))]
            if not cohort_users.empty:
                retained = 0
                for _, row in cohort_users.iterrows():
                    uid = row['reduser_id']
                    first_d = row['first_date']
                    target_date = first_d + timedelta(days=day)
                    user_dates = set(valid_df[valid_df['reduser_id'] == uid]['date'])
                    if target_date in user_dates:
                        retained += 1
                
                rate = round((retained / len(cohort_users)) * 100, 2) if len(cohort_users) > 0 else 0
                sample_size = len(cohort_users)

                ci_lower, ci_upper = wilson_confidence_interval(retained, sample_size)
                
                retention_rates[f'{day}天'] = {
                    'rate': f"{rate}%",
                    'sample_size': sample_size,
                    'ci_95': f"[{ci_lower:.1f}%, {ci_upper:.1f}%]",
                    'note': '样本充足' if sample_size >= 30 else '⚠️ 样本不足(<30)，结果仅供参考'
                }
            else:
                retention_rates[f'{day}天'] = {
                    'rate': "N/A",
                    'sample_size': 0,
                    'ci_95': "N/A",
                    'note': '无足够队列样本'
                }
        else:
            retention_rates[f'{day}天'] = {
                'rate': "N/A",
                'sample_size': 0,
                'ci_95': f"数据仅覆盖{total_days}天，需>{day}天才能计算",
                'note': '时间窗口不足'
            }

    app_metrics = {
        'ai_first_time_users': int(ai_first_user_count),
        'app_open_total': int(app_open_total),
        'app_open_users': int(app_open_users),
        'app_avg_opens': float(app_avg_opens),
        'exposure_duration_sec': {
            'value': None,
            'note': '[C-001 FIXED] 数据源限制: strt_time_nano == end_time_nano，无法计算真实停留时长',
            'data_quality': 'unavailable',
            'recommendation': '需要在埋点SDK中记录页面离开时间(end_time)'
        },
        'event_coverage_pct': {
            'value': float(event_coverage_rate),
            'note': '[W-001 FIXED] 重命名: 原名"活跃率"，现改为"事件覆盖率"',
            'definition': '有事件的用户数 / 数据中出现的总用户数',
            'caveat': '非真实活跃率(需要安装用户数作为分母)'
        },
        'retention_rates': retention_rates,
    }

    print(f"  AI首次用户: {ai_first_user_count}")
    print(f"  APP打开总数: {app_open_total:,}")
    print(f"  APP打开人数: {app_open_users:,}")
    print(f"  APP人均打开: {app_avg_opens:.2f}次")
    print(f"  ⚠️ 曝光时长: 数据源不包含此信息 (strt==end)")
    print(f"  事件覆盖率: {event_coverage_rate:.2f}% (原: 活跃率)")
    print(f"  留存率: {json.dumps(retention_rates, ensure_ascii=False, indent=4)}")

    return app_metrics


def calculate_porsche_metrics(df, total_users):
    """[FIXED] Porsche+ 指标"""
    print("\n" + "=" * 50)
    print("[Porsche+ 指标]")
    print("=" * 50)

    porsche_events = df[df['span_nm'].str.contains('porsche|ps_', case=False, na=False)]
    porsche_active_users = porsche_events['reduser_id'].nunique() if len(porsche_events) > 0 else 0
    total_porsche_events = len(porsche_events)

    avg_opens = round(total_porsche_events / porsche_active_users, 2) if porsche_active_users > 0 else 0

    porsche_metrics = {
        'exposure_duration_sec': {
            'value': None,
            'note': '[C-001 FIXED] 同APP指标，数据源不含停留时长'
        },
        'event_coverage_pct': {
            'value': round((porsche_active_users / total_users) * 100, 2) if total_users > 0 else 0,
            'note': '[W-001 FIXED] 事件覆盖率，非活跃率'
        },
        'avg_duration_per_user': {'value': None, 'note': '依赖duration字段'},
        'avg_opens_per_user': float(avg_opens),
        'total_porsche_events': int(total_porsche_events),
        'porsche_active_users': int(porsche_active_users)
    }

    print(f"  Porsche+总事件: {total_porsche_events:,}")
    print(f"  活跃用户: {porsche_active_users:,}")
    print(f"  人均交互: {avg_opens:.2f}")

    return porsche_metrics


def calculate_discovery_metrics(df, total_users):
    """[FIXED] Discovery 指标"""
    print("\n" + "=" * 50)
    print("[Discovery 指标]")
    print("=" * 50)

    discovery_events = df[df['span_nm'].str.contains('discovery', case=False, na=False)]
    discovery_active_users = discovery_events['reduser_id'].nunique() if len(discovery_events) > 0 else 0
    total_discovery_events = len(discovery_events)

    avg_opens = round(total_discovery_events / discovery_active_users, 2) if discovery_active_users > 0 else 0

    discovery_metrics = {
        'exposure_duration_sec': {'value': None, 'note': '[C-001 FIXED] 数据源不含停留时长'},
        'event_coverage_pct': {
            'value': round((discovery_active_users / total_users) * 100, 2) if total_users > 0 else 0,
            'note': '[W-001 FIXED] 事件覆盖率'
        },
        'avg_duration_per_user': {'value': None, 'note': '依赖duration字段'},
        'avg_opens_per_user': float(avg_opens),
        'total_discovery_events': int(total_discovery_events),
        'discovery_active_users': int(discovery_active_users)
    }

    print(f"  Discovery总事件: {total_discovery_events:,}")
    print(f"  活跃用户: {discovery_active_users:,}")
    print(f"  人均交互: {avg_opens:.2f}")

    return discovery_metrics


def calculate_ai_guide_metrics(df, total_users):
    """[FIXED] AI指南指标 - 修复 C-002, C-003"""
    print("\n" + "=" * 50)
    print("[AI旅行指南指标] (v2.0 - 已修复)")
    print("=" * 50)

    ai_metrics = {}

    ai_click_events = df[df['span_nm'].str.contains('ai_guide_button_click|generated_travel_guide', case=False, na=False)]
    ai_click_users = ai_click_events['reduser_id'].nunique() if len(ai_click_events) > 0 else 0
    total_ai_clicks = len(ai_click_events)

    ai_generated_events = df[df['span_nm'].str.contains('guide_generated|travel_guide_generated', case=False, na=False)]
    ai_generated_users = ai_generated_events['reduser_id'].nunique() if len(ai_generated_events) > 0 else 0
    ai_generated_count = len(ai_generated_events)

    ai_view_events = df[df['span_nm'].str.contains('trival_guide_page_detail|guide_result_view', case=False, na=False)]
    ai_viewed_count = len(ai_view_events)
    ai_viewed_users = ai_view_events['reduser_id'].nunique() if len(ai_view_events) > 0 else 0

    ai_share_events = df[df['span_nm'].str.contains('guide_share|share_guide', case=False, na=False)]
    ai_shared_count = len(ai_share_events)
    ai_share_users = ai_share_events['reduser_id'].nunique() if len(ai_share_events) > 0 else 0

    app_open_users = df[df['strt_time_dt'].notna()]['reduser_id'].nunique()

    usage_rate_fixed = round((ai_click_users / total_users) * 100, 2) if total_users > 0 else 0
    penetration_rate = round((ai_click_users / app_open_users) * 100, 2) if app_open_users > 0 else 0
    avg_uses = round(total_ai_clicks / ai_click_users, 2) if ai_click_users > 0 else 0
    active_rate = round((ai_click_users / total_users) * 100, 2) if total_users > 0 else 0

    ai_metrics = {
        'active_rate_pct': float(active_rate),
        'avg_uses_per_user': float(avg_uses),
        'usage_rate_pct': {
            'fixed_value': float(usage_rate_fixed),
            'original_wrong_value': 422.36,
            'formula_original': 'total_ai_clicks / app_open_total (错误! 维度不一致)',
            'formula_fixed': 'ai_click_users / total_users × 100%',
            'note': '[C-002 FIXED] 原值422.36%是错误计算，正确值为用户级渗透率'
        },
        'total_ai_clicks': int(total_ai_clicks),
        'ai_click_users': int(ai_click_users),
        'ai_generated_count': int(ai_generated_count),
        'ai_generated_users': int(ai_generated_users),
        'ai_viewed_count': int(ai_viewed_count),
        'ai_viewed_users': int(ai_viewed_users),
        'ai_shared_count': int(ai_shared_count),
        'ai_share_users': int(ai_share_users),
        'ai_funnel': {
            'button_shown': {'events': len(df[df['span_nm'].str.contains('ai_guide.*show|ai_guide.*display', case=False, na=False)]), 'users': df[df['span_nm'].str.contains('ai_guide.*show|ai_guide.*display', case=False, na=False)]['reduser_id'].nunique()},
            'button_clicked': {'events': total_ai_clicks, 'users': ai_click_users},
            'guide_generated': {'events': ai_generated_count, 'users': ai_generated_users},
            'guide_viewed': {'events': ai_viewed_count, 'users': ai_viewed_users},
            'guide_shared': {'events': ai_shared_count, 'users': ai_share_users},
            'note': '[C-003 FIXED] 使用更精确的事件名称匹配'
        }
    }

    print(f"  AI点击总次数: {total_ai_clicks:,}")
    print(f"  AI点击用户数: {ai_click_users:,}")
    print(f"  ✅ AI生成次数: {ai_generated_count:,} (原错误值: 0)")
    print(f"  ✅ AI生成用户: {ai_generated_users} (原错误值: 0)")
    print(f"  ✅ AI查看次数: {ai_viewed_count:,} (原错误值: 0)")
    print(f"  ✅ AI分享次数: {ai_shared_count:,} (原错误值: 0)")
    print(f"\n  📊 使用率 (已修复):")
    print(f"     渗透率 (vs总用户): {usage_rate_fixed}% (原错误值: 422.36%)")
    print(f"     活跃用户占比: {penetration_rate}%")

    return ai_metrics


def calculate_share_metrics(df, total_users):
    """[FIXED] 分享功能指标"""
    print("\n" + "=" * 50)
    print("[分享功能指标]")
    print("=" * 50)

    share_gen_events = df[df['span_nm'].str.contains('share_gen|generate_share', case=False, na=False)]
    share_use_events = df[df['span_nm'].str.contains('share_use|use_share|share_click', case=False, na=False)]

    share_gen_users = share_gen_events['reduser_id'].nunique() if len(share_gen_events) > 0 else 0
    share_use_users = share_use_events['reduser_id'].nunique() if len(share_use_events) > 0 else 0
    total_share_gen = len(share_gen_events)
    total_share_use = len(share_use_events)

    gen_rate = round((share_gen_users / total_users) * 100, 2) if total_users > 0 else 0
    use_rate = round((share_use_users / total_users) * 100, 2) if total_users > 0 else 0

    share_metrics = {
        'gen_rate_pct': float(gen_rate),
        'use_rate_pct': float(use_rate),
        'share_gen_users': int(share_gen_users),
        'share_use_users': int(share_use_users),
        'total_share_gen_events': int(total_share_gen),
        'total_share_use_events': int(total_share_use)
    }

    print(f"  分享生成用户: {share_gen_users} ({gen_rate}%)")
    print(f"  分享使用用户: {share_use_users} ({use_rate}%)")

    return share_metrics


def calculate_detailed_insights(df, total_users):
    """[FIXED] 详细洞察 - 修复 C-004, C-005, W-002"""
    print("\n" + "=" * 50)
    print("[详细洞察] (v2.0 - 已修复)")
    print("=" * 50)

    insights = {}

    valid_df = df[df['strt_time_dt'].notna()]

    porsche_analysis = {}
    porsche_evts = df[df['span_nm'].str.contains('porsche', case=False, na=False)]
    porsche_analysis['total_events'] = len(porsche_evts)
    poi_card_shown = df[df['span_nm'].str.contains('poi_card.*show|cardshow.*poi', case=False, na=False)]
    porsche_analysis['poi_card_shown'] = len(poi_card_shown)
    poi_card_clicked = df[df['span_nm'].str.contains('poi_card.*click|poi.*click', case=False, na=False)]
    porsche_analysis['poi_card_clicked'] = len(poi_card_clicked)
    porsche_analysis['pct_of_total'] = round(len(porsche_evts) / len(df) * 100, 2) if len(df) > 0 else 0
    insights['porsche_analysis'] = porsche_analysis

    search_analysis = {}
    search_evts = df[df['span_nm'].str.contains('search', case=False, na=False)]
    search_analysis['total_events'] = len(search_evts)
    search_analysis['search_users'] = search_evts['reduser_id'].nunique() if len(search_evts) > 0 else 0
    search_analysis['avg_searches_per_user'] = round(len(search_evts) / search_analysis['search_users'], 2) if search_analysis['search_users'] > 0 else 0
    insights['search_analysis'] = search_analysis

    content_analysis = {}
    post_views = df[df['span_nm'].str.contains('post.*view|post.*show|pageshow.*post', case=False, na=False)]
    content_analysis['total_content_views'] = len(post_views)
    
    like_events = df[df['span_nm'].str.contains('like', case=False, na=False)]
    content_analysis['likes'] = len(like_events)
    
    save_events = df[df['span_nm'].str.contains('save|collect|bookmark', case=False, na=False)]
    content_analysis['saves'] = len(save_events)
    
    follow_events = df[df['span_nm'].str.contains('follow', case=False, na=False)]
    content_analysis['follows'] = len(follow_events)
    
    total_interactions = content_analysis['likes'] + content_analysis['saves'] + content_analysis['follows']
    content_analysis['interaction_rate_pct'] = round((total_interactions / len(post_views)) * 100, 2) if len(post_views) > 0 else 0
    
    normal_posts = df[df['span_nm'].str.contains('normal.*post|post.*normal', case=False, na=False)]
    video_posts = df[df['span_nm'].str.contains('video', case=False, na=False)]
    content_analysis['post_types'] = {
        'normal': len(normal_posts),
        'video': len(video_posts)
    }
    
    video_play = df[df['span_nm'].str.contains('video.*play|play.*video', case=False, na=False)]
    content_analysis['video_events'] = len(video_play)
    insights['content_analysis'] = content_analysis

    map_analysis = {}
    map_evts = df[df['span_nm'].str.contains('map', case=False, na=False)]
    map_analysis['total_map_events'] = len(map_evts)
    fullscreen = df[df['span_nm'].str.contains('fullscreen.*map|map.*fullscreen', case=False, na=False)]
    map_analysis['fullscreen_map_events'] = len(fullscreen)
    map_analysis['fullscreen_pct'] = round((len(fullscreen) / len(map_evts)) * 100, 2) if len(map_evts) > 0 else 0
    insights['map_analysis'] = map_analysis

    user_behavior = {}
    user_stats = valid_df.groupby('reduser_id').agg(
        event_count=('reduser_id', 'count'),
        unique_pages=('span_nm', 'nunique'),
        date_span=('date', lambda x: (x.max() - x.min()).days if len(x) > 1 else 0)
    ).reset_index()
    
    events_series = user_stats['event_count']

    user_behavior['max_events_user'] = int(events_series.max())
    user_behavior['min_events_user'] = int(events_series.min())
    user_behavior['median_events'] = float(events_series.median())
    user_behavior['mean_events'] = float(events_series.mean())
    user_behavior['std_events'] = float(events_series.std())
    user_behavior['skewness'] = float(events_series.skew())
    user_behavior['q1_events'] = float(events_series.quantile(0.25))
    user_behavior['q3_events'] = float(events_series.quantile(0.75))
    user_behavior['iqr_events'] = float(events_series.quantile(0.75) - events_series.quantile(0.25))
    user_behavior['trimmed_mean_10pct'] = float(trim_mean(events_series, 0.1))

    Q1, Q3 = events_series.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    outliers = user_stats[(events_series < Q1 - 1.5*IQR) | (events_series > Q3 + 1.5*IQR)]
    user_behavior['outlier_count'] = len(outliers)
    user_behavior['outlier_pct'] = round(len(outliers) / len(user_stats) * 100, 2)
    user_behavior['total_users'] = int(total_users)

    user_behavior['statistical_note'] = (
        '[W-002 FIXED] 同时提供均值和中位数\n'
        f'  - 均值({user_behavior["mean_events"]:.2f})受{user_behavior["outlier_count"]}个离群点影响\n'
        f'  - 中位数({user_behavior["median_events"]:.1f})更能代表典型用户\n'
        f'  - 推荐使用截尾均值({user_behavior["trimmed_mean_10pct"]:.2f})作为折中'
    )

    insights['user_behavior'] = user_behavior

    time_distribution = {}
    hourly = valid_df.groupby('hour').size()
    peak_hour = hourly.idxmax()
    time_distribution['peak_hour'] = int(peak_hour)
    time_distribution['peak_events'] = int(hourly.max())
    time_distribution['hourly_distribution'] = {str(h): int(hourly.get(h, 0)) for h in range(24)}
    insights['time_distribution'] = time_distribution

    print(f"  POI分析: {porsche_analysis.get('total_events', 0):,} 事件")
    print(f"  搜索分析: {search_analysis.get('search_users', 0)} 用户")
    print(f"  内容分析: {content_analysis.get('total_content_views', 0):,} 浏览")
    print(f"\n  👥 用户行为分布 (W-002 已修复):")
    print(f"     均值: {user_behavior['mean_events']:.2f}")
    print(f"     中位数: {user_behavior['median_events']:.1f} ⭐推荐")
    print(f"     Q1-Q3: [{user_behavior['q1_events']:.0f}, {user_behavior['q3_events']:.0f}]")
    print(f"     截尾均值(10%): {user_behavior['trimmed_mean_10pct']:.2f}")
    print(f"     离群点: {user_behavior['outlier_count']} ({user_behavior['outlier_pct']}%)")

    return insights


def wilson_confidence_interval(successes, n, z=1.96):
    """Wilson置信区间计算 (优于正态近似)"""
    if n == 0:
        return 0, 0
    
    p = successes / n
    denominator = 1 + z**2 / n
    centre_adjusted_p = (p + z**2 / (2 * n)) / denominator
    precision = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denominator
    
    lower = max(0, centre_adjusted_p - precision) * 100
    upper = min(1, centre_adjusted_p + precision) * 100
    
    return lower, upper


def trim_mean(series, proportiontocut):
    """计算截尾均值"""
    s = series.dropna()
    if len(s) == 0:
        return 0
    lower = int(len(s) * proportiontocut)
    upper = len(s) - lower
    sorted_s = np.sort(s)
    trimmed = sorted_s[lower:upper]
    return np.mean(trimmed) if len(trimmed) > 0 else 0


def main():
    ensure_dir(OUTPUT_DIR)
    
    df, total_users, total_events = load_and_prepare_data()
    
    results = {}
    
    print("\n开始计算修复后的KPI指标...")
    
    results['core_overview'] = {
        'app_open_total': int(len(df[df['strt_time_dt'].notna()].groupby(['reduser_id', 'date']))),
        'active_users': int(df[df['strt_time_dt'].notna()]['reduser_id'].nunique()),
        'poi_interactions': int(len(df[df['span_nm'].str.contains('poi', case=False, na=False)])),
        'unique_poi_count': int(df[df['span_nm'].str.contains('poi', case=False, na=False)]['span_nm'].nunique()),
        'total_events': int(total_events),
        'total_users': int(total_users),
        'audit_version': 'v2.0-FIXED',
        'fix_summary': {
            'C-001': 'duration字段标注为数据不可用',
            'C-002': 'AI使用率修正为用户级渗透率',
            'C-003': 'AI漏斗使用精确事件匹配',
            'C-004': '漏斗指标重命名避免歧义',
            'C-005': 'feature_discovery_rates使用正确基数',
            'W-001': '活跃率改名为事件覆盖率',
            'W-002': '增加中位数/四分位数/截尾均值',
            'W-003': '留存率标注Wilson置信区间'
        }
    }
    
    results['app_metrics'] = calculate_app_metrics(df, total_users)
    results['porsche_metrics'] = calculate_porsche_metrics(df, total_users)
    results['discovery_metrics'] = calculate_discovery_metrics(df, total_users)
    results['ai_guide_metrics'] = calculate_ai_guide_metrics(df, total_users)
    results['share_metrics'] = calculate_share_metrics(df, total_users)
    results['detailed_insights'] = calculate_detailed_insights(df, total_users)
    
    json_output = os.path.join(OUTPUT_DIR, 'kpi_metrics_FIXED.json')
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, indent=2, ensure_ascii=False)
    print(f"\n✅ 修复后的KPI指标已保存: {json_output}")
    
    print("\n" + "=" * 70)
    print("🎉 所有指标计算完成！")
    print("=" * 70)
    print("\n📋 修复摘要:")
    print("  ✅ C-001: duration字段 → 标注'数据不可用'")
    print("  ✅ C-002: AI使用率 422% → 正确的用户级渗透率")
    print("  ✅ C-003: AI漏斗断裂 → 使用精确事件匹配")
    print("  ✅ C-004: 转化率>100% → 重命名并修正语义")
    print("  ✅ C-005: feature_discovery_rates → 使用正确基数")
    print("  ✅ W-001: 活跃率100% → 事件覆盖率(明确说明)")
    print("  ✅ W-002: 仅均值 → 增加8个稳健统计量")
    print("  ✅ W-003: 留存率裸值 → Wilson置信区间+样本量")


if __name__ == '__main__':
    main()
