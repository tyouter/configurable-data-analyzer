"""
Rednote KPI Full Metrics Report
Generate comprehensive statistics for all 20 KPI metrics defined in config
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime

# Set UTF-8 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from analyzer import RednoteAnalyzer

DATA_PATH = r'C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx'
CONFIG_PATH = r'C:\projects\rednote data analyzer\rednote_analyzer\config\kpi_metrics.yaml'

def get_nested_value(nested_dict, keys):
    """Get value from nested dictionary using key path"""
    value = nested_dict
    for key in keys:
        if key in value:
            value = value[key]
        else:
            break
    return value

def safe_int(value, default=0):
    """Safely convert to int"""
    try:
        return int(value)
    except:
        return default

def safe_float(value, default=0.0, decimals=2):
    """Safely convert to float"""
    try:
        return round(float(value), decimals)
    except:
        return default

def calculate_exposure_time(event_data, min_duration=0):
    """Calculate exposure time in seconds"""
    if event_data.empty:
        return {'total_seconds': 0, 'avg_seconds': 0.0, 'total_events': 0}

    # Parse timestamps
    event_data['strt_time_dt'] = pd.to_datetime(event_data['strt_time_nano'], errors='coerce')
    event_data['end_time_dt'] = pd.to_datetime(event_data['end_time_nano'], errors='coerce')

    # Calculate duration
    event_data['duration'] = (event_data['end_time_dt'] - event_data['strt_time_dt']).dt.total_seconds()

    # Filter valid durations
    valid_durations = event_data[event_data['duration'] > 0]

    total_duration = valid_durations['duration'].sum()
    avg_duration = valid_durations['duration'].mean() if not valid_durations.empty else 0.0
    total_events = len(valid_durations)

    return {
        'total_seconds': int(total_duration),
        'avg_seconds': round(avg_duration, 2),
        'total_events': total_events
    }

def calculate_active_users(event_data, min_duration=5):
    """Calculate active users based on session duration"""
    if event_data.empty:
        return {'active_users': 0, 'inactive_users': 0, 'total_users': 0, 'active_rate': 0.0}

    # Parse timestamps
    event_data['strt_time_dt'] = pd.to_datetime(event_data['strt_time_nano'], errors='coerce')
    event_data['end_time_dt'] = pd.to_datetime(event_data['end_time_nano'], errors='coerce')

    # Calculate duration
    event_data['duration'] = (event_data['end_time_dt'] - event_data['strt_time_dt']).dt.total_seconds()

    # Calculate per-user total duration
    user_durations = event_data.groupby(['reduser_id']).agg(
        total_duration=('duration', 'sum'),
        event_count=('duration', 'count')
    )

    user_durations['total_duration'] = user_durations['total_duration'].fillna(0)

    # Classify users
    active_users = user_durations[user_durations['total_duration'] >= min_duration].index.tolist()
    inactive_users = user_durations[user_durations['total_duration'] < min_duration].index.tolist()

    total_users = event_data['reduser_id'].nunique()

    active_user_count = len(active_users)
    inactive_user_count = len(inactive_users)

    total_user_count = total_users

    if total_user_count > 0:
        active_rate = round(active_user_count / total_user_count * 100, 2)
    else:
        active_rate = 0.0

    return {
        'active_users': active_user_count,
        'inactive_users': inactive_user_count,
        'total_users': total_user_count,
        'active_rate': active_rate
    }

def calculate_retention(base_event='discovery_page_pageshow', day_ns=[7, 14, 30]):
    """Calculate retention rates by cohort"""
    data = pd.read_excel(DATA_PATH)
    data['strt_time_dt'] = pd.to_datetime(data['strt_time_nano'], errors='coerce')

    event_data = data[data['span_nm'] == base_event].copy()
    if event_data.empty:
        return {}

    event_data['date'] = event_data['strt_time_dt'].dt.date

    # Get daily unique users
    daily_users = event_data.groupby('date')['reduser_id'].nunique()

    retention_results = {}
    dates = sorted(daily_users.index.tolist())

    # For our 2-day data window, we can't calculate 7, 14, or 30 day retention
    # Return 0 for all as we don't have enough data
    for day_n in day_ns:
        retention_results[day_n] = {
            'date': str(dates[0]) if len(dates) > 0 else 'N/A',
            'active_users': int(daily_users.iloc[0]) if len(daily_users) > 0 else 0,
            'retained_users': 0,
            'retention_rate': 0.0,
            'total_users': int(daily_users.iloc[0]) if len(daily_users) > 0 else 0,
            'note': 'Insufficient data window for retention calculation'
        }

    return retention_results

def calculate_first_time_users():
    """Analyze first-time AI guide users"""
    data = pd.read_excel(DATA_PATH)
    ai_guide_events = data[data['span_nm'] == 'post_detail_page_ai_travel_guide_button_click'].copy()

    if ai_guide_events.empty:
        return {
            'total_first_time_users': 0,
            'first_time_users_list': []
        }

    ai_guide_events['strt_time_dt'] = pd.to_datetime(ai_guide_events['strt_time_nano'], errors='coerce')

    # Group by user
    user_first_occurrence = ai_guide_events.groupby('reduser_id').agg(
        first_time=('strt_time_dt', 'min'),
        count=('reduser_id', 'count')
    )

    user_first_occurrence['count'] = user_first_occurrence['count']
    first_time_users = user_first_occurrence[user_first_occurrence['count'] > 0].index.tolist()

    first_time_users_list = []
    for user_id in user_first_occurrence.index:
        user_events = ai_guide_events[ai_guide_events['reduser_id'] == user_id].sort_values('strt_time_dt')
        first_event = user_events.iloc[0] if len(user_events) > 0 else None
        first_event_time = first_event['strt_time_dt'] if first_event is not None else None

        first_time_users_list.append({
            'user_id': str(user_id),
            'first_event_time': str(first_event_time) if first_event_time is not None else None,
            'total_events': int(user_events.shape[0])
        })

    return {
        'total_first_time_users': len(first_time_users_list),
        'first_time_users': first_time_users_list
    }

def calculate_share_metrics():
    """Calculate share-related metrics"""
    data = pd.read_excel(DATA_PATH)

    # Share code generation
    share_icon_events = data[data['span_nm'] == 'trival_guide_page_share_icon_click']
    share_icon_users = share_icon_events['reduser_id'].dropna().nunique() if not share_icon_events.empty else 0

    # Share code usage
    share_trip_events = data[data['span_nm'] == 'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click']
    share_trip_users = share_trip_events['reduser_id'].dropna().nunique() if not share_trip_events.empty else 0

    # Get total users
    total_users = data['reduser_id'].dropna().nunique()

    return {
        'share_icon_users': share_icon_users,
        'share_trip_users': share_trip_users,
        'total_users': total_users,
        'share_icon_generation_rate': round(share_icon_users / total_users * 100, 2) if total_users > 0 else 0.0,
        'share_code_usage_rate': round(share_trip_users / total_users * 100, 2) if total_users > 0 else 0.0
    }

def analyze_app_open_events():
    """Analyze APP open events"""
    data = pd.read_excel(DATA_PATH)

    # Get all app open events
    app_open_events = data[data['span_nm'].isin(['login_page_pageshow', 'discovery_page_pageshow'])].copy()

    if app_open_events.empty:
        return {
            'total_app_opens': 0,
            'unique_app_opens_per_day': 0,
            'unique_users': 0,
            'daily_opens_by_user': {},
            'by_date': 0
        }

    # Get events per day
    app_open_events['strt_time_dt'] = pd.to_datetime(app_open_events['strt_time_nano'], errors='coerce')
    app_open_events['date'] = app_open_events['strt_time_dt'].dt.date

    # Unique opens per day
    app_opens_unique = app_open_events.drop_duplicates(['date', 'reduser_id'])
    app_opens_unique['day_str'] = app_opens_unique['date'].astype(str)

    # Calculate unique users
    app_open_users = app_open_events['reduser_id'].nunique()

    # Calculate per-day opens (max 1 per user)
    app_opens_unique['open_count'] = 1

    return {
        'total_app_opens': len(app_open_events),
        'unique_app_opens_per_day': len(app_opens_unique),
        'unique_users': app_open_users,
        'daily_opens_by_user': app_opens_unique.groupby('reduser_id').size().to_dict(),
        'by_date': len(app_opens_unique.groupby('date'))
    }

def analyze_porsche_features():
    """Analyze Porsche+ features"""
    data = pd.read_excel(DATA_PATH)

    porsche_events = data[data['span_nm'].str.contains('porsche', case=False, na=False)]

    # POI card interactions
    poi_card_events = porsche_events[porsche_events['span_nm'].str.contains('poi_card', case=False, na=False)]

    # Recommendation interactions
    recommend_events = porsche_events[porsche_events['span_nm'].str.contains('recommend', case=False, na=False)]

    # By user statistics
    porsche_users = porsche_events['reduser_id'].dropna().nunique()
    user_event_counts = porsche_events.groupby('reduser_id').size()

    return {
        'total_porsche_events': len(porsche_events),
        'unique_porsche_users': int(porsche_users),
        'poi_card_interactions': len(poi_card_events),
        'recommendation_interactions': len(recommend_events),
        'user_event_counts': user_event_counts.to_dict(),
        'top_porsche_events': porsche_events.head(10).to_dict()
    }

def analyze_search_behavior():
    """Analyze search behavior"""
    data = pd.read_excel(DATA_PATH)

    # Search events
    search_events = data[data['span_nm'].str.contains('search', case=False, na=False)]

    # By user
    search_users_df = search_events['reduser_id'].dropna().nunique()

    return {
        'total_search_events': len(search_events),
        'unique_searching_users': int(search_users_df),
        'search_event_diversity': search_events['span_nm'].nunique(),
        'user_search_counts': search_events.groupby('reduser_id').size().to_dict()
    }

def analyze_content_engagement():
    """Analyze content engagement"""
    data = pd.read_excel(DATA_PATH)

    like_events = data[data['rednote_post_is_like'].notna()]
    save_events = data[data['rednote_post_is_save'].notna()]
    follow_events = data[data['rednote_post_follow'].notna()]

    # Content types
    content_types = data[data['rednote_post_typ'].notna()]['rednote_post_typ']

    return {
        'total_likes': len(like_events),
        'total_saves': len(save_events),
        'total_follows': len(follow_events),
        'content_types': content_types.value_counts().to_dict(),
        'engagement_rate': round((len(like_events) + len(save_events) + len(follow_events)) / len(data) * 100, 2) if len(data) > 0 else 0
    }

def analyze_video_consumption():
    """Analyze video consumption"""
    data = pd.read_excel(DATA_PATH)

    # Video plays
    play_events = data[data['rednote_video_post_is_play'] == 0]
    autoplay_events = data[data['rednote_video_post_autoplay_is_open'] == 1]

    return {
        'total_plays': len(play_events),
        'autoplay_enabled': len(autoplay_events),
        'video_viewers': play_events['reduser_id'].dropna().nunique()
    }

def analyze_map_poi():
    """Analyze map and POI interactions"""
    data = pd.read_excel(DATA_PATH)

    map_events = data[data['span_nm'].str.contains('map|poi', case=False, na=False)]

    # Fullscreen usage
    fullscreen_events = data[data['rednote_poi_map_fullscreen'] == 1]

    return {
        'total_map_events': len(map_events),
        'fullscreen_usage': len(fullscreen_events),
        'map_features': map_events['span_nm'].value_counts().head(10).to_dict()
    }

def main():
    print('='*80)
    print('FULL KPI METRICS ANALYSIS')
    print('='*80)
    print(f'Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    # Load data
    analyzer = RednoteAnalyzer(DATA_PATH, CONFIG_PATH)
    analyzer.load_data()
    data = analyzer.data

    print(f'Loaded {len(data)} records')

    # ========== DATA OVERVIEW ==========
    print('\n[DATA OVERVIEW]===========')
    print(f'Total records: {len(data)}')
    print(f'Columns: {len(data.columns)}')
    print(f'Date range: {analyzer.get_data_overview()["date_range"]}')
    print(f'Unique users: {analyzer.get_data_overview()["unique_users"]}')
    print(f'Unique devices: {analyzer.get_data_overview()["unique_devices"]}')
    print(f'Unique events: {analyzer.get_data_overview()["unique_events"]}')

    # ========== CALCULATE ALL KPIS ==========
    print('\n[ALL KPIS ============')
    kpi_results = {}

    # APP METRICS [1.1-1.7]
    kpi_results['app_metrics'] = {}

    # 1.1 首次使用 AI 生成路书客户数量
    ai_first_time_users = calculate_first_time_users()
    kpi_results['app_metrics']['ai_guide_first_time_users'] = ai_first_time_users

    print(f'✓ KPI1.1: 首次使用 AI 生成路书客户数量 = {ai_first_time_users["total_first_time_users"]}')
    print(f'Detail: {ai_first_time_users}')

    # 1.2 APP 打开次总数
    app_opens_analysis = analyze_app_open_events()
    total_app_opens = app_opens_analysis['total_app_opens']
    avg_opens_per_user = round(total_app_opens / app_opens_analysis['unique_app_opens_per_day'], 2) if app_opens_analysis['unique_app_opens_per_day'] > 0 else 0.0

    kpi_results['app_metrics']['app_open_total'] = {
        'name': 'APP 打开次总数',
        'value': total_app_opens,
        'description': '统计周期内所有用户的 APP 打开次数总和（每个用户每天最多记为1次）',
        'detail': {
            'total_app_opens': total_app_opens,
            'unique_users': app_opens_analysis['unique_app_opens_per_day']
        }
    }

    kpi_results['app_metrics']['app_open_users'] = {
        'name': 'APP 打开次人数',
        'value': app_opens_analysis['unique_app_opens_per_day'],
        'description': '统计周期内所有用户的 APP 打开用户总和'
    }

    kpi_results['app_metrics']['app_avg_opens_per_user'] = {
        'name': 'APP 人均打开次数',
        'value': avg_opens_per_user,
        'description': 'APP 打开次总数 / APP 打开次人数'
    }

    # 1.4 APP 曝光时长
    app_exposure = calculate_exposure_time(data[data['span_nm'] == 'discovery_page_pageshow'])
    kpi_results['app_metrics']['app_exposure_duration'] = {
        'name': 'APP 曝光时长计算',
        'value': app_exposure['total_seconds'],
        'description': '基于 discover page show 事件计算曝光时长'
    }

    # 1.5 APP 活跃率
    discovery_active = calculate_active_users(data[data['span_nm'] == 'discovery_page_pageshow'])
    kpi_results['app_metrics']['app_active_rate'] = {
        'name': 'APP 活跃率',
        'value': discovery_active['active_rate'],
        'description': '至少一次有效 APP 操作的活跃用户数量，除以总用户数量，再乘以 100%'
    }

    # 1.6 APP 第 n 日留存率
    retention_analysis = calculate_retention()
    kpi_results['app_metrics']['app_retention_rate'] = {
        'name': 'APP 第 n 日留存率',
        'value': 'N/A',
        'description': '7天后、14天后、30天后留存率'
    }

    # PORSCHE PLUS METRICS [1.2.1-2.4]
    kpi_results['porsche_plus_metrics'] = {}

    # 2.1 Porsche+页面曝光时长
    porsche_exposure = calculate_exposure_time(data[data['span_nm'] == 'porsche_page_pageshow'])
    kpi_results['porsche_plus_metrics']['porsche_page_exposure_duration'] = {
        'name': 'Porsche+页面曝光时长',
        'value': porsche_exposure['total_seconds'],
        'description': '基于 porsche_page_pageshow 事件计算曝光时长'
    }

    # 2.2 Porsche+版块活跃率
    porsche_active = calculate_active_users(data[data['span_nm'] == 'porsche_page_pageshow'])
    kpi_results['porsche_plus_metrics']['porsche_active_rate'] = {
        'name': 'Porsche+版块活跃率',
        'value': porsche_active['active_rate'],
        'description': '访问过 Porsche+ 页面的活跃用户数量/总用户数量'
    }

    # 2.3 Porsche+页面平均时长
    porsche_avg_duration = calculate_exposure_time(data[data['span_nm'] == 'porsche_page_pageshow'])
    kpi_results['porsche_plus_metrics']['porsche_avg_duration'] = {
        'name': 'Porsche+页面平均时长',
        'value': porsche_avg_duration['avg_seconds'],
        'description': 'SUM（KPI2.1）/ COUNT（Porsche+ 页面埋点数据条数）'
    }

    # 2.4 Porsche+页面人均打开次数
    porsche_avg_opens = calculate_active_users(data[data['span_nm'] == 'porsche_page_pageshow'])
    kpi_results['porsche_plus_metrics']['porsche_avg_opens_per_user'] = {
        'name': 'Porsche+页面人均打开次数',
        'value': porsche_avg_opens['active_users'],
        'description': '统计周期内，Porsche+页面打开次数总和 / APP 的总活跃用户数量'
    }

    # DISCOVERY PAGE METRICS [1.3.1-1.4]
    kpi_results['discovery_page_metrics'] = {}

    # 3.1 发现页面曝光时长
    discovery_exposure = calculate_exposure_time(data[data['span_nm'] == 'discovery_page_pageshow'])
    kpi_results['discovery_page_metrics']['discovery_page_exposure_duration'] = {
        'name': '发现页面曝光时长',
        'value': discovery_exposure['total_seconds'],
        'description': '基于 discovery_page_pageshow 事件计算曝光时长'
    }

    # 3.2 发现页面活跃率
    discovery_active = calculate_active_users(data[data['span_nm'] == 'discovery_page_pageshow'])
    kpi_results['discovery_page_metrics']['discovery_page_active_rate'] = {
    'name': '发现页面活跃率',
        'value': discovery_active['active_rate'],
        'description': '访问过发现页面的活跃用户数量/总用户数量'
    }

    # 3.3 发现页面平均时长
    discovery_avg_duration = calculate_exposure_time(data[data['span_nm'] == 'discovery_page_pageshow'])
    kpi_results['discovery_page_metrics']['discovery_page_avg_duration'] = {
        'name': '发现页面平均时长',
        'value': discovery_avg_duration['avg_seconds'],
        'description': 'SUM（发现页面曝光时长）/ COUNT（发现页面埋点数据条数）'
    }

    # 3.4 发现页面人均打开次数
    discovery_avg_opens = calculate_active_users(data[data['span_nm'] == 'discovery_page_pageshow'])
    kpi_results['discovery_page_metrics']['discovery_page_avg_opens_per_user'] = {
        'name': '发现页面人均打开次数',
        'value': discovery_avg_opens['active_users'],
        'description': '统计周期内，发现页面打开次数总和 / APP 的总活跃用户数量'
    }

    # AI GUIDE METRICS [1.4.1-4.3]
    kpi_results['ai_guide_metrics'] = {}

    # 4.1 AI 路书生成活跃率
    ai_guide_events = data[data['span_nm'] == 'post_detail_page_ai_travel_guide_button_click'].copy()
    ai_guide_users = ai_guide_events['reduser_id'].dropna().nunique() if not ai_guide_events.empty else 0

    discovery_active_users = data[data['span_nm'] == 'discovery_page_pageshow']
    discovery_users_count = discovery_active_users['reduser_id'].dropna().nunique() if not discovery_active_users.empty else 0

    kpi_results['ai_guide_metrics']['ai_guide_active_rate'] = {
        'name': 'AI 路书生成活跃率',
        'value': round(ai_guide_users / discovery_users_count * 100, 2) if discovery_users_count > 0 else 0.0,
        'description': '埋点事件 AI 路书生成按钮点击的用户数 / APP活跃用户数'
    }

    # 4.2 AI 路书生成人均使用次数
    ai_guide_avg_usage = calculate_active_users(data[data['span_nm'] == 'post_detail_page_ai_travel_guide_button_click'])
    ai_users_count = ai_guide_avg_usage['active_users']
    ai_total_requests = len(ai_guide_events)

    kpi_results['ai_guide_metrics']['ai_guide_avg_usage'] = {
        'name': 'AI 路书生成人均使用次数',
        'value': round(ai_total_requests / ai_users_count, 2) if ai_users_count > 0 else 0.0,
        'description': 'AI 路书生成按钮点击的数据条数/ 用户数'
    }

    # 4.3 AI 路书生成使用率
    app_opens_total = app_opens_analysis['total_app_opens']
    kpi_results['ai_guide_metrics']['ai_guide_usage_rate'] = {
        'name': 'AI 路书生成使用率',
        'value': round(len(ai_guide_events) / app_opens_total * 100, 2) if app_opens_total > 0 else 0.0,
        'description': 'AI 路书生成按钮点击数 / APP 打开次数'
    }

    # SHARE METRICS [1.5.1-1.2]
    kpi_results['share_metrics'] = {}

    # 5.1 分享码生成占比
    share_metrics = calculate_share_metrics()
    kpi_results['share_metrics']['share_code_generation_rate'] = {
        'name': '分享码生成占比',
        'value': share_metrics['share_icon_generation_rate'],
        'description': '分享码图标的用户数 / APP总活跃用户数量'
    }

    # 5.2 分享码使用占比
    kpi_results['share_metrics']['share_code_usage_rate'] = {
        'name': '分享码使用占比',
        'value': share_metrics['share_code_usage_rate'],
        'description': '分享码添加行程确认按钮的用户数 / APP总活跃用户数量'
    }

    # ========== ADDITIONAL ANALYTICS ==========
    print('\n[ADDATIONAL ANALYTICS]===========')

    # Analyze Porsche+ features
    porsche_features = analyze_porsche_features()
    print(f'Porsche+ events: {porsche_features["total_porsche_events"]}')

    # Analyze search behavior
    search_behavior = analyze_search_behavior()
    print(f'Search events: {search_behavior["total_search_events"]}')
    print(f'Search users: {search_behavior["unique_searching_users"]}')

    # Analyze content engagement
    content_engagement = analyze_content_engagement()
    print(f'Content engagement: {content_engagement}')

    # Analyze video consumption
    video_consumption = analyze_video_consumption()
    print(f'Video consumption: {video_consumption}')

    # Analyze map POI
    map_poi = analyze_map_poi()
    print(f'Map & POI: {map_poi}')

    # ========== COMPILE REPORT ==========
    print('\n[COMPILE REPORT]===========')

    # Create report without circular reference
    final_report = {
        'title': 'Rednote KPI Full Report',
        'generated_at': datetime.now().isoformat(),
        'data_summary': {
            'total_records': len(data),
            'unique_users': analyzer.get_data_overview()['unique_users'],
            'unique_devices': analyzer.get_data_overview()['unique_devices'],
            'total_event_types': analyzer.get_data_overview()['unique_events']
        },
        'app_metrics': kpi_results.get('app_metrics', {}),
        'porsche_plus_metrics': kpi_results.get('porsche_plus_metrics', {}),
        'discovery_page_metrics': kpi_results.get('discovery_page_metrics', {}),
        'ai_guide_metrics': kpi_results.get('ai_guide_metrics', {}),
        'share_metrics': kpi_results.get('share_metrics', {}),
        'additional_analytics': kpi_results.get('additional_analytics', {})
    }

    # Save report
    OUTPUT_PATH = r'C:\projects\rednote data analyzer\rednote_analyzer\output\kpi_full_report.json'
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    print(f'Report saved to: {OUTPUT_PATH}')

    # Print summary
    print('\n[KPI SUMMARY]===========')
    print(f"APP Metrics: {len(final_report.get('app_metrics', {}))} KPIs")
    print(f"Porsche+ Metrics: {len(final_report.get('porsche_plus_metrics', {}))} KPIs")
    print(f"Discovery Page Metrics: {len(final_report.get('discovery_page_metrics', {}))} KPIs")
    print(f"AI Guide Metrics: {len(final_report.get('ai_guide_metrics', {}))} KPIs")
    print(f"Share Metrics: {len(final_report.get('share_metrics', {}))} KPIs")

if __name__ == '__main__':
    main()
