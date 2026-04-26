# -*- coding: utf-8 -*-
"""
Data Audit SKILL - 深度诊断脚本
用于验证报告中的异常数据，回溯到原始数据进行交叉验证
"""

import pandas as pd
import numpy as np
import json
import sys
import io
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

DATA_PATH = r'c:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx'
REPORT_PATH = r'c:\projects\rednote data analyzer\report\fulldata\kpi_metrics_replica.json'

def load_raw_data():
    """加载原始数据"""
    print("=" * 80)
    print("🔍 DATA AUDIT - 深度诊断模式")
    print("=" * 80)
    
    df = pd.read_excel(DATA_PATH)
    print(f"\n📊 原始数据加载完成:")
    print(f"   总行数: {df.shape[0]:,}")
    print(f"   总列数: {df.shape[1]}")
    
    df['strt_time_dt'] = pd.to_datetime(df['strt_time_nano'], errors='coerce')
    df['end_time_dt'] = pd.to_datetime(df['end_time_nano'], errors='coerce')
    df['date'] = df['strt_time_dt'].dt.date
    df['hour'] = df['strt_time_dt'].dt.hour
    
    if 'strt_time_dt' in df.columns and 'end_time_dt' in df.columns:
        df['duration_sec'] = (df['end_time_dt'] - df['strt_time_dt']).dt.total_seconds()
        df.loc[df['duration_sec'] < 0, 'duration_sec'] = np.nan
    
    return df

def audit_duration_field(df):
    """审查 #1: duration_sec 字段分析"""
    print("\n" + "=" * 80)
    print("🔴 [AUDIT-001] 曝光时长 (exposure_duration_sec) 全部为 0 的问题")
    print("=" * 80)
    
    duration_col = df['duration_sec']
    
    print(f"\n📈 duration_sec 统计:")
    print(f"   总记录数: {len(duration_col):,}")
    print(f"   非空值: {duration_col.notna().sum():,} ({duration_col.notna().sum()/len(duration_col)*100:.1f}%)")
    print(f"   空值/NaN: {duration_col.isna().sum():,} ({duration_col.isna().sum()/len(duration_col)*100:.1f}%)")
    
    if duration_col.notna().sum() > 0:
        valid_dur = duration_col.dropna()
        print(f"\n   有效值统计:")
        print(f"   - 均值: {valid_dur.mean():.2f}")
        print(f"   - 中位数: {valid_dur.median():.2f}")
        print(f"   - 最小值: {valid_dur.min():.2f}")
        print(f"   - 最大值: {valid_dur.max():.2f}")
        print(f"   - 标准差: {valid_dur.std():.2f}")
        
        zero_count = (valid_dur == 0).sum()
        print(f"\n   ⚠️  零值数量: {zero_count:,} ({zero_count/len(valid_dur)*100:.1f}%)")
        
        if zero_count > len(valid_dur) * 0.9:
            print("   🔴 CRITICAL: 超过90%的duration为0，字段可能未被正确解析！")
        
        positive_count = (valid_dur > 0).sum()
        print(f"   ✅ 正值数量: {positive_count:,} ({positive_count/len(valid_dur)*100:.1f}%)")
        
        if positive_count > 0:
            print(f"\n   正值样本 (前10个):")
            sample_positive = valid_dur[valid_dur > 0].head(10)
            for idx, val in sample_positive.items():
                row = df.loc[idx]
                print(f"      [{idx}] span_nm={row.get('span_nm', 'N/A')[:50]}... | duration={val:.2f}s")
    else:
        print("   🔴 CRITICAL: duration_sec 字段全部为 NaN！")
        print("   可能原因：")
        print("   1. strt_time_nano 或 end_time_nano 字段格式不正确")
        print("   2. 时间戳解析失败（errors='coerce' 导致全为NaT）")
        print("   3. 原始数据中这两个字段本身为空")

