# -*- coding: utf-8 -*-
"""
AI 路书功能专项分析报告
四维度分析：触达(Reach) · 使用(Usage) · 留存(Retention) · 分享(Share)
"""
import pandas as pd
import numpy as np
import json
import os
import sys
import io
from datetime import datetime, timedelta
from scipy import stats

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'rednote', 'rednote data_20260319-20260330.xlsx')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'report', 'fulldata')

AI_EVENTS = {
    'button_shown': 'ai_travel_guide_button_show',
    'button_clicked': 'ai_travel_guide_button_click',
    'guide_generated': 'generated_travel_guide_button_show',
    'guide_confirmed': 'generated_travel_guide_button_click',
    'guide_detail_viewed': 'trival_guide_page_pageshow',
    'guide_shared': 'trival_guide_page_share_icon_click',
}


def wilson_ci(p, n, z=1.96):
    if n == 0:
        return {'lower': 0, 'upper': 0, 'note': '无样本'}
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return {
        'lower': round(max(0, center - spread) * 100, 2),
        'upper': round(min(1, center + spread) * 100, 2),
        'note': '样本充足' if n >= 30 else '⚠️ 样本不足(<30)，结果仅供参考'
    }


def load_data():
    print("=" * 80)
    print("AI 路书功能专项分析")
    print("=" * 80)
    print(f"\n正在加载数据: {DATA_FILE}")
    df = pd.read_excel(DATA_FILE)
    print(f"数据加载完成: {len(df):,} 行, {len(df.columns)} 列")

    if 'strt_time_nano' in df.columns:
        df['strt_time_dt'] = pd.to_datetime(df['strt_time_nano'], errors='coerce')
    if 'end_time_nano' in df.columns:
        df['end_time_dt'] = pd.to_datetime(df['end_time_nano'], errors='coerce')

    user_col = 'reduser_id' if 'reduser_id' in df.columns else 'user_id'
    print(f"用户标识列: {user_col}")
    print(f"总用户数: {df[user_col].nunique()}")
    print(f"时间范围: {df['strt_time_dt'].min()} ~ {df['strt_time_dt'].max()}")
    return df, user_col


def analyze_reach(df, user_col):
    print("\n" + "=" * 60)
    print("【维度一】触达分析 (Reach)")
    print("=" * 60)

    total_users = df[user_col].nunique()

    shown_events = df[df['span_nm'].str.contains(AI_EVENTS['button_shown'], na=False, regex=False)]
    shown_users = shown_events[user_col].nunique()
    shown_count = len(shown_events)

    reach_rate = round(shown_users / total_users * 100, 2) if total_users > 0 else 0
    reach_ci = wilson_ci(shown_users / total_users, total_users)

    shown_events['hour'] = shown_events['strt_time_dt'].dt.hour
    hourly_reach = shown_events.groupby('hour').size().to_dict()

    shown_events['date'] = shown_events['strt_time_dt'].dt.date
    daily_reach = {}
    for d, g in shown_events.groupby('date'):
        daily_reach[str(d)] = {'events': len(g), 'users': g[user_col].nunique()}

    referer_col = 'referer_page' if 'referer_page' in df.columns else None
    page_col = 'page_root' if 'page_root' in df.columns else None

    reach_sources = {}
    if page_col:
        source_pages = shown_events[page_col].value_counts().head(10).to_dict()
        reach_sources = {str(k): int(v) for k, v in source_pages.items()}

    if referer_col:
        referer_pages = shown_events[referer_col].dropna().value_counts().head(10).to_dict()
        reach_sources['referer_breakdown'] = {str(k): int(v) for k, v in referer_pages.items()}

    avg_shown_per_user = round(shown_count / shown_users, 2) if shown_users > 0 else 0

    result = {
        'total_users': int(total_users),
        'exposure_events': int(shown_count),
        'exposure_users': int(shown_users),
        'exposure_rate_pct': reach_rate,
        'exposure_ci_95': reach_ci,
        'avg_exposures_per_user': avg_shown_per_user,
        'hourly_distribution': {str(k): int(v) for k, v in hourly_reach.items()},
        'daily_distribution': daily_reach,
        'reach_sources': reach_sources,
    }

    print(f"  总用户数: {total_users:,}")
    print(f"  按钮曝光次数: {shown_count:,}")
    print(f"  曝光用户数: {shown_users:,}")
    print(f"  曝光率: {reach_rate}%")
    print(f"  95%置信区间: [{reach_ci['lower']}%, {reach_ci['upper']}%]")
    print(f"  人均曝光次数: {avg_shown_per_user}")
    print(f"  曝光来源页面: {reach_sources}")

    return result


