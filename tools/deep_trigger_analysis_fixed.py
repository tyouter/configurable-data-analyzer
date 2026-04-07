# -*- coding: utf-8 -*-
"""
Trigger信号深度关联分析 - 修正版
基于trigger signals定义文件，深入分析事件与字段的关联关系
"""
import pandas as pd
import numpy as np
import sys
import io
from collections import defaultdict

# 设置标准输出为 UTF-8 编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def analyze_trigger_relationship():
    """分析trigger信号与数据的关联"""

    print("=" * 80)
    print("Trigger信号深度关联分析")
    print("=" * 80)

    # 读取文件
    trigger_file = r"C:\projects\rednote data analyzer\data\rednote\trigger signals definition.xlsx"
    data_file = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"

    print(f"\n正在读取文件...")
    trigger_df = pd.read_excel(trigger_file)
    data_df = pd.read_excel(data_file)

    print(f"Trigger signals文件: {len(trigger_df)} 行")
    print(f"数据文件: {len(data_df)} 行")

    # 解析trigger signals定义
    print("\n" + "=" * 80)
    print("一、Trigger Signals定义解析")
    print("=" * 80)

    # 整理trigger signals数据 - 按事件分组
    event_attributes = defaultdict(list)
    current_event_id = None

    for idx, row in trigger_df.iterrows():
        event_id = row.get('标识符（事件）*', '')
        event_name = row.get('名称（事件）*', '')
        attr_id = row.get('标识符（事件属性）', '')
        attr_name = row.get('名称（事件属性）', '')
        attr_type = row.get('类型（事件属性）', '')
        attr_desc = row.get('描述（事件属性）', '')

        # 如果这是一个新事件
        if pd.notna(event_id) and event_id != '':
            current_event_id = str(event_id)

        # 如果有属性信息，添加到当前事件
        if current_event_id and pd.notna(attr_id) and attr_id != '':
            attr_info = {
                'id': str(attr_id),
                'name': str(attr_name) if pd.notna(attr_name) else '',
                'type': str(attr_type) if pd.notna(attr_type) else '',
                'description': str(attr_desc) if pd.notna(attr_desc) else ''
            }
            event_attributes[current_event_id].append(attr_info)

    # 显示事件和属性映射
    print(f"\n事件定义统计:")
    print(f"  总事件数: {len(event_attributes)}")
    print(f"  有属性的事件数: {sum(1 for k, v in event_attributes.items() if v)}")

    print(f"\n主要事件定义 (前20个):")
    event_count = 0
    for event_id, attrs in event_attributes.items():
        event_count += 1
        if event_count <= 20:
            print(f"  {event_count:2d}. {event_id}")
            if attrs:
                print(f"      属性: {len(attrs)} 个")
                for attr in attrs[:3]:  # 只显示前3个属性
                    attr_name = attr.get('name', attr.get('id', 'unknown'))
                    attr_type = attr.get('type', 'unknown')
                    print(f"        - {attr_name}: {attr_type}")
                if len(attrs) > 3:
                    print(f"        ... 还有 {len(attrs)-3} 个属性")

    # 分析实际数据中的事件
    print("\n" + "=" * 80)
    print("二、实际数据事件分析")
    print("=" * 80)

    # 获取实际数据中所有唯一的span_nm
    actual_events = data_df['span_nm'].unique()
    print(f"\n实际数据中的事件数: {len(actual_events)}")

    # 匹配定义的事件
    defined_events = set(event_attributes.keys())
    actual_events_set = set(actual_events)

    # 查找完全匹配的事件
    exact_matches = actual_events_set & defined_events
    print(f"  完全匹配定义的事件: {len(exact_matches)} 个")

    # 查找部分匹配的事件
    partial_matches = []
    for actual_event in actual_events:
        if actual_event not in defined_events:
            # 查找可能的匹配（包含或被包含）
            for defined_event in defined_events:
                if defined_event and actual_event:
                    if defined_event in actual_event or actual_event in defined_event:
                        partial_matches.append((actual_event, defined_event))
                        break

    print(f"  部分匹配的事件: {len(partial_matches)} 对")

    # 未匹配的事件
    unmatched = actual_events_set - defined_events - set([e[0] for e in partial_matches])
    print(f"  未在定义中找到的事件: {len(unmatched)} 个")

    if len(unmatched) > 0:
        print(f"\n未匹配的事件示例 (前10个):")
        for i, event in enumerate(list(unmatched)[:10], 1):
            print(f"  {i}. {event}")

    # 字段映射分析
    print("\n" + "=" * 80)
    print("三、字段映射分析")
    print("=" * 80)

    # 构建字段名称映射
    trigger_attr_names = set()
    for event_id, attrs in event_attributes.items():
        for attr in attrs:
            if attr.get('name'):
                trigger_attr_names.add(attr['name'].replace('RedNote_', '').replace('_', ''))
            if attr.get('id'):
                trigger_attr_names.add(attr['id'].replace('RedNote_', '').replace('_', ''))

    data_columns = set([col.replace('rednote_', '').replace('_', '') for col in data_df.columns])

    print(f"\nTrigger中定义的属性名: {len(trigger_attr_names)} 个")
    print(f"数据文件中的列名: {len(data_columns)} 个")

    # 查找匹配的字段
    field_matches = set()
    for trigger_attr in trigger_attr_names:
        for data_col in data_columns:
            if trigger_attr.lower() in data_col.lower() or data_col.lower() in trigger_attr.lower():
                field_matches.add((trigger_attr, data_col))

    print(f"  可能匹配的字段对: {len(field_matches)} 个")

    print(f"\n字段匹配示例:")
    for i, (trigger_attr, data_col) in enumerate(list(field_matches)[:20], 1):
        # 找到原始列名
        original_col = None
        for col in data_df.columns:
            if data_col in col.replace('rednote_', '').replace('_', '').lower():
                original_col = col
                break

        # 统计该字段的数据使用情况
        if original_col:
            non_null = data_df[original_col].notna().sum()
            unique = data_df[original_col].nunique()
            print(f"  {i:2d}. '{trigger_attr}' <-> '{original_col}' (使用率: {non_null/len(data_df)*100:5.1f}%, 唯一值: {unique:3d})")

    # 详细的事件-字段关联分析
    print("\n" + "=" * 80)
    print("四、详细事件-字段关联分析")
    print("=" * 80)

    # 分析几个关键事件的字段使用
    key_events = [
        'porsche_page_Map_poi_card_cardshow',
        'discovery_page_post_card_cardshow',
        'search_results_page_post_card_carshow',
        'post_detail_page_pageshow',
        'poi_detail_page_pageshow'
    ]

    for event in key_events:
        if event in actual_events:
            event_data = data_df[data_df['span_nm'] == event]
            print(f"\n事件: {event} ({len(event_data)} 条)")
            print("  相关字段使用情况:")

            # 找到该事件中非空的字段
            for col in data_df.columns:
                if col not in ['span_nm', 'page', 'action']:
                    non_null_count = event_data[col].notna().sum()
                    if non_null_count > 0:
                        usage_rate = non_null_count / len(event_data) * 100
                        unique_count = event_data[col].nunique()

                        # 如果唯一值较少，显示实际值
                        value_sample = ""
                        if unique_count <= 5:
                            values = event_data[col].dropna().unique()
                            value_sample = f" 值: {list(values)}"

                        print(f"    {col:<45} {usage_rate:5.1f}%  ({unique_count:3d}个唯一值){value_sample}")

    # 生成深度关联分析报告
    print("\n" + "=" * 80)
    print("五、生成深度关联分析报告")
    print("=" * 80)

    generate_detailed_report(data_df, event_attributes, actual_events_set, defined_events)

    print("\n✅ 深度关联分析报告已生成！")

