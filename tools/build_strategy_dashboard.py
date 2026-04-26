# -*- coding: utf-8 -*-
"""
Strategy Dashboard Builder
自动计算战略指标并创建Strategy看板
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, '.')
from bi.dashboard_store import create_dashboard, save_chart
from bi.data_layer import get_data_manager
from bi.agent import Agent
import json
import os

def main():
    # 初始化数据层
    dm = get_data_manager()
    agent = Agent(dm)

    # 创建Strategy看板
    result = create_dashboard('Strategy')
    print(f'Strategy dashboard created: {result}')

    # 定义战略图表查询列表
    strategy_queries = [
        {
            'name': 'S01 North Star Metrics',
            'question': 'calculate navigation conversion efficiency, navigation confirmation rate, and navigation user penetration rate as three north star metrics',
            'skip_clarification': True
        },
        {
            'name': 'S02 Navigation Efficiency Trend',
            'question': 'daily trend of navigation conversion efficiency, numerator is navigation initiation count, denominator is all CLICK events count',
            'skip_clarification': True
        },
        {
            'name': 'S03 Seeding to Purchase Funnel',
            'question': 'build a 6-step funnel from content exposure to navigation confirmation: content exposure, content click, POI trigger, POI detail, navigation initiation, navigation confirmation, count unique users at each step',
            'skip_clarification': True
        },
        {
            'name': 'S04 Entry Source Comparison',
            'question': 'compare click rate and navigation rate between Discovery page and Porsche+ page',
            'skip_clarification': True
        },
        {
            'name': 'S06 AI Guide Effect',
            'question': 'compare navigation rate between users who used AI travel guide and users who did not use AI travel guide',
            'skip_clarification': True
        },
        {
            'name': 'S09 Nav vs Non-Nav Users',
            'question': 'compare average events, average active days, and average feature breadth between navigation users and non-navigation users',
            'skip_clarification': True
        },
        {
            'name': 'S10 Daily Activity Rate Trend',
            'question': 'daily activity rate trend, numerator is daily DAU, denominator is total unique users in dataset',
            'skip_clarification': True
        },
        {
            'name': 'S11 Hourly Distribution',
            'question': 'hourly distribution of user events',
            'skip_clarification': True
        },
        {
            'name': 'S12 Weekday Weekend Comparison',
            'question': 'compare user behavior between weekday and weekend, including event count, user count, navigation rate',
            'skip_clarification': True
        },
    ]

    # 执行查询并保存图表
    print('\nStarting strategic metrics calculation...')
    charts_saved = []
    for i, q in enumerate(strategy_queries):
        print(f'\n[{i+1}/{len(strategy_queries)}] {q["name"]}...')
        try:
            result = agent.query(q['question'], skip_clarification=q['skip_clarification'])
            if result.get('error'):
                print(f'  Error: {result["error"]}')
                continue

            chart = {
                'id': f's{i+1:02d}',
                'name': q['name'],
                'chart_type': result.get('chart_type', 'table'),
                'chart_option': result.get('chart_option'),
                'sql': result.get('sql'),
                'data': result.get('data', []),
                'summary': result.get('summary', ''),
                'audit': result.get('audit'),
                'query': q['question']
            }

            save_result = save_chart('Strategy', chart)
            print(f'  Saved: {save_result}')
            charts_saved.append(q['name'])
        except Exception as e:
            print(f'  Exception: {e}')

    print(f'\nTotal {len(charts_saved)} charts saved to Strategy dashboard')
    print('Strategic analysis charts generation completed!')

    # 保存执行摘要
    summary = {
        'dashboard': 'Strategy',
        'charts_count': len(charts_saved),
        'charts_saved': charts_saved,
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }

    with open('report/fulldata_v2/strategy_dashboard_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print('Summary saved to strategy_dashboard_summary.json')

if __name__ == '__main__':
    main()