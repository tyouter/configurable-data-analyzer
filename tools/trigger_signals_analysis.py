# -*- coding: utf-8 -*-
"""
Trigger信号定义分析工具
分析trigger signals与数据表头的关联关系
"""
import pandas as pd
import numpy as np
import sys
import io
import re
from collections import defaultdict

# 设置标准输出为 UTF-8 编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def analyze_trigger_signals(trigger_file, data_file):
    """分析trigger signals与数据表头的关联"""

    print("=" * 80)
    print("Trigger信号定义与数据关联分析")
    print("=" * 80)

    # 读取trigger signals定义文件
    print(f"\n正在读取trigger signals定义文件...")
    try:
        trigger_df = pd.read_excel(trigger_file)
        print(f"Trigger signals文件读取成功！共 {len(trigger_df)} 行，{len(trigger_df.columns)} 列")
    except Exception as e:
        print(f"读取trigger signals文件失败: {e}")
        return

    # 读取数据文件
    print(f"\n正在读取数据文件...")
    try:
        data_df = pd.read_excel(data_file)
        print(f"数据文件读取成功！共 {len(data_df)} 行，{len(data_df.columns)} 列")
    except Exception as e:
        print(f"读取数据文件失败: {e}")
        return

    # 显示trigger signals文件的结构
    print("\n" + "=" * 80)
    print("一、Trigger Signals文件结构")
    print("=" * 80)

    print(f"\n列名列表:")
    for idx, col in enumerate(trigger_df.columns, 1):
        print(f"  {idx:2d}. {col}")

    # 查找关键列
    print(f"\n关键列识别:")
    potential_trigger_col = None
    potential_field_col = None

    for col in trigger_df.columns:
        col_lower = col.lower()
        if 'trigger' in col_lower or 'signal' in col_lower or 'event' in col_lower or 'span' in col_lower:
            potential_trigger_col = col
            print(f"  可能的Trigger列: {col}")
        if 'field' in col_lower or 'column' in col_lower or 'name' in col_lower or 'parameter' in col_lower:
            potential_field_col = col
            print(f"  可能的字段列: {col}")

    # 显示trigger signals数据内容
    print("\n" + "=" * 80)
    print("二、Trigger Signals数据内容")
    print("=" * 80)

    print("\n前20行数据:")
    print(trigger_df.head(20).to_string())

    # 显示数据文件的列名
    print("\n" + "=" * 80)
    print("三、数据文件列名")
    print("=" * 80)

    print(f"\n共 {len(data_df.columns)} 个列:")
    for idx, col in enumerate(data_df.columns, 1):
        non_null_count = data_df[col].notna().sum()
        print(f"  {idx:2d}. {col:<50} (非空: {non_null_count:4,}/{len(data_df):4,})")

    # 分析列之间的关联
    print("\n" + "=" * 80)
    print("四、Trigger信号与数据列关联分析")
    print("=" * 80)

    # 尝试从trigger_df中提取trigger名称和对应字段
    trigger_field_mapping = defaultdict(list)

    if potential_trigger_col and potential_field_col:
        for _, row in trigger_df.iterrows():
            trigger_name = str(row[potential_trigger_col]) if pd.notna(row[potential_trigger_col]) else ""
            field_name = str(row[potential_field_col]) if pd.notna(row[potential_field_col]) else ""

            if trigger_name and field_name and trigger_name != 'nan' and field_name != 'nan':
                trigger_field_mapping[trigger_name].append(field_name)

        if trigger_field_mapping:
            print(f"\n找到 {len(trigger_field_mapping)} 个trigger信号定义:")
            print(f"{'Trigger信号':<60} {'关联字段'}")
            print("-" * 100)

            for trigger, fields in sorted(trigger_field_mapping.items())[:20]:
                print(f"{trigger:<60} {', '.join(fields)}")
        else:
            print("\n未能从trigger signals文件中解析出trigger-字段映射关系")
            print("将采用其他方式分析...")

    # 分析数据中的span_nm与表头的关系
    print("\n" + "=" * 80)
    print("五、span_nm事件与数据表头的语义关联分析")
    print("=" * 80)

    # 提取span_nm中的关键词
    data_df['page'] = data_df['span_nm'].str.split('_').str[0]
    data_df['action'] = data_df['span_nm'].str.split('_').str[-1]

    # 分析每个表头列在不同span_nm事件中的使用情况
    print(f"\n分析各个数据列在不同事件中的使用情况:")

    # 找到非span_nm的列
    other_columns = [col for col in data_df.columns if col != 'span_nm']

    # 分析POI相关事件中的表头使用
    poi_events = data_df[data_df['span_nm'].str.contains('poi', case=False)]
    if len(poi_events) > 0:
        print(f"\n📍 POI相关事件 ({len(poi_events)} 条) 的表头使用:")
        for col in other_columns:
            non_null_in_poi = poi_events[col].notna().sum()
            if non_null_in_poi > 0:
                usage_rate = non_null_in_poi / len(poi_events) * 100
                unique_values = poi_events[col].nunique()
                print(f"  {col:<50} 使用率: {usage_rate:5.1f}%  唯一值: {unique_values:3d}")

    # 分析帖子相关事件中的表头使用
    post_events = data_df[data_df['span_nm'].str.contains('post', case=False)]
    if len(post_events) > 0:
        print(f"\n📝 帖子相关事件 ({len(post_events)} 条) 的表头使用:")
        for col in other_columns:
            non_null_in_post = post_events[col].notna().sum()
            if non_null_in_post > 0:
                usage_rate = non_null_in_post / len(post_events) * 100
                unique_values = post_events[col].nunique()
                print(f"  {col:<50} 使用率: {usage_rate:5.1f}%  唯一值: {unique_values:3d}")

    # 分析地图相关事件中的表头使用
    map_events = data_df[data_df['span_nm'].str.contains('map', case=False)]
    if len(map_events) > 0:
        print(f"\n🗺️  地图相关事件 ({len(map_events)} 条) 的表头使用:")
        for col in other_columns:
            non_null_in_map = map_events[col].notna().sum()
            if non_null_in_map > 0:
                usage_rate = non_null_in_map / len(map_events) * 100
                unique_values = map_events[col].nunique()
                print(f"  {col:<50} 使用率: {usage_rate:5.1f}%  唯一值: {unique_values:3d}")

    # 分析搜索相关事件中的表头使用
    search_events = data_df[data_df['span_nm'].str.contains('search', case=False)]
    if len(search_events) > 0:
        print(f"\n🔍 搜索相关事件 ({len(search_events)} 条) 的表头使用:")
        for col in other_columns:
            non_null_in_search = search_events[col].notna().sum()
            if non_null_in_search > 0:
                usage_rate = non_null_in_search / len(search_events) * 100
                unique_values = search_events[col].nunique()
                print(f"  {col:<50} 使用率: {usage_rate:5.1f}%  唯一值: {unique_values:3d}")

    # 生成关联说明书
    print("\n" + "=" * 80)
    print("六、数据关联说明书生成")
    print("=" * 80)

    relationship_doc = generate_relationship_documentation(data_df, poi_events, post_events, map_events, search_events)

    print("\n✅ 数据关联说明书已生成！")

    return data_df, trigger_df, relationship_doc

