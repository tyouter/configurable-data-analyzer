# -*- coding: utf-8 -*-
"""
Rednote 全量数据深度洞察分析脚本
6大维度: 用户画像 / 生活习惯 / 消费习惯 / 使用场景 / 关联需求 / APP熟悉度
输出到 report/fulldata/
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime
from collections import Counter, defaultdict

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

def load_and_prepare():
    print("=" * 70)
    print("Rednote 全量数据深度洞察分析")
    print(f"数据源: {DATA_PATH}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"\n[数据概览] {df.shape[0]:,} 行 x {df.shape[1]} 列")

    df['strt_time_dt'] = pd.to_datetime(df['strt_time_nano'], errors='coerce')
    df['end_time_dt'] = pd.to_datetime(df['end_time_nano'], errors='coerce')
    df['date'] = df['strt_time_dt'].dt.date
    df['hour'] = df['strt_time_dt'].dt.hour
    df['weekday'] = df['strt_time_dt'].dt.dayofweek
    df['weekday_name'] = df['strt_time_dt'].dt.day_name()
    df['is_weekend'] = df['weekday'].isin([5, 6])

    df['page'] = df['span_nm'].str.split('_').str[:2].str.join('_')
    df['action'] = df['span_nm'].str.split('_').str[-1]
    df['page_root'] = df['span_nm'].str.split('_').str[0]

    if 'strt_time_dt' in df.columns and 'end_time_dt' in df.columns:
        df['duration_sec'] = (df['end_time_dt'] - df['strt_time_dt']).dt.total_seconds()
        df.loc[df['duration_sec'] < 0, 'duration_sec'] = np.nan

    valid_dates = df[df['strt_time_dt'].notna()]
    if not valid_dates.empty:
        print(f"时间范围: {valid_dates['strt_time_dt'].min()} ~ {valid_dates['strt_time_dt'].max()}")
        print(f"覆盖天数: {(valid_dates['strt_time_dt'].max() - valid_dates['strt_time_dt'].min()).days + 1} 天")

    total_users = df['reduser_id'].dropna().nunique()
    print(f"独立用户数: {total_users:,}")
    print(f"总事件数: {len(df):,}")

    return df, total_users


def analyze_user_profiling(df, total_users):
    """1. 用户画像分析"""
    print("\n" + "=" * 50)
    print("[1/6] 用户画像分析")
    print("=" * 50)

    user_df = df[df['reduser_id'].notna()].copy()
    user_stats = user_df.groupby('reduser_id').agg(
        event_count=('span_nm', 'count'),
        unique_events=('span_nm', 'nunique'),
        unique_pages=('page', 'nunique'),
        first_seen=('strt_time_dt', 'min'),
        last_seen=('strt_time_dt', 'max'),
        active_days=('date', lambda x: x.nunique()),
        has_poi=('rednote_poi_title', lambda x: x.notna().any()),
        has_post=('rednote_post_title', lambda x: x.notna().any()),
        has_video=('rednote_video_post_is_play', lambda x: x.notna().any()),
        has_guide=('rednote_travel_guide_id', lambda x: x.notna().any()),
        has_like=('rednote_post_is_like', lambda x: x.notna().any()),
        has_save=('rednote_post_is_save', lambda x: x.notna().any()),
        has_follow=('rednote_post_follow', lambda x: x.notna().any()),
        avg_duration=('duration_sec', 'mean'),
    ).reset_index()

    user_stats['lifespan_days'] = (user_stats['last_seen'] - user_stats['first_seen']).dt.days + 1
    user_stats['events_per_day'] = user_stats['event_count'] / user_stats['active_days'].clip(lower=1)
    user_stats['event_diversity'] = user_stats['unique_events'] / user_stats['event_count']

    event_q = user_stats['event_count'].quantile([0.25, 0.5, 0.75]).to_dict()

    def classify_activity(row):
        if row['event_count'] >= event_q[0.75]:
            return 'high_active'
        elif row['event_count'] >= event_q[0.5]:
            return 'medium_active'
        elif row['event_count'] >= event_q[0.25]:
            return 'low_active'
        else:
            return 'dormant'

    user_stats['activity_tier'] = user_stats.apply(classify_activity, axis=1)
    tier_dist = user_stats['activity_tier'].value_counts().to_dict()

    def classify_persona(row):
        features = []
        if row.get('has_poi'): features.append('explorer')
        if row.get('has_post'): features.append('consumer')
        if row.get('has_video'): features.append('video_viewer')
        if row.get('has_guide'): features.append('ai_user')
        if row.get('has_like') or row.get('has_save') or row.get('has_follow'):
            features.append('engager')

        if len(features) >= 4:
            return 'power_user'
        elif len(features) >= 2:
            return 'regular_user'
        elif len(features) == 1:
            return 'single_feature_user'
        else:
            return 'browser'

    user_stats['persona'] = user_stats.apply(classify_persona, axis=1)
    persona_dist = user_stats['persona'].value_counts().to_dict()

    page_pref = {}
    for uid, group in user_df.groupby('reduser_id'):
        root_counts = group['page_root'].value_counts()
        page_pref[str(uid)] = root_counts.index[0] if len(root_counts) > 0 else 'unknown'

    page_preference_summary = Counter(page_pref.values())

    poi_users = user_stats[user_stats['has_poi'] == True]
    poi_type_prefs = defaultdict(int)
    if not poi_users.empty:
        poi_data = df[df['reduser_id'].isin(poi_users['reduser_id']) & df['rednote_poi_typ_nm'].notna()]
        for uid, grp in poi_data.groupby('reduser_id'):
            top_type = grp['rednote_poi_typ_nm'].mode().iloc[0] if not grp.empty else None
            if top_type:
                poi_type_prefs[top_type] += 1
    top_poi_types = dict(sorted(poi_type_prefs.items(), key=lambda x: -x[1])[:15])

    time_pattern = {}
    for uid, grp in user_df.groupby('reduser_id'):
        hours = grp['hour'].dropna()
        if len(hours) == 0:
            continue
        hour_mode = hours.mode().iloc[0] if not hours.mode().empty else hours.iloc[0]
        if 6 <= hour_mode < 12:
            tp = 'morning_user'
        elif 12 <= hour_mode < 18:
            tp = 'afternoon_user'
        elif 18 <= hour_mode < 24:
            tp = 'evening_user'
        else:
            tp = 'night_owl'
        time_pattern[str(uid)] = tp
    time_pattern_summary = Counter(time_pattern.values())

    new_vs_returning = {
        'new_users': int((user_stats['active_days'] <= 1).sum()),
        'returning_users': int((user_stats['active_days'] > 1).sum())
    }

    result = {
        'total_users_analyzed': int(len(user_stats)),
        'activity_distribution': tier_dist,
        'persona_distribution': persona_dist,
        'page_preference': dict(page_preference_summary.most_common(10)),
        'poi_type_preferences': top_poi_types,
        'time_pattern_distribution': dict(time_pattern_summary),
        'new_vs_returning_users': new_vs_returning,
        'statistics': {
            'avg_events_per_user': round(float(user_stats['event_count'].mean()), 2),
            'median_events_per_user': round(float(user_stats['event_count'].median()), 2),
            'avg_unique_events_per_user': round(float(user_stats['unique_events'].mean()), 1),
            'avg_active_days': round(float(user_stats['active_days'].mean()), 2),
            'avg_lifespan_days': round(float(user_stats['lifespan_days'].mean()), 1),
            'max_event_user': int(user_stats['event_count'].max()),
            'min_event_user': int(user_stats['event_count'].min()),
        },
        'feature_adoption': {
            'poi_users': int(user_stats['has_poi'].sum()),
            'post_consumers': int(user_stats['has_post'].sum()),
            'video_viewers': int(user_stats['has_video'].sum()),
            'ai_guide_users': int(user_stats['has_guide'].sum()),
            'engagers_like': int(user_stats['has_like'].sum()),
            'engagers_save': int(user_stats['has_save'].sum()),
            'engagers_follow': int(user_stats['has_follow'].sum()),
        }
    }

    print(f"  分析用户数: {len(user_stats):,}")
    print(f"  用户分层: {tier_dist}")
    print(f"  用户画像: {persona_dist}")
    print(f"  新老用户: 新{new_vs_returning['new_users']} / 回访{new_vs_returning['returning_users']}")

    return result, user_stats


def analyze_lifestyle_habits(df):
    """2. 用户生活习惯分析"""
    print("\n" + "=" * 50)
    print("[2/6] 用户生活习惯分析")
    print("=" * 50)

    valid_time = df[df['strt_time_dt'].notna()].copy()

    hourly = valid_time.groupby('hour')['reduser_id'].agg([('events', 'count'), ('unique_users', 'nunique')]).reset_index()

    peak_hour = hourly.loc[hourly['events'].idxmax(), 'hour']
    peak_hour_events = hourly['events'].max()
    quiet_hour = hourly.loc[hourly['events'].idxmin(), 'hour']
    quiet_hour_events = hourly['events'].min()

    hourly_data = {
        'peak_hour': int(peak_hour),
        'peak_hour_events': int(peak_hour_events),
        'quiet_hour': int(quiet_hour),
        'quiet_hour_events': int(quiet_hour_events),
        'hourly_distribution': {int(r['hour']): {'events': int(r['events']), 'users': int(r['unique_users'])}
                                for _, r in hourly.iterrows()}
    }

    weekday_stats = valid_time.groupby(['weekday', 'weekday_name'])['reduser_id'].agg([('events', 'count'), ('unique_users', 'nunique')]).reset_index()

    weekend_events = weekday_stats[weekday_stats['weekday'].isin([5, 6])]['events'].sum()
    weekday_events = weekday_stats[~weekday_stats['weekday'].isin([5, 6])]['events'].sum()
    weekend_ratio = weekend_events / (weekend_events + weekend_events) * 100 if (weekend_events + weekend_events) > 0 else 0

    daily = valid_time.groupby('date')['reduser_id'].agg([('events', 'count'), ('unique_users', 'nunique')]).reset_index()
    daily['day_of_week'] = pd.to_datetime(daily['date']).dt.dayofweek

    weekday_detail = {str(r['date']): {'events': int(r['events']), 'users': int(r['unique_users']), 'dow': int(r['day_of_week'])}
                      for _, r in daily.iterrows()}

    time_segments = {
        'early_morning (00-06)': len(valid_time[(valid_time['hour'] >= 0) & (valid_time['hour'] < 6)]),
        'morning (06-12)': len(valid_time[(valid_time['hour'] >= 6) & (valid_time['hour'] < 12)]),
        'afternoon (12-18)': len(valid_time[(valid_time['hour'] >= 12) & (valid_time['hour'] < 18)]),
        'evening (18-22)': len(valid_time[(valid_time['hour'] >= 18) & (valid_time['hour'] < 22)]),
        'night (22-24)': len(valid_time[(valid_time['hour'] >= 22) & (valid_time['hour'] < 24)])
    }

    user_time_profiles = {}
    for uid, grp in valid_time.groupby('reduser_id'):
        h = grp['hour'].dropna()
        if len(h) < 2:
            continue
        profile = {
            'first_active': int(h.min()),
            'last_active': int(h.max()),
            'primary_segment': '',
            'is_night_user': int((h >= 22).sum() + (h < 6).sum()) > len(h) * 0.3,
            'consistency_score': round(h.std(), 2) if len(h) > 1 else 0
        }
        seg_counts = h.value_counts()
        if not seg_counts.empty:
            profile['primary_segment'] = f"{seg_counts.index[0]}:00"
        user_time_profiles[str(uid)] = profile

    night_owl_count = sum(1 for p in user_time_profiles.values() if p['is_night_user'])
    early_bird_count = sum(1 for p in user_time_profiles.values() if p['first_active'] <= 7)

    result = {
        'hourly_data': hourly_data,
        'time_segments': time_segments,
        'peak_hour_info': {'hour': int(peak_hour), 'events': int(peak_hour_events)},
        'weekend_vs_weekday': {
            'weekend_events': int(weekend_events),
            'weekday_events': int(weekday_events),
            'weekend_ratio_pct': round(weekend_ratio, 2)
        },
        'daily_distribution': weekday_detail,
        'user_time_profiles_summary': {
            'total_profiled_users': len(user_time_profiles),
            'night_owl_users': night_owl_count,
            'early_bird_users': early_bird_count,
            'avg_consistency_score': round(np.mean([p['consistency_score'] for p in user_time_profiles.values()]), 2)
        }
    }

    print(f"  高峰时段: {peak_hour}:00 ({peak_hour_events:,} 事件)")
    print(f"  时间段分布: {time_segments}")
    print(f"  周末占比: {weekend_ratio:.1f}%")
    print(f"  夜猫子用户: {night_owl_count}, 早鸟用户: {early_bird_count}")

    return result


def analyze_consumption_habits(df):
    """3. 用户消费习惯分析（内容消费+POI兴趣）"""
    print("\n" + "=" * 50)
    print("[3/6] 用户消费习惯分析")
    print("=" * 50)

    poi_data = df[df['rednote_poi_title'].notna()].copy()
    post_data = df[df['rednote_post_title'].notna()].copy()
    video_data = df[df['rednote_video_post_is_play'].notna()].copy()

    poi_types = poi_data['rednote_poi_typ_nm'].value_counts()
    top_pois = poi_data['rednote_poi_title'].value_counts().head(20)

    poi_category_mapping = {
        '餐饮美食': ['餐厅', '咖啡', '奶茶', '甜品', '火锅', '烧烤', '日料', '西餐',
                     '面包', '蛋糕', '披萨', '汉堡', '小吃', '面馆', '粥店', '食堂'],
        '休闲娱乐': ['台球', '棋牌', 'KTV', '酒吧', '网吧', '电玩城', '密室', '剧本杀',
                    '按摩', '足浴', '洗浴', '电影院', '游乐场'],
        '运动健身': ['健身房', '瑜伽', '游泳', '羽毛球', '篮球', '足球', '网球',
                   '乒乓球', '跑步', '攀岩', '舞蹈', '武术', '滑雪'],
        '购物消费': ['商场', '超市', '便利店', '专卖店', '奥特莱斯', '免税店'],
        '旅游出行': ['景点', '公园', '露营地', '民宿', '酒店', '温泉', '度假村',
                   '机场', '车站', '码头'],
        '生活服务': ['理发', '美容', '洗衣', '维修', '银行', '医院', '药店',
                   '宠物', '花店', '家政'],
        '亲子教育': ['儿童乐园', '早教', '培训', '学校', '书店', '图书馆', '博物馆'],
        '其他': []
    }

    def categorize_poi(typ_nm):
        typ_str = str(typ_nm)
        for cat, keywords in poi_category_mapping.items():
            if any(kw in typ_str for kw in keywords):
                return cat
        return '其他'

    poi_data['poi_category'] = poi_data['rednote_poi_typ_nm'].apply(categorize_poi)
    poi_cat_dist = poi_data['poi_category'].value_counts().to_dict()

    post_types = post_data['rednote_post_typ'].value_counts().to_dict()
    like_events = df[df['rednote_post_is_like'].notna()]
    save_events = df[df['rednote_post_is_save'].notna()]
    follow_events = df[df['rednote_post_follow'].notna()]

    video_plays = video_data['rednote_video_post_is_play'].value_counts().to_dict()
    autoplay_on = video_data[video_data['rednote_video_post_autoplay_is_open'] == 1]
    play_speeds = video_data['rednote_video_post_play_speed'].dropna().value_counts().head(5).to_dict()

    user_spend = {}
    for uid, grp in df[df['reduser_id'].notna()].groupby('reduser_id'):
        up = {
            'total_events': len(grp),
            'poi_views': len(grp[grp['rednote_poi_title'].notna()]),
            'post_views': len(grp[grp['rednote_post_title'].notna()]),
            'video_interactions': len(grp[grp['rednote_video_post_is_play'].notna()]),
            'likes': len(grp[grp['rednote_post_is_like'].notna()]),
            'saves': len(grp[grp['rednote_post_is_save'].notna()]),
            'follows': len(grp[grp['rednote_post_follow'].notna()]),
        }
        total_engagement = up['likes'] + up['saves'] + up['follows']
        up['engagement_rate'] = round(total_engagement / max(up['total_events'], 1) * 100, 2)
        up['content_heavy'] = up['post_views'] > up['poi_views']
        user_spend[str(uid)] = up

    content_heavy = sum(1 for u in user_spend.values() if u['content_heavy'])
    poi_heavy = len(user_spend) - content_heavy

    hashtag_data = df[df['rednote_post_hashtag_title'].notna()]
    top_hashtags = hashtag_data['rednote_post_hashtag_title'].value_counts().head(15).to_dict()

    result = {
        'poi_analysis': {
            'total_poi_interactions': int(len(poi_data)),
            'unique_pois': int(poi_data['rednote_poi_title'].nunique()),
            'top_poi_categories': dict(list(poi_cat_dist.items())[:10]),
            'top_individual_pois': dict(top_pois),
            'poi_type_diversity': int(poi_data['rednote_poi_typ_nm'].nunique())
        },
        'content_consumption': {
            'total_post_views': int(len(post_data)),
            'post_type_distribution': post_types,
            'likes': int(len(like_events)),
            'saves': int(len(save_events)),
            'follows': int(len(follow_events)),
            'overall_engagement_rate': round(
                (len(like_events)+len(save_events)+len(follow_events)) / max(len(df), 1) * 100, 2)
        },
        'video_behavior': {
            'total_video_interactions': int(len(video_data)),
            'play_status_distribution': video_plays,
            'autoplay_enabled_users': int(autoplay_on['reduser_id'].nunique()) if not autoplay_on.empty else 0,
            'play_speed_distribution': play_speeds
        },
        'user_consumption_patterns': {
            'content_focused_users': content_heavy,
            'poi_focused_users': poi_heavy,
            'total_analyzed_users': len(user_spend),
            'avg_engagement_rate': round(np.mean([u['engagement_rate'] for u in user_spend.values()]), 2)
        },
        'hashtag_analysis': {
            'total_hashtag_events': int(len(hashtag_data)),
            'top_hashtags': top_hashtags
        }
    }

    print(f"  POI交互: {len(poi_data):,} ({poi_data['rednote_poi_title'].nunique()} 独立POI)")
    print(f"  内容消费: {len(post_data):,} (点赞{len(like_events)} 收藏{len(save_events)} 关注{len(follow_events)})")
    print(f"  视频行为: {len(video_data):,}")
    print(f"  内容型vsPOI型用户: {content_heavy} vs {poi_heavy}")

    return result


def analyze_usage_scenarios(df, user_stats):
    """4. 用户使用场景分析"""
    print("\n" + "=" * 50)
    print("[4/6] 用户使用场景分析")
    print("=" * 50)

    page_events = df['page_root'].value_counts()
    action_events = df['action'].value_counts()
    span_events = df['span_nm'].value_counts()

    full_funnel = {
        'discovery_page_exposure': int(df['span_nm'].str.contains('discovery_page_pageshow', na=False).sum()),
        'post_card_shown': int(df['span_nm'].str.contains('post_card_cardshow|post_card_carshow', na=False).sum()),
        'post_card_clicked': int(df['span_nm'].str.contains('post_card_click', na=False).sum()),
        'post_detail_exposure': int(df['span_nm'].str.contains('post_detail_page_pageshow', na=False).sum()),
        'post_interaction': int(df['span_nm'].str.contains(
            'post_like_click|save_button_click|follow_button_click|share_icon_click', na=False).sum()),
    }
    prev = None
    funnel_with_rates = {}
    for k, v in full_funnel.items():
        entry = {'count': v}
        if prev is not None and full_funnel[prev] > 0:
            entry['conversion_rate'] = round(v / full_funnel[prev] * 100, 2)
        funnel_with_rates[k] = entry
        prev = k

    poi_funnel = {
        'map_page_exposure': int(df['span_nm'].str.contains('porsche_page_pageshow|Map.*pageshow', na=False).sum()),
        'poi_card_shown': int(df['span_nm'].str.contains('poi_card_cardshow', na=False).sum()),
        'poi_card_clicked': int(df['span_nm'].str.contains('poi_card_click', na=False).sum()),
        'navigation_requested': int(df['span_nm'].str.contains('navigation_button_click', na=False).sum()),
        'navigation_confirmed': int(df['span_nm'].str.contains(
            'navigation_popup_confirm_click|detail_tab_poi_navigation_popup_confirm_click', na=False).sum()),
    }
    prev = None
    poi_funnel_rates = {}
    for k, v in poi_funnel.items():
        entry = {'count': v}
        if prev is not None and poi_funnel[prev] > 0:
            entry['conversion_rate'] = round(v / poi_funnel[prev] * 100, 2)
        poi_funnel_rates[k] = entry
        prev = k

    ai_funnel = {
        'ai_guide_button_shown': int(df['span_nm'].str.contains('ai_travel_guide_button_show', na=False).sum()),
        'ai_guide_button_clicked': int(df['span_nm'].str.contains('ai_travel_guide_button_click', na=False).sum()),
        'guide_generated': int(df['span_nm'].str.contains('generated_travel_guide_button_show', na=False).sum()),
        'guide_confirmed': int(df['span_nm'].str.contains('generated_travel_guide_button_click', na=False).sum()),
        'guide_detail_viewed': int(df['span_nm'].str.contains('trival_guide_page_pageshow', na=False).sum()),
        'guide_shared': int(df['span_nm'].str.contains('trival_guide_page_share_icon_click', na=False).sum()),
    }
    prev = None
    ai_funnel_rates = {}
    for k, v in ai_funnel.items():
        entry = {'count': v}
        if prev is not None and ai_funnel[prev] > 0:
            entry['conversion_rate'] = round(v / ai_funnel[prev] * 100, 2)
        ai_funnel_rates[k] = entry
        prev = k

    search_journey = {
        'search_homepage': int(df['span_nm'].str.contains('search_homepage', na=False).sum()),
        'search_results': int(df['span_nm'].str.contains('search_results_page', na=False).sum()),
        'result_to_post_click': int(df['span_nm'].str.contains('search_results_page_post_card_click', na=False).sum()),
    }

    user_journeys = {}
    for uid, grp in df[df['reduser_id'].notna()].groupby('reduser_id'):
        sorted_grp = grp.sort_values('strt_time_dt')
        pages_visited = sorted_grp['page_root'].dropna().tolist()
        journey_key = ' -> '.join(pages_visited[:8])
        user_journeys[journey_key] = user_journeys.get(journey_key, 0) + 1

    top_journeys = sorted(user_journeys.items(), key=lambda x: -x[1])[:15]

    referer_flow = df[df['referer_page'].notna()]['referer_page'].value_counts().head(10).to_dict()

    result = {
        'page_distribution': dict(page_events.head(15)),
        'action_distribution': dict(action_events.head(10)),
        'content_consumption_funnel': funnel_with_rates,
        'poi_navigation_funnel': poi_funnel_rates,
        'ai_guide_funnel': ai_funnel_rates,
        'search_journey': search_journey,
        'top_user_journeys': [{ 'journey': j, 'users': c } for j, c in top_journeys],
        'referer_flow': referer_flow,
        'top_events': dict(span_events.head(20))
    }

    print(f"  内容漏斗转化: {funnel_with_rates}")
    print(f"  POI导航漏斗转化: {poi_funnel_rates}")
    print(f"  AI指南漏斗转化: {ai_funnel_rates}")
    print(f"  Top用户路径: {len(top_journeys)} 种")

    return result


def analyze_correlation_needs(df):
    """5. 用户关联需求分析"""
    print("\n" + "=" * 50)
    print("[5/6] 用户关联需求分析")
    print("=" * 50)

    user_features = df[df['reduser_id'].notna()].groupby('reduser_id').apply(
        lambda g: pd.Series({
            'uses_poi': g['rednote_poi_title'].notna().any(),
            'uses_content': g['rednote_post_title'].notna().any(),
            'uses_search': g['span_nm'].str.contains('search', case=False, na=False).any(),
            'uses_ai': g['span_nm'].str.contains('ai|guide|travel', case=False, na=False).any(),
            'uses_video': g['rednote_video_post_is_play'].notna().any(),
            'uses_map_fullscreen': (g['rednote_poi_map_fullscreen'] == 1).any(),
            'engages': (g['rednote_post_is_like'].notna() | g['rednote_post_is_save'].notna()).any(),
        })
    )

    feature_combos = user_features.apply(lambda r: tuple(k for k, v in r.items() if v), axis=1)
    combo_counts = feature_combos.value_counts().head(15).to_dict()

    pair_correlations = {}
    features = ['uses_poi', 'uses_content', 'uses_search', 'uses_ai', 'uses_video', 'engages']
    for i, f1 in enumerate(features):
        for f2 in features[i+1:]:
            both = (user_features[f1] & user_features[f2]).sum()
            only_f1 = user_features[f1].sum() - both
            only_f2 = user_features[f2].sum() - both
            total = user_features.shape[0]
            key = f"{f1.replace('uses_', '')}_x_{f2.replace('uses_', '')}"
            pair_correlations[key] = {
                'both_use': int(both),
                'only_a': int(only_f1),
                'only_b': int(only_f2),
                'neither': int(total - both - only_f1 - only_f2),
                'co_usage_rate': round(both / max(total, 1) * 100, 2),
                'conditional_prob_a_given_b': round(both / max(user_features[f2].sum(), 1) * 100, 2),
                'conditional_prob_b_given_a': round(both / max(user_features[f1].sum(), 1) * 100, 2)
            }

    search_then_poi = 0
    poi_then_content = 0
    content_then_ai = 0
    for uid, grp in df[df['reduser_id'].notna()].sort_values('strt_time_dt').groupby('reduser_id'):
        events = grp['span_nm'].tolist()
        has_search = any('search' in str(e).lower() for e in events)
        has_poi = any('poi' in str(e).lower() or 'porsche' in str(e).lower() for e in events)
        has_content = any('post' in str(e).lower() and 'card' in str(e).lower() for e in events)
        has_ai = any('ai' in str(e).lower() or 'guide' in str(e).lower() or 'travel' in str(e).lower() for e in events)

        if has_search and has_poi:
            search_then_poi += 1
        if has_poi and has_content:
            poi_then_content += 1
        if has_content and has_ai:
            content_then_ai += 1

    temporal_patterns = {}
    for uid, grp in df[df['reduser_id'].notna() & df['strt_time_dt'].notna()].sort_values('strt_time_dt').groupby('reduser_id'):
        sorted_g = grp.sort_values('strt_time_dt')
        pages = sorted_g['page_root'].tolist()
        switches = sum(1 for i in range(1, len(pages)) if pages[i] != pages[i-1])
        temporal_patterns[str(uid)] = {
            'page_switches': switches,
            'session_length': len(pages),
            'switch_rate': round(switches / max(len(pages), 1), 2)
        }

    avg_switches = np.mean([tp['page_switches'] for tp in temporal_patterns.values()])
    high_explorers = sum(1 for tp in temporal_patterns.values() if tp['switch_rate'] > 0.7)

    poi_content_overlap_users = (user_features['uses_poi'] & user_features['uses_content']).sum()
    search_ai_overlap = (user_features['uses_search'] & user_features['uses_ai']).sum()

    result = {
        'feature_co_usage_combinations': {str(k): int(v) for k, v in combo_counts.items()},
        'pairwise_correlations': pair_correlations,
        'sequential_need_patterns': {
            'search_to_poi_users': int(search_then_poi),
            'poi_to_content_users': int(poi_then_content),
            'content_to_ai_users': int(content_then_ai),
        },
        'cross_feature_insights': {
            'poi_and_content_overlap': int(poi_content_overlap_users),
            'search_and_ai_overlap': int(search_ai_overlap),
        },
        'exploration_behavior': {
            'avg_page_switches_per_session': round(avg_switches, 2),
            'high_explorer_users': high_explorers,
            'total_sessions_analyzed': len(temporal_patterns)
        }
    }

    print(f"  功能组合使用Top: {list(combo_counts.keys())[:5]}")
    print(f"  搜索→POI关联用户: {search_then_poi:,}")
    print(f"  POI→内容关联用户: {poi_then_content:,}")
    print(f"  高探索度用户: {high_explorers:,}")

    return result


def analyze_app_familiarity(df):
    """6. 用户对APP熟悉程度分析"""
    print("\n" + "=" * 50)
    print("[6/6] APP熟悉程度分析")
    print("=" * 50)

    all_events = set(df['span_nm'].dropna().unique())
    total_unique_events = len(all_events)

    user_familiarity = {}
    for uid, grp in df[df['reduser_id'].notna()].groupby('reduser_id'):
        used_events = set(grp['span_nm'].dropna().unique())
        used_pages = set(grp['page_root'].dropna().unique())
        used_actions = set(grp['action'].dropna().unique())

        coverage = len(used_events) / max(total_unique_events, 1)
        depth = len(grp)
        breadth = len(used_pages)

        has_advanced = any(x in used_events for x in [
            'ai_travel_guide_button_click', 'generated_travel_guide_button_click',
            'travel_guide_tab_trip_card_click', 'detail_tab_poi_navigation_button_click',
        ])

        nav_efficiency = 0
        back_clicks = grp[grp['span_nm'].str.contains('back_button_click', na=False)]
        if len(grp) > 0:
            nav_efficiency = round(1 - len(back_clicks) / len(grp), 3)

        familiarity_score = (
            coverage * 30 +
            min(breadth / 10, 1) * 25 +
            min(depth / 50, 1) * 20 +
            (1 if has_advanced else 0) * 15 +
            nav_efficiency * 10
        )

        if familiarity_score >= 60:
            level = 'expert'
        elif familiarity_score >= 35:
            level = 'intermediate'
        elif familiarity_score >= 15:
            level = 'beginner'
        else:
            level = 'newbie'

        user_familiarity[str(uid)] = {
            'events_discovered': len(used_events),
            'event_coverage_pct': round(coverage * 100, 2),
            'pages_visited': breadth,
            'total_events': depth,
            'uses_advanced_features': has_advanced,
            'nav_efficiency': nav_efficiency,
            'familiarity_score': round(familiarity_score, 1),
            'level': level
        }

    levels = Counter(u['level'] for u in user_familiarity.values())
    avg_score = np.mean([u['familiarity_score'] for u in user_familiarity.values()])
    avg_coverage = np.mean([u['event_coverage_pct'] for u in user_familiarity.values()])
    avg_nav_eff = np.mean([u['nav_efficiency'] for u in user_familiarity.values()])
    advanced_users = sum(1 for u in user_familiarity.values() if u['uses_advanced_features'])

    experts = {uid: u for uid, u in user_familiarity.items() if u['level'] == 'expert'}
    expert_top_events = defaultdict(int)
    for uid in experts.keys():
        try:
            udata = df[df['reduser_id'] == float(uid)]
            for evt in udata['span_nm'].value_counts().head(5).index:
                expert_top_events[evt] += 1
        except:
            pass

    newbies = {uid: u for uid, u in user_familiarity.items() if u['level'] == 'newbie'}
    newbie_top_events = defaultdict(int)
    for uid in newbies.keys():
        try:
            udata = df[df['reduser_id'] == float(uid)]
            for evt in udata['span_nm'].value_counts().head(5).index:
                newbie_top_events[evt] += 1
        except:
            pass

    feature_discovery_rates = {}
    key_features = {
        'AI旅行指南': ['ai_travel_guide_button_click'],
        'POI导航': ['navigation_button_click', 'navigation_popup_confirm_click'],
        '视频播放': ['rednote_video_post_is_play'],
        '内容互动': ['post_like_click', 'save_button_click', 'follow_button_click'],
        '搜索功能': ['search_homepage'],
        '个人中心': ['profile_page'],
        '分享功能': ['share_icon_click'],
        '路书生成': ['generated_travel_guide_button_click'],
    }
    total_users = len(user_familiarity)
    for fname, patterns in key_features.items():
        count = 0
        for uinfo in user_familiarity.values():
            pass
        feature_discovery_rates[fname] = round(count / max(total_users, 1) * 100, 1)

    result = {
        'familiarity_level_distribution': dict(levels),
        'statistics': {
            'total_users_assessed': len(user_familiarity),
            'avg_familiarity_score': round(avg_score, 1),
            'avg_event_coverage_pct': round(avg_coverage, 2),
            'avg_navigation_efficiency': round(avg_nav_eff, 3),
            'advanced_feature_users': advanced_users,
            'total_available_events': total_unique_events
        },
        'feature_discovery_rates': feature_discovery_rates,
        'expert_behavior': {
            'expert_count': len(experts),
            'top_events_for_experts': dict(sorted(expert_top_events.items(), key=lambda x: -x[1])[:10]),
        },
        'newbie_behavior': {
            'newbie_count': len(newbies),
            'top_events_for_newbies': dict(sorted(newbie_top_events.items(), key=lambda x: -x[1])[:10]),
        }
    }

    print(f"  熟悉度分布: {dict(levels)}")
    print(f"  平均得分: {avg_score:.1f}/100")
    print(f"  平均事件覆盖率: {avg_coverage:.1f}%")
    print(f"  高级功能使用率: {advanced_users}/{len(user_familiarity)}")

    return result


def generate_html_report(all_results, output_path):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    profiling = all_results['profiling'][0]
    lifestyle = all_results['lifestyle']
    consumption = all_results['consumption']
    scenarios = all_results['scenarios']
    correlation = all_results['correlation']
    familiarity = all_results['familiarity']
    total_u = profiling['total_users_analyzed']

    def esc(s):
        import html as h
        return h.escape(str(s))

    html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rednote 全量数据深度洞察报告</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9fa;color:#1a1a2e;line-height:1.6;}}
.container{{max-width:1200px;margin:0 auto;padding:24px;}}
h1{{text-align:center;font-size:28px;color:#D94F30;padding:32px 0 16px;border-bottom:3px solid #D94F30;}}
.meta{{text-align:center;color:#666;font-size:14px;margin-bottom:40px;}}
.section{{background:white;border-radius:12px;padding:28px;margin-bottom:24px;box-shadow:0 2px 12px rgba(0,0,0,0.08);}}
h2{{font-size:20px;color:#D94F30;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #f0e8e4;}}
h3{{font-size:16px;color:#333;margin:16px 0 8px;}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px;}}
th{{background:#D94F30;color:white;padding:10px 12px;text-align:left;font-weight:600;}}
td{{padding:8px 12px;border-bottom:1px solid #eee;}}
tr:hover{{background:#fef5f0;}}
.metric-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin:16px 0;}}
.metric-card{{background:linear-gradient(135deg,#fff5f0,#fff);border-radius:10px;padding:18px;border-left:4px solid #D94F30;}}
.metric-value{{font-size:28px;font-weight:800;color:#D94F30;}}
.metric-label{{font-size:13px;color:#666;margin-top:4px;}}
.tag{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;margin:2px;}}
.tag-high{{background:#e8f5ee;color:#2D8B55;}} .tag-mid{{background:#e4f2f7;color:#2A7B9B;}} .tag-low{{background:#fde8e8;color:#C93B3B;}}
.insight-box{{background:#fffbf5;border-left:4px solid #D4A843;padding:14px 18px;margin:12px 0;border-radius:0 8px 8px 0;}}
.funnel-step{{display:flex;align-items:center;gap:12px;margin:8px 0;padding:10px;background:#fafafa;border-radius:8px;}}
.funnel-bar{{height:28px;border-radius:14px;background:linear-gradient(90deg,#D94F30,#e8836c);display:flex;align-items:center;justify-content:center;color:white;font-weight:600;font-size:13px;min-width:60px;}}
.funnel-label{{font-size:13px;min-width:180px;}} .funnel-rate{{font-size:12px;color:#888;min-width:80px;}}
</style></head><body><div class="container">
<h1>Rednote 全量数据深度洞察报告</h1>
<p class="meta">生成时间: {now} | 数据范围: 2026-03-19 ~ 2026-03-30 | 6大分析维度</p>

<div class="section"><h2>核心指标总览</h2><div class="metric-grid">
<div class="metric-card"><div class="metric-value">{profiling["statistics"]["avg_events_per_user"]}</div><div class="metric-label">人均事件数</div></div>
<div class="metric-card"><div class="metric-value">{profiling["total_users_analyzed"]:,}</div><div class="metric-label">分析用户总数</div></div>
<div class="metric-card"><div class="metric-value">{profiling["statistics"]["avg_active_days"]:.1f}</div><div class="metric-label">平均活跃天数</div></div>
<div class="metric-card"><div class="metric-value">{lifestyle["weekend_vs_weekday"]["weekend_ratio_pct"]:.1f}%</div><div class="metric-label">周末事件占比</div></div>
<div class="metric-card"><div class="metric-value">{consumption["content_consumption"]["overall_engagement_rate"]:.2f}%</div><div class="metric-label">整体互动率</div></div>
<div class="metric-card"><div class="metric-value">{familiarity["statistics"]["avg_familiarity_score"]:.1f}</div><div class="metric-label">平均APP熟悉度</div></div>
</div></div>

<div class="section"><h2>一、用户画像分析</h2>
<h3>活跃度分层</h3><table><tr><th>层级</th><th>用户数</th><th>占比</th><th>说明</th></tr>'''

    tier_desc = {
        'high_active': ('高活用户', '高频深度使用者，核心价值群体', 'tag-high'),
        'medium_active': ('中活用户', '稳定使用的常规用户', 'tag-mid'),
        'low_active': ('低活用户', '偶发使用的轻度用户', 'tag-low'),
        'dormant': ('沉睡用户', '几乎不活跃，需唤醒', 'tag-low')
    }
    for tier, count in profiling['activity_distribution'].items():
        desc, note, cls = tier_desc.get(tier, (tier, '', 'tag-info'))
        pct = round(count / max(total_u, 1) * 100, 1)
        html += f'<tr><td><span class="tag {cls}">{esc(desc)}</span></td><td>{count:,}</td><td>{pct}%</td><td>{esc(note)}</td></tr>'
    html += '</table><h3>用户角色画像</h3><table><tr><th>画像类型</th><th>用户数</th><th>占比</th><th>特征</th></tr>'
    persona_desc = {
        'power_user': ('全能玩家', '同时使用4+功能模块，高粘性核心用户', 'tag-high'),
        'regular_user': ('常规用户', '使用2-3个功能模块，有明确偏好', 'tag-mid'),
        'single_feature_user': ('单功能用户', '仅使用单一功能，有增长空间', 'tag-low'),
        'browser': ('浏览者', '仅浏览无深度交互', 'tag-low')
    }
    for persona, count in profiling['persona_distribution'].items():
        desc, note, cls = persona_desc.get(persona, (persona, '', 'tag-info'))
        pct = round(count / max(total_u, 1) * 100, 1)
        html += f'<tr><td><span class="tag {cls}">{esc(desc)}</span></td><td>{count:,}</td><td>{pct}%</td><td>{esc(note)}</td></tr>'
    html += '</table>'

    html += f'''
<h3>新老用户构成</h3><table><tr><th>类型</th><th>数量</th><th>占比</th></tr>
<tr><td>新用户(≤1天)</td><td>{profiling["new_vs_returning_users"]["new_users"]:,}</td><td>{round(profiling["new_vs_returning_users"]["new_users"]/max(total_u,1)*100,1)}%</td></tr>
<tr><td>回访用户(>1天)</td><td>{profiling["new_vs_returning_users"]["returning_users"]:,}</td><td>{round(profiling["new_vs_returning_users"]["returning_users"]/max(total_u,1)*100,1)}%</td></tr>
</table>
<h3>页面偏好TOP</h3><table><tr><th>首选页面</th><th>用户数</th></tr>'''
    for page, cnt in list(profiling['page_preference'].items())[:8]:
        html += f'<tr><td>{esc(page)}</td><td>{cnt:,}</td></tr>'
    html += '</table>'

    html += '''<h3>功能渗透率</h3><div class="metric-grid">'''
    feat_labels = {
        'poi_users': ('📍 POI地图', '探索过POI的用户'),
        'post_consumers': ('📝 内容消费', '浏览过笔记内容的用户'),
        'video_viewers': ('🎬 视频观看', '有过视频交互的用户'),
        'ai_guide_users': ('🤖 AI指南', '使用过AI旅行指南的用户'),
        'engagers_like': ('❤️ 点赞互动', '有过点赞行为的用户'),
        'engagers_save': ('⭐ 收藏互动', '有过收藏行为的用户'),
        'engagers_follow': ('👤 关注互动', '有过关注行为的用户'),
    }
    for key, (label, desc) in feat_labels.items():
        val = profiling['feature_adoption'].get(key, 0)
        rate = round(val / max(total_u, 1) * 100, 1)
        html += f'<div class="metric-card"><div class="metric-value">{val:,}</div><div class="metric-label">{label} ({rate}%)</div></div>'
    html += '</div>'

    html += f'''
<div class="insight-box"><strong>💡 核心洞察：</strong>
全能玩家占{round(profiling["persona_distribution"].get("power_user",0)/max(total_u,1)*100,1)}%，
回访用户占{round(profiling["new_vs_returning_users"]["returning_users"]/max(total_u,1)*100,1)}%，
POI地图功能渗透率达{round(profiling["feature_adoption"].get("poi_users",0)/max(total_u,1)*100,1)}%。
</div></div>'''

    html += f'''
<div class="section"><h2>二、用户生活习惯分析</h2>
<h3>24小时活跃分布</h3><table><tr><th>时段</th><th>事件数</th><th>活跃用户</th></tr>'''
    for hr, data in lifestyle['hourly_data']['hourly_distribution'].items():
        peak_tag = ' 🔥' if hr == lifestyle['hourly_data']['peak_hour'] else ''
        html += f'<tr><td>{hr:02d}:00-{hr:02d}:59</td><td>{data["events"]:,}</td><td>{data["users"]:,}</td>{peak_tag}</tr>'
    html += '</table>'

    html += f'''
<h3>周末 vs 工作日</h3><table><tr><th>类型</th><th>事件数</th><th>占比</th></tr>
<tr><td>周末 (周六日)</td><td>{lifestyle["weekend_vs_weekday"]["weekend_events"]:,}</td><td>{lifestyle["weekend_vs_weekday"]["weekend_ratio_pct"]}%</td></tr>
<tr><td>工作日 (周一至五)</td><td>{lifestyle["weekend_vs_weekday"]["weekday_events"]:,}</td><td>{round(100-lifestyle["weekend_vs_weekday"]["weekend_ratio_pct"],1)}%</td></tr>
</table>

<div class="insight-box"><strong>💡 核心洞察：</strong>
高峰时段为{lifestyle["peak_hour_info"]["hour"]:02d}:00，
夜猫子用户达{lifestyle["user_time_profiles_summary"]["night_owl_users"]}人，
早鸟用户{lifestyle["user_time_profiles_summary"]["early_bird_users"]}人。
</div></div>'''

    html += f'''
<div class="section"><h2>三、用户消费习惯分析</h2>
<h3>POI兴趣分类</h3><table><tr><th>类别</th><th>交互次数</th></tr>'''
    for cat, cnt in consumption['poi_analysis']['top_poi_categories'].items():
        html += f'<tr><td>{esc(cat)}</td><td>{cnt:,}</td></tr>'
    html += '</table>'

    html += f'''
<h3>热门POI TOP10</h3><table><tr><th>排名</th><th>POI名称</th><th>出现次数</th></tr>'''
    for i, (poi, cnt) in enumerate(list(consumption['poi_analysis']['top_individual_pois'].items())[:10], 1):
        html += f'<tr><td>{i}</td><td>{esc(str(poi)[:40])}</td><td>{cnt:,}</td></tr>'
    html += '</table>'

    html += f'''
<h3>内容消费行为</h3><div class="metric-grid">
<div class="metric-card"><div class="metric-value">{consumption["content_consumption"]["total_post_views"]:,}</div><div class="metric-label">笔记浏览总量</div></div>
<div class="metric-card"><div class="metric-value">{consumption["content_consumption"]["likes"]:,}</div><div class="metric-label">点赞次数</div></div>
<div class="metric-card"><div class="metric-value">{consumption["content_consumption"]["saves"]:,}</div><div class="metric-label">收藏次数</div></div>
<div class="metric-card"><div class="metric-value">{consumption["content_consumption"]["follows"]:,}</div><div class="metric-label">关注次数</div></div>
<div class="metric-card"><div class="metric-value">{consumption["content_consumption"]["overall_engagement_rate"]:.2f}%</div><div class="metric-label">整体互动率</div></div>
<div class="metric-card"><div class="metric-value">{consumption["video_behavior"]["total_video_interactions"]:,}</div><div class="metric-label">视频交互量</div></div>
</div>

<h3>用户消费倾向</h3><table><tr><th>类型</th><th>用户数</th><th>占比</th></tr>
<tr><td>📖 内容导向型</td><td>{consumption["user_consumption_patterns"]["content_focused_users"]:,}</td><td>{round(consumption["user_consumption_patterns"]["content_focused_users"]/max(consumption["user_consumption_patterns"]["total_analyzed_users"],1)*100,1)}%</td></tr>
<tr><td>📍 POI导向型</td><td>{consumption["user_consumption_patterns"]["poi_focused_users"]:,}</td><td>{round(consumption["user_consumption_patterns"]["poi_focused_users"]/max(consumption["user_consumption_patterns"]["total_analyzed_users"],1)*100,1)}%</td></tr>
</table>

<div class="insight-box"><strong>💡 核心洞察：</strong>
共发现{consumption["poi_analysis"]["unique_pois"]}个独立POI点，
内容互动率{consumption["content_consumption"]["overall_engagement_rate"]}%，
平均用户参与度{consumption["user_consumption_patterns"]["avg_engagement_rate"]}%。
</div></div>'''

    cf = scenarios['content_consumption_funnel']
    pf = scenarios['poi_navigation_funnel']
    af = scenarios['ai_guide_funnel']

    html += f'''
<div class="section"><h2>四、用户使用场景分析</h2>
<h3>内容消费转化漏斗</h3>'''
    for step, data in cf.items():
        label = step.replace('_', ' ').title()
        bar_w = max(20, int(data['count'] / max(cf[list(cf.keys())[0]]['count'], 1) * 400))
        rate_str = f" → {data.get('conversion_rate','')}%" if 'conversion_rate' in data else ''
        html += f'<div class="funnel-step"><div class="funnel-label">{esc(label)}</div><div class="funnel-bar" style="width:{bar_w}px">{data["count"]:,}</div><div class="funnel-rate">{rate_str}</div></div>'

    html += '<h3>POI导航转化漏斗</h3>'
    for step, data in pf.items():
        label = step.replace('_', ' ').title()
        bar_w = max(20, int(data['count'] / max(pf[list(pf.keys())[0]]['count'], 1) * 400))
        rate_str = f" → {data.get('conversion_rate','')}%" if 'conversion_rate' in data else ''
        html += f'<div class="funnel-step"><div class="funnel-label">{esc(label)}</div><div class="funnel-bar" style="width:{bar_w}px">{data["count"]:,}</div><div class="funnel-rate">{rate_str}</div></div>'

    html += '<h3>AI旅行指南转化漏斗</h3>'
    for step, data in af.items():
        label = step.replace('_', ' ').title()
        bar_w = max(20, int(data['count'] / max(af[list(af.keys())[0]]['count'], 1) * 400))
        rate_str = f" → {data.get('conversion_rate','')}%" if 'conversion_rate' in data else ''
        html += f'<div class="funnel-step"><div class="funnel-label">{esc(label)}</div><div class="funnel-bar" style="width:{bar_w}px">{data["count"]:,}</div><div class="funnel-rate">{rate_str}</div></div>'

    html += '''<h3>TOP用户行为路径</h3>
<table><tr><th>#</th><th>路径</th><th>用户数</th></tr>'''
    for i, j in enumerate(scenarios['top_user_journeys'][:10], 1):
        path_display = j['journey'][:80] + ('...' if len(j['journey']) > 80 else '')
        html += f'<tr><td>{i}</td><td style="font-family:monospace;font-size:12px;">{esc(path_display)}</td><td>{j["users"]:,}</td></tr>'
    html += '</table></div>'

    html += f'''
<div class="section"><h2>五、用户关联需求分析</h2>
<h3>功能两两关联强度</h3><table><tr><th>功能对</th><th>共同使用</th><th>A→B概率</th><th>B→A概率</th></tr>'''
    sorted_pairs = sorted(correlation['pairwise_correlations'].items(), key=lambda x: -x[1]['co_usage_rate'])
    for pair, data in sorted_pairs[:10]:
        html += f'<tr><td>{esc(pair)}</td><td>{data["both_use"]:,}</td><td>{data["conditional_prob_a_given_b"]}%</td><td>{data["conditional_prob_b_given_a"]}%</td></tr>'
    html += '</table>'

    html += f'''
<h3>跨场景需求流转</h3><table><tr><th>需求链路</th><th>涉及用户数</th></tr>
<tr><td>搜索 → POI探索</td><td>{correlation["sequential_need_patterns"]["search_to_poi_users"]:,}</td></tr>
<tr><td>POI探索 → 内容消费</td><td>{correlation["sequential_need_patterns"]["poi_to_content_users"]:,}</td></tr>
<tr><td>内容消费 → AI指南</td><td>{correlation["sequential_need_patterns"]["content_to_ai_users"]:,}</td></tr>
</table>

<h3>探索行为</h3><table><tr><th>指标</th><th>数值</th></tr>
<tr><td>平均每会话页面切换次数</td><td>{correlation["exploration_behavior"]["avg_page_switches_per_session"]:.1f}</td></tr>
<tr><td>高探索度用户(切换率>70%)</td><td>{correlation["exploration_behavior"]["high_explorer_users"]:,}</td></tr>
</table>

<div class="insight-box"><strong>💡 核心洞察：</strong>
搜索与POI强关联({correlation["sequential_need_patterns"]["search_to_poi_users"]}人)，
{correlation["exploration_behavior"]["high_explorer_users"]}用户为高探索型。
</div></div>'''

    fd = familiarity['familiarity_level_distribution']
    fs = familiarity['statistics']

    html += f'''
<div class="section"><h2>六、APP熟悉程度分析</h2>
<h3>熟悉度分级分布</h3><table><tr><th>等级</th><th>用户数</th><th>占比</th><th>特征描述</th></tr>
<tr><td><span class="tag tag-high">专家 Expert</span></td><td>{fd.get("expert",0):,}</td><td>{round(fd.get("expert",0)/max(fs["total_users_assessed"],1)*100,1)}%</td><td>精通大部分功能，主动探索高级特性</td></tr>
<tr><td><span class="tag tag-mid">中级 Intermediate</span></td><td>{fd.get("intermediate",0):,}</td><td>{round(fd.get("intermediate",0)/max(fs["total_users_assessed"],1)*100,1)}%</td><td>掌握核心流程，偶尔尝试新功能</td></tr>
<tr><td><span class="tag tag-low">新手 Beginner</span></td><td>{fd.get("beginner",0):,}</td><td>{round(fd.get("beginner",0)/max(fs["total_users_assessed"],1)*100,1)}%</td><td>了解基础操作，需要引导</td></tr>
<tr><td><span class="tag tag-low">萌新 Newbie</span></td><td>{fd.get("newbie",0):,}</td><td>{round(fd.get("newbie",0)/max(fs["total_users_assessed"],1)*100,1)}%</td><td>刚接触产品，仅完成基本浏览</td></tr>
</table>

<div class="metric-grid">
<div class="metric-card"><div class="metric-value">{fs["avg_familiarity_score"]:.1f}<small>/100</small></div><div class="metric-label">平均熟悉度得分</div></div>
<div class="metric-card"><div class="metric-value">{fs["avg_event_coverage_pct"]:.1f}%</div><div class="metric-label">平均事件覆盖率</div></div>
<div class="metric-card"><div class="metric-value">{fs["avg_navigation_efficiency"]:.3f}</div><div class="metric-label">平均导航效率</div></div>
<div class="metric-card"><div class="metric-value">{fs["advanced_feature_users"]:,}</div><div class="metric-label">高级功能使用者</div></div>
</div>

<div class="insight-box"><strong>💡 核心洞察：</strong>
专家级用户{fd.get("expert",0)}人({round(fd.get("expert",0)/max(fs["total_users_assessed"],1)*100,1)}%)，
{fs["advanced_feature_users"]}人使用过高级功能，
整体平均熟悉度{fs["avg_familiarity_score"]:.1f}分。
</div></div>

</div></body></html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    ensure_dir(OUTPUT_DIR)

    df, total_users = load_and_prepare()

    results = {}

    print("\n开始执行6大维度分析...")

    results['profiling'] = analyze_user_profiling(df, total_users)
    results['lifestyle'] = analyze_lifestyle_habits(df)
    results['consumption'] = analyze_consumption_habits(df)
    results['scenarios'] = analyze_usage_scenarios(df, results['profiling'][1])
    results['correlation'] = analyze_correlation_needs(df)
    results['familiarity'] = analyze_app_familiarity(df)

    json_output = os.path.join(OUTPUT_DIR, 'deep_insights.json')
    json_results = {k: (v[0] if isinstance(v, tuple) else v) for k, v in results.items()}
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(json_results), f, indent=2, ensure_ascii=False)
    print(f"\n✅ JSON洞察数据已保存: {json_output}")

    html_output = os.path.join(OUTPUT_DIR, 'full_insight_report.html')
    generate_html_report(results, html_output)
    print(f"✅ HTML报告已保存: {html_output}")

    user_stats_df = results['profiling'][1]
    csv_output = os.path.join(OUTPUT_DIR, 'user_profile_table.csv')
    user_stats_df.to_csv(csv_output, index=False, encoding='utf-8-sig')
    print(f"✅ 用户画像CSV已保存: {csv_output}")

    print("\n" + "=" * 70)
    print("全部分析完成！输出文件:")
    print(f"  1. {json_output}")
    print(f"  2. {html_output}")
    print(f"  3. {csv_output}")
    print("=" * 70)


if __name__ == '__main__':
    main()
