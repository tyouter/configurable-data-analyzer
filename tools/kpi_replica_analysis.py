# -*- coding: utf-8 -*-
"""
Rednote 原报告 KPI 指标复刻脚本
基于更新后的数据重新计算所有原报告的核心 KPI 指标
输出到 report/fulldata/
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime, timedelta
from collections import Counter

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
    print("Rednote 原 KPI 指标复刻分析")
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
    """计算 APP 核心指标"""
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
    exposure_duration = discovery_exposure['duration_sec'].sum()
    if pd.isna(exposure_duration) or exposure_duration < 0:
        exposure_duration = 0

    active_users = valid_df['reduser_id'].nunique()
    app_active_rate = round((active_users / total_users) * 100, 2) if total_users > 0 else 0

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
                retention_rates[f'{day}天'] = f"{rate}%"
            else:
                retention_rates[f'{day}天'] = "N/A"
        else:
            retention_rates[f'{day}天'] = "N/A"

    app_metrics = {
        'ai_first_time_users': int(ai_first_user_count),
        'app_open_total': int(app_open_total),
        'app_open_users': int(app_open_users),
        'app_avg_opens': float(app_avg_opens),
        'exposure_duration_sec': float(exposure_duration),
        'active_rate_pct': float(app_active_rate),
        'retention_rates': retention_rates,
    }

    print(f"  AI首次用户: {ai_first_user_count}")
    print(f"  APP打开总数: {app_open_total:,}")
    print(f"  APP打开人数: {app_open_users:,}")
    print(f"  APP人均打开: {app_avg_opens:.2f}次")
    print(f"  曝光时长: {exposure_duration:.0f}秒")
    print(f"  活跃率: {app_active_rate:.2f}%")
    print(f"  留存率: {retention_rates}")

    return app_metrics


def calculate_porsche_metrics(df, total_users):
    """计算 Porsche+ 指标"""
    print("\n" + "=" * 50)
    print("[Porsche+ 指标]")
    print("=" * 50)

    porsche_df = df[df['span_nm'].str.contains('porsche', case=False, na=False)]

    porsche_exposure = porsche_df[porsche_df['span_nm'].str.contains('show|exposure|pageshow', case=False, na=False)]
    exposure_duration = porsche_exposure['duration_sec'].sum() if not porsche_exposure.empty else 0
    if pd.isna(exposure_duration) or exposure_duration < 0:
        exposure_duration = 0

    porsche_active_users = porsche_df['reduser_id'].nunique()
    porsche_active_rate = round((porsche_active_users / total_users) * 100, 2) if total_users > 0 else 0

    porsche_avg_duration = round(exposure_duration / porsche_active_users, 2) if porsche_active_users > 0 else 0

    porsche_page_opens = len(porsche_df[porsche_df['span_nm'].str.contains('pageshow|page_show', case=False, na=False)])
    porsche_avg_opens = round(porsche_page_opens / porsche_active_users, 2) if porsche_active_users > 0 else 0

    porsche_metrics = {
        'exposure_duration_sec': float(exposure_duration),
        'active_rate_pct': float(porsche_active_rate),
        'avg_duration_per_user': float(porsche_avg_duration),
        'avg_opens_per_user': float(porsche_avg_opens),
        'total_porsche_events': int(len(porsche_df)),
        'porsche_active_users': int(porsche_active_users),
    }

    print(f"  Porsche+总事件: {len(porsche_df):,}")
    print(f"  曝光时长: {exposure_duration:.0f}秒")
    print(f"  活跃率: {porsche_active_rate:.2f}%")
    print(f"  人均使用时长: {porsche_avg_duration:.2f}秒")
    print(f"  人均使用次数: {porsche_avg_opens:.2f}次")

    return porsche_metrics


def calculate_discovery_metrics(df, total_users):
    """计算 Discovery 页面指标"""
    print("\n" + "=" * 50)
    print("[Discovery 页面指标]")
    print("=" * 50)

    discovery_df = df[df['span_nm'].str.contains('discovery', case=False, na=False)]

    discovery_exposure = discovery_df[discovery_df['span_nm'].str.contains('show|exposure|pageshow', case=False, na=False)]
    exposure_duration = discovery_exposure['duration_sec'].sum() if not discovery_exposure.empty else 0
    if pd.isna(exposure_duration) or exposure_duration < 0:
        exposure_duration = 0

    discovery_active_users = discovery_df['reduser_id'].nunique()
    discovery_active_rate = round((discovery_active_users / total_users) * 100, 2) if total_users > 0 else 0

    discovery_avg_duration = round(exposure_duration / discovery_active_users, 2) if discovery_active_users > 0 else 0

    discovery_page_opens = len(discovery_df[discovery_df['span_nm'].str.contains('pageshow|page_show', case=False, na=False)])
    discovery_avg_opens = round(discovery_page_opens / discovery_active_users, 2) if discovery_active_users > 0 else 0

    discovery_metrics = {
        'exposure_duration_sec': float(exposure_duration),
        'active_rate_pct': float(discovery_active_rate),
        'avg_duration_per_user': float(discovery_avg_duration),
        'avg_opens_per_user': float(discovery_avg_opens),
        'total_discovery_events': int(len(discovery_df)),
        'discovery_active_users': int(discovery_active_users),
    }

    print(f"  Discovery总事件: {len(discovery_df):,}")
    print(f"  曝光时长: {exposure_duration:.0f}秒")
    print(f"  活跃率: {discovery_active_rate:.2f}%")
    print(f"  人均使用时长: {discovery_avg_duration:.2f}秒")
    print(f"  人均使用次数: {discovery_avg_opens:.2f}次")

    return discovery_metrics


def calculate_ai_guide_metrics(df, total_users, app_open_total):
    """计算 AI 路书指标"""
    print("\n" + "=" * 50)
    print("[AI 路书指标]")
    print("=" * 50)

    ai_click_df = df[df['span_nm'].str.contains('ai_guide.*click|ai.*button.*click', case=False, na=False)]
    ai_click_count = len(ai_click_df)
    ai_click_users = ai_click_df['reduser_id'].nunique()

    active_users = df[df['strt_time_dt'].notna()]['reduser_id'].nunique()
    ai_active_rate = round((ai_click_users / active_users) * 100, 2) if active_users > 0 else 0

    ai_avg_uses = round(ai_click_count / ai_click_users, 2) if ai_click_users > 0 else 0

    ai_usage_rate = round((ai_click_count / app_open_total) * 100, 2) if app_open_total > 0 else 0

    ai_generated = df[df['span_nm'].str.contains('ai_guide.*generat|ai.*guide.*confirm', case=False, na=False)]
    ai_generated_count = len(ai_generated)
    ai_generated_users = ai_generated['reduser_id'].nunique()

    ai_viewed = df[df['span_nm'].str.contains('ai_guide.*view|ai.*guide.*detail', case=False, na=False)]
    ai_viewed_count = len(ai_viewed)

    ai_shared = df[df['span_nm'].str.contains('ai_guide.*share|ai.*guide.*send', case=False, na=False)]
    ai_shared_count = len(ai_shared)

    ai_metrics = {
        'active_rate_pct': float(ai_active_rate),
        'avg_uses_per_user': float(ai_avg_uses),
        'usage_rate_pct': float(ai_usage_rate),
        'total_ai_clicks': int(ai_click_count),
        'ai_click_users': int(ai_click_users),
        'ai_generated_count': int(ai_generated_count),
        'ai_generated_users': int(ai_generated_users),
        'ai_viewed_count': int(ai_viewed_count),
        'ai_shared_count': int(ai_shared_count),
    }

    print(f"  AI点击总数: {ai_click_count:,}")
    print(f"  AI点击用户: {ai_click_users:,}")
    print(f"  AI活跃率: {ai_active_rate:.2f}%")
    print(f"  AI人均使用: {ai_avg_uses:.2f}次")
    print(f"  AI使用率: {ai_usage_rate:.2f}%")

    return ai_metrics


def calculate_share_metrics(df, total_users):
    """计算分享功能指标"""
    print("\n" + "=" * 50)
    print("[分享功能指标]")
    print("=" * 50)

    share_gen_df = df[df['span_nm'].str.contains('share.*code|share.*generat|qrcode', case=False, na=False)]
    share_gen_users = share_gen_df['reduser_id'].nunique()

    active_users = df[df['strt_time_dt'].notna()]['reduser_id'].nunique()
    share_gen_rate = round((share_gen_users / active_users) * 100, 2) if active_users > 0 else 0

    share_use_df = df[df['span_nm'].str.contains('share.*confirm|share.*add|itinerary.*add', case=False, na=False)]
    share_use_users = share_use_df['reduser_id'].nunique()
    share_use_rate = round((share_use_users / active_users) * 100, 2) if active_users > 0 else 0

    share_metrics = {
        'gen_rate_pct': float(share_gen_rate),
        'use_rate_pct': float(share_use_rate),
        'share_gen_users': int(share_gen_users),
        'share_use_users': int(share_use_users),
        'total_share_gen_events': int(len(share_gen_df)),
        'total_share_use_events': int(len(share_use_df)),
    }

    print(f"  分享码生成用户: {share_gen_users:,}")
    print(f"  分享码生成占比: {share_gen_rate:.2f}%")
    print(f"  分享码使用用户: {share_use_users:,}")
    print(f"  分享码使用占比: {share_use_rate:.2f}%")

    return share_metrics


def calculate_core_overview(df):
    """计算核心指标概览"""
    print("\n" + "=" * 50)
    print("[核心指标概览]")
    print("=" * 50)

    valid_df = df[df['strt_time_dt'].notna()]
    
    daily_app_opens = valid_df.groupby(['reduser_id', 'date']).size().reset_index(name='daily_opens')
    app_open_total = len(daily_app_opens)
    active_users = valid_df['reduser_id'].nunique()

    poi_interactions = df[df['rednote_poi_title'].notna()]
    poi_total = len(poi_interactions)
    unique_pois = poi_interactions['rednote_poi_title'].nunique()

    core_overview = {
        'app_open_total': int(app_open_total),
        'active_users': int(active_users),
        'poi_interactions': int(poi_total),
        'unique_poi_count': int(unique_pois),
        'total_events': int(len(df)),
        'total_users': int(df['reduser_id'].nunique()),
    }

    print(f"  APP打开总数: {app_open_total:,}")
    print(f"  活跃用户数: {active_users:,}")
    print(f"  POI交互次数: {poi_total:,}")
    print(f"  独立POI数量: {unique_pois:,}")

    return core_overview


def calculate_detailed_insights(df):
    """计算详细洞察数据"""
    print("\n" + "=" * 50)
    print("[详细洞察分析]")
    print("=" * 50)

    insights = {}

    porsche_df = df[df['span_nm'].str.contains('porsche', case=False, na=False)]
    if not porsche_df.empty:
        poi_card_shown = len(porsche_df[porsche_df['span_nm'].str.contains('poi.*card.*shown|poi.*show', case=False, na=False)])
        poi_card_clicked = len(porsche_df[porsche_df['span_nm'].str.contains('poi.*card.*click|poi.*click', case=False, na=False)])
        insights['porsche_analysis'] = {
            'total_events': int(len(porsche_df)),
            'poi_card_shown': int(poi_card_shown),
            'poi_card_clicked': int(poi_card_clicked),
            'pct_of_total': round((len(porsche_df) / len(df)) * 100, 2),
        }
        print(f"  Porsche+: {len(porsche_df)}事件 ({insights['porsche_analysis']['pct_of_total']}%)")

    search_df = df[df['span_nm'].str.contains('search', case=False, na=False)]
    if not search_df.empty:
        search_users = search_df['reduser_id'].nunique()
        search_events = len(search_df)
        insights['search_analysis'] = {
            'total_events': int(search_events),
            'search_users': int(search_users),
            'avg_searches_per_user': round(search_events / search_users, 2) if search_users > 0 else 0,
        }
        print(f"  搜索: {search_events}事件, {search_users}用户")

    content_df = df[df['rednote_post_title'].notna()]
    likes = len(df[df['rednote_post_is_like'].notna()])
    saves = len(df[df['rednote_post_is_save'].notna()])
    follows = len(df[df['rednote_post_follow'].notna()])
    total_content_views = len(content_df)
    interaction_rate = round(((likes + saves + follows) / total_content_views) * 100, 4) if total_content_views > 0 else 0

    post_types = df['rednote_post_typ'].value_counts().head(10).to_dict()
    video_events = len(df[df['rednote_video_post_is_play'].notna()])

    insights['content_analysis'] = {
        'total_content_views': int(total_content_views),
        'likes': int(likes),
        'saves': int(saves),
        'follows': int(follows),
        'interaction_rate_pct': float(interaction_rate),
        'post_types': to_serializable(post_types),
        'video_events': int(video_events),
    }
    print(f"  内容互动: 点赞{likes} 收藏{saves} 关注{follows}, 互动率{interaction_rate:.4f}%")

    map_df = df[df['span_nm'].str.contains('map', case=False, na=False)]
    fullscreen_map = len(map_df[map_df['span_nm'].str.contains('fullscreen|full_screen', case=False, na=False)])
    insights['map_analysis'] = {
        'total_map_events': int(len(map_df)),
        'fullscreen_map_events': int(fullscreen_map),
        'fullscreen_pct': round((fullscreen_map / len(map_df)) * 100, 2) if len(map_df) > 0 else 0,
    }
    print(f"  地图: {len(map_df)}事件, 全屏地图{fullscreen_map}({insights['map_analysis']['fullscreen_pct']}%)")

    user_event_counts = df.groupby('reduser_id').size()
    insights['user_behavior'] = {
        'max_events_user': int(user_event_counts.max()),
        'min_events_user': int(user_event_counts.min()),
        'median_events': float(user_event_counts.median()),
        'mean_events': round(float(user_event_counts.mean()), 2),
        'total_users': int(len(user_event_counts)),
    }
    print(f"  用户行为: 最高{user_event_counts.max()} 最低{user_event_counts.min()} 中位数{user_event_counts.median():.1f}")

    hourly_dist = {}
    if 'hour' in df.columns and df['hour'].notna().any():
        hourly = df.groupby('hour').size()
        for h, cnt in hourly.items():
            hourly_dist[int(h)] = int(cnt)
        peak_hour = hourly.idxmax()
        insights['time_distribution'] = {
            'peak_hour': int(peak_hour),
            'peak_events': int(hourly.max()),
            'hourly_distribution': hourly_dist,
        }
        print(f"  高峰时段: {int(peak_hour)}:00 ({hourly.max():,}事件)")

    return insights


def generate_kpi_html_report(all_results, output_path):
    """生成 KPI HTML 报告"""
    print("\n正在生成 KPI HTML 报告...")

    core = all_results['core_overview']
    app = all_results['app_metrics']
    porsche = all_results['porsche_metrics']
    discovery = all_results['discovery_metrics']
    ai = all_results['ai_guide_metrics']
    share = all_results['share_metrics']
    insights = all_results['detailed_insights']

    def esc(s):
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rednote KPI 指标全面分析报告（全量数据更新版）</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        :root {{
            --bg-primary: #0a0f1e;
            --bg-secondary: #111827;
            --text-primary: #e8eaf6;
            --text-secondary: #64748b;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-cyan: #06b6d4;
            --accent-orange: #f97316;
            --accent-pink: #ec4899;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
            border-radius: 16px;
        }}
        header h1 {{ font-size: 2.5rem; margin-bottom: 0.5rem; }}
        .header-meta {{
            display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; margin-top: 1rem;
        }}
        .meta-item {{
            background: rgba(255,255,255,0.1);
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }}
        .meta-label {{ font-size: 0.75rem; color: rgba(255,255,255,0.7); }}
        .meta-value {{ font-size: 1.125rem; font-weight: 600; color: #fff; }}
        .section-header {{
            display: flex; align-items: center; gap: 1rem;
            margin-bottom: 2rem; padding-bottom: 1rem;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .section-title {{ font-size: 1.75rem; font-weight: 600; }}
        .section-badge {{
            background: #fff; color: var(--bg-primary);
            padding: 0.25rem 0.75rem; border-radius: 20px;
            font-size: 0.875rem; font-weight: 500;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem; margin-bottom: 2rem;
        }}
        .metric-card {{
            background: var(--bg-secondary);
            border-radius: 16px; padding: 1.5rem;
            border: 1px solid rgba(255,255,255,0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        .metric-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }}
        .metric-card.app {{ border-top: 3px solid var(--accent-blue); }}
        .metric-card.porsche {{ border-top: 3px solid var(--accent-purple); }}
        .metric-card.discovery {{ border-top: 3px solid var(--accent-cyan); }}
        .metric-card.ai {{ border-top: 3px solid var(--accent-orange); }}
        .metric-card.share {{ border-top: 3px solid var(--accent-pink); }}
        .category-icon {{
            width: 36px; height: 36px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.85rem; color: #fff;
            margin-bottom: 0.75rem;
        }}
        .category-title {{ font-size: 0.9rem; font-weight: 600; margin-bottom: 0.25rem; }}
        .metric-count {{ font-size: 0.75rem; color: var(--text-secondary); }}
        .metric-name {{ font-size: 0.85rem; color: var(--text-secondary); }}
        .metric-value {{
            font-size: 1.75rem; font-weight: 700; color: #fff; margin: 0.5rem 0;
        }}
        .metric-value.highlight {{ color: var(--success); }}
        .metric-value.warning {{ color: var(--warning); }}
        .metric-description {{ font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.5rem; }}
        table {{
            width: 100%; border-collapse: collapse; margin: 1rem 0;
            background: var(--bg-secondary); border-radius: 12px; overflow: hidden;
        }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        th {{ background: rgba(59,130,246,0.1); font-weight: 600; color: var(--accent-blue); }}
        tr:hover {{ background: rgba(255,255,255,0.02); }}
        .insight-box {{
            background: var(--bg-secondary);
            border-left: 4px solid var(--accent-cyan);
            padding: 1.25rem; margin: 1rem 0; border-radius: 0 12px 12px 0;
        }}
        .insight-title {{ font-weight: 600; color: var(--accent-cyan); margin-bottom: 0.5rem; }}
        .insight-text {{ font-size: 0.9rem; color: var(--text-secondary); }}
        .chart-container {{
            background: var(--bg-secondary);
            border-radius: 16px; padding: 1.5rem; margin: 1.5rem 0;
        }}
        .core-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem; margin-bottom: 2rem;
        }}
        .core-card {{
            background: linear-gradient(135deg, rgba(59,130,246,0.1), rgba(139,92,246,0.1));
            border-radius: 16px; padding: 1.5rem; text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .core-value {{ font-size: 2.5rem; font-weight: 700; color: #fff; }}
        .core-label {{ font-size: 0.9rem; color: var(--text-secondary); margin-top: 0.5rem; }}
        @media (max-width: 768px) {{
            .metrics-grid {{ grid-template-columns: 1fr; }}
            .core-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
<div class="container">
<header>
    <h1>Rednote KPI 指标全面分析报告</h1>
    <div style="color: rgba(255,255,255,0.8); margin-bottom: 1rem;">全量数据更新版 · 基于 40,681 条记录</div>
    <div class="header-meta">
        <div class="meta-item"><div class="meta-label">数据周期</div><div class="meta-value">2026-03-19 至 2026-04-02</div></div>
        <div class="meta-item"><div class="meta-label">总记录数</div><div class="meta-value">{core['total_events']:,}</div></div>
        <div class="meta-item"><div class="meta-label">独立用户数</div><div class="meta-value">{core['total_users']}</div></div>
        <div class="meta-item"><div class="meta-label">覆盖天数</div><div class="meta-value">15 天</div></div>
    </div>
</header>

<!-- 核心指标概览 -->
<div class="section-header">
    <h2 class="section-title">核心指标概览</h2>
    <div class="section-badge">4 项核心指标</div>
</div>
<div class="core-grid">
    <div class="core-card">
        <div class="core-value">{core['app_open_total']:,}</div>
        <div class="core-label">APP 打开总数</div>
    </div>
    <div class="core-card">
        <div class="core-value">{core['active_users']:,}</div>
        <div class="core-label">活跃用户数</div>
    </div>
    <div class="core-card">
        <div class="core-value">{core['poi_interactions']:,}</div>
        <div class="core-label">POI 交互次数</div>
    </div>
    <div class="core-card">
        <div class="core-value">{core['unique_poi_count']:,}</div>
        <div class="core-label">独立 POI 数量</div>
    </div>
</div>

<!-- APP 指标 -->
<div class="section-header">
    <h2 class="section-title">APP 指标</h2>
    <div class="section-badge">7 个 KPI</div>
</div>
<div class="metrics-grid">
    <div class="metric-card app">
        <div class="category-icon">1.1</div>
        <div class="category-title">首次使用 AI 生成路书客户数量</div>
        <div class="metric-count">个</div>
        <div class="metric-name">数量</div>
        <div class="metric-value highlight">{app['ai_first_time_users']}</div>
        <div class="metric-description">统计周期内首次点击 AI 路书生成按钮的用户数量</div>
    </div>
    <div class="metric-card app">
        <div class="category-icon">1.2</div>
        <div class="category-title">APP 打开次总数</div>
        <div class="metric-count">次</div>
        <div class="metric-name">总打开次数</div>
        <div class="metric-value">{app['app_open_total']:,}</div>
        <div class="metric-description">统计周期内所有用户的 APP 打开次数总和</div>
    </div>
    <div class="metric-card app">
        <div class="category-icon">1.3</div>
        <div class="category-title">APP 打开次人数</div>
        <div class="metric-count">人</div>
        <div class="metric-name">打开用户数</div>
        <div class="metric-value">{app['app_open_users']:,}</div>
        <div class="metric-description">统计周期内所有用户的 APP 打开用户总和</div>
    </div>
    <div class="metric-card app">
        <div class="category-icon">1.4</div>
        <div class="category-title">APP 人均打开次数</div>
        <div class="metric-count">次</div>
        <div class="metric-name">平均次数</div>
        <div class="metric-value">{app['app_avg_opens']}</div>
        <div class="metric-description">APP 打开次总数 / APP 打开次人数</div>
    </div>
    <div class="metric-card app">
        <div class="category-icon">1.5</div>
        <div class="category-title">APP 曝光时长</div>
        <div class="metric-count">秒</div>
        <div class="metric-name">总时长</div>
        <div class="metric-value {'highlight' if app['exposure_duration_sec'] > 0 else 'warning'}">{app['exposure_duration_sec']:,.0f}</div>
        <div class="metric-description">基于 discovery page show 事件计算曝光时长</div>
    </div>
    <div class="metric-card app">
        <div class="category-icon">1.6</div>
        <div class="category-title">APP 活跃率</div>
        <div class="metric-count">%</div>
        <div class="metric-name">活跃率</div>
        <div class="metric-value {'highlight' if app['active_rate_pct'] > 50 else 'warning'}">{app['active_rate_pct']}%</div>
        <div class="metric-description">至少一次有效 APP 操作的活跃用户数量 / 总用户数量 × 100%</div>
    </div>
    <div class="metric-card app">
        <div class="category-icon">1.7</div>
        <div class="category-title">APP 第 n 日留存率</div>
        <div class="metric-count">%</div>
        <div class="metric-name">7天/14天/30天</div>
        <div class="metric-value warning">{app['retention_rates'].get('7天', 'N/A')} / {app['retention_rates'].get('14天', 'N/A')} / {app['retention_rates'].get('30天', 'N/A')}</div>
        <div class="metric-description">7天后、14天后、30天后留存率</div>
    </div>
</div>

<!-- Porsche+ 指标 -->
<div class="section-header">
    <h2 class="section-title">Porsche+ 指标</h2>
    <div class="section-badge">4 个 KPI</div>
</div>
<div class="metrics-grid" style="grid-template-columns: repeat(2, 1fr);">
    <div class="metric-card porsche">
        <div class="category-icon">2.1</div>
        <div class="category-title">Porsche+ 页面曝光时长</div>
        <div class="metric-count">秒</div>
        <div class="metric-name">总时长</div>
        <div class="metric-value {'highlight' if porsche['exposure_duration_sec'] > 0 else 'warning'}">{porsche['exposure_duration_sec']:,.0f}</div>
        <div class="metric-description">基于 porsche_page_pageshow 事件计算曝光时长</div>
    </div>
    <div class="metric-card porsche">
        <div class="category-icon">2.2</div>
        <div class="category-title">Porsche+ 版块活跃率</div>
        <div class="metric-count">%</div>
        <div class="metric-name">活跃率</div>
        <div class="metric-value {'highlight' if porsche['active_rate_pct'] > 20 else 'warning'}">{porsche['active_rate_pct']}%</div>
        <div class="metric-description">访问过 Porsche+ 页面的活跃用户数量 / 总用户数量</div>
    </div>
    <div class="metric-card porsche">
        <div class="category-icon">2.3</div>
        <div class="category-title">Porsche+ 人均使用时长</div>
        <div class="metric-count">秒</div>
        <div class="metric-name">平均时长</div>
        <div class="metric-value">{porsche['avg_duration_per_user']:,.1f}</div>
        <div class="metric-description">SUM(KPI2.1) / COUNT(Porsche+页面埋点数据条数)</div>
    </div>
    <div class="metric-card porsche">
        <div class="category-icon">2.4</div>
        <div class="category-title">Porsche+ 人均使用次数</div>
        <div class="metric-count">次</div>
        <div class="metric-name">平均次数</div>
        <div class="metric-value">{porsche['avg_opens_per_user']:.1f}</div>
        <div class="metric-description">统计周期内 Porsche+ 页面打开次数总和 / APP 总活跃用户数量</div>
    </div>
</div>

<!-- Discovery 页面指标 -->
<div class="section-header">
    <h2 class="section-title">Discovery 页面指标</h2>
    <div class="section-badge">4 个 KPI</div>
</div>
<div class="metrics-grid" style="grid-template-columns: repeat(2, 1fr);">
    <div class="metric-card discovery">
        <div class="category-icon">3.1</div>
        <div class="category-title">Discovery 页面曝光时长</div>
        <div class="metric-count">秒</div>
        <div class="metric-name">总时长</div>
        <div class="metric-value {'highlight' if discovery['exposure_duration_sec'] > 0 else 'warning'}">{discovery['exposure_duration_sec']:,.0f}</div>
        <div class="metric-description">基于 discovery_page_pageshow 事件计算曝光时长</div>
    </div>
    <div class="metric-card discovery">
        <div class="category-icon">3.2</div>
        <div class="category-title">Discovery 版块活跃率</div>
        <div class="metric-count">%</div>
        <div class="metric-name">活跃率</div>
        <div class="metric-value {'highlight' if discovery['active_rate_pct'] > 50 else 'warning'}">{discovery['active_rate_pct']}%</div>
        <div class="metric-description">访问过发现页面的活跃用户数量 / 总用户数量</div>
    </div>
    <div class="metric-card discovery">
        <div class="category-icon">3.3</div>
        <div class="category-title">Discovery 人均使用时长</div>
        <div class="metric-count">秒</div>
        <div class="metric-name">平均时长</div>
        <div class="metric-value">{discovery['avg_duration_per_user']:,.1f}</div>
        <div class="metric-description">SUM(KPI3.1) / COUNT(发现页面埋点数据条数)</div>
    </div>
    <div class="metric-card discovery">
        <div class="category-icon">3.4</div>
        <div class="category-title">Discovery 人均使用次数</div>
        <div class="metric-count">次</div>
        <div class="metric-name">平均次数</div>
        <div class="metric-value">{discovery['avg_opens_per_user']:.1f}</div>
        <div class="metric-description">统计周期内发现页面打开次数总和 / APP 总活跃用户数量</div>
    </div>
</div>

<!-- AI 路书指标 -->
<div class="section-header">
    <h2 class="section-title">AI 路书指标</h2>
    <div class="section-badge">3 个 KPI</div>
</div>
<div class="metrics-grid" style="grid-template-columns: repeat(3, 1fr);">
    <div class="metric-card ai">
        <div class="category-icon">4.1</div>
        <div class="category-title">AI 路书生成活跃率</div>
        <div class="metric-count">%</div>
        <div class="metric-name">活跃率</div>
        <div class="metric-value highlight">{ai['active_rate_pct']}%</div>
        <div class="metric-description">AI 路书生成按钮点击的用户数 / APP 活跃用户数</div>
    </div>
    <div class="metric-card ai">
        <div class="category-icon">4.2</div>
        <div class="category-title">AI 路书生成人均使用次数</div>
        <div class="metric-count">次</div>
        <div class="metric-name">平均次数</div>
        <div class="metric-value">{ai['avg_uses_per_user']}</div>
        <div class="metric-description">AI 路书生成按钮点击的数据条数 / 用户数</div>
    </div>
    <div class="metric-card ai">
        <div class="category-icon">4.3</div>
        <div class="category-title">AI 路书生成使用率</div>
        <div class="metric-count">%</div>
        <div class="metric-name">使用率</div>
        <div class="metric-value {'highlight' if ai['usage_rate_pct'] > 5 else 'warning'}">{ai['usage_rate_pct']}%</div>
        <div class="metric-description">AI 路书生成按钮点击数 / APP 打开次数</div>
    </div>
</div>

<!-- 分享功能指标 -->
<div class="section-header">
    <h2 class="section-title">分享功能指标</h2>
    <div class="section-badge">2 个 KPI</div>
</div>
<div class="metrics-grid" style="grid-template-columns: repeat(2, 1fr);">
    <div class="metric-card share">
        <div class="category-icon">5.1</div>
        <div class="category-title">分享码生成占比</div>
        <div class="metric-count">%</div>
        <div class="metric-name">生成占比</div>
        <div class="metric-value highlight">{share['gen_rate_pct']}%</div>
        <div class="metric-description">分享码图标的用户数 / APP 总活跃用户数量</div>
    </div>
    <div class="metric-card share">
        <div class="category-icon">5.2</div>
        <div class="category-title">分享码使用占比</div>
        <div class="metric-count">%</div>
        <div class="metric-name">使用占比</div>
        <div class="metric-value {'highlight' if share['use_rate_pct'] > 0 else 'warning'}">{share['use_rate_pct']}%</div>
        <div class="metric-description">分享码添加行程确认按钮的用户数 / APP 总活跃用户数量</div>
    </div>
</div>'''

    html += f'''
<!-- 详细洞察与结论 -->
<div class="section-header">
    <h2 class="section-title">关键洞察与结论</h2>
    <div class="section-badge">基于全量数据分析</div>
</div>'''

    if 'porsche_analysis' in insights:
        pa = insights['porsche_analysis']
        html += f'''
<div class="insight-box">
    <div class="insight-title">Porsche+ 功能是核心</div>
    <div class="insight-text">
        Porsche+ 模块共产生 <strong>{pa['total_events']:,}</strong> 次事件（占总事件的 <strong>{pa['pct_of_total']}%</strong>），
        其中 POI 卡片展示 <strong>{pa['poi_card_shown']:,}</strong> 次，POI 卡片点击 <strong>{pa['poi_card_clicked']:,}</strong> 次。
        Porsche+ 是用户最活跃的功能模块。
    </div>
</div>'''

    if 'search_analysis' in insights:
        sa = insights['search_analysis']
        html += f'''
<div class="insight-box">
    <div class="insight-title">搜索行为活跃</div>
    <div class="insight-text">
        搜索相关事件共 <strong>{sa['total_events']:,}</strong> 次，有 <strong>{sa['search_users']:,}</strong> 个用户进行了搜索行为，
        平均每用户搜索 <strong>{sa['avg_searches_per_user']:.2f}</strong> 次。搜索功能被广泛使用。
    </div>
</div>'''

    if 'content_analysis' in insights:
        ca = insights['content_analysis']
        html += f'''
<div class="insight-box">
    <div class="insight-title">内容消费与互动</div>
    <div class="insight-text">
        共有 <strong>{ca['total_content_views']:,}</strong> 次内容浏览，其中视频内容 <strong>{ca['video_events']:,}</strong> 次。
        用户互动情况：点赞 <strong>{ca['likes']}</strong> 次、收藏 <strong>{ca['saves']}</strong> 次、关注 <strong>{ca['follows']}</strong> 次，
        整体互动率为 <strong>{ca['interaction_rate_pct']:.4f}%</strong>。
    </div>
</div>'''

    if 'map_analysis' in insights:
        ma = insights['map_analysis']
        html += f'''
<div class="insight-box">
    <div class="insight-title">地图使用情况</div>
    <div class="insight-text">
        地图相关事件共 <strong>{ma['total_map_events']:,}</strong> 次，其中全屏地图使用达到 <strong>{ma['fullscreen_map_events']:,}</strong> 次
        （占 <strong>{ma['fullscreen_pct']}%</strong>）。这表明用户有深度地图探索需求。
    </div>
</div>'''

    if 'user_behavior' in insights:
        ub = insights['user_behavior']
        html += f'''
<div class="insight-box">
    <div class="insight-title">用户行为差异显著</div>
    <div class="insight-text">
        最高频用户产生 <strong>{ub['max_events_user']:,}</strong> 次交互，最低频用户仅 <strong>{ub['min_events_user']}</strong> 次。
        中位数交互为 <strong>{ub['median_events']:.1f}</strong> 次，平均值 <strong>{ub['mean_events']:.2f}</strong> 次。
        用户活跃度呈长尾分布，共 <strong>{ub['total_users']:,}</strong> 个用户。
    </div>
</div>'''

    if 'time_distribution' in insights:
        td = insights['time_distribution']
        html += f'''
<div class="insight-box">
    <div class="insight-title">高峰时段分析</div>
    <div class="insight-text">
        用户活跃高峰出现在 <strong>{td['peak_hour']}:00</strong>（该时段 <strong>{td['peak_events']:,}</strong> 次事件）。
        建议在高峰时段推送优质内容，提升用户参与度。
    </div>
</div>'''

    html += f'''
<div class="chart-container">
    <h3 style="margin-bottom: 1rem;">关键指标对比可视化</h3>
    <canvas id="kpiChart"></canvas>
</div>

<footer style="text-align: center; margin-top: 3rem; padding: 2rem; color: var(--text-secondary); font-size: 0.85rem;">
    <p>Rednote KPI 分析报告 · 全量数据版本 · 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>基于 40,681 条原始埋点数据 | 206 个独立用户 | 15 天数据周期</p>
</footer>
</div>

<script>
const ctx = document.getElementById('kpiChart').getContext('2d');
new Chart(ctx, {{
    type: 'bar',
    data: {{
        labels: ['APP打开', '活跃用户', 'POI交互', '独立POI', 'Porsche+事件', 'AI点击用户', '分享用户'],
        datasets: [{{
            label: '数值',
            data: [
                {core['app_open_total']},
                {core['active_users']},
                {core['poi_interactions']},
                {core['unique_poi_count']},
                {porsche.get('total_porsche_events', 0)},
                {ai.get('ai_click_users', 0)},
                {share.get('share_gen_users', 0)}
            ],
            backgroundColor: [
                'rgba(59, 130, 246, 0.7)',
                'rgba(139, 92, 246, 0.7)',
                'rgba(6, 182, 212, 0.7)',
                'rgba(249, 115, 22, 0.7)',
                'rgba(236, 72, 153, 0.7)',
                'rgba(16, 185, 129, 0.7)',
                'rgba(245, 158, 11, 0.7)'
            ],
            borderColor: [
                'rgb(59, 130, 246)',
                'rgb(139, 92, 246)',
                'rgb(6, 182, 212)',
                'rgb(249, 115, 22)',
                'rgb(236, 72, 153)',
                'rgb(16, 185, 129)',
                'rgb(245, 158, 11)'
            ],
            borderWidth: 2
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ display: false }},
            title: {{
                display: true,
                text: '核心 KPI 指标概览',
                color: '#e8eaf6',
                font: {{ size: 16 }}
            }}
        }},
        scales: {{
            y: {{
                beginAtZero: true,
                ticks: {{ color: '#64748b' }},
                grid: {{ color: 'rgba(255,255,255,0.05)' }}
            }},
            x: {{
                ticks: {{ color: '#64748b' }},
                grid: {{ display: false }}
            }}
        }}
    }}
}});
</script>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    ensure_dir(OUTPUT_DIR)

    df, total_users, total_events = load_and_prepare_data()

    results = {}

    print("\n开始计算所有 KPI 指标...")

    results['core_overview'] = calculate_core_overview(df)
    results['app_metrics'] = calculate_app_metrics(df, total_users)
    results['porsche_metrics'] = calculate_porsche_metrics(df, total_users)
    results['discovery_metrics'] = calculate_discovery_metrics(df, total_users)
    results['ai_guide_metrics'] = calculate_ai_guide_metrics(df, total_users, results['app_metrics']['app_open_total'])
    results['share_metrics'] = calculate_share_metrics(df, total_users)
    results['detailed_insights'] = calculate_detailed_insights(df)

    json_output = os.path.join(OUTPUT_DIR, 'kpi_metrics_replica.json')
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON KPI数据已保存: {json_output}")

    html_output = os.path.join(OUTPUT_DIR, 'kpi_full_report.html')
    generate_kpi_html_report(results, html_output)
    print(f"✅ HTML KPI报告已保存: {html_output}")

    print("\n" + "=" * 70)
    print("KPI 指标复刻完成！输出文件:")
    print(f"  1. {json_output}")
    print(f"  2. {html_output}")
    print("=" * 70)


if __name__ == '__main__':
    main()
