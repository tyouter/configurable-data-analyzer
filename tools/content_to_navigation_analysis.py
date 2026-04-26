# -*- coding: utf-8 -*-
# Adapted for v2 dataset: rednote data_20260319-20260330.xlsx
"""
种草→拔草 端到端分析
Content to Navigation End-to-End Funnel Analysis (User-Level)
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
import math
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_PATH = r'C:\projects\rednote data analyzer\data\rednote\rednote20260319-20260412.xlsx'
OUTPUT_DIR = r'C:\projects\rednote data analyzer\report\fulldata_v2'

# Event definitions
CONTENT_SHOW_EVENTS = [
    'discovery_page_post_card_cardshow',
    'porsche_page_recommend_post_card_cardshow'
]
CONTENT_CLICK_EVENTS = [
    'discovery_page_post_card_click',
    'porsche_page_recommend_post_card_click'
]
DISCOVERY_SHOW = ['discovery_page_post_card_cardshow']
DISCOVERY_CLICK = ['discovery_page_post_card_click']
PORSCHE_SHOW = ['porsche_page_recommend_post_card_cardshow']
PORSCHE_CLICK = ['porsche_page_recommend_post_card_click']
POI_TRIGGER = ['post_detail_page_POI_button_show']
POI_DETAIL = ['poi_detail_page_pageshow']
NAV_INIT_EVENTS = [
    'poi_detail_page_navigation_button_click',
    'trival_guide_page_detail_tab_poi_navigation_button_click'
]
NAV_CONFIRM_EVENTS = [
    'poi_detail_page_navigation_popup_confirm_click',
    'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
]
AI_GUIDE_EVENTS = [
    'post_detail_page_ai_travel_guide_button_click',
    'post_detail_page_generated_travel_guide_button_click',
    'trival_guide_page_pageshow'
]
SHARE_EVENTS = [
    'trival_guide_page_share_icon_click',
    'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click'
]

# Active feature trigger events
ACTIVE_TRIGGER_EVENTS = [
    'discovery_page_post_card_click', 'porsche_page_recommend_post_card_click',
    'discovery_page_post_like_click', 'porsche_page_recommend_account_cardclick',
    'porsche_page_recommend_account_follow_button_click',
    'post_detail_page_POI_button_click', 'poi_detail_page_post_card_click',
    'poi_detail_page_tel_btn_click',
    'poi_detail_page_navigation_button_click', 'poi_detail_page_navigation_popup_confirm_click',
    'poi_detail_page_navigation_popup_cancel_click',
    'trival_guide_page_detail_tab_poi_navigation_button_click',
    'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click',
    'trival_guide_page_detail_tab_poi_navigation_popup_cancel_click',
    'post_detail_page_ai_travel_guide_button_click',
    'post_detail_page_generated_travel_guide_button_click',
    'discovery_page_search_click', 'porsche_page_search_click',
    'search_homepage_search_history_query_item_delete_click',
    'trival_guide_page_share_icon_click',
    'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click',
    'porsche_page_Map_poi_card_click', 'porsche_page_Map_POI_Category_click',
    'porsche_page_Map_poi_Category_entry_click',
    'porsche_page_map_onFullscreen_Entry_Click', 'porsche_page_map_onFullscreen_Exit_Click',
    'porsche_page_map_return_to_my_location_click',
    'porsche_page_map_map_zoom_in', 'porsche_page_map_map_zoom_out',
    'login_page_QRCode_Authentication',
    'discovery_page_search_mic_click', 'porsche_page_search_mic_click',
    'Profile_page_travel_guide_tab_click',
    'profile_page_travel_guide_tab_trip_card_click',
    'profile_page_travel_guide_tab_create_trip_click',
    'profile_page_travel_guide_tab_add_trip_entry_click',
    'trival_guide_page_detail_tab_click',
    'trival_guide_page_detail_tab_add_place_entry_click',
    'trival_guide_page_detail_tab_add_place_card_click',
    'trival_guide_page_overview_tab_click',
    'trival_guide_page_detail_tab_poi_post_search_button_click',
]


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
    else:
        return obj


def wilson_confidence_interval(successes, n, z=1.96):
    if n == 0:
        return 0, 0
    p = successes / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominator
    precision = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denominator
    lower = max(0, centre - precision) * 100
    upper = min(1, centre + precision) * 100
    return lower, upper


def load_data():
    print("=" * 70)
    print("种草→拔草 端到端分析")
    print(f"数据源: {DATA_PATH}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"数据概览: {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['timestamp'] = pd.to_datetime(df['start_time_nano'], errors='coerce')
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour

    total_users = df['reduser_id'].nunique()
    active_users = df[df['span_name'].isin(ACTIVE_TRIGGER_EVENTS)]['reduser_id'].nunique()
    print(f"总用户数: {total_users}")
    print(f"活跃用户数(功能触发): {active_users}")

    return df, total_users, active_users


def build_e2e_funnel(df):
    """构建种草拔草端到端漏斗（用户级）"""
    print("\n" + "=" * 50)
    print("[种草→拔草 漏斗]")
    print("=" * 50)

    steps = [
        ('Step1 内容曝光', CONTENT_SHOW_EVENTS),
        ('Step2 内容点击', CONTENT_CLICK_EVENTS),
        ('Step3 POI触发', POI_TRIGGER),
        ('Step4 POI详情', POI_DETAIL),
        ('Step5 发起导航', NAV_INIT_EVENTS),
        ('Step6 确认导航', NAV_CONFIRM_EVENTS)
    ]

    funnel = []
    prev_users = set(df['reduser_id'].dropna().unique())

    for step_name, events in steps:
        users = set(df[df['span_name'].isin(events)]['reduser_id'].dropna().unique())
        user_count = len(users)

        conv_prev = round(user_count / len(prev_users) * 100, 2) if len(prev_users) > 0 else 0
        event_count = len(df[df['span_name'].isin(events)])

        # Median events per user
        if user_count > 0:
            user_evts = df[df['reduser_id'].isin(users) & df['span_name'].isin(events)].groupby('reduser_id').size()
            median_evts = float(user_evts.median())
        else:
            median_evts = 0

        step_data = {
            'step_name': step_name,
            'events': events,
            'user_count': user_count,
            'event_count': int(event_count),
            'conversion_from_prev_pct': float(conv_prev),
            'median_events_per_user': float(median_evts)
        }
        funnel.append(step_data)

        print(f"  {step_name}: {user_count} 用户 ({conv_prev}%)")
        prev_users = users

    # Calculate overall conversion from step 1
    step1_users = funnel[0]['user_count']
    for i, step in enumerate(funnel):
        step['conversion_from_step1_pct'] = round(
            step['user_count'] / step1_users * 100, 2
        ) if step1_users > 0 else 0

    return funnel


def entry_source_analysis(df):
    """按入口来源分析"""
    print("\n" + "=" * 50)
    print("[入口来源对比]")
    print("=" * 50)

    sources = {
        'Discovery页面': {
            'show': DISCOVERY_SHOW,
            'click': DISCOVERY_CLICK
        },
        'Porsche+页面': {
            'show': PORSCHE_SHOW,
            'click': PORSCHE_CLICK
        }
    }

    results = {}
    for source_name, events in sources.items():
        entry_users = set(df[df['span_name'].isin(events['show'])]['reduser_id'].dropna().unique())
        click_users = set(df[df['span_name'].isin(events['click'])]['reduser_id'].dropna().unique())
        poi_users = set(df[df['span_name'].isin(POI_DETAIL)]['reduser_id'].dropna().unique())
        nav_users = set(df[df['span_name'].isin(NAV_INIT_EVENTS)]['reduser_id'].dropna().unique())
        confirm_users = set(df[df['span_name'].isin(NAV_CONFIRM_EVENTS)]['reduser_id'].dropna().unique())

        total = len(entry_users)
        results[source_name] = {
            'exposure_users': total,
            'click_users': len(click_users),
            'poi_users': len(poi_users & entry_users),
            'navigation_users': len(nav_users & entry_users),
            'confirm_users': len(confirm_users & entry_users),
            'click_rate': round(len(click_users) / total * 100, 2) if total > 0 else 0,
            'nav_rate': round(len(nav_users & entry_users) / total * 100, 2) if total > 0 else 0,
            'confirm_rate': round(len(confirm_users & entry_users) / total * 100, 2) if total > 0 else 0
        }

        print(f"  {source_name}: {total}曝光 → {results[source_name]['click_rate']}%点击 → {results[source_name]['nav_rate']}%导航")

    return results


def poi_type_analysis(df):
    """POI类型分析"""
    print("\n" + "=" * 50)
    print("[POI类型分析]")
    print("=" * 50)

    poi_df = df[df['span_name'].isin(NAV_INIT_EVENTS + NAV_CONFIRM_EVENTS)].copy()
    if 'rednote_poi_type_name' not in poi_df.columns:
        print("  无 rednote_poi_type_name 列")
        return {}

    poi_types = poi_df[poi_df['rednote_poi_type_name'].notna()].groupby('rednote_poi_type_name').agg(
        nav_init_count=('reduser_id', 'count'),
        nav_users=('reduser_id', 'nunique')
    ).sort_values('nav_init_count', ascending=False).head(10)

    results = {}
    for poi_type, row in poi_types.iterrows():
        confirm_df = poi_df[
            (poi_df['rednote_poi_type_name'] == poi_type) &
            (poi_df['span_name'].isin(NAV_CONFIRM_EVENTS))
        ]
        results[str(poi_type)] = {
            'navigation_count': int(row['nav_init_count']),
            'navigation_users': int(row['nav_users']),
            'confirm_count': len(confirm_df),
            'confirm_rate': round(len(confirm_df) / int(row['nav_init_count']) * 100, 2) if row['nav_init_count'] > 0 else 0
        }
        print(f"  {poi_type}: {int(row['nav_init_count'])}次导航, {int(row['nav_users'])}用户")

    return results


def content_type_analysis(df):
    """内容类型分析"""
    print("\n" + "=" * 50)
    print("[内容类型分析]")
    print("=" * 50)

    content_df = df[df['span_name'].isin(CONTENT_SHOW_EVENTS + CONTENT_CLICK_EVENTS)].copy()
    if 'rednote_post_type' not in content_df.columns:
        print("  无 rednote_post_type 列")
        return {}

    post_types = content_df[content_df['rednote_post_type'].notna()].groupby('rednote_post_type').agg(
        show_count=('reduser_id', 'count'),
        unique_users=('reduser_id', 'nunique')
    ).sort_values('show_count', ascending=False).head(10)

    results = {}
    for post_type, row in post_types.iterrows():
        type_clicks = content_df[
            (content_df['rednote_post_type'] == post_type) &
            (content_df['span_name'].isin(CONTENT_CLICK_EVENTS))
        ]
        results[str(post_type)] = {
            'exposure_count': int(row['show_count']),
            'click_count': len(type_clicks),
            'click_rate': round(len(type_clicks) / int(row['show_count']) * 100, 2) if row['show_count'] > 0 else 0,
            'unique_users': int(row['unique_users'])
        }
        print(f"  {post_type}: {int(row['show_count'])}曝光, {results[str(post_type)]['click_rate']}%点击率")

    return results


def ai_guide_impact(df):
    """AI路书对导航的拉动效应"""
    print("\n" + "=" * 50)
    print("[AI路书拉动效应]")
    print("=" * 50)

    ai_users = set(df[df['span_name'].isin(AI_GUIDE_EVENTS)]['reduser_id'].dropna().unique())
    all_users = set(df['reduser_id'].dropna().unique())
    non_ai_users = all_users - ai_users

    def user_metrics(user_set, label):
        if not user_set:
            return None
        udf = df[df['reduser_id'].isin(user_set)]
        click_events = udf[udf['event_type'] == 'CLICK']
        nav_init = udf[udf['span_name'].isin(NAV_INIT_EVENTS)]
        nav_confirm = udf[udf['span_name'].isin(NAV_CONFIRM_EVENTS)]

        user_stats = udf.groupby('reduser_id').agg(
            events=('span_name', 'count'),
            days=('date', 'nunique')
        )

        return {
            'label': label,
            'user_count': len(user_set),
            'avg_events': round(float(user_stats['events'].mean()), 1),
            'avg_active_days': round(float(user_stats['days'].mean()), 1),
            'navigation_init_count': len(nav_init),
            'navigation_init_users': nav_init['reduser_id'].nunique(),
            'navigation_init_rate': round(nav_init['reduser_id'].nunique() / len(user_set) * 100, 2),
            'navigation_confirm_count': len(nav_confirm),
            'navigation_confirm_users': nav_confirm['reduser_id'].nunique(),
            'navigation_confirm_rate': round(nav_confirm['reduser_id'].nunique() / len(user_set) * 100, 2),
            'total_clicks': len(click_events),
            'nav_conversion_efficiency': round(len(nav_init) / len(click_events) * 100, 4) if len(click_events) > 0 else 0
        }

    ai_metrics = user_metrics(ai_users, 'AI路书用户')
    non_ai_metrics = user_metrics(non_ai_users, '非AI路书用户')

    # AI guide page navigation rate
    trival_guide_df = df[df['span_name'].str.contains('trival_guide', case=False, na=False)]
    trival_guide_users = trival_guide_df['reduser_id'].nunique()
    trival_nav_users = trival_guide_df[trival_guide_df['span_name'].isin([
        'trival_guide_page_detail_tab_poi_navigation_button_click',
        'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
    ])]['reduser_id'].nunique()
    ai_page_nav_rate = round(trival_nav_users / trival_guide_users * 100, 2) if trival_guide_users > 0 else 0

    # Retention comparison
    user_first_date = df.groupby('reduser_id')['date'].min()
    min_date = df['date'].min()
    max_date = df['date'].max()
    total_days = (max_date - min_date).days + 1

    ai_retention = {'rate': 'N/A', 'eligible': 0}
    non_ai_retention = {'rate': 'N/A', 'eligible': 0}

    if total_days >= 8:
        for group_users, retention_dict, label in [(ai_users, ai_retention, 'AI'), (non_ai_users, non_ai_retention, 'Non-AI')]:
            eligible = 0
            retained = 0
            for uid in group_users:
                if uid not in user_first_date.index:
                    continue
                first_d = user_first_date[uid]
                target_d = first_d + timedelta(days=7)
                if target_d <= max_date:
                    eligible += 1
                    if target_d in set(df[df['reduser_id'] == uid]['date']):
                        retained += 1
            if eligible > 0:
                ci_l, ci_u = wilson_confidence_interval(retained, eligible)
                retention_dict['rate'] = round(retained / eligible * 100, 2)
                retention_dict['eligible'] = eligible
                retention_dict['retained'] = retained
                retention_dict['ci_95'] = [round(ci_l, 2), round(ci_u, 2)]

    result = {
        'ai_users': ai_metrics,
        'non_ai_users': non_ai_metrics,
        'ai_guide_page_navigation_rate': {
            'rate_pct': ai_page_nav_rate,
            'trival_guide_users': trival_guide_users,
            'trival_nav_users': trival_nav_users
        },
        'retention_comparison': {
            'ai_guide_users': ai_retention,
            'non_ai_users': non_ai_retention
        }
    }

    if ai_metrics:
        print(f"  AI路书用户({ai_metrics['user_count']}): 导航率{ai_metrics['navigation_init_rate']}%, 转化效率{ai_metrics['nav_conversion_efficiency']}%")
    if non_ai_metrics:
        print(f"  非AI路书用户({non_ai_metrics['user_count']}): 导航率{non_ai_metrics['navigation_init_rate']}%, 转化效率{non_ai_metrics['nav_conversion_efficiency']}%")
    print(f"  AI路书页内导航率: {ai_page_nav_rate}%")

    return result


def main():
    ensure_dir(OUTPUT_DIR)

    df, total_users, active_users = load_data()

    results = {
        'meta': {
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': DATA_PATH,
            'total_users': int(total_users),
            'active_users': int(active_users),
            'active_user_definition': '触发过至少一项核心功能的用户',
            'inactive_users': int(total_users - active_users)
        },
        'e2e_funnel': build_e2e_funnel(df),
        'entry_source_analysis': entry_source_analysis(df),
        'poi_type_analysis': poi_type_analysis(df),
        'content_type_analysis': content_type_analysis(df),
        'ai_guide_impact': ai_guide_impact(df)
    }

    json_path = os.path.join(OUTPUT_DIR, 'content_to_navigation_analysis.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, ensure_ascii=False, indent=2)
    print(f"\n种草拔草分析已保存: {json_path}")

    print("\n" + "=" * 70)
    print("种草→拔草 分析完成!")
    print("=" * 70)

    return results


if __name__ == '__main__':
    main()