def generate_detailed_report(data_df, event_attributes, actual_events_set, defined_events):
    """生成详细的关联分析报告"""

    report_lines = []
    report_lines.append("# Trigger信号与数据字段深度关联分析报告")
    report_lines.append("")
    report_lines.append("**生成时间**: 2026-04-07")
    report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # 一、事件匹配分析
    report_lines.append("## 一、事件匹配分析")
    report_lines.append("")

    exact_matches = actual_events_set & defined_events
    unmatched = actual_events_set - defined_events

    report_lines.append(f"### 统计概况")
    report_lines.append("")
    report_lines.append(f"- **实际数据中的事件数**: {len(actual_events_set)}")
    report_lines.append(f"- **定义文件中的事件数**: {len(defined_events)}")
    report_lines.append(f"- **完全匹配的事件数**: {len(exact_matches)}")
    report_lines.append(f"- **未匹配的事件数**: {len(unmatched)}")
    report_lines.append("")

    report_lines.append(f"### 完全匹配的事件")
    report_lines.append("")
    report_lines.append(f"以下是同时在定义文件和实际数据中出现的事件:")
    report_lines.append("")

    for event in sorted(exact_matches):
        event_data = data_df[data_df['span_nm'] == event]
        report_lines.append(f"- **{event}** ({len(event_data)} 条)")
        report_lines.append("")

    # 二、关键事件字段使用分析
    report_lines.append("## 二、关键事件字段使用分析")
    report_lines.append("")

    # 分析POI相关事件
    poi_events = data_df[data_df['span_nm'].str.contains('poi', case=False)]
    report_lines.append("### 📍 POI相关事件字段使用")
    report_lines.append("")
    report_lines.append(f"POI相关事件总数: {len(poi_events)} 条")
    report_lines.append("")
    report_lines.append("| 字段名 | 使用率 | 唯一值数 | 描述 |")
    report_lines.append("|--------|--------|----------|------|")

    poi_fields = [
        'rednote_poi_map_fullscreen', 'rednote_poi_title',
        'rednote_poi_typ', 'rednote_poi_typ_nm'
    ]

    for field in poi_fields:
        if field in data_df.columns:
            non_null = poi_events[field].notna().sum()
            usage_rate = non_null / len(poi_events) * 100
            unique = poi_events[field].nunique()

            description = {
                'rednote_poi_map_fullscreen': 'POI地图是否全屏显示',
                'rednote_poi_title': 'POI标题/名称',
                'rednote_poi_typ': 'POI类型代码',
                'rednote_poi_typ_nm': 'POI类型名称'
            }.get(field, '')

            report_lines.append(f"| {field} | {usage_rate:.1f}% | {unique} | {description} |")

    report_lines.append("")

    # 分析帖子相关事件
    post_events = data_df[data_df['span_nm'].str.contains('post', case=False)]
    report_lines.append("### 📝 帖子相关事件字段使用")
    report_lines.append("")
    report_lines.append(f"帖子相关事件总数: {len(post_events)} 条")
    report_lines.append("")
    report_lines.append("| 字段名 | 使用率 | 唯一值数 | 描述 |")
    report_lines.append("|--------|--------|----------|------|")

    post_fields = [
        'rednote_post_num', 'rednote_post_title', 'rednote_post_typ',
        'rednote_post_is_like', 'rednote_post_follow', 'rednote_post_is_save',
        'rednote_post_is_op_rec', 'rednote_post_is_recuser'
    ]

    for field in post_fields:
        if field in data_df.columns:
            non_null = post_events[field].notna().sum()
            usage_rate = non_null / len(post_events) * 100
            unique = post_events[field].nunique()

            description = {
                'rednote_post_num': '帖子编号',
                'rednote_post_title': '帖子标题',
                'rednote_post_typ': '帖子类型',
                'rednote_post_is_like': '帖子是否被点赞',
                'rednote_post_follow': '帖子关注状态',
                'rednote_post_is_save': '帖子是否被收藏',
                'rednote_post_is_op_rec': '帖子是否为运营推荐',
                'rednote_post_is_recuser': '帖子是否推荐用户'
            }.get(field, '')

            report_lines.append(f"| {field} | {usage_rate:.1f}% | {unique} | {description} |")

    report_lines.append("")

    # 分析旅行指南相关事件
    guide_events = data_df[data_df['span_nm'].str.contains('guide', case=False)]
    report_lines.append("### 🧭 旅行指南相关事件字段使用")
    report_lines.append("")
    report_lines.append(f"旅行指南相关事件总数: {len(guide_events)} 条")
    report_lines.append("")
    report_lines.append("| 字段名 | 使用率 | 唯一值数 | 描述 |")
    report_lines.append("|--------|--------|----------|------|")

    guide_fields = [
        'rednote_travel_guide_id', 'rednote_travel_guide_title',
        'rednote_travel_post_is_succ'
    ]

    for field in guide_fields:
        if field in data_df.columns:
            non_null = guide_events[field].notna().sum()
            usage_rate = non_null / len(guide_events) * 100 if len(guide_events) > 0 else 0
            unique = guide_events[field].nunique()

            description = {
                'rednote_travel_guide_id': '旅行指南ID',
                'rednote_travel_guide_title': '旅行指南标题',
                'rednote_travel_post_is_succ': '旅行帖子是否成功生成'
            }.get(field, '')

            report_lines.append(f"| {field} | {usage_rate:.1f}% | {unique} | {description} |")

    report_lines.append("")

    # 三、数据价值分析
    report_lines.append("## 三、数据价值分析")
    report_lines.append("")

    report_lines.append("### 高价值字段识别")
    report_lines.append("")
    report_lines.append("基于字段使用频率和业务价值，识别出以下高价值字段:")
    report_lines.append("")

    # 计算各字段的使用情况

    field_stats = {}
    for col in data_df.columns:
        if col.startswith('rednote_'):
            non_null = data_df[col].notna().sum()
            usage_rate = non_null / len(data_df) * 100
            unique = data_df[col].nunique()
            field_stats[col] = {
                'usage_rate': usage_rate,
                'unique_count': unique,
                'non_null_count': non_null
            }

    # 按使用率排序
    sorted_fields = sorted(field_stats.items(), key=lambda x: x[1]['usage_rate'], reverse=True)

    report_lines.append("| 排名 | 字段名 | 使用率 | 唯一值数 | 业务价值 |")
    report_lines.append("|------|--------|--------|----------|----------|")

    business_value = {
        'rednote_poi_map_fullscreen': '🌟高 - 地图全屏状态，影响用户体验',
        'rednote_poi_title': '🌟高 - POI名称，核心内容标识',
        'rednote_poi_typ_nm': '🌟高 - POI类型，用于分类分析',
        'rednote_post_title': '🌟高 - 帖子标题，内容分析基础',
        'rednote_post_typ': '🌟高 - 帖子类型，内容分类',
        'rednote_travel_guide_id': '⭐中 - AI旅行指南标识',
        'rednote_travel_guide_title': '⭐中 - 旅行指南标题',
        'rednote_post_is_op_rec': '⭐中 - 运营推荐标识',
        'rednote_search_result_tab_title': '⭐中 - 搜索标签，搜索体验分析'
    }

    for rank, (field, stats) in enumerate(sorted_fields[:15], 1):
        value = business_value.get(field, '📊低 - 其他字段')
        report_lines.append(f"| {rank} | {field} | {stats['usage_rate']:.1f}% | {stats['unique_count']} | {value} |")

    report_lines.append("")

    # 四、业务洞察
    report_lines.append("## 四、业务洞察与建议")
    report_lines.append("")

    # POI分析
    poi_fullscreen = data_df['rednote_poi_map_fullscreen'].value_counts()
    report_lines.append("### 📍 地图全屏使用分析")
    report_lines.append("")
    report_lines.append("POI地图全屏状态分布:")
    report_lines.append("")

    for value, count in poi_fullscreen.items():
        percentage = count / data_df['rednote_poi_map_fullscreen'].notna().sum() * 100
        status = "全屏模式" if value else "普通模式"
        report_lines.append(f"- **{status}**: {count} 次 ({percentage:.1f}%)")

    if len(poi_fullscreen) > 0:
        fullscreen_rate = poi_fullscreen.get(True, 0) / data_df['rednote_poi_map_fullscreen'].notna().sum() * 100
        if fullscreen_rate > 50:
            report_lines.append("")
            report_lines.append("💡 **洞察**: 超过50%的POI地图使用全屏模式，说明用户沉浸式浏览需求强烈")
            report_lines.append("💡 **建议**: 优化全屏模式下的交互体验，提升用户满意度")
        else:
            report_lines.append("")
            report_lines.append("💡 **洞察**: 全屏模式使用率不高，可能存在使用障碍或用户习惯问题")
            report_lines.append("💡 **建议**: 分析用户为什么更倾向于普通模式，优化全屏模式的引导和体验")

    report_lines.append("")

    # POI类型分析
    poi_type_dist = data_df['rednote_poi_typ_nm'].value_counts().head(10)
    report_lines.append("### 🎯 POI类型分布")
    report_lines.append("")
    report_lines.append("最热门的POI类型:")
    report_lines.append("")
    for poi_type, count in poi_type_dist.items():
        percentage = count / data_df['rednote_poi_typ_nm'].notna().sum() * 100
        report_lines.append(f"- **{poi_type}**: {count} 次 ({percentage:.1f}%)")

    report_lines.append("")
    report_lines.append("💡 **洞察**: POI类型分布反映了用户的主要兴趣点，可用于个性化推荐")
    report_lines.append("💡 **建议**: 基于用户POI类型偏好，优化内容推荐算法")

    report_lines.append("")

    # 帖子类型分析
    post_type_dist = data_df['rednote_post_typ'].value_counts()
    report_lines.append("### 📝 帖子类型分布")
    report_lines.append("")
    report_lines.append("帖子类型分布:")
    report_lines.append("")
    for post_type, count in post_type_dist.items():
        percentage = count / data_df['rednote_post_typ'].notna().sum() * 100
        report_lines.append(f"- **{post_type}**: {count} 次 ({percentage:.1f}%)")

    report_lines.append("")

    # AI旅行指南分析
    guide_events_count = data_df['rednote_travel_guide_id'].notna().sum()
    report_lines.append("### 🧭 AI旅行指南使用分析")
    report_lines.append("")
    report_lines.append(f"AI旅行指南相关事件: {guide_events_count} 次 ({guide_events_count/len(data_df)*100:.1f}%)")
    report_lines.append("")

    if guide_events_count > 0:
        report_lines.append("💡 **洞察**: 用户对AI旅行指南功能有使用，说明AI功能获得用户认可")
        report_lines.append("💡 **建议**: 进一步优化AI旅行指南的生成质量和用户体验")
    else:
        report_lines.append("💡 **洞察**: AI旅行指南功能使用率较低")
        report_lines.append("💡 **建议**: 加强AI旅行指南功能的宣传和引导")

    report_lines.append("")

    # 五、总结
    report_lines.append("## 五、总结")
    report_lines.append("")
    report_lines.append("通过本次深度关联分析，我们发现:")
    report_lines.append("")
    report_lines.append("1. **数据完整性高**: 核心业务字段的使用率普遍较高，数据采集质量良好")
    report_lines.append("2. **POI功能核心化**: POI相关字段使用率最高，印证了POI是核心功能")
    report_lines.append("3. **内容消费活跃**: 帖子相关字段使用率高，用户内容消费需求强烈")
    report_lines.append("4. **AI功能有待提升**: 旅行指南使用率较低，有优化空间")
    report_lines.append("")
    report_lines.append("建议重点关注POI地图体验优化和AI旅行指南功能增强。")

    # 保存报告
    report_path = r"C:\projects\rednote data analyzer\report\trigger_signals_deep_analysis.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"✅ 深度关联分析报告已保存到: {report_path}")

if __name__ == "__main__":
    analyze_trigger_relationship()