def generate_relationship_documentation(data_df, poi_events, post_events, map_events, search_events):
    """生成数据关联说明书"""

    doc = []
    doc.append("# 数据字段关联说明书")
    doc.append("")
    doc.append("本文档详细说明了小红书点击事件数据中各字段与事件类型的关联关系。")
    doc.append("")
    doc.append("---")
    doc.append("")

    # 字段分类
    basic_fields = ['dvc_id', 'pltfm', 'span_nm', 'span_kind', 'strt_time_nano', 'end_time_nano', 'reduser_id']
    user_fields = ['reduser_id', 'rednote_user_logging_status', 'user_ip']
    post_fields = ['rednote_post_num', 'rednote_post_title', 'rednote_post_typ', 'rednote_post_is_like',
                   'rednote_post_follow', 'rednote_post_is_op_rec', 'rednote_post_is_recuser',
                   'rednote_post_hashtag_title', 'rednote_post_is_save']
    poi_fields = ['rednote_poi_map_fullscreen', 'rednote_poi_title', 'rednote_poi_typ', 'rednote_poi_typ_nm']
    video_fields = ['rednote_video_post_is_play', 'rednote_video_post_autoplay_is_open', 'rednote_video_post_play_speed']
    guide_fields = ['rednote_travel_guide_id', 'rednote_travel_guide_title', 'rednote_travel_post_is_succ']

    # 基础字段说明
    doc.append("## 一、基础字段")
    doc.append("")
    for field in basic_fields:
        if field in data_df.columns:
            usage = data_df[field].notna().sum()
            unique = data_df[field].nunique()
            doc.append(f"### {field}")
            doc.append(f"- **描述**: {get_field_description(field)}")
            doc.append(f"- **数据完整率**: {usage/len(data_df)*100:.2f}%")
            doc.append(f"- **唯一值数量**: {unique}")
            doc.append("")

    # 帖子相关字段
    doc.append("## 二、帖子相关字段")
    doc.append("")
    doc.append("这些字段主要在帖子详情页、发现页、搜索结果页等与帖子内容相关的事件中出现。")
    doc.append("")
    for field in post_fields:
        if field in data_df.columns:
            if len(post_events) > 0:
                usage = post_events[field].notna().sum()
                usage_rate = usage/len(post_events)*100 if len(post_events) > 0 else 0
                unique = post_events[field].nunique()

                doc.append(f"### {field}")
                doc.append(f"- **描述**: {get_field_description(field)}")
                doc.append(f"- **在帖子事件中使用率**: {usage_rate:.2f}%")
                doc.append(f"- **唯一值数量**: {unique}")
                if unique <= 10 and unique > 0:
                    doc.append(f"- **可能的取值**: {list(post_events[field].dropna().unique())}")
                doc.append("")

    # POI相关字段
    doc.append("## 三、POI (兴趣点) 相关字段")
    doc.append("")
    doc.append("这些字段主要在Porsche地图页面、POI详情页等与地理信息相关的事件中出现。")
    doc.append("")
    for field in ['rednote_poi_map_fullscreen', 'rednote_poi_title', 'rednote_poi_typ', 'rednote_poi_typ_nm']:
        if field in data_df.columns:
            if len(poi_events) > 0:
                usage = poi_events[field].notna().sum()
                usage_rate = usage/len(poi_events)*100 if len(poi_events) > 0 else 0
                unique = poi_events[field].nunique()

                doc.append(f"### {field}")
                doc.append(f"- **描述**: {get_field_description(field)}")
                doc.append(f"- **在POI事件中使用率**: {usage_rate:.2f}%")
                doc.append(f"- **唯一值数量**: {unique}")
                if unique <= 10 and unique > 0:
                    doc.append(f"- **可能的取值**: {list(poi_events[field].dropna().unique())}")
                doc.append("")

    # 视频相关字段
    doc.append("## 四、视频相关字段")
    doc.append("")
    doc.append("这些字段主要在视频帖子相关的事件中出现。")
    doc.append("")
    for field in video_fields:
        if field in data_df.columns:
            usage = data_df[field].notna().sum()
            usage_rate = usage/len(data_df)*100
            unique = data_df[field].nunique()

            doc.append(f"### {field}")
            doc.append(f"- **描述**: {get_field_description(field)}")
            doc.append(f"- **数据完整率**: {usage_rate:.2f}%")
            doc.append(f"- **唯一值数量**: {unique}")
            if unique <= 10 and unique > 0:
                doc.append(f"- **可能的取值**: {list(data_df[field].dropna().unique())}")
            doc.append("")

    # 旅行指南相关字段
    doc.append("## 五、旅行指南相关字段")
    doc.append("")
    doc.append("这些字段主要在AI旅行指南相关的事件中出现。")
    doc.append("")
    for field in guide_fields:
        if field in data_df.columns:
            usage = data_df[field].notna().sum()
            usage_rate = usage/len(data_df)*100
            unique = data_df[field].nunique()

            doc.append(f"### {field}")
            doc.append(f"- **描述**: {get_field_description(field)}")
            doc.append(f"- **数据完整率**: {usage_rate:.2f}%")
            doc.append(f"- **唯一值数量**: {unique}")
            if unique <= 10 and unique > 0:
                doc.append(f"- **可能的取值**: {list(data_df[field].dropna().unique())}")
            doc.append("")

    # 保存文档
    doc_path = "report/data_field_relationship_guide.md"
    with open(doc_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(doc))

    print(f"✅ 数据关联说明书已保存到: {doc_path}")

    return '\n'.join(doc)

