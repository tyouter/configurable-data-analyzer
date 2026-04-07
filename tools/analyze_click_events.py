# -*- coding: utf-8 -*-
"""
小红书用户点击事件分析工具
分析 span_nm 列的详细数据，提供基础统计和业务洞察
"""
import pandas as pd
import numpy as np
from collections import Counter
import json
import sys
import io

# 设置标准输出为 UTF-8 编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def analyze_span_nm(file_path):
    """分析 span_nm 列的详细数据"""
    print("=" * 60)
    print("小红书用户点击事件数据分析报告")
    print("=" * 60)

    # 读取数据
    print(f"\n正在读取数据文件: {file_path}")
    df = pd.read_excel(file_path)
    print(f"数据加载完成！共 {len(df)} 行，{len(df.columns)} 列")

    # 检查 span_nm 列是否存在
    if 'span_nm' not in df.columns:
        print("\n错误：数据中没有 'span_nm' 列")
        print(f"\n可用列名: {list(df.columns)}")
        return

    # 基础统计
    print("\n" + "=" * 60)
    print("一、基础统计信息")
    print("=" * 60)

    total_events = len(df)
    span_nm_column = df['span_nm']
    non_null_events = span_nm_column.notna().sum()
    null_events = span_nm_column.isna().sum()

    print(f"\n总事件数: {total_events:,}")
    print(f"span_nm 非空事件数: {non_null_events:,}")
    print(f"span_nm 空值事件数: {null_events:,}")
    print(f"数据完整率: {non_null_events/total_events*100:.2f}%")

    # span_nm 值分布
    print("\n" + "=" * 60)
    print("二、span_nm 值分布 Top 50")
    print("=" * 60)

    span_nm_counts = span_nm_column.value_counts().head(50)
    print(f"\n共有 {span_nm_column.nunique()} 个唯一的 span_nm 值\n")
    print("排名\t事件数\t占比\t\tspan_nm")
    print("-" * 80)
    for idx, (span_nm, count) in enumerate(span_nm_counts.items(), 1):
        percentage = count / non_null_events * 100
        print(f"{idx}\t{count:,}\t{percentage:.2f}%\t\t{str(span_nm)[:50]}")

    # span_nm 长度分布
    print("\n" + "=" * 60)
    print("三、span_nm 文本长度分布")
    print("=" * 60)

    span_nm_lengths = span_nm_column[span_nm_column.notna()].str.len()
    print(f"\n平均长度: {span_nm_lengths.mean():.2f} 字符")
    print(f"中位数长度: {span_nm_lengths.median():.2f} 字符")
    print(f"最大长度: {span_nm_lengths.max()} 字符")
    print(f"最小长度: {span_nm_lengths.min()} 字符")
    print(f"标准差: {span_nm_lengths.std():.2f} 字符")

    # 长度分布桶
    print("\n长度分布:")
    length_bins = [0, 10, 20, 50, 100, 200, float('inf')]
    length_labels = ['0-10', '11-20', '21-50', '51-100', '101-200', '200+']
    length_dist = pd.cut(span_nm_lengths, bins=length_bins, labels=length_labels).value_counts().sort_index()
    for length_range, count in length_dist.items():
        print(f"  {length_range} 字符: {count:,} ({count/len(span_nm_lengths)*100:.2f}%)")

    # 特殊模式分析
    print("\n" + "=" * 60)
    print("四、特殊模式分析")
    print("=" * 60)

    # 检查常见的 span_nm 模式
    patterns = {
        '包含数字': span_nm_column[span_nm_column.notna()].str.contains(r'\d', regex=True).sum(),
        '包含下划线': span_nm_column[span_nm_column.notna()].str.contains('_', regex=True).sum(),
        '包含冒号': span_nm_column[span_nm_column.notna()].str.contains(':', regex=True).sum(),
        '包含点号': span_nm_column[span_nm_column.notna()].str.contains(r'\.', regex=True).sum(),
        '包含中文': span_nm_column[span_nm_column.notna()].str.contains(r'[\u4e00-\u9fff]', regex=True).sum(),
        '纯英文': span_nm_column[span_nm_column.notna()].str.match(r'^[a-zA-Z_\.:\-]+$').sum()
    }

    for pattern, count in patterns.items():
        if count > 0:
            print(f"{pattern}: {count:,} ({count/non_null_events*100:.2f}%)")

    # 如果存在 user_id 列，进行用户维度分析
    if 'user_id' in df.columns or 'user' in df.columns or 'user_id:' in df.columns:
        print("\n" + "=" * 60)
        print("五、用户维度分析")
        print("=" * 60)

        user_col = None
        for col in ['user_id', 'user', 'user_id:']:
            if col in df.columns:
                user_col = col
                break

        if user_col:
            unique_users = df[user_col].nunique()
            print(f"\n总用户数: {unique_users:,}")
            print(f"平均每用户事件数: {total_events/unique_users:.2f}")

            # 用户行为多样性分析
            user_span_nm_diversity = df.groupby(user_col)['span_nm'].nunique()
            print(f"\n用户行为多样性:")
            print(f"  平均每用户不同的 span_nm 数: {user_span_nm_diversity.mean():.2f}")
            print(f"  中位数: {user_span_nm_diversity.median():.2f}")
            print(f"  最大: {user_span_nm_diversity.max()}")
            print(f"  最小: {user_span_nm_diversity.min()}")

    # 如果存在时间戳列，进行时间维度分析
    timestamp_cols = ['timestamp', 'time', 'event_time', 'created_at', 'log_time']
    timestamp_col = None
    for col in timestamp_cols:
        if col in df.columns:
            timestamp_col = col
            break

    if timestamp_col:
        print("\n" + "=" * 60)
        print("六、时间维度分析")
        print("=" * 60)

        try:
            df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
            df_valid_time = df[df[timestamp_col].notna()]

            if len(df_valid_time) > 0:
                print(f"\n时间范围: {df_valid_time[timestamp_col].min()} 到 {df_valid_time[timestamp_col].max()}")
                print(f"时间跨度: {(df_valid_time[timestamp_col].max() - df_valid_time[timestamp_col].min()).days} 天")

                # 按小时分布
                df_valid_time['hour'] = df_valid_time[timestamp_col].dt.hour
                hourly_dist = df_valid_time['hour'].value_counts().sort_index()

                print(f"\n24小时事件分布:")
                for hour, count in hourly_dist.items():
                    bar_length = int(count / hourly_dist.max() * 50)
                    bar = '█' * bar_length
                    print(f"  {hour:02d}:00 - {hour:02d}:59 {bar} {count:,}")
        except Exception as e:
            print(f"\n时间解析错误: {e}")

    # 业务洞察
    print("\n" + "=" * 60)
    print("七、业务洞察与建议")
    print("=" * 60)

    insights = []

    # 热门事件分析
    top_5_span_nm = span_nm_counts.head(5)
    total_top5 = top_5_span_nm.sum()
    insights.append(f"• 核心事件集中度高：前5个 span_nm 占比 {total_top5/non_null_events*100:.2f}%")
    insights.append(f"• 最热门事件 '{list(top_5_span_nm.index)[0]}' 占比 {top_5_span_nm.iloc[0]/non_null_events*100:.2f}%")

    # 长尾分析
    long_tail_events = (span_nm_counts.iloc[5:].sum() if len(span_nm_counts) > 5 else 0)
    insights.append(f"• 长尾效应明显：除了Top5，还有 {len(span_nm_counts)-5 if len(span_nm_counts) > 5 else 0} 个不同的事件类型")

    # 数据质量
    if null_events / total_events > 0.1:
        insights.append(f"• 数据质量问题：{null_events/total_events*100:.2f}% 的事件缺少 span_nm 值，建议检查埋点逻辑")
    else:
        insights.append(f"• 数据质量良好：仅 {null_events/total_events*100:.2f}% 的事件缺少 span_nm 值")

    # 命名规范洞察
    if patterns['纯英文'] / non_null_events > 0.8:
        insights.append("• 命名规范：大部分 span_nm 采用英文命名，建议统一使用驼峰或下划线命名")
    if patterns['包含下划线'] / non_null_events > 0.5:
        insights.append("• 命名模式：广泛使用下划线分隔，可能采用模块.功能.动作的命名结构")

    for insight in insights:
        print(f"\n{insight}")

    # 保存详细数据到文件
    print("\n" + "=" * 60)
    print("八、数据导出")
    print("=" * 60)

    # 导出 span_nm 分布
    export_path = 'span_nm_distribution.csv'
    span_nm_column.value_counts().to_csv(export_path, encoding='utf-8-sig')
    print(f"\n已导出 span_nm 分布数据到: {export_path}")

    # 导出原始 span_nm 列表（去重）
    unique_span_nm_path = 'unique_span_nm.txt'
    with open(unique_span_nm_path, 'w', encoding='utf-8') as f:
        for span_nm in span_nm_column.dropna().unique():
            f.write(f"{span_nm}\n")
    print(f"已导出唯一 span_nm 列表到: {unique_span_nm_path}")

    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)

if __name__ == "__main__":
    file_path = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"
    analyze_span_nm(file_path)