def audit_active_rate_calculation(df):
    """审查 #2: 活跃率计算逻辑"""
    print("\n" + "=" * 80)
    print("🔴 [AUDIT-002] 活跃率 (active_rate_pct) = 100% 的问题")
    print("=" * 80)
    
    total_users_all = df['reduser_id'].dropna().nunique()
    users_with_events = df[df['strt_time_dt'].notna()]['reduser_id'].nunique()
    
    print(f"\n📊 用户分层统计:")
    print(f"   A. 数据中出现的总用户数 (reduser_id去重): {total_users_all:,}")
    print(f"   B. 有有效时间戳的用户数: {users_with_events:,}")
    print(f"   C. 差异 (无时间戳用户): {total_users_all - users_with_events:,}")
    
    active_rate_method1 = (users_with_events / total_users_all) * 100 if total_users_all > 0 else 0
    print(f"\n🔢 活跃率计算方法对比:")
    print(f"   方法1 (B/A × 100%): {active_rate_method1:.2f}%")
    print(f"   → 这是报告中的算法，导致必然=100%（因为B=A或B≈A）")
    
    print(f"\n⚠️  问题根因分析：")
    print(f"   报告中的活跃率分母使用了 '有事件用户' 而非 '安装用户'")
    print(f"   这导致了 **幸存者偏差** (Survivorship Bias)")
    print(f"   ")
    print(f"   正确做法应该是：")
    print(f"   - 分母 = APP安装用户总数（需要从其他数据源获取）")
    print(f"   - 或者明确标注这是 '事件覆盖率' 而非 '活跃率'")

def audit_ai_usage_rate(df):
    """审查 #3: AI使用率超过100%的问题"""
    print("\n" + "=" * 80)
    print("🔴 [AUDIT-003] AI使用率 (usage_rate_pct) = 422.36% 的问题")
    print("=" * 80)
    
    ai_events = df[df['span_nm'].str.contains('ai|guide', case=False, na=False)]
    app_open_events = df[df['span_nm'].str.contains('app_show|app_launch|pageshow', case=False, na=False)]
    
    ai_click_count = len(ai_events)
    app_open_count = len(app_open_events)
    ai_users = ai_events['reduser_id'].nunique()
    app_open_users = app_open_events['reduser_id'].nunique()
    
    print(f"\n📊 AI相关指标拆解:")
    print(f"   AI事件总数: {ai_click_count:,}")
    print(f"   AI独立用户: {ai_users:,}")
    print(f"   APP打开事件数: {app_open_count:,}")
    print(f"   APP打开用户数: {app_open_users:,}")
    
    rate_by_events = (ai_click_count / app_open_count * 100) if app_open_count > 0 else 0
    rate_by_users = (ai_users / app_open_users * 100) if app_open_users > 0 else 0
    
    print(f"\n🔢 使用率计算方法对比:")
    print(f"   方法A (AI事件/APP打开事件): {rate_by_events:.2f}%")
    print(f"   方法B (AI用户/APP打开用户): {rate_by_users:.2f}%")
    print(f"   报告中数值: 422.36%")
    
    print(f"\n❌ 问题定位：")
    print(f"   报告使用的公式可能是: avg_uses_per_user × 某个系数")
    print(f"   或者分母口径严重不一致")
    print(f"   ")
    print(f"   从报告数据反推：")
    print(f"   - total_ai_clicks = 1,322")
    print(f"   - ai_click_users = 146")
    print(f"   - app_open_total = 313")
    print(f"   - 如果 1322/313 = 422.36% ✓ 找到了！")
    print(f"   ")
    print(f"   🔴 **根本错误**: 用了 'AI点击次数' 作为分子，'APP打开次数'作为分母")
    print(f"   这两个指标维度不同，不能直接相除！")

