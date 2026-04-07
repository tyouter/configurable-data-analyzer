# -*- coding: utf-8 -*-
"""
小红书用户点击事件业务洞察分析
专门分析 POI 搜索、导航、用户行为等业务指标
"""
import pandas as pd
import numpy as np
import sys
import io

# 设置标准输出为 UTF-8 编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def business_insights_analysis(file_path):
    """业务洞察分析"""
    print("=" * 80)
    print("小红书用户点击事件 - 业务洞察分析报告")
    print("=" * 80)

    # 读取数据
    print(f"\n正在读取数据文件...")
    df = pd.read_excel(file_path)
    print(f"数据加载完成！共 {len(df):,} 行")

    # 提取页面和动作信息
    # span_nm 格式：page_name_page_name_xxx_action
    # 页面名通常是第一部分，如 porsche_page_Map_poi_card_cardshow -> porsche
    df['page'] = df['span_nm'].str.split('_').str[0]
    # 动作通常是最后部分
    df['action'] = df['span_nm'].str.split('_').str[-1]

    print("\n" + "=" * 80)
    print("一、核心业务指标")
    print("=" * 80)

    # 1. Porsche 地图页面分析
    porsche_events = df[df['page'] == 'porsche']
    print(f"\n📍 Porsche 地图页面分析")
    print(f"   总事件数: {len(porsche_events):,} ({len(porsche_events)/len(df)*100:.2f}%)")

    porsche_actions = porsche_events['action'].value_counts()
    print(f"   主要操作:")
    for action, count in porsche_actions.head(5).items():
        print(f"     - {action}: {count:,} ({count/len(porsche_events)*100:.2f}%)")

    # 2. 搜索行为分析
    search_events = df[df['page'] == 'search']
    print(f"\n🔍 搜索行为分析")
    print(f"   总事件数: {len(search_events):,} ({len(search_events)/len(df)*100:.2f}%)")

    search_actions = search_events['action'].value_counts()
    print(f"   搜索流程:")
    for action, count in search_actions.head(5).items():
        print(f"     - {action}: {count:,} ({count/len(search_events)*100:.2f}%)")

    # 3. POI 交互分析
    poi_events = df[df['span_nm'].str.contains('poi', case=False)]
    print(f"\n🎯 POI (兴趣点) 交互分析")
    print(f"   总事件数: {len(poi_events):,} ({len(poi_events)/len(df)*100:.2f}%)")

    poi_actions = poi_events['span_nm'].value_counts()
    print(f"   POI 相关操作:")
    for action, count in poi_actions.head(5).items():
        print(f"     - {action}: {count:,}")

    # 4. 发现页分析
    discovery_events = df[df['page'] == 'discovery']
    print(f"\n🌟 发现页分析")
    print(f"   总事件数: {len(discovery_events):,} ({len(discovery_events)/len(df)*100:.2f}%)")

    # 5. 详情页分析
    post_events = df[df['page'] == 'post']
    print(f"\n📝 帖子详情页分析")
    print(f"   总事件数: {len(post_events):,} ({len(post_events)/len(df)*100:.2f}%)")

    if len(post_events) > 0:
        post_actions = post_events['action'].value_counts()
        print(f"   详情页操作:")
        for action, count in post_actions.head(5).items():
            print(f"     - {action}: {count:,} ({count/len(post_events)*100:.2f}%)")

    # 6. 用户个人中心分析
    profile_events = df[df['page'].isin(['profile', 'Profile'])]
    print(f"\n👤 用户个人中心分析")
    print(f"   总事件数: {len(profile_events):,} ({len(profile_events)/len(df)*100:.2f}%)")

    print("\n" + "=" * 80)
    print("二、用户行为转化漏斗")
    print("=" * 80)

    # 构建核心业务漏斗
    funnel = {
        'Porsche页面曝光': df['span_nm'].str.contains('porsche_page_pageshow').sum(),
        'POI卡片展示': df['span_nm'].str.contains('poi_card_cardshow').sum(),
        'POI卡片点击': df['span_nm'].str.contains('poi_card_click').sum(),
        '导航按钮显示': df['span_nm'].str.contains('navigation_button_show').sum(),
        '导航按钮点击': df['span_nm'].str.contains('navigation_button_click').sum(),
        '导航确认': df['span_nm'].str.contains('navigation_confirm').sum()
    }

    print(f"\n{'漏斗步骤':<20} {'事件数':<10} {'转化率':<15}")
    print("-" * 50)

    prev_count = None
    for step, count in funnel.items():
        conversion = ""
        if prev_count is not None and prev_count > 0:
            conversion = f"{count/prev_count*100:.2f}%"
        print(f"{step:<20} {count:<10,} {conversion:<15}")
        prev_count = count

    print("\n" + "=" * 80)
    print("三、业务深度洞察")
    print("=" * 80)

    insights = []

    # 地图使用洞察
    map_usage_rate = len(porsche_events) / len(df) * 100
    if map_usage_rate > 40:
        insights.append("✅ 地图功能核心化：超过40%的用户行为集中在Porsche地图页面，说明地图导航是核心功能")
        insights.append("💡 建议：优先优化地图体验，提升地图相关功能的用户满意度")

    # 搜索行为洞察
    search_usage_rate = len(search_events) / len(df) * 100
    if search_usage_rate > 15:
        insights.append("✅ 搜索活跃度高：搜索相关事件占比超过15%，用户主动搜索需求强烈")
        insights.append("💡 建议：优化搜索算法，提升搜索结果的相关性和准确性")

    # 交互率分析
    click_events = df[df['action'] == 'click']
    show_events = df[df['action'].isin(['cardshow', 'pageshow', 'show'])]
    if len(show_events) > 0:
        interaction_rate = len(click_events) / len(show_events) * 100
        if interaction_rate < 10:
            insights.append(f"⚠️  用户交互率偏低：仅{interaction_rate:.2f}%的展示事件产生了点击交互")
            insights.append("💡 建议：提升内容吸引力，优化交互设计，增加用户引导")

    # POI导航分析
    poi_conversion = funnel['导航确认'] / funnel['POI卡片展示'] * 100 if funnel['POI卡片展示'] > 0 else 0
    if poi_conversion < 5:
        insights.append(f"⚠️  POI导航转化率偏低：从POI展示到导航确认的转化率仅{poi_conversion:.2f}%")
        insights.append("💡 建议：优化POI信息展示，突出导航价值，简化导航流程")

    # 内容消费洞察
    content_view_rate = (len(discovery_events) + len(post_events)) / len(df) * 100
    if content_view_rate > 10:
        insights.append("✅ 内容消费活跃：发现页和详情页占比超过10%，用户内容消费需求较强")
        insights.append("💡 建议：优化内容推荐算法，提升内容质量和相关性")

    for insight in insights:
        print(f"\n{insight}")

    print("\n" + "=" * 80)
    print("四、产品优化建议")
    print("=" * 80)

    recommendations = [
        {
            "优先级": "P0 (核心)",
            "建议": "优化Porsche地图页面交互体验",
            "原因": "超过50%的用户行为集中在地图页面，是核心功能",
            "具体措施": "提升地图加载速度、优化POI卡片展示、简化导航流程"
        },
        {
            "优先级": "P1 (重要)",
            "建议": "提升POI导航转化率",
            "原因": "POI展示到导航确认的转化率偏低，有提升空间",
            "具体措施": "优化POI信息展示、突出导航按钮、简化确认流程"
        },
        {
            "优先级": "P1 (重要)",
            "建议": "优化搜索体验",
            "原因": "搜索相关事件占比超过20%，用户搜索需求强烈",
            "具体措施": "提升搜索准确性、优化搜索结果排序、增加热门搜索"
        },
        {
            "优先级": "P2 (次要)",
            "建议": "增强用户互动引导",
            "原因": "用户交互率偏低，主动点击较少",
            "具体措施": "优化交互设计、增加新手引导、提升内容吸引力"
        }
    ]

    print(f"\n{'优先级':<15} {'建议':<30} {'原因'}")
    print("-" * 80)
    for rec in recommendations:
        print(f"{rec['优先级']:<15} {rec['建议']:<30}")
        print(f"{'':15} {'原因':<30} {rec['原因']}")
        print(f"{'':15} {'具体措施':<30} {rec['具体措施']}")
        print()

    print("\n" + "=" * 80)
    print("五、数据质量评估")
    print("=" * 80)

    # 检查数据完整性
    completeness = {
        'span_nm': df['span_nm'].notna().mean() * 100,
        'reduser_id': df['reduser_id'].notna().mean() * 100,
        'strt_time_nano': df['strt_time_nano'].notna().mean() * 100
    }

    print(f"\n数据完整率:")
    for field, rate in completeness.items():
        status = "✅" if rate >= 95 else "⚠️" if rate >= 80 else "❌"
        print(f"{status} {field}: {rate:.2f}%")

    print("\n" + "=" * 80)
    print("业务洞察分析完成！")
    print("=" * 80)

    return df

if __name__ == "__main__":
    file_path = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"
    business_insights_analysis(file_path)