def get_field_description(field_name):
    """获取字段描述"""

    descriptions = {
        'dvc_id': '设备ID，用于标识唯一设备',
        'pltfm': '平台信息（iOS/Android等）',
        'span_nm': 'Span名称，用于标识具体的事件类型',
        'span_kind': 'Span类型，用于分类事件',
        'strt_time_nano': '开始时间（纳秒级时间戳）',
        'end_time_nano': '结束时间（纳秒级时间戳）',
        'reduser_id': '小红书用户ID',
        'resource_attr': '资源属性',
        'screen_size': '屏幕尺寸',
        'disp_id': '展示ID',
        'user_ip': '用户IP地址',
        'event_typ': '事件类型',
        'page_strt_time': '页面开始时间',
        'page_end_time': '页面结束时间',
        'referer_page': '来源页面',
        'rednote_prfl_typ': '小红书个人资料类型',
        'rednote_search_result_tab_title': '搜索结果标签标题',
        'rednote_user_logging_status': '用户登录状态',
        'rednote_post_num': '帖子编号',
        'rednote_post_title': '帖子标题',
        'rednote_post_typ': '帖子类型',
        'rednote_post_is_like': '帖子是否被点赞',
        'rednote_post_follow': '帖子关注状态',
        'rednote_post_is_op_rec': '帖子是否为运营推荐',
        'rednote_post_is_recuser': '帖子是否推荐用户',
        'rednote_post_hashtag_title': '帖子话题标签标题',
        'rednote_post_is_save': '帖子是否被收藏',
        'rednote_poi_map_fullscreen': 'POI地图是否全屏显示',
        'rednote_poi_title': 'POI标题',
        'rednote_poi_typ': 'POI类型',
        'rednote_poi_typ_nm': 'POI类型名称',
        'rednote_video_post_is_play': '视频帖子是否播放',
        'rednote_video_post_autoplay_is_open': '视频帖子自动播放是否开启',
        'rednote_video_post_play_speed': '视频帖子播放速度',
        'rednote_travel_guide_id': '旅行指南ID',
        'rednote_travel_guide_title': '旅行指南标题',
        'rednote_travel_post_is_succ': '旅行帖子是否成功'
    }

    return descriptions.get(field_name, '暂无描述')

if __name__ == "__main__":
    trigger_file = r"C:\projects\rednote data analyzer\data\rednote\trigger signals definition.xlsx"
    data_file = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"

    analyze_trigger_signals(trigger_file, data_file)
