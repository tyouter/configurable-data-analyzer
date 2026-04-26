# -*- coding: utf-8 -*-
"""
Rednote 全量数据深度洞察分析脚本 V2
基于 rednote20260319-20260412.xlsx 数据
6大维度: 用户画像 / 生活习惯 / 消费习惯 / 使用场景 / 关联需求 / APP熟悉度
输出到 report/fulldata_v2/
"""

import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime, timedelta
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_PATH = r'C:\projects\rednote data analyzer\data\rednote\rednote20260319-20260412.xlsx'
OUTPUT_DIR = r'C:\projects\rednote data analyzer\report\fulldata_v2'

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def to_serializable(obj):
    """转换为可序列化的对象"""
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

def load_and_prepare():
    """加载并预处理数据"""
    print("=" * 70)
    print("Rednote 全量数据深度洞察分析 V2")
    print(f"数据源: {DATA_PATH}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 70)

    df = pd.read_excel(DATA_PATH)
    print(f"\n[数据概览] {df.shape[0]:,} 行 x {df.shape[1]} 列")

    # 时间处理
    df['timestamp'] = pd.to_datetime(df['start_time_nano'], errors='coerce')
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.dayofweek

    print(f"[时间范围] {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"[用户数] {df['reduser_id'].nunique():,} 人")
    print(f"[设备数] {df['device_id'].nunique():,} 台")
    print(f"[事件类型] {df['span_name'].nunique():,} 种")

    return df

def calculate_basic_kpis(df):
    """计算基础KPI指标"""
    print("\n[1] 计算基础KPI指标...")

    kpis = {}

    # 用户与设备统计
    kpis['total_users'] = df['reduser_id'].nunique()
    kpis['total_devices'] = df['device_id'].nunique()
    kpis['total_events'] = len(df)
    kpis['event_types'] = df['span_name'].nunique()

    # APP打开统计
    app_open_events = df[df['span_name'].str.contains('login_page_pageshow|discovery_page_pageshow', case=False, na=False)]
    kpis['app_open_count'] = len(app_open_events)

    # 按用户日期去重计算打开天数
    if len(app_open_events) > 0:
        app_open_events['user_date'] = app_open_events['reduser_id'].astype(str) + '_' + app_open_events['date'].astype(str)
        kpis['app_open_days'] = app_open_events['user_date'].nunique()
        kpis['app_open_users'] = app_open_events['reduser_id'].nunique()
    else:
        kpis['app_open_days'] = 0
        kpis['app_open_users'] = 0

    # 人均打开次数
    if kpis['app_open_users'] > 0:
        kpis['avg_open_per_user'] = round(kpis['app_open_days'] / kpis['app_open_users'], 2)
    else:
        kpis['avg_open_per_user'] = 0

    # 计算日活跃用户数
    dau = df.groupby('date')['reduser_id'].nunique()
    kpis['avg_dau'] = round(dau.mean(), 1)
    kpis['max_dau'] = int(dau.max())
    kpis['min_dau'] = int(dau.min())

    # 计算平均每用户事件数
    user_events = df.groupby('reduser_id').size()
    kpis['avg_events_per_user'] = round(user_events.mean(), 1)
    kpis['max_events_per_user'] = int(user_events.max())
    kpis['min_events_per_user'] = int(user_events.min())

    print(f"  总用户数: {kpis['total_users']}")
    print(f"  总事件数: {kpis['total_events']}")
    print(f"  日均活跃用户: {kpis['avg_dau']}")
    print(f"  人均事件数: {kpis['avg_events_per_user']}")

    return kpis

def calculate_page_metrics(df):
    """计算页面相关指标"""
    print("\n[2] 计算页面曝光指标...")

    metrics = {}

    # 发现页面指标
    discovery = df[df['span_name'] == 'discovery_page_pageshow']
    metrics['discovery'] = {
        'total_views': len(discovery),
        'unique_users': discovery['reduser_id'].nunique() if len(discovery) > 0 else 0
    }

    # 计算曝光时长
    if len(discovery) > 0 and 'page_start_time' in df.columns and 'page_end_time' in df.columns:
        discovery_copy = discovery.copy()
        discovery_copy['duration'] = (
            pd.to_datetime(discovery_copy['page_end_time'], errors='coerce') -
            pd.to_datetime(discovery_copy['page_start_time'], errors='coerce')
        ).dt.total_seconds()
        valid_duration = discovery_copy['duration'].dropna()
        valid_duration = valid_duration[valid_duration > 0]
        if len(valid_duration) > 0:
            metrics['discovery']['avg_duration'] = round(valid_duration.mean(), 2)
            metrics['discovery']['total_duration'] = round(valid_duration.sum(), 2)
            metrics['discovery']['max_duration'] = round(valid_duration.max(), 2)
        else:
            metrics['discovery']['avg_duration'] = 0
            metrics['discovery']['total_duration'] = 0
            metrics['discovery']['max_duration'] = 0
    else:
        metrics['discovery']['avg_duration'] = 0
        metrics['discovery']['total_duration'] = 0
        metrics['discovery']['max_duration'] = 0

    # Porsche+页面指标
    porsche = df[df['span_name'] == 'porsche_page_pageshow']
    metrics['porsche'] = {
        'total_views': len(porsche),
        'unique_users': porsche['reduser_id'].nunique() if len(porsche) > 0 else 0
    }

    # 计算Porsche曝光时长
    if len(porsche) > 0 and 'page_start_time' in df.columns and 'page_end_time' in df.columns:
        porsche_copy = porsche.copy()
        porsche_copy['duration'] = (
            pd.to_datetime(porsche_copy['page_end_time'], errors='coerce') -
            pd.to_datetime(porsche_copy['page_start_time'], errors='coerce')
        ).dt.total_seconds()
        valid_duration = porsche_copy['duration'].dropna()
        valid_duration = valid_duration[valid_duration > 0]
        if len(valid_duration) > 0:
            metrics['porsche']['avg_duration'] = round(valid_duration.mean(), 2)
            metrics['porsche']['total_duration'] = round(valid_duration.sum(), 2)
            metrics['porsche']['max_duration'] = round(valid_duration.max(), 2)
        else:
            metrics['porsche']['avg_duration'] = 0
            metrics['porsche']['total_duration'] = 0
            metrics['porsche']['max_duration'] = 0
    else:
        metrics['porsche']['avg_duration'] = 0
        metrics['porsche']['total_duration'] = 0
        metrics['porsche']['max_duration'] = 0

    print(f"  发现页面访问: {metrics['discovery']['total_views']} 次")
    print(f"  发现页面平均时长: {metrics['discovery']['avg_duration']} 秒")
    print(f"  Porsche+页面访问: {metrics['porsche']['total_views']} 次")
    print(f"  Porsche+页面平均时长: {metrics['porsche']['avg_duration']} 秒")

    return metrics

def analyze_user_behavior(df):
    """分析用户行为模式"""
    print("\n[3] 分析用户行为模式...")

    behavior = {}

    # 用户活跃度分布
    user_events = df.groupby('reduser_id').size()
    behavior['user_activity_distribution'] = {
        'high_activity_users': int((user_events > user_events.mean() + user_events.std()).sum()),
        'medium_activity_users': int((user_events.between(user_events.mean(), user_events.mean() + user_events.std())).sum()),
        'low_activity_users': int((user_events < user_events.mean()).sum())
    }

    # 用户使用天数分布
    user_days = df.groupby('reduser_id')['date'].nunique()
    behavior['user_days_distribution'] = {
        'heavy_users': int((user_days >= 10).sum()),
        'regular_users': int((user_days.between(5, 9)).sum()),
        'light_users': int((user_days < 5).sum())
    }

    # 时段分布
    hour_dist = df.groupby('hour').size()
    behavior['hour_distribution'] = {str(h): int(c) for h, c in hour_dist.items()}

    # 高峰时段识别
    peak_hours = hour_dist.nlargest(5).index.tolist()
    behavior['peak_hours'] = peak_hours

    # 星期分布
    weekday_dist = df.groupby('weekday').size()
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    behavior['weekday_distribution'] = {weekday_names[i]: int(weekday_dist.get(i, 0)) for i in range(7)}

    print(f"  高活跃用户: {behavior['user_activity_distribution']['high_activity_users']}")
    print(f"  重度用户(>=10天): {behavior['user_days_distribution']['heavy_users']}")
    print(f"  高峰时段: {peak_hours}")

    return behavior

def analyze_content_interaction(df):
    """分析内容互动行为"""
    print("\n[4] 分析内容互动行为...")

    content = {}

    # 笔记卡片曝光与点击
    card_show = df[df['span_name'].str.contains('post_card_cardshow', case=False, na=False)]
    card_click = df[df['span_name'].str.contains('post_card_click', case=False, na=False)]

    content['post_card'] = {
        'total_shows': len(card_show),
        'total_clicks': len(card_click),
        'click_rate': round(len(card_click) / len(card_show) * 100, 2) if len(card_show) > 0 else 0
    }

    # 点赞行为
    like_events = df[df['span_name'].str.contains('like_click', case=False, na=False)]
    content['likes'] = {
        'total': len(like_events),
        'unique_users': like_events['reduser_id'].nunique() if len(like_events) > 0 else 0
    }

    # 收藏行为
    save_events = df[df['span_name'].str.contains('save', case=False, na=False)]
    content['saves'] = {
        'total': len(save_events),
        'unique_users': save_events['reduser_id'].nunique() if len(save_events) > 0 else 0
    }

    # 关注行为
    follow_events = df[df['span_name'].str.contains('follow', case=False, na=False)]
    content['follows'] = {
        'total': len(follow_events),
        'unique_users': follow_events['reduser_id'].nunique() if len(follow_events) > 0 else 0
    }

    # 视频播放
    video_events = df[df['span_name'].str.contains('video', case=False, na=False)]
    content['video'] = {
        'total': len(video_events),
        'unique_users': video_events['reduser_id'].nunique() if len(video_events) > 0 else 0
    }

    print(f"  笔记卡片点击率: {content['post_card']['click_rate']}%")
    print(f"  点赞总数: {content['likes']['total']}")
    print(f"  收藏总数: {content['saves']['total']}")

    return content

def analyze_poi_behavior(df):
    """分析POI相关行为"""
    print("\n[5] 分析POI行为...")

    poi = {}

    # POI相关事件
    poi_events = df[df['span_name'].str.contains('poi', case=False, na=False)]
    poi['total_events'] = len(poi_events)

    # POI卡片曝光
    poi_card_show = df[df['span_name'].str.contains('poi_card', case=False, na=False)]
    poi['card_shows'] = len(poi_card_show)

    # POI导航点击
    poi_nav = df[df['span_name'].str.contains('navigation_button', case=False, na=False)]
    poi['navigation_clicks'] = len(poi_nav)
    poi['navigation_users'] = poi_nav['reduser_id'].nunique() if len(poi_nav) > 0 else 0

    # POI类型分布
    if 'rednote_poi_type' in df.columns:
        poi_types = poi_events['rednote_poi_type'].value_counts().head(10)
        poi['type_distribution'] = {str(k): int(v) for k, v in poi_types.items() if pd.notna(k)}
    else:
        poi['type_distribution'] = {}

    # 地图全屏使用
    if 'rednote_poi_map_fullscreen' in df.columns:
        fullscreen = df[df['rednote_poi_map_fullscreen'] == 1]
        poi['fullscreen_usage'] = len(fullscreen)
    else:
        poi['fullscreen_usage'] = 0

    print(f"  POI相关事件: {poi['total_events']}")
    print(f"  POI导航点击: {poi['navigation_clicks']}")
    print(f"  导航用户数: {poi['navigation_users']}")

    return poi

def analyze_ai_guide(df):
    """分析AI路书功能"""
    print("\n[6] 分析AI路书功能...")

    ai = {}

    # AI路书生成
    ai_click = df[df['span_name'].str.contains('ai_travel_guide', case=False, na=False)]
    ai['generation'] = {
        'total_clicks': len(ai_click),
        'unique_users': ai_click['reduser_id'].nunique() if len(ai_click) > 0 else 0
    }

    # 计算AI路书活跃率
    total_active_users = df['reduser_id'].nunique()
    if total_active_users > 0 and ai['generation']['unique_users'] > 0:
        ai['generation']['active_rate'] = round(ai['generation']['unique_users'] / total_active_users * 100, 2)
        ai['generation']['avg_usage'] = round(ai['generation']['total_clicks'] / ai['generation']['unique_users'], 2)
    else:
        ai['generation']['active_rate'] = 0
        ai['generation']['avg_usage'] = 0

    # 分享功能
    share_events = df[df['span_name'].str.contains('share', case=False, na=False)]
    ai['share'] = {
        'total': len(share_events),
        'unique_users': share_events['reduser_id'].nunique() if len(share_events) > 0 else 0
    }

    print(f"  AI路书点击: {ai['generation']['total_clicks']}")
    print(f"  AI路书活跃率: {ai['generation']['active_rate']}%")
    print(f"  分享功能使用: {ai['share']['total']}")

    return ai

def analyze_search_behavior(df):
    """分析搜索行为"""
    print("\n[7] 分析搜索行为...")

    search = {}

    # 搜索相关事件
    search_events = df[df['span_name'].str.contains('search', case=False, na=False)]
    search['total_events'] = len(search_events)
    search['unique_users'] = search_events['reduser_id'].nunique() if len(search_events) > 0 else 0

    # 搜索首页展示
    search_homepage = df[df['span_name'] == 'search_homepage_pageshow']
    search['homepage_views'] = len(search_homepage)

    # 搜索唤起
    search_trigger = df[df['span_name'].str.contains('triggering_search', case=False, na=False)]
    search['trigger_count'] = len(search_trigger)

    print(f"  搜索事件总数: {search['total_events']}")
    print(f"  搜索用户数: {search['unique_users']}")

    return search

def analyze_event_distribution(df):
    """分析事件类型分布"""
    print("\n[8] 分析事件分布...")

    events = {}

    # 事件频率分布
    event_counts = df['span_name'].value_counts()
    events['top_events'] = {str(k): int(v) for k, v in event_counts.head(20).items()}
    events['total_types'] = len(event_counts)

    # 按类别分组
    categories = {
        'page_view': event_counts[event_counts.index.str.contains('pageshow', case=False, na=False)].sum(),
        'click': event_counts[event_counts.index.str.contains('click', case=False, na=False)].sum(),
        'card_show': event_counts[event_counts.index.str.contains('cardshow', case=False, na=False)].sum(),
        'navigation': event_counts[event_counts.index.str.contains('navigation', case=False, na=False)].sum(),
        'search': event_counts[event_counts.index.str.contains('search', case=False, na=False)].sum(),
        'like': event_counts[event_counts.index.str.contains('like', case=False, na=False)].sum(),
        'save': event_counts[event_counts.index.str.contains('save', case=False, na=False)].sum(),
        'share': event_counts[event_counts.index.str.contains('share', case=False, na=False)].sum()
    }
    events['category_distribution'] = categories

    print(f"  事件类型总数: {events['total_types']}")
    print(f"  页面曝光事件: {categories['page_view']}")
    print(f"  点击事件: {categories['click']}")

    return events

def generate_daily_metrics(df):
    """生成每日指标"""
    print("\n[9] 生成每日指标...")

    daily = {}

    for date in df['date'].unique():
        date_str = str(date)
        day_df = df[df['date'] == date]

        daily[date_str] = {
            'total_events': len(day_df),
            'active_users': day_df['reduser_id'].nunique(),
            'active_devices': day_df['device_id'].nunique(),
            'event_types': day_df['span_name'].nunique()
        }

    print(f"  生成 {len(daily)} 天的每日指标")

    return daily

def generate_user_profiles(df):
    """生成用户画像"""
    print("\n[10] 生成用户画像...")

    profiles = {}

    for user_id in df['reduser_id'].unique():
        if pd.isna(user_id):
            continue

        user_df = df[df['reduser_id'] == user_id]

        # 基础统计
        profile = {
            'total_events': len(user_df),
            'active_days': user_df['date'].nunique(),
            'first_seen': str(user_df['timestamp'].min()),
            'last_seen': str(user_df['timestamp'].max()),
            'device_count': user_df['device_id'].nunique()
        }

        # 主要行为
        top_events = user_df['span_name'].value_counts().head(5)
        profile['top_events'] = {str(k): int(v) for k, v in top_events.items()}

        # 活跃时段
        peak_hours = user_df['hour'].value_counts().head(3).index.tolist()
        profile['peak_hours'] = peak_hours

        profiles[str(user_id)] = profile

    # 保存为单独文件
    profile_path = os.path.join(OUTPUT_DIR, 'user_profiles.json')
    with open(profile_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(profiles), f, ensure_ascii=False, indent=2)

    print(f"  生成 {len(profiles)} 个用户画像")
    print(f"  保存到: {profile_path}")

    return profiles

def generate_report(all_data):
    """生成综合报告"""
    print("\n[11] 生成综合报告...")

    report = {
        'meta': {
            'data_source': DATA_PATH,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_period': {
                'start': str(all_data['df']['timestamp'].min()),
                'end': str(all_data['df']['timestamp'].max()),
                'days': all_data['df']['date'].nunique()
            }
        },
        'overview': all_data['kpis'],
        'page_metrics': all_data['page_metrics'],
        'user_behavior': all_data['user_behavior'],
        'content_interaction': all_data['content'],
        'poi_behavior': all_data['poi'],
        'ai_guide': all_data['ai'],
        'search_behavior': all_data['search'],
        'event_distribution': all_data['events'],
        'daily_metrics': all_data['daily']
    }

    return report

def main():
    """主函数"""
    ensure_dir(OUTPUT_DIR)

    # 加载数据
    df = load_and_prepare()

    # 执行各项分析
    all_data = {
        'df': df,
        'kpis': calculate_basic_kpis(df),
        'page_metrics': calculate_page_metrics(df),
        'user_behavior': analyze_user_behavior(df),
        'content': analyze_content_interaction(df),
        'poi': analyze_poi_behavior(df),
        'ai': analyze_ai_guide(df),
        'search': analyze_search_behavior(df),
        'events': analyze_event_distribution(df),
        'daily': generate_daily_metrics(df)
    }

    # 生成用户画像
    all_data['user_profiles'] = generate_user_profiles(df)

    # 生成综合报告
    report = generate_report(all_data)

    # 保存JSON报告
    json_path = os.path.join(OUTPUT_DIR, 'deep_insights.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(to_serializable(report), f, ensure_ascii=False, indent=2)
    print(f"\n[保存] JSON报告: {json_path}")

    # 打印摘要
    print("\n" + "=" * 70)
    print("分析完成！")
    print("=" * 70)
    print(f"\n核心指标摘要:")
    print(f"  数据周期: {report['meta']['data_period']['days']} 天")
    print(f"  总事件数: {report['overview']['total_events']:,}")
    print(f"  总用户数: {report['overview']['total_users']}")
    print(f"  日均活跃: {report['overview']['avg_dau']}")
    print(f"  人均事件: {report['overview']['avg_events_per_user']}")

    return report

if __name__ == "__main__":
    main()