def analyze_usage(df, user_col):
    print("\n" + "=" * 60)
    print("【维度二】使用分析 (Usage)")
    print("=" * 60)

    total_users = df[user_col].nunique()

    funnel_steps = ['button_shown', 'button_clicked', 'guide_generated', 'guide_confirmed', 'guide_detail_viewed', 'guide_shared']
    funnel_data = {}
    for step in funnel_steps:
        pattern = AI_EVENTS[step]
        events = df[df['span_nm'].str.contains(pattern, na=False, regex=False)]
        funnel_data[step] = {
            'event_name': pattern,
            'events': int(len(events)),
            'users': int(events[user_col].nunique()),
        }

    prev_users = None
    for step in funnel_steps:
        curr_users = funnel_data[step]['users']
        curr_events = funnel_data[step]['events']
        if prev_users is not None and prev_users > 0:
            funnel_data[step]['user_conversion_rate'] = round(curr_users / prev_users * 100, 2)
            funnel_data[step]['event_conversion_rate'] = round(curr_events / funnel_data[funnel_steps[funnel_steps.index(step) - 1]]['events'] * 100, 2) if funnel_data[funnel_steps[funnel_steps.index(step) - 1]]['events'] > 0 else 0
        else:
            funnel_data[step]['user_conversion_rate'] = None
            funnel_data[step]['event_conversion_rate'] = None
        funnel_data[step]['penetration_rate'] = round(curr_users / total_users * 100, 2)
        prev_users = curr_users

    click_events = df[df['span_nm'].str.contains(AI_EVENTS['button_clicked'], na=False, regex=False)]
    click_users = click_events[user_col].unique()

    user_usage_depth = {}
    for uid in click_users:
        user_all = df[df[user_col] == uid]
        ai_events_count = 0
        for step in funnel_steps:
            pattern = AI_EVENTS[step]
            ai_events_count += user_all['span_nm'].str.contains(pattern, na=False, regex=False).sum()
        user_usage_depth[uid] = int(ai_events_count)

    depth_values = list(user_usage_depth.values())
    depth_stats = {
        'mean': round(np.mean(depth_values), 2) if depth_values else 0,
        'median': round(np.median(depth_values), 2) if depth_values else 0,
        'p25': round(np.percentile(depth_values, 25), 2) if depth_values else 0,
        'p75': round(np.percentile(depth_values, 75), 2) if depth_values else 0,
        'max': int(max(depth_values)) if depth_values else 0,
        'min': int(min(depth_values)) if depth_values else 0,
    }

    depth_distribution = {}
    for v in depth_values:
        bucket = '1-5' if v <= 5 else '6-10' if v <= 10 else '11-20' if v <= 20 else '21-50' if v <= 50 else '50+'
        depth_distribution[bucket] = depth_distribution.get(bucket, 0) + 1

    click_user_daily = {}
    for uid in click_users:
        user_clicks = click_events[click_events[user_col] == uid]
        user_clicks = user_clicks.copy()
        user_clicks['date'] = user_clicks['strt_time_dt'].dt.date
        usage_days = user_clicks['date'].nunique()
        click_user_daily[uid] = usage_days

    repeat_users = sum(1 for v in click_user_daily.values() if v >= 2)
    single_users = sum(1 for v in click_user_daily.values() if v == 1)
    repeat_rate = round(repeat_users / len(click_users) * 100, 2) if len(click_users) > 0 else 0

    click_events_copy = click_events.copy()
    click_events_copy['hour'] = click_events_copy['strt_time_dt'].dt.hour
    hourly_usage = click_events_copy.groupby('hour').size().to_dict()

    click_events_copy['dow'] = click_events_copy['strt_time_dt'].dt.dayofweek
    dow_usage = click_events_copy.groupby('dow').size().to_dict()
    dow_labels = {0: '周一', 1: '周二', 2: '周三', 3: '周四', 4: '周五', 5: '周六', 6: '周日'}
    dow_usage_named = {dow_labels.get(k, str(k)): int(v) for k, v in dow_usage.items()}

    result = {
        'funnel': funnel_data,
        'usage_depth_stats': depth_stats,
        'usage_depth_distribution': depth_distribution,
        'total_click_users': int(len(click_users)),
        'repeat_users': int(repeat_users),
        'single_use_users': int(single_users),
        'repeat_rate_pct': repeat_rate,
        'hourly_usage': {str(k): int(v) for k, v in hourly_usage.items()},
        'dow_usage': dow_usage_named,
    }

    print(f"  使用漏斗:")
    for step in funnel_steps:
        d = funnel_data[step]
        conv = f" → 用户转化: {d['user_conversion_rate']}%" if d['user_conversion_rate'] is not None else ""
        print(f"    {step}: {d['events']}次 / {d['users']}人 (渗透率: {d['penetration_rate']}%){conv}")

    print(f"\n  使用深度统计:")
    print(f"    人均AI事件数: {depth_stats['mean']}")
    print(f"    中位数: {depth_stats['median']}")
    print(f"    P25/P75: {depth_stats['p25']} / {depth_stats['p75']}")
    print(f"    深度分布: {depth_distribution}")

    print(f"\n  重复使用:")
    print(f"    重复使用用户: {repeat_users} / {len(click_users)} ({repeat_rate}%)")
    print(f"    单次使用用户: {single_users}")

    return result