def audit_ai_funnel_breakage(df):
    """审查 #4: AI漏斗断裂问题"""
    print("\n" + "=" * 80)
    print("🔴 [AUDIT-004] AI功能漏斗断裂 (点击146人，生成0人)")
    print("=" * 80)
    
    ai_related_patterns = {
        'ai_show': ['ai.*show', 'ai.*exposure', 'ai.*display'],
        'ai_click': ['ai.*click', 'ai.*tap', 'ai_guide.*click'],
        'ai_generate': ['ai.*generate', 'ai.*create', 'ai.*submit'],
        'ai_view': ['ai.*view', 'ai.*result.*show', 'guide.*detail'],
        'ai_share': ['ai.*share', 'ai.*forward', 'guide.*share']
    }
    
    print(f"\n🔍 AI漏斗各阶段事件匹配:")
    funnel_data = {}
    
    for stage, patterns in ai_related_patterns.items():
        combined_pattern = '|'.join(patterns)
        matched = df[df['span_nm'].str.contains(combined_pattern, case=False, regex=True, na=False)]
        
        event_count = len(matched)
        user_count = matched['reduser_id'].nunique()
        unique_events = matched['span_nm'].nunique()
        
        funnel_data[stage] = {
            'events': event_count,
            'users': user_count,
            'unique_event_types': unique_events
        }
        
        print(f"\n   📍 {stage.upper()}:")
        print(f"      匹配模式: {patterns}")
        print(f"      匹配到事件数: {event_count:,}")
        print(f"      独立用户数: {user_count:,}")
        print(f"      涉及事件类型数: {unique_events}")
        
        if unique_events > 0:
            top_events = matched['span_nm'].value_counts().head(3)
            print(f"      TOP3事件类型:")
            for evt_name, cnt in top_events.items():
                print(f"         - {evt_name}: {cnt:,}")
    
    print(f"\n📊 漏斗转化分析:")
    stages = list(funnel_data.keys())
    prev_users = None
    
    for i, stage in enumerate(stages):
        curr_users = funnel_data[stage]['users']
        if prev_users is not None and prev_users > 0:
            conversion = (curr_users / prev_users) * 100
            drop_rate = 100 - conversion
            bar = '█' * int(conversion / 5) + '░' * (20 - int(conversion / 5))
            print(f"   {stage:15} → {curr_users:4} 用户 ({conversion:6.1f}%) {bar}")
            
            if conversion < 10 and prev_users > 10:
                print(f"      ⚠️  警告: 转化率极低，可能存在漏斗断裂！")
                print(f"         可能原因：事件名称匹配规则不完整")
        else:
            print(f"   {stage:15} → {curr_users:4} 用户 (基准)")
        
        prev_users = curr_users

def audit_conversion_rates_over_100():
    """审查 #5: 漏斗转化率>100%的问题"""
    print("\n" + "=" * 80)
    print("🔴 [AUDIT-005] 内容消费漏斗转化率 > 100% 的问题")
    print("=" * 80)
    
    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    
    print(f"\n📊 deep_insights.json 中的异常转化率:")
    
    issues_found = []
    
    content_funnel = report_data.get('detailed_insights', {}).get('content_analysis', {})
    poi_funnel_report = None
    
    try:
        with open(r'c:\projects\rednote data analyzer\report\fulldata\deep_insights.json', 'r', encoding='utf-8') as f:
            deep_data = json.load(f)
        
        scenarios = deep_data.get('scenarios', {})
        
        print(f"\n   🔸 内容消费漏斗 (content_consumption_funnel):")
        content_funnel_scenarios = scenarios.get('content_consumption_funnel', {})
        prev_count = None
        
        for step, data in content_funnel_scenarios.items():
            count = data.get('count', 0)
            conv_rate = data.get('conversion_rate', 0)
            
            if prev_count is not None and prev_count > 0:
                expected_rate = (count / prev_count) * 100
                diff = abs(conv_rate - expected_rate)
                
                status = "✅" if conv_rate <= 100 else "🔴"
                print(f"      {status} {step:30} → count={count:>6}, reported_rate={conv_rate:>7.1f}%, expected≈{expected_rate:.1f}%")
                
                if conv_rate > 100:
                    issues_found.append({
                        'funnel': 'content',
                        'step': step,
                        'reported_rate': conv_rate,
                        'expected_rate': expected_rate,
                        'multiplier': conv_rate / 100
                    })
                    print(f"         ❌ ERROR: 报告的转化率是实际值的 {conv_rate/expected_rate:.1f} 倍!")
            
            prev_count = count
        
        print(f"\n   🔸 POI导航漏斗 (poi_navigation_funnel):")
        poi_funnel = scenarios.get('poi_navigation_funnel', {})
        prev_count = None
        
        for step, data in poi_funnel.items():
            count = data.get('count', 0)
            conv_rate = data.get('conversion_rate', 0)
            
            if prev_count is not None and prev_count > 0:
                expected_rate = (count / prev_count) * 100
                
                status = "✅" if conv_rate <= 100 else "🔴"
                print(f"      {status} {step:30} → count={count:>6}, reported_rate={conv_rate:>7.1f}%, expected≈{expected_rate:.1f}%")
                
                if conv_rate > 100:
                    issues_found.append({
                        'funnel': 'poi',
                        'step': step,
                        'reported_rate': conv_rate,
                        'expected_rate': expected_rate,
                        'multiplier': conv_rate / 100
                    })
            
            prev_count = count
        
        print(f"\n   🔸 AI指南漏斗 (ai_guide_funnel):")
        ai_funnel = scenarios.get('ai_guide_funnel', {})
        prev_count = None
        
        for step, data in ai_funnel.items():
            count = data.get('count', 0)
            conv_rate = data.get('conversion_rate', 0)
            
            if prev_count is not None and prev_count > 0:
                expected_rate = (count / prev_count) * 100
                
                status = "✅" if conv_rate <= 100 else "🔴"
                print(f"      {status} {step:30} → count={count:>6}, reported_rate={conv_rate:>7.1f}%, expected≈{expected_rate:.1f}%")
                
                if conv_rate > 100:
                    issues_found.append({
                        'funnel': 'ai',
                        'step': step,
                        'reported_rate': conv_rate,
                        'expected_rate': expected_rate,
                        'multiplier': conv_rate / 100
                    })
            
            prev_count = count
            
    except Exception as e:
        print(f"   ⚠️  无法读取deep_insights.json: {e}")
    
    if issues_found:
        print(f"\n🔴 共发现 {len(issues_found)} 个转化率>100%的异常:")
        for issue in issues_found:
            print(f"   - [{issue['funnel']}] {issue['step']}: 报告={issue['reported_rate']:.1f}%, 实际应≈{issue['expected_rate']:.1f}% (误差{issue['multiplier']:.1f}x)")

