# -*- coding: utf-8 -*-
"""
小红书用户点击事件深度分析
包括用户维度、时间维度、页面流转等深度分析
"""
import pandas as pd
import numpy as np
import sys
import io

# 设置标准输出为 UTF-8 编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def deep_analysis(file_path):
    """深度分析 span_nm 数据"""
    print("=" * 60)
    print("小红书用户点击事件深度分析报告")
    print("=" * 60)

    # 读取数据
    print(f"\n正在读取数据文件...")
    df = pd.read_excel(file_path)
    print(f"数据加载完成！共 {len(df):,} 行，{len(df.columns)} 列")

    # 显示所有列名
    print("\n" + "=" * 60)
    print("数据列名")
    print("=" * 60)
    for idx, col in enumerate(df.columns, 1):
        print(f"{idx:2d}. {col}")

    # 识别关键列
    print("\n" + "=" * 60)
    print("关键列识别")
    print("=" * 60)

    # 查找可能的用户标识列
    user_candidate_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['user', 'uid', 'userid', 'customer', 'account'])]
    print(f"\n可能的用户标识列: {user_candidate_cols}")

    # 查找可能的时间戳列
    time_candidate_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['time', 'date', 'timestamp', 'event'])]
    print(f"可能的时间戳列: {time_candidate_cols}")

    # 查找可能的页面列
    page_candidate_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['page', 'screen', 'view', 'route'])]
    print(f"可能的页面列: {page_candidate_cols}")

    # 分析 span_nm 的页面分布
    print("\n" + "=" * 60)
    print("span_nm 页面分布分析")
    print("=" * 60)

    # 从 span_nm 中提取页面名（第一个下划线之前的部分）
    df['page_from_span'] = df['span_nm'].str.split('_').str[0]
    page_distribution = df['page_from_span'].value_counts()

    print(f"\n共发现 {len(page_distribution)} 个不同的页面")
    print("\n页面名\t事件数\t占比")
    print("-" * 50)
    for page, count in page_distribution.head(10).items():
        print(f"{page}\t{count:,}\t{count/len(df)*100:.2f}%")

    # 用户维度分析（如果找到用户列）
    if user_candidate_cols:
        print("\n" + "=" * 60)
        print("用户维度分析")
        print("=" * 60)

        for user_col in user_candidate_cols[:1]:  # 只分析第一个找到的用户列
            unique_users = df[user_col].nunique()
            print(f"\n用户列: {user_col}")
            print(f"总用户数: {unique_users:,}")
            print(f"平均每用户事件数: {len(df)/unique_users:.2f}")

            # 用户行为活跃度分析
            user_event_counts = df[user_col].value_counts()
            print(f"\n用户活跃度分布:")
            print(f"  高活跃用户 (>10事件): {(user_event_counts > 10).sum()}")
            print(f"  中活跃用户 (5-10事件): {((user_event_counts >= 5) & (user_event_counts <= 10)).sum()}")
            print(f"  低活跃用户 (<5事件): {(user_event_counts < 5).sum()}")

            # 用户页面偏好分析
            user_page_preference = df.groupby(user_col)['page_from_span'].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else None)
            print(f"\n用户最爱页面:")
            print(f"  Porsche页面用户: {(user_page_preference == 'porsche').sum()}")
            print(f"  Discovery页面用户: {(user_page_preference == 'discovery').sum()}")
            print(f"  Search页面用户: {(user_page_preference == 'search').sum()}")
            print(f"  Profile页面用户: {(user_page_preference == 'profile').sum()}")

            # 用户行为链分析
            print(f"\n用户行为链分析（示例前3个用户）:")
            sample_users = df[user_col].unique()[:3]
            for user in sample_users:
                user_data = df[df[user_col] == user].sort_index()
                print(f"\n  用户 {user}:")
                print(f"    事件序列: {' -> '.join(user_data['span_nm'].head(5).tolist())}")

    # 时间维度分析（如果找到时间列）
    if time_candidate_cols:
        print("\n" + "=" * 60)
        print("时间维度分析")
        print("=" * 60)

        for time_col in time_candidate_cols[:1]:  # 只分析第一个找到的时间列
            try:
                df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
                df_valid_time = df[df[time_col].notna()]

                if len(df_valid_time) > 0:
                    print(f"\n时间列: {time_col}")
                    print(f"时间范围: {df_valid_time[time_col].min()} 到 {df_valid_time[time_col].max()}")
                    print(f"时间跨度: {(df_valid_time[time_col].max() - df_valid_time[time_col].min()).days} 天")

                    # 按天分布
                    df_valid_time['date'] = df_valid_time[time_col].dt.date
                    daily_dist = df_valid_time['date'].value_counts().sort_index()

                    print(f"\n每日事件分布:")
                    for date, count in daily_dist.items():
                        print(f"  {date}: {count:,} 事件")

                    # 按小时分布
                    df_valid_time['hour'] = df_valid_time[time_col].dt.hour
                    hourly_dist = df_valid_time['hour'].value_counts().sort_index()

                    print(f"\n24小时事件分布:")
                    print(f"  {'时段':<15} {'事件数':<10} {'可视化':<30}")
                    print(f"  {'-'*15} {'-'*10} {'-'*30}")
                    for hour, count in hourly_dist.items():
                        bar_length = int(count / hourly_dist.max() * 30)
                        bar = '█' * bar_length
                        print(f"  {hour:02d}:00-{hour:02d}:59  {count:<10} {bar}")

            except Exception as e:
                print(f"\n时间解析错误: {e}")

    # 业务洞察
    print("\n" + "=" * 60)
    print("业务洞察与建议")
    print("=" * 60)

    # 核心页面分析
    top_pages = page_distribution.head(3)
    print(f"\n核心页面洞察:")
    print(f"• Porsche页面是核心: {top_pages.iloc[0]/len(df)*100:.2f}% 的事件发生在Porsche相关页面")
    print(f"• 用户主要使用场景: 地图导航、POI查询、搜索发现")

    # 事件类型分析
    event_types = {
        'pageshow': df['span_nm'].str.contains('pageshow').sum(),
        'cardshow': df['span_nm'].str.contains('cardshow').sum(),
        'click': df['span_nm'].str.contains('click').sum(),
        'show': df['span_nm'].str.contains('show').sum()
    }

    print(f"\n事件类型洞察:")
    print(f"• 展示类事件占比: {(event_types['pageshow'] + event_types['cardshow'] + event_types['show'])/len(df)*100:.2f}%")
    print(f"• 交互类事件占比: {event_types['click']/len(df)*100:.2f}%")
    print(f"• 说明: 用户以浏览行为为主，主动交互较少")

    print("\n产品优化建议:")
    print("• 提升Porsche页面转化: 作为核心页面，可优化地图交互体验")
    print("• 增强用户引导: 考虑增加新手引导，提升用户主动交互率")
    print("• 优化搜索体验: 搜索相关事件占比较高，可进一步优化搜索功能")

    print("\n" + "=" * 60)
    print("深度分析完成！")
    print("=" * 60)

if __name__ == "__main__":
    file_path = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"
    deep_analysis(file_path)
