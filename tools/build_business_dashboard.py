# -*- coding: utf-8 -*-
"""
Business Dashboard Builder
商业化战略分析看板生成器
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
    # 初始化
    dm = get_data_manager()
    agent = Agent(dm)

    # 创建Business看板
    result = create_dashboard('Business')
    print(f'Business dashboard created: {result}')

    # 心动旅程模块 (B01-B05)
    journey_queries = [
        {
            'name': 'B01 Active User Trend',
            'question': 'daily and weekly active users trend with activity rate, mark weekend and holiday days separately',
            'skip_clarification': True
        },
        {
            'name': 'B02 Path1 Discovery Funnel',
            'question': 'build funnel for path 1 from Discovery page: post card show -> post detail -> POI exposure -> POI visit -> navigation click -> navigation confirm, count events not users',
            'skip_clarification': True
        },
        {
            'name': 'B03 Navigation User Profile',
            'question': 'analyze navigation users profile including POI type preference, hourly usage distribution, search behavior, and compare with non-navigation users on metrics like like, save, AI guide, share',
            'skip_clarification': True
        },
        {
            'name': 'B04 Navigation Retention',
            'question': 'calculate day 7 and day 14 retention rate for users who initiated navigation, use highest navigation day as first day baseline',
            'skip_clarification': True
        },
        {
            'name': 'B05 AI Guide Pull Effect',
            'question': 'compare navigation rate between AI travel guide users and non-AI users, calculate pull multiplier ratio',
            'skip_clarification': True
        },
    ]

    # AI拉动效应模块 (B06-B10)
    ai_queries = [
        {
            'name': 'B06 Operation vs Non-Op AI Funnel',
            'question': 'compare funnel from operation position vs non-operation position to AI travel guide generation and navigation completion',
            'skip_clarification': True
        },
        {
            'name': 'B07 AI Share Path Funnel',
            'question': 'build funnel for AI travel guide sharing path: generate -> view -> share -> accept -> navigate, find bottleneck',
            'skip_clarification': True
        },
        {
            'name': 'B09 AI POI Type Feature',
            'question': 'compare POI type distribution between AI travel guide generated POIs and non-AI navigation POIs, find significant differences',
            'skip_clarification': True
        },
        {
            'name': 'B10 Reverse Generation Feasibility',
            'question': 'analyze users who navigated without using AI travel guide, count repeated navigation to same POI, evaluate reverse generation potential',
            'skip_clarification': True
        },
    ]

    # 运营位增长模块 (B11-B14)
    growth_queries = [
        {
            'name': 'B11 Operation Position Comparison',
            'question': 'compare click rate and navigation rate between operation position POIs and non-operation position POIs',
            'skip_clarification': True
        },
        {
            'name': 'B13 Discovery vs Porsche Comparison',
            'question': 'compare navigation heat and POI type preference between Discovery page and Porsche+ page',
            'skip_clarification': True
        },
        {
            'name': 'B14 POI View to Nav Funnel',
            'question': 'build funnel from POI view to navigation confirmation, analyze by POI type',
            'skip_clarification': True
        },
    ]

    all_queries = journey_queries + ai_queries + growth_queries

    # 执行查询
    print('\nStarting Business metrics calculation...')
    charts_saved = []

    for i, q in enumerate(all_queries):
        print(f'\n[{i+1}/{len(all_queries)}] {q["name"]}...')
        try:
            result = agent.query(q['question'], skip_clarification=q['skip_clarification'])
            if result.get('error'):
                print(f'  Error: {result["error"]}')
                continue

            chart = {
                'id': q['name'].split()[0].lower(),
                'name': q['name'],
                'chart_type': result.get('chart_type', 'table'),
                'chart_option': result.get('chart_option'),
                'sql': result.get('sql'),
                'data': result.get('data', []),
                'summary': result.get('summary', ''),
                'audit': result.get('audit'),
                'query': q['question']
            }

            save_result = save_chart('Business', chart)
            print(f'  Saved: {save_result}')
            charts_saved.append(q['name'])
        except Exception as e:
            print(f'  Exception: {e}')

    print(f'\nTotal {len(charts_saved)} charts saved to Business dashboard')

    # 保存摘要
    summary = {
        'dashboard': 'Business',
        'charts_count': len(charts_saved),
        'charts_saved': charts_saved,
        'modules': {
            'journey': len(journey_queries),
            'ai_effect': len(ai_queries),
            'growth': len(growth_queries)
        },
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }

    with open('report/fulldata_v2/business_dashboard_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print('Summary saved to business_dashboard_summary.json')

if __name__ == '__main__':
    main()