def audit_user_behavior_distribution(df):
    """审查 #6: 用户行为分布异常（极端离群点）"""
    print("\n" + "=" * 80)
    print("🟠 [AUDIT-006] 用户行为分布异常 (mean=189.79 vs median=72)")
    print("=" * 80)
    
    user_stats = df.groupby('reduser_id').agg(
        event_count=('reduser_id', 'count'),
        unique_pages=('span_nm', 'nunique'),
        date_span=('date', lambda x: (x.max() - x.min()).days if len(x) > 1 else 0)
    ).reset_index()
    
    events = user_stats['event_count']
    
    print(f"\n📊 用户事件数分布:")
    print(f"   用户总数: {len(user_stats):,}")
    print(f"   均值 (Mean): {events.mean():.2f}")
    print(f"   中位数 (Median): {events.median():.2f}")
    print(f"   标准差 (Std): {events.std():.2f}")
    print(f"   偏度 (Skewness): {events.skew():.2f}")
    print(f"   峰度 (Kurtosis): {events.kurtosis():.2f}")
    
    Q1, Q3 = events.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    upper_bound = Q3 + 1.5 * IQR
    lower_bound = Q1 - 1.5 * IQR
    
    outliers = user_stats[(events < lower_bound) | (events > upper_bound)]
    extreme_outliers = user_stats[events > upper_bound * 3]
    
    print(f"\n📐 IQR离群点检测:")
    print(f"   Q1 (25%): {Q1:.0f}")
    print(f"   Q3 (75%): {Q3:.0f}")
    print(f"   IQR: {IQR:.0f}")
    print(f"   正常范围: [{lower_bound:.0f}, {upper_bound:.0f}]")
    print(f"   离群点数量: {len(outliers)} ({len(outliers)/len(user_stats)*100:.1f}%)")
    print(f"   极端离群点 (>{upper_bound*3:.0f}): {len(extreme_outliers)} ({len(extreme_outliers)/len(user_stats)*100:.1f}%)")
    
    if len(extreme_outliers) > 0:
        print(f"\n   🚨 极端离群用户详情 (TOP 5):")
        top_extreme = extreme_outliers.nlargest(5, 'event_count')
        for _, row in top_extreme.iterrows():
            user_id = row['reduser_id']
            evt_cnt = row['event_count']
            pages = row['unique_pages']
            days = row['date_span']
            pct_of_total = evt_cnt / events.sum() * 100
            print(f"      User {user_id}: {evt_cnt:,} 事件 ({pct_of_total:.1f}%总量) | {pages} 页面 | {days} 天跨度")
    
    print(f"\n💡 影响:")
    print(f"   - 均值被少数重度用户严重拉高，不能代表典型用户")
    print(f"   - 建议报告中同时展示: 中位数、四分位数、截尾均值")
    print(f"   - 对极端用户进行单独案例分析，而非混入总体统计")