def analyze_retention(df, user_col):
    print("\n" + "=" * 60)
    print("【维度三】留存分析 (Retention)")
    print("=" * 60)

    click_events = df[df['span_nm'].str.contains(AI_EVENTS['button_clicked'], na=False, regex=False)].copy()
    click_events['date'] = click_events['strt_time_dt'].dt.date
    ai_users = click_events[user_col].unique()

    if len(ai_users) == 0:
        print("  ⚠️ 无AI路书点击用户，无法计算留存")
        return {
            'ai_users_count': 0,
            'note': '无AI路书点击用户',
            'feature_retention': {},
            'app_retention': {},
            'retention_user_profiles': {}
        }

    if 'date' not in df.columns:
        df = df.copy()
        df['date'] = df['strt_time_dt'].dt.date

    ai_user_first_date = {}
    for uid in ai_users:
        user_clicks = click_events[click_events[user_col] == uid]
        first_date = user_clicks['date'].min()
        ai_user_first_date[uid] = first_date

    feature_retention = {}
    for day_offset in [1, 3, 7]:
        retained = 0
        eligible = 0
        for uid, first_date in ai_user_first_date.items():
            target_date = first_date + timedelta(days=day_offset)
            max_data_date = df['date'].max()
            if target_date <= max_data_date:
                eligible += 1
                user_events_on_target = click_events[
                    (click_events[user_col] == uid) &
                    (click_events['date'] == target_date)
                ]
                if len(user_events_on_target) > 0:
                    retained += 1

        rate = round(retained / eligible * 100, 2) if eligible > 0 else 0
        ci = wilson_ci(retained / eligible, eligible) if eligible > 0 else {'lower': 0, 'upper': 0, 'note': '无样本'}
        feature_retention[f'{day_offset}day'] = {
            'retained': retained,
            'eligible': eligible,
            'rate_pct': rate,
            'ci_95': ci
        }
        print(f"  功能级 {day_offset}日留存: {retained}/{eligible} = {rate}%  CI: [{ci['lower']}%, {ci['upper']}%]")

    app_retention = {}
    for day_offset in [1, 3, 7]:
        retained = 0
        eligible = 0
        for uid, first_date in ai_user_first_date.items():
            target_date = first_date + timedelta(days=day_offset)
            max_data_date = df['date'].max()
            if target_date <= max_data_date:
                eligible += 1
                user_events_on_target = df[
                    (df[user_col] == uid) &
                    (df['date'] == target_date)
                ]
                if len(user_events_on_target) > 0:
                    retained += 1

        rate = round(retained / eligible * 100, 2) if eligible > 0 else 0
        ci = wilson_ci(retained / eligible, eligible) if eligible > 0 else {'lower': 0, 'upper': 0, 'note': '无样本'}
        app_retention[f'{day_offset}day'] = {
            'retained': retained,
            'eligible': eligible,
            'rate_pct': rate,
            'ci_95': ci
        }
        print(f"  APP级 {day_offset}日留存: {retained}/{eligible} = {rate}%  CI: [{ci['lower']}%, {ci['upper']}%]")

    retained_1d_users = []
    churned_1d_users = []
    for uid, first_date in ai_user_first_date.items():
        target_date = first_date + timedelta(days=1)
        max_data_date = df['date'].max()
        if target_date <= max_data_date:
            user_next_day = df[(df[user_col] == uid) & (df['date'] == target_date)]
            if len(user_next_day) > 0:
                retained_1d_users.append(uid)
            else:
                churned_1d_users.append(uid)

    retention_profiles = {}
    for label, uids in [('retained', retained_1d_users), ('churned', churned_1d_users)]:
        if not uids:
            retention_profiles[label] = {'count': 0, 'avg_events': 0, 'top_pages': {}}
            continue
        user_data = df[df[user_col].isin(uids)]
        avg_events = round(user_data.groupby(user_col).size().mean(), 2)
        page_col = 'page_root' if 'page_root' in df.columns else None
        top_pages = {}
        if page_col:
            top_pages = user_data[page_col].value_counts().head(5).to_dict()
            top_pages = {str(k): int(v) for k, v in top_pages.items()}
        retention_profiles[label] = {
            'count': len(uids),
            'avg_total_events': avg_events,
            'top_pages': top_pages
        }

    result = {
        'ai_users_count': int(len(ai_users)),
        'feature_retention': feature_retention,
        'app_retention': app_retention,
        'retention_user_profiles': retention_profiles,
    }

    print(f"\n  留存用户画像对比:")
    for label, profile in retention_profiles.items():
        print(f"    {label}: {profile['count']}人, 人均事件{profile['avg_total_events']}, 热门页面{profile.get('top_pages', {})}")

    return result


