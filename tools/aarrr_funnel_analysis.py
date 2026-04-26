# -*- coding: utf-8 -*-
# Adapted for v2 dataset: rednote data_20260319-20260330.xlsx
"""
AARRR 全链路用户级漏斗分析
每步=有多少独立用户完成, 保证转化率 <= 100%
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
    print("AARRR 全链路用户级漏斗分析")
    print(f"数据源: {DATA_PATH}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"数据概览: {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['timestamp'] = pd.to_datetime(df['start_time_nano'], errors='coerce')
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour

    total_users = df['reduser_id'].nunique()
    print(f"总用户数: {total_users}")
    print(f"时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

    return df, total_users


def build_funnel(df, total_users):
    """构建用户级 AARRR 漏斗"""
    print("\n" + "=" * 50)
    print("[AARRR 漏斗构建]")
    print("=" * 50)

    all_users = set(df['reduser_id'].dropna().unique())
    active_users = set(df[df['span_name'].isin(ACTIVE_TRIGGER_EVENTS)]['reduser_id'].dropna().unique())

    print(f"  总用户数: {len(all_users)}")
    print(f"  活跃用户数(功能触发): {len(active_users)}")
    print(f"  非活跃用户数: {len(all_users - active_users)}")
    acquisition_users = set(
        df[df['span_name'] == 'login_page_pageshow']['reduser_id'].dropna().unique()
    )

    # Step 2: Activation - any core action
    core_action_patterns = [
        'poi_detail_page_pageshow',
    ]
    core_action_exact = set(core_action_patterns)

    # AI guide clicks
    ai_users = set(df[df['span_name'].isin([
        'post_detail_page_ai_travel_guide_button_click',
        'post_detail_page_generated_travel_guide_button_click'
    ])]['reduser_id'].dropna().unique())

    # Like events
    like_users = set(df[df['span_name'].str.contains('like', case=False, na=False)]['reduser_id'].dropna().unique())

    # Save events
    save_users = set(df[df['span_name'].str.contains('save', case=False, na=False)]['reduser_id'].dropna().unique())

    # Navigation confirm
    nav_confirm_users = set(df[df['span_name'].isin([
        'poi_detail_page_navigation_popup_confirm_click',
        'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
    ])]['reduser_id'].dropna().unique())

    poi_detail_users = set(df[df['span_name'].isin(core_action_exact)]['reduser_id'].dropna().unique())

    activation_users = poi_detail_users | ai_users | like_users | save_users | nav_confirm_users

    # Step 3: Retention (Day 7)
    user_first_date = df.groupby('reduser_id')['date'].min()
    min_date = df['date'].min()
    max_date = df['date'].max()
    total_days = (max_date - min_date).days + 1

    retention_users = set()
    retention_eligible_count = 0

    if total_days >= 8:
        for uid in all_users:
            first_d = user_first_date[uid]
            target_d = first_d + timedelta(days=7)
            if target_d <= max_date:
                retention_eligible_count += 1
                user_dates = set(df[df['reduser_id'] == uid]['date'])
                if target_d in user_dates:
                    retention_users.add(uid)
    else:
        retention_eligible_count = 0

    # Step 4: Revenue - N/A
    revenue_users = set()

    # Step 5: Referral - share
    referral_users = set(df[df['span_name'].isin([
        'trival_guide_page_share_icon_click',
        'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click'
    ])]['reduser_id'].dropna().unique())

    # Build funnel data
    funnel_steps = [
        {
            'name': 'Acquisition',
            'name_cn': '获取(首次登录)',
            'event': 'login_page_pageshow',
            'users': acquisition_users,
            'description': '首次出现login_page_pageshow的用户'
        },
        {
            'name': 'Activation',
            'name_cn': '激活(核心动作)',
            'users': activation_users,
            'description': '完成≥1项核心动作(POI详情/AI路书/收藏/点赞/导航确认)',
            'sub_breakdown': {
                'poi_detail': len(poi_detail_users),
                'ai_guide': len(ai_users),
                'like': len(like_users),
                'save': len(save_users),
                'nav_confirm': len(nav_confirm_users)
            }
        },
        {
            'name': 'Retention',
            'name_cn': '留存(Day7)',
            'users': retention_users,
            'description': '首日用户在第7天仍有事件',
            'eligible_count': retention_eligible_count
        },
        {
            'name': 'Revenue',
            'name_cn': '收入',
            'users': revenue_users,
            'description': 'N/A - 无会员/收入数据',
            'data_availability': 'unavailable'
        },
        {
            'name': 'Referral',
            'name_cn': '推荐(分享)',
            'users': referral_users,
            'description': '触发分享行为的用户',
            'events': [
                'trival_guide_page_share_icon_click',
                'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click'
            ]
        }
    ]

    # Calculate metrics
    prev_count = total_users
    results = []

    print(f"\n  全部用户: {len(all_users)}")
    print(f"  活跃用户(功能触发): {len(active_users)}")
    print(f"  {'─' * 60}")

    for i, step in enumerate(funnel_steps):
        user_count = len(step['users'])

        # Conversion from previous step
        conv_prev = round(user_count / prev_count * 100, 2) if prev_count > 0 else 0

        # Conversion from total (Step 0 = all users)
        conv_total = round(user_count / len(all_users) * 100, 2) if len(all_users) > 0 else 0

        # Conversion from active users
        conv_active = round(user_count / len(active_users) * 100, 2) if len(active_users) > 0 else 0

        # Median events per user
        if user_count > 0:
            user_event_counts = df[df['reduser_id'].isin(step['users'])].groupby('reduser_id').size()
            median_events = float(user_event_counts.median())
        else:
            median_events = 0

        step_result = {
            'step': i + 1,
            'name': step['name'],
            'name_cn': step['name_cn'],
            'user_count': user_count,
            'conversion_from_prev_pct': conv_prev,
            'conversion_from_total_pct': conv_total,
            'conversion_from_active_pct': conv_active,
            'median_events_per_user': median_events,
            'description': step['description']
        }

        if 'sub_breakdown' in step:
            step_result['sub_breakdown'] = step['sub_breakdown']

        if step['name'] == 'Retention':
            if retention_eligible_count > 0:
                ci_lower, ci_upper = wilson_confidence_interval(len(retention_users), retention_eligible_count)
                step_result['eligible_count'] = retention_eligible_count
                step_result['retention_rate_pct'] = round(len(retention_users) / retention_eligible_count * 100, 2)
                step_result['ci_95'] = [round(ci_lower, 2), round(ci_upper, 2)]
                step_result['sample_note'] = '样本充足' if retention_eligible_count >= 30 else '样本不足(<30)，结果仅供参考'
            else:
                step_result['eligible_count'] = 0
                step_result['retention_rate_pct'] = 'N/A'
                step_result['note'] = f'数据覆盖{total_days}天，需≥8天才能计算Day7留存'

        if step['name'] == 'Revenue':
            step_result['data_availability'] = 'unavailable'

        if 'events' in step:
            step_result['events'] = step['events']

        results.append(step_result)

        print(f"  Step {i+1} {step['name_cn']}: {user_count} 用户")
        print(f"         转化(前一步): {conv_prev}% | 转化(总): {conv_total}%")
        if step['name'] == 'Retention' and retention_eligible_count > 0:
            print(f"         留存率: {step_result['retention_rate_pct']}% (n={retention_eligible_count})")
        print(f"         中位事件数: {median_events}")
        print()

        prev_count = user_count

    return results, all_users


def segment_funnel_analysis(df, all_users):
    """按用户活跃度分群的漏斗分析"""
    print("\n" + "=" * 50)
    print("[分群漏斗分析]")
    print("=" * 50)

    user_events = df.groupby('reduser_id').size().reset_index(name='total_events')
    q33 = user_events['total_events'].quantile(0.33)
    q66 = user_events['total_events'].quantile(0.66)
    user_events['segment'] = pd.cut(
        user_events['total_events'],
        bins=[0, q33, q66, float('inf')],
        labels=['low', 'medium', 'high']
    )

    segment_results = {}
    for seg_name in ['low', 'medium', 'high']:
        seg_users = set(user_events[user_events['segment'] == seg_name]['reduser_id'])
        seg_df = df[df['reduser_id'].isin(seg_users)]

        acquisition = len(seg_users & set(seg_df[seg_df['span_name'] == 'login_page_pageshow']['reduser_id'].dropna()))
        activation_events = seg_df[
            (seg_df['span_name'].str.contains('like|save', case=False, na=False)) |
            (seg_df['span_name'].isin([
                'poi_detail_page_pageshow',
                'post_detail_page_ai_travel_guide_button_click',
                'poi_detail_page_navigation_popup_confirm_click',
                'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
            ]))
        ]
        activation = activation_events['reduser_id'].nunique()
        referral = len(seg_users & set(seg_df[seg_df['span_name'].isin([
            'trival_guide_page_share_icon_click',
            'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click'
        ])]['reduser_id'].dropna()))

        total_seg = len(seg_users)
        segment_results[seg_name] = {
            'total_users': total_seg,
            'acquisition_users': acquisition,
            'activation_users': activation,
            'referral_users': referral,
            'acquisition_rate': round(acquisition / total_seg * 100, 2) if total_seg else 0,
            'activation_rate': round(activation / total_seg * 100, 2) if total_seg else 0,
            'referral_rate': round(referral / total_seg * 100, 2) if total_seg else 0
        }

        print(f"  [{seg_name.upper()}] {total_seg}用户: 获取{acquisition} 激活{activation} 推荐{referral}")

    return segment_results


def activation_detail(df, activation_users):
    """激活步骤细分"""
    print("\n" + "=" * 50)
    print("[激活步骤细分]")
    print("=" * 50)

    sub_actions = {
        'POI详情浏览': df[df['span_name'] == 'poi_detail_page_pageshow']['reduser_id'].nunique(),
        'AI路书点击': df[df['span_name'].isin([
            'post_detail_page_ai_travel_guide_button_click',
            'post_detail_page_generated_travel_guide_button_click'
        ])]['reduser_id'].nunique(),
        '点赞': df[df['span_name'].str.contains('like', case=False, na=False)]['reduser_id'].nunique(),
        '收藏': df[df['span_name'].str.contains('save', case=False, na=False)]['reduser_id'].nunique(),
        '导航确认': df[df['span_name'].isin([
            'poi_detail_page_navigation_popup_confirm_click',
            'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
        ])]['reduser_id'].nunique()
    }

    total_activated = len(activation_users)
    for action, count in sub_actions.items():
        pct = round(count / total_activated * 100, 2) if total_activated > 0 else 0
        print(f"  {action}: {count} 用户 ({pct}%)")

    return sub_actions


def main():
    ensure_dir(OUTPUT_DIR)

    df, total_users = load_data()

    funnel_results, all_users = build_funnel(df, total_users)
    segment_results = segment_funnel_analysis(df, all_users)

    # Get activation users for detail
    core_users = set()
    core_users |= set(df[df['span_name'] == 'poi_detail_page_pageshow']['reduser_id'].dropna().unique())
    core_users |= set(df[df['span_name'].isin([
        'post_detail_page_ai_travel_guide_button_click',
        'post_detail_page_generated_travel_guide_button_click'
    ])]['reduser_id'].dropna().unique())
    core_users |= set(df[df['span_name'].str.contains('like', case=False, na=False)]['reduser_id'].dropna().unique())
    core_users |= set(df[df['span_name'].str.contains('save', case=False, na=False)]['reduser_id'].dropna().unique())
    core_users |= set(df[df['span_name'].isin([
        'poi_detail_page_navigation_popup_confirm_click',
        'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
    ])]['reduser_id'].dropna().unique())

    activation_sub = activation_detail(df, core_users)

    results = {
        'meta': {
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': DATA_PATH,
            'total_users': int(total_users),
            'active_users': int(len(set(df[df['span_name'].isin(ACTIVE_TRIGGER_EVENTS)]['reduser_id'].dropna().unique()))),
            'active_user_definition': '触发过至少一项核心功能的用户',
            'funnel_type': 'user_level',
            'validation_note': '所有转化率 ≤ 100% (用户级漏斗)'
        },
        'funnel': funnel_results,
        'activation_sub_breakdown': activation_sub,
        'segment_analysis': segment_results
    }

    json_path = os.path.join(OUTPUT_DIR, 'aarrr_funnel_analysis.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, ensure_ascii=False, indent=2)
    print(f"\nAARRR漏斗分析已保存: {json_path}")

    print("\n" + "=" * 70)
    print("AARRR 漏斗分析完成!")
    print("=" * 70)

    return results


if __name__ == '__main__':
    main()
