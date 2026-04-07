# -*- coding: utf-8 -*-
"""
用户行为路径分析工具
分析用户在应用中的行为序列和页面流转路径
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

def analyze_user_behavior_paths(file_path):
    """分析用户行为路径"""
    print("=" * 80)
    print("用户行为路径分析报告")
    print("=" * 80)

    # 读取数据
    print(f"\n正在读取数据文件: {file_path}")
    df = pd.read_excel(file_path)
    print(f"数据加载完成！共 {len(df):,} 行")

    # 检查用户标识列
    user_col = None
    for col in ['reduser_id', 'user_id', 'user']:
        if col in df.columns:
            user_col = col
            break

    if user_col is None:
        print("\n警告: 未找到用户标识列，将尝试使用其他列")
        user_col = 'dvc_id'  # 使用设备ID作为替代

    print(f"\n用户标识列: {user_col}")

    # 按用户分组并按时间排序
    print("\n正在按用户分组并排序...")
    user_groups = df.groupby(user_col)

    # 获取每个用户的事件序列
    user_sequences = {}
    for user, group in user_groups:
        # 按时间戳排序
        group = group.sort_values('strt_time_nano')
        sequence = group['span_nm'].tolist()
        user_sequences[user] = sequence

    # 分析用户行为路径
    print("\n" + "=" * 80)
    print("一、用户行为路径分析")
    print("=" * 80)

    # 计算用户数量
    user_count = len(user_sequences)
    print(f"\n总用户数: {user_count}")

    # 分析用户行为序列
    sequence_length = []
    for user, seq in user_sequences.items():
        if len(seq) > 1:
            sequence_length.append(len(seq))

    if sequence_length:
        avg_sequence_length = np.mean(sequence_length)
        max_sequence_length = np.max(sequence_length)
        min_sequence_length = np.min(sequence_length)
        print(f"\n用户行为序列平均长度: {avg_sequence_length:.1f} 事件")
        print(f"最长行为序列: {max_sequence_length} 事件")
        print(f"最短行为序列: {min_sequence_length} 事件")

    # 分析用户主要行为路径
    print(f"\n分析 {min(user_count, 10)} 个用户的行为路径...")
    sample_users = list(user_sequences.keys())[:min(user_count, 10)]

    path_analysis = defaultdict(int)
    for user in sample_users:
        seq = user_sequences[user]
        for i in range(len(seq)-1):
            path = f"{seq[i]} -> {seq[i+1]}"
            path_analysis[path] += 1

    # 显示主要路径
    print("\n主要用户行为路径 (Top 10):")
    sorted_paths = sorted(path_analysis.items(), key=lambda x: x[1], reverse=True)[:10]
    for path, count in sorted_paths:
        print(f"  {path}: {count} 次")

    # 生成用户行为路径报告
    print("\n" + "=" * 80)
    print("二、用户行为路径报告")
    print("=" * 80)

    report_lines = []
    report_lines.append("# 用户行为路径分析报告")
    report_lines.append("")
    report_lines.append(f"**生成时间**: 2026-04-07")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # 用户数量统计
    report_lines.append("## 一、用户统计")
    report_lines.append("")
    report_lines.append(f"- **总用户数**: {user_count}")
    report_lines.append(f"- **分析用户数**: {len(sample_users)} (前 {min(user_count, 10)} 个用户)")
    report_lines.append("")

    # 用户行为序列统计
    if sequence_length:
        report_lines.append(f"- **平均行为序列长度**: {avg_sequence_length:.1f} 事件")
        report_lines.append(f"- **最长行为序列**: {max_sequence_length} 事件")
        report_lines.append(f"- **最短行为序列**: {min_sequence_length} 事件")
    else:
        report_lines.append("- **用户行为序列统计**: 无法计算 (所有用户行为序列长度为1)")

    # 主要行为路径
    report_lines.append("## 二、主要用户行为路径")
    report_lines.append("")
    report_lines.append("以下是用户最常走的路径 (Top 10):")
    report_lines.append("")

    for path, count in sorted_paths:
        report_lines.append(f"- **{path}** ({count} 次)")

    # 页面流转分析
    print("\n" + "=" * 80)
    print("三、页面流转分析")
    print("=" * 80)

    # 计算页面流转矩阵
    page_counts = df['page'].value_counts()
    print(f"\n页面分布:")
    for page, count in page_counts.head(10).items():
        percentage = count / len(df) * 100
        report_lines.append(f"- **{page}**: {count:,} 次 ({percentage:.1f}%)")

    # 计算页面间的流转
    page_flow = defaultdict(lambda: defaultdict(int))
    for user, group in user_groups:
        if len(group) > 1:
            for i in range(len(group)-1):
                from_page = group.iloc[i]['page']
                to_page = group.iloc[i+1]['page']
                page_flow[from_page][to_page] += 1

    # 显示主要页面流转
    report_lines.append("## 三、页面流转分析")
    report_lines.append("")
    report_lines.append("主要页面流转 (Top 10):")
    report_lines.append("")

    for from_page, to_counts in page_flow.items():
        sorted_to_pages = sorted(to_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        for to_page, count in sorted_to_pages:
            if from_page != to_page:
                percentage = count / page_flow[from_page].sum() * 100
                report_lines.append(f"- **{from_page} → {to_page}**: {count:,} 次 ({percentage:.1f}%)")

    # 保存报告
    report_path = r"C:\projects\rednote data analyzer\report\user_behavior_path_analysis.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"\n✅ 用户行为路径分析报告已保存到: {report_path}")

if __name__ == "__main__":
    file_path = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"
    analyze_user_behavior_paths(file_path)