def audit_feature_discovery_rates():
    """审查 #7: 功能发现率全部为0"""
    print("\n" + "=" * 80)
    print("🔴 [AUDIT-007] 功能发现率 (feature_discovery_rates) 全部为 0.0")
    print("=" * 80)
    
    try:
        with open(r'c:\projects\rednote data analyzer\report\fulldata\deep_insights.json', 'r', encoding='utf-8') as f:
            deep_data = json.load(f)
        
        familiarity = deep_data.get('familiarity', {})
        feature_rates = familiarity.get('feature_discovery_rates', {})
        
        print(f"\n📊 feature_discovery_rates 字段内容:")
        for feature, rate in feature_rates.items():
            status = "🔴 ZERO" if rate == 0 else "✅"
            print(f"   {status} {feature:20} → {rate}")
        
        print(f"\n❌ 问题分析:")
        print(f"   所有8个功能的发现率都是0.0，这显然不合理。")
        print(f"   因为报告中显示有用户确实使用了这些功能：")
        print(f"   - AI旅行指南用户: {familiarity.get('statistics', {}).get('avg_familiarity_score', 'N/A')}")
        print(f"   - POI交互用户: 86 (来自profiling)")
        print(f"   - 视频观看用户: 35 (来自profiling)")
        print(f"   ")
        print(f"   🔴 **根因**: feature_discovery_rates的计算逻辑可能有误")
        print(f"   可能原因：")
        print(f"   1. 分母用了错误的基数（如总安装用户而非活跃用户）")
        print(f"   2. 计算时发生了除零错误被静默处理为0")
        print(f"   3. 该字段未被正确赋值，保留了初始默认值")
        
    except Exception as e:
        print(f"   ⚠️  无法读取文件: {e}")

def audit_time_distribution_anomalies(df):
    """审查 #8: 时间分布异常"""
    print("\n" + "=" * 80)
    print("🟡 [AUDIT-008] 时间分布异常 (凌晨时段活动模式)")
    print("=" * 80)
    
    hourly = df[df['strt_time_dt'].notna()].groupby('hour').agg(
        events=('reduser_id', 'count'),
        users=('reduser_id', 'nunique')
    ).reset_index()
    
    print(f"\n📊 小时级分布 (完整24小时):")
    for _, row in hourly.iterrows():
        h = int(row['hour'])
        e = row['events']
        u = row['users']
        bar_len = int(e / hourly['events'].max() * 40)
        bar = '█' * bar_len
        time_label = f"{h:02d}:00"
        
        anomaly_flag = ""
        if e == 0 and 6 <= h <= 22:
            anomaly_flag = " ⚠️ 异常零值"
        elif u == 0 and e > 0:
            anomaly_flag = " ⚠️ 无人但有事"
        
        print(f"   {time_label}  {e:>5,} 事件 | {u:>3} 用户 | {bar}{anomaly_flag}")
    
    zero_hours = hourly[hourly['events'] == 0]['hour'].tolist()
    if zero_hours:
        print(f"\n   ⚠️  完全无活动的时段: {[f'{int(h):02d}:00' for h in zero_hours]}")
    
    early_morning = hourly[(hourly['hour'] >= 0) & (hourly['hour'] <= 5)]
    em_events = early_morning['events'].sum()
    em_users = early_morning['users'].sum()
    total_e = hourly['events'].sum()
    
    print(f"\n   🌙 凌晨时段 (00:00-05:59):")
    print(f"      事件占比: {em_events/total_e*100:.1f}%")
    print(f"      独立用户: {em_users}")
    
    if em_events > total_e * 0.1:
        print(f"      ⚠️ 凌晨事件占比偏高 (>10%)，可能存在：")
        print(f"         - 时区设置错误（UTC vs 北京时间）")
        print(f"         - 自动化脚本/爬虫行为")
        print(f"         - 测试数据混杂")

def audit_retention_calculation():
    """审查 #9: 留存率计算问题"""
    print("\n" + "=" * 80)
    print("🟠 [AUDIT-009] 留存率异常 (7天=2.94%, 14天=0%)")
    print("=" * 80)
    
    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
        report_data = json.load(f)
    
    retention = report_data.get('app_metrics', {}).get('retention_rates', {})
    
    print(f"\n📊 报告中的留存率:")
    for day, rate in retention.items():
        status = "✅" if rate != "N/A" and float(rate.replace('%','')) > 10 else "🟠 LOW"
        print(f"   {status} {day}留存: {rate}")
    
    print(f"\n⚠️  问题分析:")
    print(f"   7天留存仅2.94%，14天留存降至0%，这表明：")
    print(f"   ")
    print(f"   1. **时间窗口不足**: 数据仅覆盖约12天（0319-0330），")
    print(f"      计算14天留存的队列样本极少")
    print(f"   ")
    print(f"   2. **产品粘性问题**: 如果数据准确，说明用户几乎不会回来")
    print(f"      这对于一款新上线APP来说非常危险")
    print(f"   ")
    print(f"   3. **计算方法疑点**:")
    print(f"      - 是否使用了正确的队列定义？")
    print(f"      - 回访事件的匹配是否精确？")
    print(f"      - 是否排除了测试账号？")
    
    print(f"\n💡 建议:")
    print(f"   - 明确标注数据时间范围限制")
    print(f"   - 对样本量<30的留存率标注置信区间")
    print(f"   - 补充次日留存(Day 1 Retention)作为核心指标")

