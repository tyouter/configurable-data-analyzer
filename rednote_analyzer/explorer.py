"""
RedRednote Data Explorer
Advanced exploratory analysis for discovering user behavior patterns
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any
import json
from collections import Counter

from analyzer import RednoteAnalyzer


class RednoteExplorer:
    """Exploratory analytics for Rednote data"""

    def __init__(self, analyzer: RednoteAnalyzer):
        """
        Initialize explorer with analyzer instance

        Args:
            analyzer: RednoteAnalyzer instance
        """
        self.analyzer = analyzer
        self.data = analyzer.data

    def analyze_sports_and_venues(self) -> Dict[str, Any]:
        """
        TOPIC 1: Analyze user sports habits and venue searches
        Analyzes search patterns related to sports, gyms, venues
        """
        print("\n[1] Analyzing Sports & Venue Search Patterns...")

        # Search events related to sports/venues
        search_data = self.data[
            self.data['span_nm'].str.contains('search', case=False, na=False)
        ].copy()

        # Analyze POI types for sports/venues
        sports_poi = self.data[
            self.data['rednote_poi_typ_nm'].notna()
        ].copy()

        results = {
            'topic': 'Sports & Venue Analysis',
            'description': 'Analysis of user sports habits and venue search patterns',
            'total_search_events': len(search_data),
            'users_searching_sports': 0,
            'venue_categories': {},
            'top_venues': {},
            'search_event_patterns': {},
            'insights': []
        }

        # Categorize POI types
        if not sports_poi.empty:
            poi_types = sports_poi['rednote_poi_typ_nm'].value_counts()
            results['venue_categories'] = poi_types.head(10).to_dict()

            # Identify sports-related categories
            sports_keywords = ['gym', 'sport', 'fitness', 'exercise', 'workout',
                          'basketball', 'tennis', 'swimming', 'running']
            sports_related = poi_types.filter(
                regex='|'.join(sports_keywords), axis=0
            )

            results['insights'].append(
                f"Found {len(sports_related)} sports (related venue categories"
            )

        # Top venues
        if 'rednote_poi_title' in sports_poi.columns:
            top_venues = sports_poi['rednote_poi_title'].value_counts()
            results['top_venues'] = top_venues.head(10).to_dict()

        # Search patterns by event type
        if not search_data.empty:
            search_patterns = search_data['span_nm'].value_counts()
            results['search_event_patterns'] = search_patterns.head(10).to_dict()
            results['users_searching_sports'] = search_data['reduser_id'].dropna().nunique()

        return results

    def analyze_travel_frequency(self) -> Dict[str, Any]:
        """
        TOPIC 2: Analyze user travel frequency and patterns
        Analyzes POI interaction frequency and user travel behavior
        """
        print("\n[2] Analyzing Travel Frequency Patterns...")

        # Get POI interactions
        poi_data = self.data[self.data['reduser_id'].notna()].copy()

        results = {
            'topic': 'Travel Frequency Analysis',
            'description': 'Analysis of user travel and POI interaction frequency',
            'total_users': 0,
            'avg_poi_interactions_per_user': 0,
            'user_interaction_distribution': {},
            'high_frequency_users': {},
            'low_frequency_users': {},
            'daily_interaction_pattern': {},
            'insights': []
        }

        if poi_data.empty:
            return results

        results['total_users'] = poi_data['reduser_id'].nunique()

        # Calculate interactions per user
        user_interactions = poi_data.groupby('reduser_id').size()
        results['avg_poi_interactions_per_user'] = round(
            user_interactions.mean(), 2
        )

        # Distribution statistics
        results['user_interaction_distribution'] = {
            'min': int(user_interactions.min()),
            'max': int(user_interactions.max()),
            'median': float(user_interactions.median()),
            'std': float(user_interactions.std())
        }

        # High frequency users (> 2x average)
        threshold = user_interactions.mean() * 2
        high_freq = user_interactions[user_interactions > threshold].head(10)
        results['high_frequency_users'] = high_freq.to_dict()

        # Low frequency users (< 25th percentile)
        low_threshold = user_interactions.quantile(0.25)
        low_freq = user_interactions[user_interactions <= low_threshold].head(10)
        results['low_frequency_users'] = low_freq.to_dict()

        # Daily interaction patterns
        if 'strt_time_dt' in poi_data.columns:
            poi_data['date'] = poi_data['strt_time_dt'].dt.date
            daily_interactions = poi_data.groupby('date').size()
            results['daily_interaction_pattern'] = daily_interactions.to_dict()

        results['insights'].append(
            f"Average {results['avg_poi_interactions_per_user']} POI interactions per user"
        )
        results['insights'].append(
            f"Found {len(high_freq)} high-frequency users (>{threshold} interactions)"
        )

        return results

    def analyze_content_engagement(self) -> Dict[str, Any]:
        """
        TOPIC 3: Analyze content engagement patterns
        Analyzes likes, saves, follows, and content type preferences
        """
        print("\n[3] Analyzing Content Engagement Patterns...")

        results = {
            'topic': 'Content Engagement Analysis',
            'description': 'Analysis of user content interaction and engagement patterns',
            'total_likes': 0,
            'total_saves': 0,
            'total_follows': 0,
            'engagement_ratio': 0,
            'content_type_preferences': {},
            'most_engaged_users': {},
            'engagement_events_distribution': {},
            'insights': []
        }

        # Count engagement events
        like_events = self.data[self.data['rednote_post_is_like'].notna()]
        save_events = self.data[self.data['rednote_post_is_save'].notna()]
        follow_events = self.data[self.data['rednote_post_follow'].notna()]

        results['total_likes'] = len(like_events)
        results['total_saves'] = len(save_events)
        results['total_follows'] = len(follow_events)

        # Calculate engagement ratio
        total_events = len(self.data)
        engagement_events = results['total_likes'] + results['total_saves'] + results['total_follows']
        results['engagement_ratio'] = round(
            (engagement_events / total_events * 100) if total_events > 0 else 0, 2
        )

        # Content type preferences
        if 'rednote_post_typ' in self.data.columns:
            content_with_type = self.data[self.data['rednote_post_typ'].notna()]
            if not content_with_type.empty:
                results['content_type_preferences'] = content_with_type[
                    'rednote_post_typ'
                ].value_counts().head(10).to_dict()

        # Most engaged users
        engaged_users = pd.DataFrame({
            'likes': like_events.groupby('reduser_id').size(),
            'saves': save_events.groupby('reduser_id').size(),
            'follows': follow_events.groupby('reduser_id').size()
        }).fillna(0)

        engaged_users['total'] = (
            engaged_users['likes'] +
            engaged_users['saves'] +
            engaged_users['follows']
        )

        results['most_engaged_users'] = engaged_users.nlargest(10, 'total')['total'].to_dict()

        # Engagement events distribution
        results['engagement_events_distribution'] = {
            'likes': results['total_likes'],
            'saves': results['total_saves'],
            'follows': results['total_follows'],
            'total': engagement_events
        }

        results['insights'].append(
            f"Overall engagement rate: {results['engagement_ratio']}%"
        )

        return results

    def analyze_search_behavior_depth(self) -> Dict[str, Any]:
        """
        TOPIC 4: Deep analysis of search behavior
        Analyzes search patterns, terms, and user search journeys
        """
        print("\n[4] Analyzing Search Behavior Depth...")

        search_data = self.data[
            self.data['span_nm'].str.contains('search', case=False, na=False)
        ].copy()

        results = {
            'topic': 'Search Behavior Analysis',
            'description': 'Deep analysis of user search patterns and behavior',
            'total_search_events': len(search_data),
            'unique_searching_users': 0,
            'search_event_diversity': {},
            'search_frequency_per_user': {},
            'search_journey_patterns': {},
            'search_type_breakdown': {},
            'insights': []
        }

        if search_data.empty:
            return results

        results['unique_searching_users'] = search_data['reduser_id'].dropna().nunique()

        # Search event diversity
        search_events = search_data['span_nm'].value_counts()
        results['search_event_diversity'] = {
            'unique_search_event_types': len(search_events),
            'top_search_events': search_events.head(10).to_dict()
        }

        # Search frequency per user
        user_search_counts = search_data.groupby('reduser_id').size()
        results['search_frequency_per_user'] = {
            'min': int(user_search_counts.min()),
            'max': int(user_search_counts.max()),
            'mean': float(user_search_counts.mean()),
            'median': float(user_search_counts.median())
        }

        # Search type breakdown
        search_types = {
            'homepage_search': search_data[
                search_data['span_nm'].str.contains('homepage', case=False)
            ].shape[0],
            'results_search': search_data[
                search_data['span_nm'].str.contains('results', case=False)
            ].shape[0],
            'other_search': search_data.shape[0] - (
                search_data[search_data['span_nm'].str.contains('homepage|results', case=False)].shape[0]
            )
        }
        results['search_type_breakdown'] = search_types

        # Search journey patterns (sequential search events per user)
        if 'strt_time_dt' in search_data.columns:
            search_data = search_data.sort_values('strt_time_dt')
            user_journeys = search_data.groupby('reduser_id')['span_nm'].apply(list)

            # Calculate common patterns
            all_patterns = []
            for _, journey in user_journeys.items():
                for i in range(len(journey) - 1):
                    pattern = f"{journey[i]} -> {journey[i+1]}"
                    all_patterns.append(pattern)

            pattern_counts = Counter(all_patterns)
            results['search_journey_patterns'] = dict(
                sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            )

        results['insights'].append(
            f"On average {results['search_frequency_per_user']['mean']:.2f} "
            f"search events per user"
        )

        return results

    def analyze_porsche_plus_engagement(self) -> Dict[str, Any]:
        """
        TOPIC 5: Analyze Porsche+ feature engagement
        Analyzes user interactions with Porsche+ specific features
        """
        print("\n[5] Analyzing Porsche+ Feature Engagement...")

        porsche_data = self.data[
            self.data['span_nm'].str.contains('porsche', case=False, na=False)
        ].copy()

        results = {
            'topic': 'Porsche+ Engagement Analysis',
            'description': 'Analysis of Porsche+ feature usage and engagement',
            'total_porsche_events': len(porsche_data),
            'unique_porsche_users': 0,
            'porsche_feature_breakdown': {},
            'user_porsche_activity_levels': {},
            'poi_card_interactions': 0,
            'recommendation_engagement': 0,
            'insights': []
        }

        if porsche_data.empty:
            return results

        results['unique_porsche_users'] = porsche_data['reduser_id'].dropna().nunique()

        # Feature breakdown
        feature_events = porsche_data['span_nm'].value_counts()
        results['porsche_feature_breakdown'] = feature_events.head(15).to_dict()

        # Specific interactions
        results['poi_card_interactions'] = len(
            porsche_data[porsche_data['span_nm'].str.contains('poi_card', case=False)]
        )
        results['recommendation_engagement'] = len(
            porsche_data[porsche_data['span_nm'].str.contains('recommend', case=False)]
        )

        # User activity levels
        user_activity = porsche_data.groupby('reduser_id').size()
        results['user_porsche_activity_levels'] = {
            'low_activity_users': int((user_activity < 5).sum()),
            'medium_activity_users': int(((user_activity >= 5) & (user_activity < 20)).sum()),
            'high_activity_users': int((user_activity >= 20).sum()),
            'average_events_per_user': float(user_activity.mean())
        }

        results['insights'].append(
            f"Average {results['user_porsche_activity_levels']['average_events_per_user']:.2f} "
            f"Porsche+ events per user"
        )

        return results

    def analyze_video_consumption(self) -> Dict[str, Any]:
        """
        TOPIC 6: Analyze video content consumption
        Analyzes video plays, autoplay settings, and consumption patterns
        """
        print("\n[6] Analyzing Video Consumption Patterns...")

        video_data = self.data[
            self.data['rednote_video_post_is_play'].notna() |
            self.data['rednote_video_post_autoplay_is_open'].notna()
        ].copy()

        results = {
            'topic': 'Video Consumption Analysis',
            'description': 'Analysis of video content consumption and playback patterns',
            'total_video_events': len(video_data),
            'video_plays': 0,
            'autoplay_enabled': 0,
            'playback_speed_distribution': {},
            'video_engagement_rate': 0,
            'user_video_behavior': {},
            'insights': []
        }

        if video_data.empty:
            return results

        # Video plays
        play_events = video_data[video_data['rednote_video_post_is_play'] == 0]
        results['video_plays'] = len(play_events)

        # Autoplay settings
        autoplay_events = video_data[video_data['rednote_video_post_autoplay_is_open'] == 1]
        results['autoplay_enabled'] = len(autoplay_events)

        # Playback speed distribution
        if 'rednote_video_post_play_speed' in video_data.columns:
            speed_data = video_data[video_data['rednote_video_post_play_speed'].notna()]
            if not speed_data.empty:
                results['playback_speed_distribution'] = speed_data[
                    'rednote_video_post_play_speed'
                ].value_counts().to_dict()

        # Video engagement rate
        total_posts = len(self.data[self.data['reduser_id'].notna()])
        results['video_engagement_rate'] = round(
            (results['video_plays'] / total_posts * 100) if total_posts > 0 else 0, 2
        )

        # User video behavior
        video_users = video_data['reduser_id'].dropna()
        results['user_video_behavior'] = {
            'unique_video_viewers': video_users.nunique(),
            'avg_plays_per_viewer': round(
                results['video_plays'] / video_users.nunique(), 2
            ) if video_users.nunique() > 0 else 0
        }

        results['insights'].append(
            f"Video engagement rate: {results['video_engagement_rate']}%"
        )

        return results

    def analyze_map_interactions(self) -> Dict[str, Any]:
        """
        TOPIC 7: Analyze map and POI interaction patterns
        Analyzes map usage, POI card interactions, and location exploration
        """
        print("\n[7] Analyzing Map & POI Interaction Patterns...")

        map_data = self.data[
            self.data['span_nm'].str.contains('map|poi', case=False, na=False)
        ].copy()

        results = {
            'topic': 'Map & POI Interaction Analysis',
            'description': 'Analysis of map usage and point-of-interest interactions',
            'total_map_events': len(map_data),
            'unique_map_users': 0,
            'map_feature_usage': {},
            'poi_interaction_depth': {},
            'location_exploration_patterns': {},
            'fullscreen_map_usage': 0,
            'insights': []
        }

        if map_data.empty:
            return results

        results['unique_map_users'] = map_data['reduser_id'].dropna().nunique()

        # Map feature usage
        map_features = map_data['span_nm'].value_counts()
        results['map_feature_usage'] = map_features.head(10).to_dict()

        # POI interaction depth
        poi_interactions = map_data[map_data['span_nm'].str.contains('poi', case=False)]
        results['poi_interaction_depth'] = {
            'total_poi_events': len(poi_interactions),
            'avg_poi_events_per_user': round(
                len(poi_interactions) / results['unique_map_users'], 2
            ) if results['unique_map_users'] > 0 else 0
        }

        # Fullscreen map usage
        fullscreen_events = self.data[self.data['rednote_poi_map_fullscreen'] == 1]
        results['fullscreen_map_usage'] = len(fullscreen_events)

        results['insights'].append(
            f"Found {results['poi_interaction_depth']['total_poi_events']} "
            f"POI interaction events"
        )

        return results

    def analyze_ai_guide_adoption(self) -> Dict[str, Any]:
        """
        TOPIC 8: Analyze AI Travel Guide adoption and usage
        Analyzes AI route generation, guide usage, and adoption patterns
        """
        print("\n[8] Analyzing AI Guide Adoption Patterns...")

        ai_data = self.data[
            self.data['span_nm'].str.contains('ai|guide|travel', case=False, na=False)
        ].copy()

        results = {
            'topic': 'AI Guide Adoption Analysis',
            'description': 'Analysis of AI travel guide adoption and usage patterns',
            'total_ai_events': len(ai_data),
            'ai_guide_requests': 0,
            'unique_ai_users': 0,
            'adoption_rate': 0,
            'ai_feature_usage': {},
            'guide_generation_patterns': {},
            'share_guide_interactions': 0,
            'insights': []
        }

        if ai_data.empty:
            return results

        # AI guide requests
        ai_requests = ai_data[
            ai_data['span_nm'].str.contains('ai_travel_guide_button', case=False)
        ]
        results['ai_guide_requests'] = len(ai_requests)
        results['unique_ai_users'] = ai_requests['reduser_id'].dropna().nunique()

        # Adoption rate
        total_users = self.data['reduser_id'].dropna().nunique()
        results['adoption_rate'] = round(
            (results['unique_ai_users'] / total_users * 100) if total_users > 0 else 0, 2
        )

        # AI feature usage
        ai_features = ai_data['span_nm'].value_counts()
        results['ai_feature_usage'] = ai_features.head(10).to_dict()

        # Share guide interactions
        share_events = ai_data[
            ai_data['span_nm'].str.contains('share', case=False)
        ]
        results['share_guide_interactions'] = len(share_events)

        results['insights'].append(
            f"AI guide adoption rate: {results['adoption_rate']}%"
        )
        if results['unique_ai_users'] > 0:
            results['insights'].append(
                f"Average {results['ai_guide_requests'] / results['unique_ai_users']:.2f} "
                f"requests per user"
            )

        return results

    def analyze_session_patterns(self) -> Dict[str, Any]:
        """
        TOPIC 9: Analyze user session patterns
        Analyzes session duration, frequency, and user activity patterns
        """
        print("\n[9] Analyzing User Session Patterns...")

        session_data = self.data[
            self.data['strt_time_dt'].notna() & self.data['reduser_id'].notna()
        ].copy()

        results = {
            'topic': 'User Session Analysis',
            'description': 'Analysis of user session patterns and activity cycles',
            'total_sessions': 0,
            'avg_session_duration': 0,
            'session_frequency': {},
            'peak_activity_hours': {},
            'user_session_diversity': {},
            'daily_active_users': {},
            'insights': []
        }

        if session_data.empty:
            return results

        # Calculate session duration
        session_data['duration'] = (
            session_data['end_time_dt'] - session_data['strt_time_dt']
        ).dt.total_seconds()
        valid_durations = session_data[session_data['duration'] > 0]

        results['total_sessions'] = len(valid_durations)
        results['avg_session_duration'] = round(
            valid_durations['duration'].mean(), 2
        ) if not valid_durations.empty else 0

        # Session frequency per user
        user_sessions = session_data.groupby('reduser_id').size()
        results['session_frequency'] = {
            'min': int(user_sessions.min()),
            'max': int(user_sessions.max()),
            'mean': float(user_sessions.mean()),
            'median': float(user_sessions.median())
        }

        # Peak activity hours
        if 'strt_time_dt' in session_data.columns:
            session_data['hour'] = session_data['strt_time_dt'].dt.hour
            hourly_activity = session_data.groupby('hour')['reduser_id'].nunique()
            results['peak_activity_hours'] = hourly_activity.to_dict()

        # Daily active users
        session_data['date'] = session_data['strt_time_dt'].dt.date
        results['daily_active_users'] = session_data.groupby('date')['reduser_id'].nunique().to_dict()

        results['insights'].append(
            f"Average session duration: {results['avg_session_duration']:.2f} seconds"
        )
        results['insights'].append(
            f"Average {results['session_frequency']['mean']:.2f} sessions per user"
        )

        return results

    def analyze_social_sharing(self) -> Dict[str, Any]:
        """
        TOPIC 10: Analyze social sharing behavior
        Analyzes sharing patterns, shared content types, and social engagement
        """
        print("\n[10] Analyzing Social Sharing Behavior...")

        share_data = self.data[
            self.data['span_nm'].str.contains('share', case=False, na=False)
        ].copy()

        results = {
            'topic': 'Social Sharing Analysis',
            'description': 'Analysis of social sharing behavior and patterns',
            'total_share_events': len(share_data),
            'unique_sharers': 0,
            'share_type_distribution': {},
            'share_frequency_per_user': {},
            'travel_guide_shares': 0,
            'social_engagement_from_shares': 0,
            'insights': []
        }

        if share_data.empty:
            return results

        results['unique_sharers'] = share_data['reduser_id'].dropna().nunique()

        # Share type distribution
        share_types = share_data['span_nm'].value_counts()
        results['share_type_distribution'] = share_types.head(10).to_dict()

        # Share frequency per user
        user_shares = share_data.groupby('reduser_id').size()
        results['share_frequency_per_user'] = {
            'min': int(user_shares.min()),
            'max': int(user_shares.max()),
            'mean': float(user_shares.mean()),
            'median': float(user_shares.median())
        }

        # Travel guide specific shares
        guide_shares = share_data[
            share_data['span_nm'].str.contains('guide|trip', case=False)
        ]
        results['travel_guide_shares'] = len(guide_shares)

        # Calculate sharing rate
        total_users = self.data['reduser_id'].dropna().nunique()
        sharing_rate = round(
            (results['unique_sharers'] / total_users * 100) if total_users > 0 else 0, 2
        )

        results['insights'].append(
            f"Sharing adoption rate: {sharing_rate}%"
        )
        results['insights'].append(
            f"Average {results['share_frequency_per_user']['mean']:.2f} "
            f"shares per user"
        )

        return results

    def generate_exploratory_report(self) -> Dict[str, Any]:
        """
        Generate complete exploratory analysis report
        Covers all 10 exploration topics
        """
        print("\n" + "=" * 80)
        print("GENERATING EXPLORATORY ANALYSIS REPORT")
        print("=" * 80)

        # Run all analyses
        topics = [
            self.analyze_sports_and_venues(),
            self.analyze_travel_frequency(),
            self.analyze_content_engagement(),
            self.analyze_search_behavior_depth(),
            self.analyze_porsche_plus_engagement(),
            self.analyze_video_consumption(),
            self.analyze_map_interactions(),
            self.analyze_ai_guide_adoption(),
            self.analyze_session_patterns(),
            self.analyze_social_sharing()
        ]

        # Compile report
        report = {
            'report_metadata': {
                'title': 'Rednote Exploratory Analysis Report',
                'topics_analyzed': len(topics),
                'generated_at': pd.Timestamp.now().isoformat()
            },
            'topics': topics
        }

        print("\n" + "=" * 80)
        print("EXPLORATORY ANALYSIS COMPLETE")
        print(f"Analyzed {len(topics)} topics")
        print("=" * 80)

        return report


def main():
    """Main entry point for exploratory analysis"""
    import os

    # Initialize analyzer
    DATA_PATH = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"
    CONFIG_PATH = r"C:\projects\rednote data analyzer\rednote_analyzer\config\kpi_metrics.yaml"

    analyzer = RednoteAnalyzer(DATA_PATH, CONFIG_PATH)
    analyzer.load_data()

    # Initialize explorer
    explorer = RednoteExplorer(analyzer)

    # Generate report
    report = explorer.generate_exploratory_report()

    # Save report
    OUTPUT_PATH = r"C:\projects\rednote data analyzer\rednote_analyzer\output\exploratory_report.json"
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nExploratory report saved to: {OUTPUT_PATH}")

    # Print summary
    print("\n" + "=" * 80)
    print("TOPIC SUMMARY")
    print("=" * 80)
    for topic in report['topics']:
        print(f"\n{topic['topic']}:")
        print(f"  {topic['description']}")
        if topic['insights']:
            for insight in topic['insights']:
                print(f"  - {insight}")


if __name__ == '__main__':
    main()