def analyze_share(df, user_col):
    print("\n" + "=" * 60)
    print("【维度四】分享分析 (Share)")
    print("=" * 60)

    detail_events = df[df['span_nm'].str.contains(AI_EVENTS['guide_detail_viewed'], na=False, regex=False)]
    share_events = df[df['span_nm'].str.contains(AI_EVENTS['guide_shared'], na=False, regex=False)]

    detail_users = detail_events[user_col].nunique()
    share_users = share_events[user_col].nunique()
    detail_count = len(detail_events)
    share_count = len(share_events)

    share_trigger_rate = round(share_users / detail_users * 100, 2) if detail_users > 0 else 0
    share_ci = wilson_ci(share_users / detail_users, detail_users) if detail_users > 0 else {'lower': 0, 'upper': 0, 'note': '无样本'}

    share_per_user = round(share_count / share_users, 2) if share_users > 0 else 0

    share_events_copy = share_events.copy()
    share_events_copy['hour'] = share_events_copy['strt_time_dt'].dt.hour
    hourly_share = share_events_copy.groupby('hour').size().to_dict()

    share_user_ids = share_events[user_col].unique()
    share_profiles = {}
    if len(share_user_ids) > 0:
        share_user_data = df[df[user_col].isin(share_user_ids)]
        avg_events = round(share_user_data.groupby(user_col).size().mean(), 2)
        page_col = 'page_root' if 'page_root' in df.columns else None
        top_pages = {}
        if page_col:
            top_pages = share_user_data[page_col].value_counts().head(5).to_dict()
            top_pages = {str(k): int(v) for k, v in top_pages.items()}

        share_user_ai_events = 0
        for step in AI_EVENTS.values():
            share_user_ai_events += share_user_data['span_nm'].str.contains(step, na=False, regex=False).sum()
        avg_ai_depth = round(share_user_ai_events / len(share_user_ids), 2)

        share_profiles = {
            'count': int(len(share_user_ids)),
            'avg_total_events': avg_events,
            'avg_ai_depth': avg_ai_depth,
            'top_pages': top_pages,
        }

    result = {
        'detail_view_users': int(detail_users),
        'detail_view_events': int(detail_count),
        'share_users': int(share_users),
        'share_events': int(share_count),
        'share_trigger_rate_pct': share_trigger_rate,
        'share_ci_95': share_ci,
        'share_per_user': share_per_user,
        'hourly_distribution': {str(k): int(v) for k, v in hourly_share.items()},
        'share_user_profiles': share_profiles,
    }

    print(f"  详情浏览用户: {detail_users}")
    print(f"  分享用户: {share_users}")
    print(f"  分享触发率: {share_trigger_rate}%  CI: [{share_ci['lower']}%, {share_ci['upper']}%]")
    print(f"  人均分享次数: {share_per_user}")
    print(f"  分享用户画像: {share_profiles}")

    return result


