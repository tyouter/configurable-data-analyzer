# -*- coding: utf-8 -*-
# Adapted for v2 dataset: rednote data_20260319-20260330.xlsx
"""
北极星指标分析: 导航转化效率
North Star Metric: Navigation Conversion Efficiency
= Navigation Initiation Total / All CLICK Events Total
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

NAV_INIT_EVENTS = [
    'poi_detail_page_navigation_button_click',
    'trival_guide_page_detail_tab_poi_navigation_button_click'
]
NAV_CONFIRM_EVENTS = [
    'poi_detail_page_navigation_popup_confirm_click',
    'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
]

# Active feature trigger events: users who triggered at least one core feature
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
    print("北极星指标分析: 导航转化效率")
    print(f"数据源: {DATA_PATH}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"数据概览: {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['timestamp'] = pd.to_datetime(df['start_time_nano'], errors='coerce')
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.dayofweek

    total_users = df['reduser_id'].nunique()
    print(f"用户数: {total_users}")
    print(f"时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

    return df, total_users


def calculate_north_star(df):
    """计算北极星指标核心值"""
    print("\n" + "=" * 50)
    print("[北极星指标]")
    print("=" * 50)

    click_df = df[df['event_type'] == 'CLICK']
    total_clicks = len(click_df)

    nav_init_df = df[df['span_name'].isin(NAV_INIT_EVENTS)]
    nav_init_count = len(nav_init_df)
    nav_init_users = nav_init_df['reduser_id'].nunique()

    nav_confirm_df = df[df['span_name'].isin(NAV_CONFIRM_EVENTS)]
    nav_confirm_count = len(nav_confirm_df)
    nav_confirm_users = nav_confirm_df['reduser_id'].nunique()

    total_users = df['reduser_id'].nunique()
    active_users = df[df['span_name'].isin(ACTIVE_TRIGGER_EVENTS)]['reduser_id'].nunique()
    nav_conversion = round(nav_init_count / total_clicks * 100, 4) if total_clicks > 0 else 0
    nav_user_ratio = round(nav_init_users / total_users * 100, 2) if total_users > 0 else 0
    nav_user_ratio_active = round(nav_init_users / active_users * 100, 2) if active_users > 0 else 0
    nav_confirm_rate = round(nav_confirm_count / nav_init_count * 100, 2) if nav_init_count > 0 else 0

    ci_lower, ci_upper = wilson_confidence_interval(nav_init_users, total_users)
    ci_lower_a, ci_upper_a = wilson_confidence_interval(nav_init_users, active_users)

    result = {
        'user_counts': {
            'total_users': int(total_users),
            'active_users': int(active_users),
            'active_user_definition': '触发过至少一项核心功能(内容点击/POI/导航/AI路书/搜索/点赞/收藏/分享)的用户',
            'inactive_users': int(total_users - active_users)
        },
        'north_star_metric': {
            'name': '导航转化效率',
            'formula': '发起导航总次数 / 用户总有效操作次数(所有CLICK事件)',
            'value_pct': float(nav_conversion),
            'numerator': {
                'description': '发起导航总次数',
                'events': NAV_INIT_EVENTS,
                'count': int(nav_init_count)
            },
            'denominator': {
                'description': '用户总有效操作次数(所有CLICK事件)',
                'count': int(total_clicks)
            }
        },
        'navigation_user_ratio': {
            'name': '导航用户占比(总用户)',
            'formula': '发起过导航的用户 / 总用户',
            'value_pct': float(nav_user_ratio),
            'navigation_users': int(nav_init_users),
            'total_users': int(total_users),
            'ci_95': [round(ci_lower, 2), round(ci_upper, 2)]
        },
        'navigation_user_ratio_active': {
            'name': '导航用户占比(活跃用户)',
            'formula': '发起过导航的用户 / 活跃用户(功能触发)',
            'value_pct': float(nav_user_ratio_active),
            'navigation_users': int(nav_init_users),
            'active_users': int(active_users),
            'ci_95': [round(ci_lower_a, 2), round(ci_upper_a, 2)]
        },
        'navigation_confirmation_rate': {
            'name': '导航确认率',
            'value_pct': float(nav_confirm_rate),
            'confirm_count': int(nav_confirm_count),
            'initiation_count': int(nav_init_count),
            'confirm_users': int(nav_confirm_users)
        }
    }

    print(f"  总用户: {total_users} | 活跃用户(功能触发): {active_users} | 非活跃: {total_users - active_users}")
    print(f"  导航转化效率: {nav_conversion}%")
    print(f"    分子(发起导航): {nav_init_count}")
    print(f"    分母(CLICK事件): {total_clicks}")
    print(f"  导航用户占比(总用户): {nav_user_ratio}% ({nav_init_users}/{total_users})")
    print(f"  导航用户占比(活跃用户): {nav_user_ratio_active}% ({nav_init_users}/{active_users})")
    print(f"    Wilson 95% CI (总): [{ci_lower:.1f}%, {ci_upper:.1f}%]")
    print(f"    Wilson 95% CI (活跃): [{ci_lower_a:.1f}%, {ci_upper_a:.1f}%]")
    print(f"  导航确认率: {nav_confirm_rate}% ({nav_confirm_count}/{nav_init_count})")

    return result


def daily_trend(df):
    """每日趋势"""
    print("\n" + "=" * 50)
    print("[每日趋势]")
    print("=" * 50)

    daily_data = []
    for date, day_df in df.groupby('date'):
        clicks = len(day_df[day_df['event_type'] == 'CLICK'])
        nav_inits = len(day_df[day_df['span_name'].isin(NAV_INIT_EVENTS)])
        nav_users = day_df[day_df['span_name'].isin(NAV_INIT_EVENTS)]['reduser_id'].nunique()
        total_users_day = day_df['reduser_id'].nunique()
        rate = round(nav_inits / clicks * 100, 4) if clicks > 0 else 0
        user_ratio = round(nav_users / total_users_day * 100, 2) if total_users_day > 0 else 0

        daily_data.append({
            'date': str(date),
            'click_events': int(clicks),
            'navigation_inits': int(nav_inits),
            'navigation_users': int(nav_users),
            'total_users': int(total_users_day),
            'conversion_rate_pct': float(rate),
            'nav_user_ratio_pct': float(user_ratio)
        })

    # 3-day moving average
    rates = [d['conversion_rate_pct'] for d in daily_data]
    for i in range(len(daily_data)):
        start = max(0, i - 1)
        end = min(len(rates), i + 2)
        daily_data[i]['ma3_rate_pct'] = round(sum(rates[start:end]) / (end - start), 4)

    print(f"  生成 {len(daily_data)} 天数据")
    if daily_data:
        print(f"  日均转化效率: {round(sum(d['conversion_rate_pct'] for d in daily_data) / len(daily_data), 4)}%")
        print(f"  最高: {max(d['conversion_rate_pct'] for d in daily_data)}%")
        print(f"  最低: {min(d['conversion_rate_pct'] for d in daily_data)}%")

    return daily_data


def weekly_trend(df):
    """周趋势"""
    print("\n" + "=" * 50)
    print("[周趋势]")
    print("=" * 50)

    df['iso_week'] = df['timestamp'].dt.isocalendar().week.astype(int)
    df['iso_year'] = df['timestamp'].dt.isocalendar().year.astype(int)

    weekly_data = []
    for (year, week), week_df in df.groupby(['iso_year', 'iso_week']):
        clicks = len(week_df[week_df['event_type'] == 'CLICK'])
        nav_inits = len(week_df[week_df['span_name'].isin(NAV_INIT_EVENTS)])
        nav_users = week_df[week_df['span_name'].isin(NAV_INIT_EVENTS)]['reduser_id'].nunique()
        total_users_week = week_df['reduser_id'].nunique()
        rate = round(nav_inits / clicks * 100, 4) if clicks > 0 else 0

        weekly_data.append({
            'year_week': f"{year}-W{week:02d}",
            'click_events': int(clicks),
            'navigation_inits': int(nav_inits),
            'navigation_users': int(nav_users),
            'total_users': int(total_users_week),
            'conversion_rate_pct': float(rate)
        })

    for w in weekly_data:
        print(f"  {w['year_week']}: {w['conversion_rate_pct']}% ({w['navigation_inits']}/{w['click_events']})")

    return weekly_data


def user_segmentation_comparison(df):
    """按用户活跃度分群对比"""
    print("\n" + "=" * 50)
    print("[用户分群对比]")
    print("=" * 50)

    user_events = df.groupby('reduser_id').size().reset_index(name='total_events')
    q33 = user_events['total_events'].quantile(0.33)
    q66 = user_events['total_events'].quantile(0.66)

    user_events['segment'] = pd.cut(
        user_events['total_events'],
        bins=[0, q33, q66, float('inf')],
        labels=['low', 'medium', 'high']
    )

    segments = {}
    for seg_name in ['low', 'medium', 'high']:
        seg_users = user_events[user_events['segment'] == seg_name]['reduser_id'].tolist()
        seg_df = df[df['reduser_id'].isin(seg_users)]

        clicks = len(seg_df[seg_df['event_type'] == 'CLICK'])
        nav_inits = len(seg_df[seg_df['span_name'].isin(NAV_INIT_EVENTS)])
        nav_users = seg_df[seg_df['span_name'].isin(NAV_INIT_EVENTS)]['reduser_id'].nunique()
        total_seg_users = len(seg_users)

        conversion = round(nav_inits / clicks * 100, 4) if clicks > 0 else 0
        nav_ratio = round(nav_users / total_seg_users * 100, 2) if total_seg_users > 0 else 0

        segments[seg_name] = {
            'user_count': total_seg_users,
            'event_range': f"≤{int(q33)}" if seg_name == 'low' else (f"{int(q33)+1}-{int(q66)}" if seg_name == 'medium' else f">{int(q66)}"),
            'avg_events': round(seg_df.groupby('reduser_id').size().mean(), 1),
            'click_events': int(clicks),
            'navigation_inits': int(nav_inits),
            'navigation_users': int(nav_users),
            'conversion_rate_pct': float(conversion),
            'nav_user_ratio_pct': float(nav_ratio)
        }

        print(f"  [{seg_name.upper()}] {total_seg_users}用户, 转化: {conversion}%, 导航用户占比: {nav_ratio}%")

    return segments


def navigation_user_profile(df):
    """导航用户画像对比"""
    print("\n" + "=" * 50)
    print("[导航用户画像]")
    print("=" * 50)

    nav_users = set(df[df['span_name'].isin(NAV_INIT_EVENTS)]['reduser_id'].unique())
    active_users = set(df[df['span_name'].isin(ACTIVE_TRIGGER_EVENTS)]['reduser_id'].unique())
    all_users = set(df['reduser_id'].unique())
    non_nav_users = all_users - nav_users

    def profile(user_set, label):
        if not user_set:
            return None
        udf = df[df['reduser_id'].isin(user_set)]
        user_stats = udf.groupby('reduser_id').agg(
            events=('span_name', 'count'),
            features=('span_name', 'nunique'),
            days=('date', 'nunique')
        )
        return {
            'label': label,
            'user_count': len(user_set),
            'avg_events': round(float(user_stats['events'].mean()), 1),
            'median_events': float(user_stats['events'].median()),
            'avg_active_days': round(float(user_stats['days'].mean()), 1),
            'avg_feature_breadth': round(float(user_stats['features'].mean()), 1)
        }

    nav_profile = profile(nav_users, '导航用户')
    non_nav_profile = profile(non_nav_users, '非导航用户')

    if nav_profile and non_nav_profile:
        print(f"  导航用户: {nav_profile['user_count']}人, 均事件{nav_profile['avg_events']}, 均{nav_profile['avg_active_days']}天")
        print(f"  非导航用户: {non_nav_profile['user_count']}人, 均事件{non_nav_profile['avg_events']}, 均{non_nav_profile['avg_active_days']}天")

    return {'navigation_users': nav_profile, 'non_navigation_users': non_nav_profile}


def main():
    ensure_dir(OUTPUT_DIR)

    df, total_users = load_data()

    results = {
        'meta': {
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': DATA_PATH,
            'data_period': {
                'start': str(df['timestamp'].min()),
                'end': str(df['timestamp'].max()),
                'days': int((df['timestamp'].max() - df['timestamp'].min()).days + 1)
            },
            'total_users': int(total_users),
            'total_events': int(len(df))
        }
    }

    results['north_star'] = calculate_north_star(df)
    results['daily_trend'] = daily_trend(df)
    results['weekly_trend'] = weekly_trend(df)
    results['user_segmentation'] = user_segmentation_comparison(df)
    results['navigation_user_profile'] = navigation_user_profile(df)

    json_path = os.path.join(OUTPUT_DIR, 'north_star_analysis.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, ensure_ascii=False, indent=2)
    print(f"\n北极星指标分析已保存: {json_path}")

    print("\n" + "=" * 70)
    print("北极星指标分析完成!")
    print("=" * 70)

    return results


if __name__ == '__main__':
    main()