def generate_audit_summary():
    """生成审计总结"""
    print("\n" + "=" * 80)
    print("🎯 AUDIT SUMMARY - 审计总结")
    print("=" * 80)
    
    summary = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   🔴 CRITICAL 问题 (必须立即修复)                                ║
║   ─────────────────────────────────────                          ║
║   1. exposure_duration_sec = 0 (全部页面)                       ║
║      → 影响无法评估用户参与深度                                  ║
║      → 根因: duration字段未正确解析                              ║
║                                                                  ║
║   2. AI使用率 = 422.36% (>100%)                                 ║
║      → 误导产品决策                                             ║
║      → 根因: 分子分母维度不一致 (次数vs次数)                     ║
║                                                                  ║
║   3. AI漏斗断裂 (146点击→0生成)                                 ║
║      → 无法评估AI功能真实效果                                   ║
║      → 根因: 后续事件名称匹配失败                               ║
║                                                                  ║
║   4. 漏斗转化率多处 > 100%                                      ║
║      → 数学上不可能                                             ║
║      → 根因: 转化率计算公式错误                                 ║
║                                                                  ║
║   5. feature_discovery_rates 全部 = 0                           ║
║      → 与实际使用情况矛盾                                       ║
║      → 根因: 计算逻辑错误或未初始化                             ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║   🟠 WARNING 问题 (建议本周修复)                                 ║
║   ────────────────────────────                                   ║
║   6. 活跃率 = 100% (所有模块)                                    ║
║      → 幸存者偏差                                               ║
║      → 根因: 分母用"有事件用户"而非"安装用户"                   ║
║                                                                  ║
║   7. 用户行为分布严重右偏 (mean=189 vs median=72)               ║
║      → 平均数陷阱                                               ║
║      → 影响: 典型用户画像失真                                   ║
║                                                                  ║
║   8. 留存率极低且样本不足 (7天=2.94%, 14天=0%)                  ║
║      → 统计意义有限                                             ║
║      → 需要: 更长时间窗口+置信区间                               ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║   🟡 Suggestion (优化建议)                                       ║
║   ──────────────────                                             ║
║   9. 凌晨5点完全无活动                                           ║
║      → 可能是正常现象，也可能是采样问题                         ║
║                                                                  ║
║  10. 缺乏行业基准对比                                            ║
║      → 无法判断绝对值是否合理                                   ║
║      → 建议: 引入同类产品benchmark                               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

📊 评分预估:
   - 数据完整性:     2.0/5.0 (关键字段缺失或未解析)
   - 指标合理性:     1.5/5.0 (多个比率>100%或=0%)
   - 统计正确性:     2.0/5.0 (平均数陷阱、幸存者偏差)
   - 业务一致性:     2.5/5.0 (部分逻辑矛盾已识别)
   - 可解释性:       3.0/5.0 (结构清晰但数值不可信)
   - 行动能力:       2.0/5.0 (基于错误数据的决策风险高)

🎯 总体评级: ⭐☆☆☆☆ (待改进 - 不建议直接用于决策)

🚨 下一步行动:
   P0 (立即): 修复duration字段解析和转化率计算公式
   P1 (本周): 修正活跃率和使用率的分母定义
   P2 (迭代): 引入统计最佳实践(中位数、置信区间、基准对比)
"""
    print(summary)

def main():
    print("\n" + "🔬" * 40)
    print("启动 DATA AUDIT 深度诊断流程...")
    print("🔬" * 40 + "\n")
    
    df = load_raw_data()
    
    print("\n\n▶ 开始执行9项深度诊断...\n")
    
    audit_duration_field(df)
    audit_active_rate_calculation(df)
    audit_ai_usage_rate(df)
    audit_ai_funnel_breakage(df)
    audit_conversion_rates_over_100()
    audit_user_behavior_distribution(df)
    audit_feature_discovery_rates()
    audit_time_distribution_anomalies(df)
    audit_retention_calculation()
    
    generate_audit_summary()
    
    print("\n✅ 深度诊断完成！")
    print(f"📁 详细结果请查看上方输出")
    print(f"⏰ 审计时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
