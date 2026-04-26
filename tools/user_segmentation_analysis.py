# -*- coding: utf-8 -*-
# Adapted for v2 dataset: rednote data_20260319-20260330.xlsx
"""
用户深度洞察: 多维用户分群分析
5维度聚类 + 功能共现 + 时间模式
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
import math
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_PATH = r'C:\projects\rednote data analyzer\data\rednote\rednote20260319-20260412.xlsx'
OUTPUT_DIR = r'C:\projects\rednote data analyzer\report\fulldata_v2'

NAV_EVENTS = [
    'poi_detail_page_navigation_button_click',
    'poi_detail_page_navigation_popup_confirm_click',
    'trival_guide_page_detail_tab_poi_navigation_button_click',
    'trival_guide_page_detail_tab_poi_navigation_popup_confirm_click'
]
CONTENT_EVENTS_PATTERNS = ['post_card', 'pageshow', 'post_detail']
AI_GUIDE_PATTERNS = ['ai_travel_guide', 'generated_travel_guide', 'trival_guide']

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


def kmeans(data, k, max_iter=100, seed=42):
    """K-Means clustering (no sklearn dependency)"""
    np.random.seed(seed)
    n = len(data)
    if n <= k:
        labels = np.arange(n) % k
        centroids = np.zeros((k, data.shape[1]))
        return labels, centroids

    # K-means++ init
    centroids = [data[np.random.randint(n)].copy()]
    for _ in range(1, k):
        dists = np.array([min(np.sum((x - c) ** 2) for c in centroids) for x in data])
        total = dists.sum()
        if total == 0:
            centroids.append(data[np.random.randint(n)].copy())
        else:
            probs = dists / total
            centroids.append(data[np.random.choice(n, p=probs)].copy())
    centroids = np.array(centroids)

    labels = np.zeros(n, dtype=int)
    for iteration in range(max_iter):
        # Assign
        for i in range(n):
            dists = np.sum((centroids - data[i]) ** 2, axis=1)
            labels[i] = np.argmin(dists)
        # Update
        new_centroids = np.zeros_like(centroids)
        for j in range(k):
            members = data[labels == j]
            if len(members) > 0:
                new_centroids[j] = members.mean(axis=0)
            else:
                new_centroids[j] = centroids[j]
        if np.allclose(centroids, new_centroids, atol=1e-6):
            break
        centroids = new_centroids

    return labels, centroids


def load_data():
    print("=" * 70)
    print("用户深度洞察: 多维用户分群分析")
    print(f"数据源: {DATA_PATH}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"数据概览: {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['timestamp'] = pd.to_datetime(df['start_time_nano'], errors='coerce')
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.dayofweek

    total_users = df['reduser_id'].nunique()
    active_users = df[df['span_name'].isin(ACTIVE_TRIGGER_EVENTS)]['reduser_id'].nunique()
    print(f"总用户数: {total_users}")
    print(f"活跃用户数(功能触发): {active_users}")

    return df, total_users, active_users


def compute_user_features(df):
    """计算5维度用户特征"""
    print("\n" + "=" * 50)
    print("[计算5维度用户特征]")
    print("=" * 50)

    users = df['reduser_id'].dropna().unique()
    features = {}

    for uid in users:
        udf = df[df['reduser_id'] == uid]
        total = len(udf)
        if total == 0:
            continue

        # Dimension 1: Activity Level (events per day)
        active_days = udf['date'].nunique()
        activity_level = total / active_days if active_days > 0 else 0

        # Dimension 2: Feature Breadth
        feature_breadth = udf['span_name'].nunique()

        # Dimension 3: Navigation Tendency
        nav_count = len(udf[udf['span_name'].isin(NAV_EVENTS)])
        nav_tendency = nav_count / total

        # Dimension 4: Content Consumption
        content_count = len(udf[udf['span_name'].str.contains(
            '|'.join(CONTENT_EVENTS_PATTERNS), case=False, na=False
        )])
        content_consumption = content_count / total

        # Dimension 5: AI Acceptance
        ai_count = len(udf[udf['span_name'].str.contains(
            '|'.join(AI_GUIDE_PATTERNS), case=False, na=False
        )])
        ai_acceptance = ai_count / total

        features[uid] = {
            'activity_level': activity_level,
            'feature_breadth': feature_breadth,
            'nav_tendency': nav_tendency,
            'content_consumption': content_consumption,
            'ai_acceptance': ai_acceptance,
            'total_events': total,
            'active_days': active_days
        }

    feature_df = pd.DataFrame(features).T
    print(f"  计算完成: {len(feature_df)} 个用户")

    for dim in ['activity_level', 'feature_breadth', 'nav_tendency', 'content_consumption', 'ai_acceptance']:
        print(f"  {dim}: mean={feature_df[dim].mean():.3f}, median={feature_df[dim].median():.3f}")

    return feature_df


def perform_clustering(feature_df):
    """K-Means聚类 + Elbow方法"""
    print("\n" + "=" * 50)
    print("[K-Means 聚类]")
    print("=" * 50)

    dims = ['activity_level', 'feature_breadth', 'nav_tendency', 'content_consumption', 'ai_acceptance']
    data = feature_df[dims].values.astype(float)

    # Standardize
    means = data.mean(axis=0)
    stds = data.std(axis=0)
    stds[stds == 0] = 1
    data_norm = (data - means) / stds

    # Elbow method
    inertias = []
    for k in range(2, 7):
        labels, centroids = kmeans(data_norm, k)
        inertia = sum(np.sum((data_norm[i] - centroids[labels[i]]) ** 2) for i in range(len(data_norm)))
        inertias.append({'k': k, 'inertia': float(inertia)})
        print(f"  k={k}: inertia={inertia:.2f}")

    # Select k=4 (good balance for 206 users)
    best_k = 4
    labels, centroids = kmeans(data_norm, best_k)

    feature_df['cluster'] = labels

    # Build cluster profiles
    clusters = {}
    persona_names = {
        0: 'Persona A',
        1: 'Persona B',
        2: 'Persona C',
        3: 'Persona D'
    }

    for c in range(best_k):
        cluster_users = feature_df[feature_df['cluster'] == c]
        n_users = len(cluster_users)

        profile = {
            'cluster_id': c,
            'user_count': n_users,
            'user_pct': round(n_users / len(feature_df) * 100, 2),
            'avg_values': {},
            'distinguishing_features': [],
            'top_events': [],
            'business_recommendation': ''
        }

        for dim in dims:
            profile['avg_values'][dim] = round(float(cluster_users[dim].mean()), 4)

        # Find distinguishing features (dimensions where cluster differs most from global mean)
        diffs = {}
        for dim in dims:
            global_mean = feature_df[dim].mean()
            cluster_mean = cluster_users[dim].mean()
            diffs[dim] = cluster_mean - global_mean

        sorted_diffs = sorted(diffs.items(), key=lambda x: abs(x[1]), reverse=True)
        profile['distinguishing_features'] = [
            f"{name} ({'+' if diff > 0 else ''}{diff:.3f})" for name, diff in sorted_diffs[:3]
        ]

        # Name persona based on top features
        top_feat = sorted_diffs[0][0]
        second_feat = sorted_diffs[1][0]
        if top_feat == 'nav_tendency' or second_feat == 'nav_tendency':
            name = '导航导向型'
        elif top_feat == 'ai_acceptance' or second_feat == 'ai_acceptance':
            name = 'AI探索型'
        elif top_feat == 'activity_level':
            name = '高活跃型'
        elif top_feat == 'content_consumption':
            name = '内容消费型'
        elif top_feat == 'feature_breadth':
            name = '全能探索型'
        else:
            name = f'分群{c + 1}'
        persona_names[c] = name
        profile['persona_name'] = name

        # Business recommendation
        if name == '导航导向型':
            profile['business_recommendation'] = '核心用户群体，优化导航到POI的路径，提高目的地匹配精度'
        elif name == 'AI探索型':
            profile['business_recommendation'] = '高潜力用户，推广AI路书功能，引导更多内容到导航转化'
        elif name == '高活跃型':
            profile['business_recommendation'] = '重度使用者，提供个性化推荐，增加粘性和深度'
        elif name == '内容消费型':
            profile['business_recommendation'] = '潜在转化用户，优化内容到POI的引导，降低导航门槛'
        elif name == '全能探索型':
            profile['business_recommendation'] = '功能探索者，保持体验流畅度，推送新功能引导'
        else:
            profile['business_recommendation'] = '关注用户需求，提供更精准的内容推荐'

        clusters[f'cluster_{c}'] = profile
        print(f"  Cluster {c} [{name}]: {n_users}用户 ({profile['user_pct']}%)")

    return clusters, feature_df, inertias


def feature_cooccurrence(df, feature_df):
    """功能共现与关联分析"""
    print("\n" + "=" * 50)
    print("[功能共现分析]")
    print("=" * 50)

    # Define feature categories
    feature_categories = {
        'navigation': NAV_EVENTS,
        'content_browse': ['discovery_page_post_card_cardshow', 'porsche_page_recommend_post_card_cardshow',
                          'discovery_page_post_card_click', 'porsche_page_recommend_post_card_click'],
        'search': ['discovery_page_search_click', 'porsche_page_search_click'],
        'ai_guide': ['post_detail_page_ai_travel_guide_button_click',
                     'post_detail_page_generated_travel_guide_button_click',
                     'trival_guide_page_pageshow'],
        'share': ['trival_guide_page_share_icon_click',
                  'profile_page_travel_guide_tab_share_code_trip_add_confirm_button_click'],
        'poi': ['poi_detail_page_pageshow', 'post_detail_page_POI_button_click'],
        'like': ['discovery_page_post_like_click'],
        'save': ['post_detail_page_collect_click'] if 'post_detail_page_collect_click' in df['span_name'].values else []
    }

    # Build binary matrix (user × feature)
    users = feature_df.index.tolist()
    binary = {}
    for uid in users:
        udf = df[df['reduser_id'] == uid]
        binary[uid] = {}
        for cat, events in feature_categories.items():
            binary[uid][cat] = 1 if len(udf[udf['span_name'].isin(events)]) > 0 else 0

    # Co-occurrence matrix
    categories = list(feature_categories.keys())
    cooccurrence = {}
    for c1 in categories:
        cooccurrence[c1] = {}
        for c2 in categories:
            count = sum(1 for uid in users if binary[uid].get(c1, 0) == 1 and binary[uid].get(c2, 0) == 1)
            cooccurrence[c1][c2] = count

    # Association rules (confidence > 30%, support > 5)
    rules = []
    for c1 in categories:
        c1_users = sum(1 for uid in users if binary[uid].get(c1, 0) == 1)
        if c1_users < 5:
            continue
        for c2 in categories:
            if c1 == c2:
                continue
            both = cooccurrence[c1][c2]
            confidence = round(both / c1_users * 100, 2) if c1_users > 0 else 0
            if confidence > 30 and both >= 5:
                rules.append({
                    'rule': f'{c1} → {c2}',
                    'antecedent': c1,
                    'consequent': c2,
                    'support': both,
                    'confidence_pct': float(confidence)
                })

    rules.sort(key=lambda x: x['confidence_pct'], reverse=True)

    # Sequential pattern: search → POI → navigation
    sequential = {}
    for uid in users:
        udf = df[df['reduser_id'] == uid].sort_values('timestamp')
        events_list = udf['span_name'].tolist()

        has_search = any(e in events_list for e in feature_categories['search'])
        has_poi = any(e in events_list for e in feature_categories['poi'])
        has_nav = any(e in events_list for e in feature_categories['navigation'])

        if has_search and has_poi and has_nav:
            sequential[uid] = 'search→POI→navigation'
        elif has_search and has_poi:
            sequential[uid] = 'search→POI'
        elif has_poi and has_nav:
            sequential[uid] = 'POI→navigation'

    seq_summary = defaultdict(int)
    for v in sequential.values():
        seq_summary[v] += 1

    result = {
        'cooccurrence_matrix': cooccurrence,
        'association_rules': rules[:15],
        'sequential_patterns': dict(seq_summary),
        'category_user_counts': {cat: sum(1 for uid in users if binary[uid].get(cat, 0) == 1) for cat in categories}
    }

    print(f"  共现矩阵: {len(categories)}x{len(categories)}")
    print(f"  关联规则(>30%): {len(rules)} 条")
    print(f"  顺序模式: {dict(seq_summary)}")

    return result


def time_pattern_analysis(df, feature_df):
    """时间模式分析"""
    print("\n" + "=" * 50)
    print("[时间模式分析]")
    print("=" * 50)

    # Hourly distribution
    hourly = df.groupby('hour').size()
    hourly_dict = {str(h): int(hourly.get(h, 0)) for h in range(24)}

    # Time period classification
    commute_hours = [7, 8, 9, 17, 18, 19]
    leisure_hours = [10, 11, 12, 13, 14, 15, 16]
    evening_hours = [20, 21, 22, 23]

    time_periods = {
        '通勤时段(7-9,17-19)': int(sum(hourly.get(h, 0) for h in commute_hours)),
        '休闲时段(10-16)': int(sum(hourly.get(h, 0) for h in leisure_hours)),
        '晚间时段(20-23)': int(sum(hourly.get(h, 0) for h in evening_hours)),
        '其他时段': int(hourly.sum() - sum(hourly.get(h, 0) for h in commute_hours + leisure_hours + evening_hours))
    }

    # Weekday vs Weekend
    weekday_df = df[df['weekday'] < 5]
    weekend_df = df[df['weekday'] >= 5]

    weekday_weekend = {
        'weekday': {
            'event_count': int(len(weekday_df)),
            'user_count': int(weekday_df['reduser_id'].nunique()),
            'nav_rate': round(
                len(weekday_df[weekday_df['span_name'].isin(NAV_EVENTS)]) / max(len(weekday_df[weekday_df['event_type'] == 'CLICK']), 1) * 100, 4
            )
        },
        'weekend': {
            'event_count': int(len(weekend_df)),
            'user_count': int(weekend_df['reduser_id'].nunique()),
            'nav_rate': round(
                len(weekend_df[weekend_df['span_name'].isin(NAV_EVENTS)]) / max(len(weekend_df[weekend_df['event_type'] == 'CLICK']), 1) * 100, 4
            )
        }
    }

    # Usage frequency decay
    user_first_date = df.groupby('reduser_id')['date'].min()
    df_with_day_offset = df.copy()
    df_with_day_offset['days_since_first'] = df_with_day_offset.apply(
        lambda row: (row['date'] - user_first_date.get(row['reduser_id'], row['date'])).days
        if pd.notna(row['reduser_id']) else None, axis=1
    )

    decay = df_with_day_offset.groupby('days_since_first').agg(
        events=('reduser_id', 'count'),
        users=('reduser_id', 'nunique')
    )
    decay_dict = {str(int(k)): {'events': int(v['events']), 'users': int(v['users'])}
                  for k, v in decay.to_dict('index').items() if pd.notna(k)}

    result = {
        'hourly_distribution': hourly_dict,
        'time_periods': time_periods,
        'weekday_vs_weekend': weekday_weekend,
        'usage_decay': decay_dict
    }

    peak_hour = hourly.idxmax()
    print(f"  峰值时段: {peak_hour}时 ({int(hourly[peak_hour])}事件)")
    print(f"  工作日: {weekday_weekend['weekday']['event_count']}事件, {weekday_weekend['weekday']['nav_rate']}%导航率")
    print(f"  周末: {weekday_weekend['weekend']['event_count']}事件, {weekday_weekend['weekend']['nav_rate']}%导航率")

    return result


def main():
    ensure_dir(OUTPUT_DIR)

    df, total_users, active_users = load_data()

    # Part A: Feature computation
    feature_df = compute_user_features(df)

    # Part B: Clustering
    clusters, feature_df_clustered, inertias = perform_clustering(feature_df)

    # Part C: Feature co-occurrence
    cooccurrence = feature_cooccurrence(df, feature_df_clustered)

    # Part D: Time patterns
    time_patterns = time_pattern_analysis(df, feature_df_clustered)

    results = {
        'meta': {
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': DATA_PATH,
            'total_users': int(total_users),
            'active_users': int(active_users),
            'active_user_definition': '触发过至少一项核心功能的用户',
            'inactive_users': int(total_users - active_users),
            'clustering_method': 'K-Means (k=4)',
            'dimensions': ['activity_level', 'feature_breadth', 'nav_tendency', 'content_consumption', 'ai_acceptance']
        },
        'elbow_analysis': inertias,
        'clusters': clusters,
        'feature_cooccurrence': cooccurrence,
        'time_patterns': time_patterns
    }

    json_path = os.path.join(OUTPUT_DIR, 'user_segmentation_analysis.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(results), f, ensure_ascii=False, indent=2)
    print(f"\n用户分群分析已保存: {json_path}")

    print("\n" + "=" * 70)
    print("用户分群分析完成!")
    print("=" * 70)

    return results


if __name__ == '__main__':
    main()
