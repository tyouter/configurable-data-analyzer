"""
Comprehensive Exploratory Analysis for Rednote Data
Performs in-depth analysis on all 10 exploration topics
"""

import pandas as pd
import json
import os
import sys
import io
from collections import Counter
import numpy as np

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

def main():
    print('Running comprehensive exploratory analysis...')

    analyzer = RednoteAnalyzer(DATA_PATH, CONFIG_PATH)
    analyzer.load_data()
    data = analyzer.data

    # Topic 1: Sports & Venues
    print('\n[1] Sports & Venues Analysis')
    poi_data = data[data['rednote_poi_title'].notna()].copy()
    poi_types = poi_data['rednote_poi_typ_nm'].value_counts()
    top_venues = poi_data['rednote_poi_title'].value_counts().head(20)
    sports_keywords = ['gym', 'sport', 'fitness', 'exercise', 'workout',
                      'basketball', 'tennis', 'swimming', 'running', 'yoga',
                      'pool', 'badminton', 'football', 'golf', 'stadium']
    sports_related = {str(k): int(v) for k, v in poi_types.items()
                     if any(sk in str(k).lower() for sk in sports_keywords)}

    # Topic 2: Travel Frequency
    print('\n[2] Travel Frequency Analysis')
    poi_data = data[data['reduser_id'].notna()].copy()
    user_interactions = poi_data.groupby('reduser_id').size()
    high_freq_users = user_interactions[user_interactions > user_interactions.mean() * 2]
    low_freq_users = user_interactions[user_interactions <= user_interactions.quantile(0.25)]

    # Topic 3: Content Engagement
    print('\n[3] Content Engagement Analysis')
    like_events = data[data['rednote_post_is_like'].notna()]
    save_events = data[data['rednote_post_is_save'].notna()]
    follow_events = data[data['rednote_post_follow'].notna()]
    content_types = data[data['rednote_post_typ'].notna()]['rednote_post_typ'].value_counts()

    # Topic 4: Search Behavior
    print('\n[4] Search Behavior Analysis')
    search_data = data[data['span_nm'].str.contains('search', case=False, na=False)].copy()
    search_users = search_data['reduser_id'].dropna().nunique()
    search_events_dist = search_data['span_nm'].value_counts()
    user_search_counts = search_data.groupby('reduser_id').size()

    # Topic 5: Porsche+ Engagement
    print('\n[5] Porsche+ Engagement Analysis')
    porsche_data = data[data['span_nm'].str.contains('porsche', case=False, na=False)].copy()
    porsche_users = porsche_data['reduser_id'].dropna().nunique()
    porsche_features = porsche_data['span_nm'].value_counts()
    poi_card_interactions = len(porsche_data[porsche_data['span_nm'].str.contains('poi_card', case=False)])
    recommendation_interactions = len(porsche_data[porsche_data['span_nm'].str.contains('recommend', case=False)])

    # Topic 6: Video Consumption
    print('\n[6] Video Consumption Analysis')
    video_plays = len(data[data['rednote_video_post_is_play'] == 0])
    autoplay_enabled = len(data[data['rednote_video_post_autoplay_is_open'] == 1])
    video_users = data[data['rednote_video_post_is_play'].notna()]['reduser_id'].dropna().nunique()

    # Topic 7: Map & POI Interactions
    print('\n[7] Map & POI Interactions Analysis')
    map_data = data[data['span_nm'].str.contains('map|poi', case=False, na=False)].copy()
    map_users = map_data['reduser_id'].dropna().nunique()
    map_features = map_data['span_nm'].value_counts()
    fullscreen_usage = len(data[data['rednote_poi_map_fullscreen'] == 1])

    # Topic 8: AI Guide Adoption
    print('\n[8] AI Guide Adoption Analysis')
    ai_data = data[data['span_nm'].str.contains('ai|guide|travel', case=False, na=False)].copy()
    ai_requests = ai_data[ai_data['span_nm'].str.contains('ai_travel_guide_button', case=False)]
    ai_users = ai_requests['reduser_id'].dropna().nunique()
    share_guide_events = len(ai_data[ai_data['span_nm'].str.contains('share', case=False)])

    # Topic 9: Session Patterns
    print('\n[9] Session Patterns Analysis')
    session_data = data[data['strt_time_dt'].notna() & data['reduser_id'].notna()].copy()
    session_data['duration'] = (session_data['end_time_dt'] - session_data['strt_time_dt']).dt.total_seconds()
    valid_durations = session_data[session_data['duration'] > 0]
    avg_session = valid_durations['duration'].mean() if not valid_durations.empty else 0
    session_data['hour'] = session_data['strt_time_dt'].dt.hour
    hourly_activity = session_data.groupby('hour')['reduser_id'].nunique()
    peak_hour = hourly_activity.idxmax() if not hourly_activity.empty else None

    # Topic 10: Social Sharing
    print('\n[10] Social Sharing Analysis')
    share_data = data[data['span_nm'].str.contains('share', case=False, na=False)].copy()
    share_users = share_data['reduser_id'].dropna().nunique()
    share_types = share_data['span_nm'].value_counts()
    guide_shares = len(share_data[share_data['span_nm'].str.contains('guide|trip', case=False)])
    user_shares = share_data.groupby('reduser_id').size()

    # Compile comprehensive results
    comprehensive_report = {
        'sports_venues': {
            'total_poi': int(len(poi_data)),
            'unique_poi': int(poi_data['rednote_poi_title'].nunique()),
            'venue_categories': dict(poi_types.head(10)),
            'sports_categories': sports_related,
            'top_venues': dict(top_venues)
        },
        'travel_frequency': {
            'total_users': int(user_interactions.shape[0]),
            'avg_interactions': float(user_interactions.mean()),
            'median_interactions': float(user_interactions.median()),
            'max_interactions': int(user_interactions.max()),
            'min_interactions': int(user_interactions.min()),
            'high_freq_count': int(len(high_freq_users)),
            'low_freq_count': int(len(low_freq_users))
        },
        'content_engagement': {
            'total_likes': int(len(like_events)),
            'total_saves': int(len(save_events)),
            'total_follows': int(len(follow_events)),
            'content_types': dict(content_types.head(10)),
            'engagement_rate': round((len(like_events) + len(save_events) + len(follow_events)) / len(data) * 100, 2)
        },
        'search_behavior': {
            'total_search_events': int(len(search_data)),
            'unique_searching_users': int(search_users),
            'search_diversity': int(len(search_events_dist)),
            'avg_searches_per_user': round(float(user_search_counts.mean()), 2) if not user_search_counts.empty else 0,
            'top_search_events': dict(search_events_dist.head(10))
        },
        'porsche_engagement': {
            'total_porsche_events': int(len(porsche_data)),
            'unique_porsche_users': int(porsche_users),
            'poi_card_interactions': int(poi_card_interactions),
            'recommendation_interactions': int(recommendation_interactions),
            'top_features': dict(porsche_features.head(10))
        },
        'video_consumption': {
            'total_video_plays': int(video_plays),
            'autoplay_enabled': int(autoplay_enabled),
            'unique_video_viewers': int(video_users),
            'video_engagement_rate': round(video_plays / video_users * 100, 2) if video_users > 0 else 0
        },
        'map_poi_interactions': {
            'total_map_events': int(len(map_data)),
            'unique_map_users': int(map_users),
            'fullscreen_usage': int(fullscreen_usage),
            'top_features': dict(map_features.head(10))
        },
        'ai_guide_adoption': {
            'total_ai_events': int(len(ai_data)),
            'ai_guide_requests': int(len(ai_requests)),
            'unique_ai_users': int(ai_users),
            'share_guide_events': int(share_guide_events),
            'adoption_rate': round(ai_users / data['reduser_id'].nunique() * 100, 2)
        },
        'session_patterns': {
            'total_sessions': int(len(valid_durations)),
            'avg_duration': round(float(avg_session), 2),
            'median_duration': round(float(valid_durations['duration'].median()), 2) if not valid_durations.empty else 0,
            'peak_hour': int(peak_hour) if peak_hour is not None else None,
            'hourly_distribution': dict(hourly_activity)
        },
        'social_sharing': {
            'total_share_events': int(len(share_data)),
            'unique_sharers': int(share_users),
            'guide_shares': int(guide_shares),
            'avg_shares_per_user': round(float(user_shares.mean()), 2) if not user_shares.empty else 0,
            'top_share_types': dict(share_types.head(10))
        }
    }

    # Convert all to serializable format
    comprehensive_report = convert_to_serializable(comprehensive_report)

    OUTPUT_PATH = r'C:\projects\rednote data analyzer\rednote_analyzer\output\comprehensive_analysis.json'
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(comprehensive_report, f, indent=2, ensure_ascii=False)

    print(f'\nComprehensive analysis saved to: {OUTPUT_PATH}')
    print('Analysis complete with 10 topics!')

    # Print summary
    print('\n' + '='*60)
    print('ANALYSIS SUMMARY')
    print('='*60)
    print(f'Sports & Venues: {comprehensive_report["sports_venues"]["total_poi"]} POIs, {comprehensive_report["sports_venues"]["unique_poi"]} unique')
    print(f'Travel Frequency: {comprehensive_report["travel_frequency"]["avg_interactions"]:.2f} avg interactions/user')
    print(f'Content Engagement: {comprehensive_report["content_engagement"]["engagement_rate"]}% engagement rate')
    print(f'Search Behavior: {comprehensive_report["search_behavior"]["total_search_events"]} search events')
    print(f'Porsche+ Engagement: {comprehensive_report["porsche_engagement"]["total_porsche_events"]} events')
    print(f'Video Consumption: {comprehensive_report["video_consumption"]["total_video_plays"]} video plays')
    print(f'Map & POI: {comprehensive_report["map_poi_interactions"]["total_map_events"]} map events')
    print(f'AI Guide Adoption: {comprehensive_report["ai_guide_adoption"]["adoption_rate"]}% adoption rate')
    print(f'Session Patterns: {comprehensive_report["session_patterns"]["avg_duration"]:.2f}s avg session duration')
    print(f'Social Sharing: {comprehensive_report["social_sharing"]["total_share_events"]} share events')


if __name__ == '__main__':
    main()