def generate_health_score(reach, usage, retention, share):
    print("\n" + "=" * 60)
    print("【综合评估】功能健康度")
    print("=" * 60)

    reach_score = min(100, reach['exposure_rate_pct'] * 2)

    click_rate = 0
    if usage['funnel']['button_shown']['users'] > 0:
        click_rate = usage['funnel']['button_clicked']['users'] / usage['funnel']['button_shown']['users'] * 100
    usage_score = min(100, click_rate * 1.5 + usage['repeat_rate_pct'] * 0.5)

    ret_1d = retention['feature_retention'].get('1day', {}).get('rate_pct', 0)
    retention_score = min(100, ret_1d * 2)

    share_score = min(100, share['share_trigger_rate_pct'] * 5)

    overall = round((reach_score * 0.25 + usage_score * 0.35 + retention_score * 0.25 + share_score * 0.15), 1)

    bottlenecks = []
    if reach['exposure_rate_pct'] < 30:
        bottlenecks.append({'dimension': '触达', 'issue': f"曝光率仅{reach['exposure_rate_pct']}%，大量用户未触达AI路书入口", 'priority': '高'})
    if click_rate < 40:
        bottlenecks.append({'dimension': '使用', 'issue': f"点击转化率{round(click_rate, 1)}%，入口吸引力不足", 'priority': '高'})
    if ret_1d < 20:
        bottlenecks.append({'dimension': '留存', 'issue': f"次日功能留存{ret_1d}%，用户缺乏回访动力", 'priority': '高'})
    if share['share_trigger_rate_pct'] < 10:
        bottlenecks.append({'dimension': '分享', 'issue': f"分享触发率{share['share_trigger_rate_pct']}%，社交传播链断裂", 'priority': '中'})

    suggestions = []
    if reach['exposure_rate_pct'] < 50:
        suggestions.append("增加AI路书入口曝光：在发现页、POI详情页增加入口卡片")
    if click_rate < 50:
        suggestions.append("优化入口设计：使用更吸引人的文案和视觉引导")
    if ret_1d < 30:
        suggestions.append("增强回访动力：添加路书更新提醒、个性化推荐")
    if share['share_trigger_rate_pct'] < 15:
        suggestions.append("激励分享机制：添加分享奖励、社交裂变功能")

    result = {
        'scores': {
            'reach': round(reach_score, 1),
            'usage': round(usage_score, 1),
            'retention': round(retention_score, 1),
            'share': round(share_score, 1),
            'overall': overall,
        },
        'bottlenecks': bottlenecks,
        'suggestions': suggestions,
    }

    print(f"  健康度评分:")
    print(f"    触达: {reach_score:.1f}/100")
    print(f"    使用: {usage_score:.1f}/100")
    print(f"    留存: {retention_score:.1f}/100")
    print(f"    分享: {share_score:.1f}/100")
    print(f"    综合: {overall}/100")
    print(f"\n  关键瓶颈:")
    for b in bottlenecks:
        print(f"    [{b['priority']}] {b['dimension']}: {b['issue']}")
    print(f"\n  优化建议:")
    for s in suggestions:
        print(f"    → {s}")

    return result


def main():
    df, user_col = load_data()

    reach = analyze_reach(df, user_col)
    usage = analyze_usage(df, user_col)
    retention = analyze_retention(df, user_col)
    share = analyze_share(df, user_col)
    health = generate_health_score(reach, usage, retention, share)

    report = {
        'report_meta': {
            'title': 'AI 路书功能专项分析报告',
            'subtitle': '触达 · 使用 · 留存 · 分享 四维度深度分析',
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': os.path.basename(DATA_FILE),
            'data_period': f"{df['strt_time_dt'].min().strftime('%Y-%m-%d')} ~ {df['strt_time_dt'].max().strftime('%Y-%m-%d')}",
            'total_users': int(df[user_col].nunique()),
            'total_events': int(len(df)),
            'analysis_dimensions': ['reach', 'usage', 'retention', 'share'],
        },
        'reach': reach,
        'usage': usage,
        'retention': retention,
        'share': share,
        'health_score': health,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, 'ai_guide_feature_report.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 报告已保存: {output_path}")

    return report


if __name__ == '__main__':
    main()
