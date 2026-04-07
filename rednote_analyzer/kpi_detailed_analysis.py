"""
Detailed KPI Metrics Analysis
Generate comprehensive KPI statistics based on the 20 defined metrics
"""

import pandas as pd
import json
import os
import sys
import io
from collections import Counter
from datetime import datetime, timedelta

# Set UTF-8 encoding for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from analyzer import RednoteAnalyzer

DATA_PATH = r'C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx'
CONFIG_PATH = r'C:\projects\rednote data analyzer\rednote_analyzer\config\kpi_metrics.yaml'

def convert_to_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return int(obj) if isinstance(obj, np.integer) else float(obj)
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        return convert_to_serializable(obj.to_dict())
    else:
        return obj

def analyze_user_sessions(data, event='discovery_page_pageshow'):
    """Analyze user session patterns by hour"""
    event_data = data[data['span_nm'] == event].copy()
    if event_data.empty:
        return {}

    event_data['hour'] = pd.to_datetime(event_data['strt_time_nano'], errors='coerce').dt.hour
    event_data['date'] = pd.to_datetime(event_data['strt_time_nano'], errors='coerce').dt.date

    # Unique users per hour
    hourly_users = event_data.groupby('hour')['reduser_id'].nunique().to_dict()

    # Events per hour
    hourly_events = event_data.groupby('hour').size().to_dict()

    # Unique users per date
    daily_users = event_data.groupby('date')['reduser_id'].nunique().to_dict()

    # Sessions per hour (simplified: count events as sessions)
    hourly_sessions = event_data.groupby('hour').size().to_dict()

    return {
        'hourly_users': hourly_users,
        'hourly_events': hourly_events,
        'daily_users': daily_users,
        'hourly_sessions': hourly_sessions
    }

def calculate_retention_by_cohort(data, event='discovery_page_pageshow', days=[7, 14, 30]):
    """Calculate retention rates by cohort"""
    event_data = data[data['span_nm'] == event].copy()
    if event_data.empty:
        return {}

    event_data['date'] = pd.to_datetime(event_data['strt_time_nano'], errors='coerce').dt.date

    # Get unique users per date
    daily_users = event_data.groupby('date')['reduser_id'].apply(set)

    retention_results = {}

    for day_n in days:
        result_key = f'retention_{day_n}_day'
        retention_rates = []

        dates = sorted(daily_users.keys())
        for i in range(len(dates) - day_n):
            current_date = dates[i]
            future_date = dates[i + day_n]

            if future_date in daily_users:
                current_users = daily_users[current_date]
                future_users = daily_users[future_date]
                retained = len(current_users & future_users)
                rate = len(future_users) > 0 and (retained / len(current_users)) * 100

                retention_rates.append({
                    'date': str(current_date),
                    'retained': int(retained),
                    'total': len(current_users),
                    'rate': round(rate, 2)
                })

        retention_results[result_key] = retention_rates

    return retention_results

def analyze_event_flow(data, events=None):
    """Analyze event flow patterns"""
    if events is None:
        # Get top events
        event_counts = data['span_nm'].value_counts()
        events = event_counts.head(10).index.tolist()

    if len(events) == 0:
        return {}

    event_flow = {}
    for i, event in enumerate(events):
        event_data = data[data['span_nm'] == event].copy()
        if event_data.empty:
            continue

        # Add time info
        event_data['time'] = pd.to_datetime(event_data['strt_time_nano'], errors='coerce')
        event_data = event_data.sort_values('time')

        # Calculate transition patterns
        transitions = []
        if len(event_data) > 1:
            for j in range(len(event_data) - 1):
                current = event_data.iloc[j]
                next_event = event_data.iloc[j + 1]
                time_diff = (next_event['time'] - current_event['time']).total_seconds()

                transitions.append({
                    'from_time': str(current_event['time']),
                    'to_time': str(next_event['time']),
                    'time_diff': round(time_diff, 2),
                    'user_id': current_event['reduser_id']
                })

        # Calculate typical intervals
        intervals = []
        for j in range(1, len(event_data)):
            if j < len(event_data):
                prev = event_data.iloc[j - 1]
                curr = event_data.iloc[j]
                time_diff = (curr['time'] - prev['time']).total_seconds()
                intervals.append(time_diff)

        typical_interval = np.median(intervals) if intervals else 0

        event_flow[event] = {
            'total_events': len(event_data),
            'unique_users': int(event_data['reduser_id'].dropna().nunique()),
            'transitions': transitions[:20],  # Top 20
            'typical_interval': typical_interval,
            'interval_stats': {
                'min': int(np.min(intervals)) if intervals else 0,
                'max': int(np.max(intervals)) if intervals else 0,
                'median': typical_interval,
                'mean': round(np.mean(intervals), 2)
            }
        }

    return event_flow

