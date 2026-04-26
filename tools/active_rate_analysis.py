# -*- coding: utf-8 -*-
# 活跃率专项分析报告
# Total Users = 206 (all parsed), Active Users = triggered ≥1 core feature
# Daily / Weekly / Weekend / Weekday / Holiday active rate trends

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

# Chinese holidays in the data range
HOLIDAYS = {
    '2026-04-04': '清明节',
    '2026-04-05': '清明节',
    '2026-04-06': '清明节',
}


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


def load_data():
    print("=" * 70)
    print("活跃率专项分析报告")
    print(f"数据源: {DATA_PATH}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"数据概览: {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['timestamp'] = pd.to_datetime(df['start_time_nano'], errors='coerce')
    df['date'] = df['timestamp'].dt.date
    df['weekday'] = df['timestamp'].dt.dayofweek  # 0=Mon, 6=Sun
    df['iso_week'] = df['timestamp'].dt.isocalendar().week.astype(int)
    df['iso_year'] = df['timestamp'].dt.isocalendar().year.astype(int)

    df['is_active_trigger'] = df['span_name'].isin(ACTIVE_TRIGGER_EVENTS)

    total_users = df['reduser_id'].nunique()
    active_users_overall = df[df['is_active_trigger']]['reduser_id'].nunique()
    print(f"总用户数: {total_users}")
    print(f"活跃用户数(功能触发): {active_users_overall}")
    print(f"整体活跃率: {round(active_users_overall/total_users*100, 2)}%")
    print(f"时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

    return df, total_users


def daily_active_rate(df, total_users):
    """日活跃率 = 当日触发核心功能的用户数 / 总用户数"""
    print("\n" + "=" * 50)
    print("[日活跃率趋势]")
    print("=" * 50)

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_names_cn = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

    daily = []
    for date in sorted(df['date'].unique()):
        day_df = df[df['date'] == date]
        dau_total = day_df['reduser_id'].nunique()
        dau_active = day_df[day_df['is_active_trigger']]['reduser_id'].nunique()
        wd = pd.Timestamp(date).dayofweek
        is_weekend = wd >= 5
        date_str = str(date)
        is_holiday = date_str in HOLIDAYS

        rate_total = round(dau_total / total_users * 100, 2)
        rate_active = round(dau_active / total_users * 100, 2)

        daily.append({
            'date': date_str,
            'weekday': day_names[wd],
            'weekday_cn': day_names_cn[wd],
            'is_weekend': is_weekend,
            'is_holiday': is_holiday,
            'holiday_name': HOLIDAYS.get(date_str, ''),
            'dau_total': int(dau_total),
            'dau_active': int(dau_active),
            'active_rate_pct': float(rate_active),
            'dau_total_rate_pct': float(rate_total),
            'events': int(len(day_df))
        })

        label = 'WEEKEND' if is_weekend else ('HOLIDAY' if is_holiday else '')
        print(f"  {date} ({day_names_cn[wd]}) {label}: {dau_active}/{total_users} = {rate_active}%")

    return daily


def weekly_active_rate(df, total_users):
    """周活跃率 = 当周触发核心功能的用户数 / 总用户数"""
    print("\n" + "=" * 50)
    print("[周活跃率趋势]")
    print("=" * 50)

    weekly = []
    for (year, week), week_df in df.groupby(['iso_year', 'iso_week']):
        wau_total = week_df['reduser_id'].nunique()
        wau_active = week_df[week_df['is_active_trigger']]['reduser_id'].nunique()
        rate_active = round(wau_active / total_users * 100, 2)

        # Get date range for this week
        dates_in_week = sorted(week_df['date'].unique())

        weekly.append({
            'year_week': f"{year}-W{week:02d}",
            'start_date': str(dates_in_week[0]),
            'end_date': str(dates_in_week[-1]),
            'days_in_week': len(dates_in_week),
            'wau_total': int(wau_total),
            'wau_active': int(wau_active),
            'active_rate_pct': float(rate_active),
            'events': int(len(week_df))
        })

        print(f"  {year}-W{week:02d} ({dates_in_week[0]}~{dates_in_week[-1]}): {wau_active}/{total_users} = {rate_active}%")

    return weekly


def weekend_active_rate(df, total_users):
    """周末活跃率（累积）: 从开始至每个周末日的累积活跃用户/总用户"""
    print("\n" + "=" * 50)
    print("[周末活跃率]")
    print("=" * 50)

    weekend_dates = sorted(d for d in df['date'].unique() if pd.Timestamp(d).dayofweek >= 5)

    # Per-weekend-day active rate
    per_day = []
    cumulative_active = set()
    for d in weekend_dates:
        day_df = df[df['date'] == d]
        day_active = set(day_df[day_df['is_active_trigger']]['reduser_id'].unique())
        day_total = day_df['reduser_id'].nunique()
        cumulative_active |= day_active

        per_day.append({
            'date': str(d),
            'weekday': 'Sat' if pd.Timestamp(d).dayofweek == 5 else 'Sun',
            'dau_active': len(day_active),
            'dau_total': int(day_total),
            'active_rate_pct': round(len(day_active) / total_users * 100, 2),
            'cumulative_active_users': len(cumulative_active),
            'cumulative_active_rate_pct': round(len(cumulative_active) / total_users * 100, 2)
        })

    overall_weekend_active = df[(df['weekday'] >= 5) & (df['is_active_trigger'])]['reduser_id'].nunique()
    overall_weekend_total = df[df['weekday'] >= 5]['reduser_id'].nunique()

    result = {
        'definition': '周末(周六/周日)触发核心功能的用户数 / 总用户数',
        'overall': {
            'weekend_active_users': int(overall_weekend_active),
            'weekend_total_users_seen': int(overall_weekend_total),
            'weekend_active_rate_pct': round(overall_weekend_active / total_users * 100, 2),
            'total_users': int(total_users),
            'weekend_days': len(weekend_dates)
        },
        'per_day': per_day
    }

    print(f"  周末总活跃用户: {overall_weekend_active}/{total_users} = {round(overall_weekend_active/total_users*100,2)}%")
    for p in per_day:
        print(f"  {p['date']} ({p['weekday']}): {p['dau_active']}/{total_users} = {p['active_rate_pct']}%")

    return result


def weekday_active_rate(df, total_users):
    """工作日活跃率（累积）"""
    print("\n" + "=" * 50)
    print("[工作日活跃率]")
    print("=" * 50)

    weekday_dates = sorted(d for d in df['date'].unique() if pd.Timestamp(d).dayofweek < 5)

    per_day = []
    cumulative_active = set()
    for d in weekday_dates:
        day_df = df[df['date'] == d]
        day_active = set(day_df[day_df['is_active_trigger']]['reduser_id'].unique())
        day_total = day_df['reduser_id'].nunique()
        cumulative_active |= day_active

        per_day.append({
            'date': str(d),
            'dau_active': len(day_active),
            'dau_total': int(day_total),
            'active_rate_pct': round(len(day_active) / total_users * 100, 2),
            'cumulative_active_users': len(cumulative_active),
            'cumulative_active_rate_pct': round(len(cumulative_active) / total_users * 100, 2)
        })

    overall_weekday_active = df[(df['weekday'] < 5) & (df['is_active_trigger'])]['reduser_id'].nunique()

    result = {
        'definition': '工作日(周一~周五)触发核心功能的用户数 / 总用户数',
        'overall': {
            'weekday_active_users': int(overall_weekday_active),
            'weekday_active_rate_pct': round(overall_weekday_active / total_users * 100, 2),
            'total_users': int(total_users),
            'weekday_days': len(weekday_dates)
        },
        'per_day': per_day
    }

    print(f"  工作日总活跃用户: {overall_weekday_active}/{total_users} = {round(overall_weekday_active/total_users*100,2)}%")
    for p in per_day:
        print(f"  {p['date']}: {p['dau_active']}/{total_users} = {p['active_rate_pct']}%")

    return result


def holiday_active_rate(df, total_users):
    """节假日活跃率"""
    print("\n" + "=" * 50)
    print("[节假日活跃率]")
    print("=" * 50)

    holiday_dates_in_data = [d for d in df['date'].unique() if str(d) in HOLIDAYS]

    result = {
        'definition': '法定节假日触发核心功能的用户数 / 总用户数',
        'holidays_in_range': HOLIDAYS,
        'holiday_dates_in_data': [str(d) for d in holiday_dates_in_data],
        'per_day': [],
        'overall': {
            'holiday_active_users': 0,
            'holiday_active_rate_pct': 0,
            'total_users': int(total_users),
            'holiday_days': 0
        },
        'note': '数据周期(2026-03-19~2026-04-12)，含清明节(4/4-4/6)'
    }

    if holiday_dates_in_data:
        per_day = []
        cumulative = set()
        for d in holiday_dates_in_data:
            day_df = df[df['date'] == d]
            day_active = set(day_df[day_df['is_active_trigger']]['reduser_id'].unique())
            cumulative |= day_active
            per_day.append({
                'date': str(d),
                'holiday_name': HOLIDAYS[str(d)],
                'dau_active': len(day_active),
                'dau_total': int(day_df['reduser_id'].nunique()),
                'active_rate_pct': round(len(day_active) / total_users * 100, 2),
                'cumulative_active_rate_pct': round(len(cumulative) / total_users * 100, 2)
            })

        overall_active = df[(df['date'].isin(holiday_dates_in_data)) & df['is_active_trigger']]['reduser_id'].nunique()
        result['per_day'] = per_day
        result['overall'] = {
            'holiday_active_users': int(overall_active),
            'holiday_active_rate_pct': round(overall_active / total_users * 100, 2),
            'total_users': int(total_users),
            'holiday_days': len(holiday_dates_in_data)
        }

    print(f"  数据范围内节假日: {len(holiday_dates_in_data)} 天")
    print(f"  {result['note']}")

    return result


def active_rate_comparison(daily, total_users):
    """按类型汇总对比"""
    weekday_rates = [d['active_rate_pct'] for d in daily if not d['is_weekend'] and not d['is_holiday']]
    weekend_rates = [d['active_rate_pct'] for d in daily if d['is_weekend']]
    holiday_rates = [d['active_rate_pct'] for d in daily if d['is_holiday']]

    comparison = {
        'weekday': {
            'days': len(weekday_rates),
            'avg_active_rate_pct': round(sum(weekday_rates) / len(weekday_rates), 2) if weekday_rates else 0,
            'max_active_rate_pct': round(max(weekday_rates), 2) if weekday_rates else 0,
            'min_active_rate_pct': round(min(weekday_rates), 2) if weekday_rates else 0,
        },
        'weekend': {
            'days': len(weekend_rates),
            'avg_active_rate_pct': round(sum(weekend_rates) / len(weekend_rates), 2) if weekend_rates else 0,
            'max_active_rate_pct': round(max(weekend_rates), 2) if weekend_rates else 0,
            'min_active_rate_pct': round(min(weekend_rates), 2) if weekend_rates else 0,
        },
        'holiday': {
            'days': len(holiday_rates),
            'avg_active_rate_pct': round(sum(holiday_rates) / len(holiday_rates), 2) if holiday_rates else 0,
            'max_active_rate_pct': round(max(holiday_rates), 2) if holiday_rates else 0,
            'min_active_rate_pct': round(min(holiday_rates), 2) if holiday_rates else 0,
        }
    }
    return comparison


def main():
    ensure_dir(OUTPUT_DIR)

    df, total_users = load_data()

    daily = daily_active_rate(df, total_users)
    weekly = weekly_active_rate(df, total_users)
    weekend = weekend_active_rate(df, total_users)
    weekday = weekday_active_rate(df, total_users)
    holiday = holiday_active_rate(df, total_users)
    comparison = active_rate_comparison(daily, total_users)

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
            'active_users_overall': int(df[df['is_active_trigger']]['reduser_id'].nunique()),
            'overall_active_rate_pct': round(df[df['is_active_trigger']]['reduser_id'].nunique() / total_users * 100, 2),
            'active_user_definition': '触发过至少一项核心功能(内容点击/POI交互/导航/AI路书/搜索/点赞/收藏/分享/地图操作/登录认证)的用户'
        },
        'daily_active_rate': daily,
        'weekly_active_rate': weekly,
        'weekend_active_rate': weekend,
        'weekday_active_rate': weekday,
        'holiday_active_rate': holiday,
        'comparison': comparison
    }

    json_path = os.path.join(OUTPUT_DIR, 'active_rate_analysis.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, ensure_ascii=False, indent=2)
    print(f"\n活跃率分析已保存: {json_path}")

    print("\n" + "=" * 70)
    print("活跃率专项分析完成!")
    print("=" * 70)

    return results


if __name__ == '__main__':
    main()