def main():
    print('Running detailed KPI metrics analysis...')

    # Initialize analyzer
    analyzer = RednoteAnalyzer(DATA_PATH, CONFIG_PATH)
    analyzer.load_data()
    data = analyzer.data
    print(f'Loaded {len(data)} records from {len(data.columns)} columns')

    # Calculate all detailed metrics
    kpi_details = {}

    # 1. APP Metrics - User Sessions
    print('\n[1] Analyzing APP User Sessions')
    session_analysis = analyze_user_sessions(data, 'discovery_page_pageshow')

    kpi_details['app_sessions'] = {
        'description': 'APP 用户会话时模式分析',
        'hourly_active_users': session_analysis['hourly_users'],
        'hourly_events': session_analysis['hourly_events'],
        'peak_usage_hour': max(session_analysis['hourly_events'].items(), key=lambda x: x[1]) if session_analysis['hourly_events'] else 0,
        'peak_users_hour': max(session_analysis['hourly_users'].items(), key=lambda x: x[1]) if session_analysis['hourly_users'] else 0,
        'total_events': sum(session_analysis['hourly_events'].values()) if session_analysis['hourly_events'] else 0
    }

    # 2. Porsche+ Sessions
    print('\n[2] Analyzing Porsche+ Sessions')
    porsche_sessions = analyze_user_sessions(data, 'porsche_page_pageshow')

    kpi_details['porsche_sessions'] = {
        'description': 'Porsche+ 用户会话时模式分析',
        'hourly_active_users': porsche_sessions['hourly_users'],
        'hourly_events': porsche_sessions['hourly_events'],
        'peak_usage_hour': max(porsche_sessions['hourly_events'].items(), key=lambda x: x[1]) if porsche_sessions['hourly_events'] else 0,
        'peak_users_hour': max(porsche_sessions['hourly_users'].items(), key=lambda x: x[1]) if porsche_sessions['hourly_users'] else 0,
        'total_events': sum(porsche_sessions['hourly_events'].values()) if porsche_sessions['hourly_events'] else 0
    }

    # 3. Retention Analysis
    print('\n[3] Analyzing User Retention')
    retention_analysis = calculate_retention_by_cohort(data)
    kpi_details['retention_analysis'] = retention_analysis

    # 4. Event Flow Analysis
    print('\n[4] Analyzing Event Flow Patterns')
    top_events = data['span_nm'].value_counts().head(10).index.tolist()
    event_flow_analysis = analyze_event_flow(data, top_events)
    kpi_details['event_flow'] = event_flow_analysis

    # 5. User Journey Analysis
    print('\n[5] Analyzing User Journeys')
    journey_data = data[data['reduser_id'].notna()].copy()
    journey_data['time'] = pd.to_datetime(journey_data['strt_time_nano'], errors='coerce')
    journey_data = journey_data.sort_values(['reduser_id', 'time'])

    user_journeys = {}
    for user_id in journey_data['reduser_id'].unique()[:5]:  # Top 5 users
        user_events = journey_data[journey_data['reduser_id'] == user_id]

        if not user_events.empty:
            journey = []
            for i, row in user_events.iterrows():
                journey.append({
                    'event': row['span_nm'],
                    'time': str(row['time']),
                    'user_id': row['reduser_id']
                })

            user_journeys[str(int(user_id))] = {
                'total_events': len(journey),
                'unique_events': len(user_events['span_nm'].unique()),
                'journey': journey[:20],
                'first_event_time': str(journey[0]['time']) if journey else None,
                'last_event_time': str(journey[-1]['time']) if journey else None,
                'duration': (pd.to_datetime(journey[-1]['time']) - pd.to_datetime(journey[0]['time'])).total_seconds() if len(journey) > 1 else 0
            }

    kpi_details['user_journeys'] = user {
        'description': 'Top 5 用户的行为旅程分析',
        'journeys': user_journeys
    }

    # 6. POI Detail Analysis
    print('\n[6] Analyzing POI Details')
    poi_data = data[data['rednote_poi_title'].notna()].copy()

    # POI by user
    poi_by_user = poi_data.groupby('reduser_id').agg({
        'total_poi': ('rednote_poi_title', 'count'),
        'unique_poi': ('rednote_poi_title', 'nunique'),
        'avg_poi_duration': lambda x: 0 0
    }).to_dict('index')

    # Most active POI users
    poi_user_counts = poi_data.groupby('reduser_id').size().sort_values(ascending=False)

    kpi_details['poi_analysis'] = {
        'description': 'POI 详情和用户参与度分析',
        'total_poi_interactions': len(poi_data),
        'unique_poi': len(poi_data['rednote_poi_title'].nunique()),
        'poi_by_user': poi_by_user,
        'top_poi_users': poi_user_counts.head(10).to_dict(),
        'poi_categories': data[data['rednote_poi_typ_nm'].notna()]['rednote_poi_typ_nm'].value_counts().head(10).to_dict()
    }

    # 7. Search Pattern Analysis
    print('\n[7] Analyzing Search Patterns')
    search_data = data[data['span_nm'].str.contains('search', case=False, na=False)].copy()

    search_by_user = search_data.groupby('reduser_id').size().sort_values(ascending=False)

    # Search sequences
    search_sequences = []
    top_users_list = search_by_user.head(5).index.tolist()

    for user_id in top_users_list:
        user_searches = search_data[search_data['reduser_id'] == user_id].sort_values('strt_time_nano')
        for i, row in user_searches.iterrows():
            search_sequences.append({
                'user_id': str(row['reduser_id']),
                'event': row['span_nm'],
                'time': str(row['strt_time_nano'])
            })
        search_sequences = search_sequences[:50]

    kpi_details['search_analysis'] = {
        'description': '搜索模式分析',
        'total_search_events': len(search_data),
        'search_by_user': search_by_user.head(10).to_dict(),
        'search_sequences': search_sequences
    }

    # 8. Content Engagement Depth
    print('\n[8] Analyzing Content Engagement Depth')

    # Like details
    like_data = data[data['rednote_post_is_like'].notna()]

    # Save details
    save_data = data[data['rednote_post_is_save'].notna()]

    # Follow details
    follow_data = data[data['rednote_post_follow'].notna()]

    kpi_details['content_engagement_detail'] = {
        'description': '内容互动详情分析',
        'like_events': {
            'total': len(like_data),
            'by_user': like_data.groupby('reduser_id').size().to_dict(),
            'by_time': like_data.groupby([pd.Grouper(pd.to_datetime(like_data['strt_time_nano'], errors='coerce').dt.hour)]).size().to_dict()
        },
        'save_events': {
            'total': len(save_data),
            'by_user': save_data.groupby('reduser_id').size().to_dict(),
            'by_time': save_data.groupby([pd.Grouper(pd.to_datetime(save_data['strt_time_nano'], errors='coerce').dt.hour)]).size().to_dict()
        },
        'follow_events': {
            'total': len(follow_data),
            'by_user': follow_data.groupby('reduser_id').size().to_dict(),
            'by_time': follow_data.groupby([pd.Grouper(pd.to_datetime(follow_data['strt_time_nano'], errors='coerce').dt.hour)]).size().to_dict()
        }
    }

    # 9. AI Guide Usage
    print('\n[9] Analyzing AI Guide Usage')
    ai_data = data[data['span_nm'] == 'post_detail_page_ai_travel_guide_button_click'].copy()

    kpi_details['ai_guide_usage_detail'] = {
        'description': 'AI 路书使用详情分析',
        'total_requests': len(ai_data),
        'by_user': ai_data.groupby('reduser_id').size().to_dict(),
        'by_time': ai_data.groupby([pd.Grouper(pd.to_datetime(ai_data['strt_time_nano'], errors='coerce').dt.hour)]).size().to_dict(),
        'first_time': str(ai_data['strt_time_nano'].min()) if not ai_data.empty else None,
        'last_time': str(ai_data['strt_time_nano'].max()) if not ai_data.empty else None
    }

    # 10. Porsche+ Feature Usage
    print('\n[10] Analyzing Porsche+ Feature Usage')
    porsche_data = data[data['span_nm'].str.contains('porsche', case=False, na=False)].copy()

    porsche_events = porsche_data['span_nm'].value_counts().to_dict()
    porsche_users = porsche_data.groupby('reduser_id').size().sort_values(ascending=False).to_dict()

    kpi_details['porsche_usage_detail'] = {
        'description': 'Porsche+ 功能使用详情',
        'total_events': len(porsche_data),
        'event_breakdown': porsche_events,
        'top_users': porsche_users
    }

    # Compile complete report
    kpi_details['report_metadata'] = {
        'title': 'Rednote KPI 指标详细分析报告',
        'generated_at': datetime.now().isoformat(),
        'data_period': {
            'start': str(data['strt_time_nano'].min()),
            'end': str(data['strt_time_nano'].max())
        },
        'total_records': len(data),
        'unique_users': int(data['reduser_id'].nunique()),
        'unique_devices': int(data['dvc_id'].nunique()),
        'total_event_types': int(data['span_nm'].nunique())
    }

    # Convert to serializable
    kpi_details_serializable = convert_to_serializable(kpi_details)

    # Save report
    OUTPUT_PATH = r'C:\projects\rednote data analyzer\rednote_analyzer\output\kpi_detailed_analysis.json'
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(kpi_details_serializable, f, indent=2, ensure_ascii=False)

    print(f'\nDetailed KPI analysis saved to: {OUTPUT_PATH}')
    print('Analysis complete!')

    # Print summary
    print('\n' + '='*80)
    print('KPI METRICS SUMMARY')
    print('='*80)
    print(f'APP Sessions Peak Hour: {kpi_details["app_sessions"]["peak_usage_hour"]}:00')
    print(f'Porsche+ Peak Hour: {kpi_details["porsche_sessions"]["peak_usage_hour"]}:00')
    print(f'Total APP events: {kpi_details["app_sessions"]["total_events"]}')
    print(f'Total Porsche+ events: {kpi_details["porsche_sessions"]["total_events"]}')
    print(f'Total POI interactions: {kpi_details["poi_analysis"]["total_poi_interactions"]}')
    print(f'Total search events: {kpi_details["search_analysis"]["total_search_events"]}')
    print(f'Unique users analyzed: {len(kpi_details["user_journeys"]["journeys"])}')


if __name__ == '__main__':
    main()
