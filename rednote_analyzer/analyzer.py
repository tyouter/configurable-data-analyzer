"""
Rednote Data Analyzer
Core analytics module for processing Rednote tracking data and calculating KPIs
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import yaml
import os


class RednoteAnalyzer:
    """Main analyzer class for Rednote data"""

    def __init__(self, data_path: str, config_path: str = None):
        """
        Initialize analyzer

        Args:
            data_path: Path to the Excel data file
            config_path: Path to KPI config YAML file
        """
        self.data_path = data_path
        self.data = None
        self.config = None
        self.config_path = config_path

        if config_path:
            self.load_config()

    def load_data(self) -> pd.DataFrame:
        """Load data from Excel file"""
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        self.data = pd.read_excel(self.data_path)

        # Parse timestamps
        if 'strt_time_nano' in self.data.columns:
            self.data['strt_time_dt'] = pd.to_datetime(self.data['strt_time_nano'], errors='coerce')

        if 'end_time_nano' in self.data.columns:
            self.data['end_time_dt'] = pd.to_datetime(self.data['end_time_nano'], errors='coerce')

        # Extract date
        if 'strt_time_dt' in self.data.columns:
            self.data['date'] = self.data['strt_time_dt'].dt.date

        return self.data

    def load_config(self) -> Dict:
        """Load KPI configuration from YAML"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        return self.config

    def get_data_overview(self) -> Dict:
        """Get basic data overview statistics"""
        if self.data is None:
            self.load_data()

        overview = {
            'total_records': len(self.data),
            'total_columns': len(self.data.columns),
            'date_range': {},
            'unique_devices': 0,
            'unique_users': 0,
            'unique_events': 0,
            'event_types': {}
        }

        # Date range
        if 'strt_time_dt' in self.data.columns:
            valid_dates = self.data['strt_time_dt'].dropna()
            if not valid_dates.empty:
                overview['date_range'] = {
                    'start': str(valid_dates.min()),
                    'end': str(valid_dates.max()),
                    'days': (valid_dates.max() - valid_dates.min()).days + 1
                }

        # Unique counts
        if 'dvc_id' in self.data.columns:
            overview['unique_devices'] = self.data['dvc_id'].nunique()

        if 'reduser_id' in self.data.columns:
            overview['unique_users'] = self.data['reduser_id'].dropna().nunique()

        if 'span_nm' in self.data.columns:
            overview['unique_events'] = self.data['span_nm'].nunique()
            event_counts = self.data['span_nm'].value_counts().head(20)
            overview['event_types'] = event_counts.to_dict()

        return overview

    def get_user_behavior_chain(self, user_id: float, max_events: int = 50) -> pd.DataFrame:
        """
        Get behavior chain for a specific user

        Args:
            user_id: The reduser_id to analyze
            max_events: Maximum number of events to return

        Returns:
            DataFrame with user's behavior chain
        """
        if self.data is None:
            self.load_data()

        user_data = self.data[self.data['reduser_id'] == user_id].copy()

        if user_data.empty:
            return pd.DataFrame()

        # Sort by time
        if 'strt_time_dt' in user_data.columns:
            user_data = user_data.sort_values('strt_time_dt')

        # Select relevant columns
        cols_to_keep = ['span_nm', 'strt_time_dt', 'event_typ', 'page_strt_time']
        available_cols = [col for col in cols_to_keep if col in user_data.columns]
        user_data = user_data[available_cols]

        return user_data.head(max_events)

    def count_unique_users(self, event: str = None, start_date: str = None, end_date: str = None) -> int:
        """
        Count unique users, optionally filtered by event and date range

        Args:
            event: Filter by specific event name
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            Count of unique users
        """
        if self.data is None:
            self.load_data()

        filtered_data = self.data.copy()

        if event:
            filtered_data = filtered_data[filtered_data['span_nm'] == event]

        if start_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] >= pd.to_datetime(start_date)]

        if end_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] <= pd.to_datetime(end_date)]

        return filtered_data['reduser_id'].dropna().nunique()

    def count_events(self, events: List[str] = None, start_date: str = None, end_date: str = None,
                    unique_per_user_per_day: bool = False) -> int:
        """
        Count events, optionally with unique per user per day constraint

        Args:
            events: List of event names to count
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            unique_per_user_per_day: If True, count each user's events once per day

        Returns:
            Count of events
        """
        if self.data is None:
            self.load_data()

        filtered_data = self.data.copy()

        if events:
            filtered_data = filtered_data[filtered_data['span_nm'].isin(events)]

        if start_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] >= pd.to_datetime(start_date)]

        if end_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] <= pd.to_datetime(end_date)]

        if unique_per_user_per_day and 'date' in filtered_data.columns:
            # Count unique (user, date) combinations
            return filtered_data[['reduser_id', 'date']].drop_duplicates().shape[0]

        return len(filtered_data)

    def calculate_exposure_time(self, event: str, start_date: str = None, end_date: str = None) -> float:
        """
        Calculate total exposure time for an event

        Args:
            event: Event name to calculate exposure for
            start: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            Total exposure time in seconds
        """
        if self.data is None:
            self.load_data()

        filtered_data = self.data[self.data['span_nm'] == event].copy()

        if start_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] >= pd.to_datetime(start_date)]

        if end_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] <= pd.to_datetime(end_date)]

        # Calculate exposure time
        if 'strt_time_dt' in filtered_data.columns and 'end_time_dt' in filtered_data.columns:
            filtered_data['duration'] = (filtered_data['end_time_dt'] - filtered_data['strt_time_dt']).dt.total_seconds()
            # Only count valid durations (positive and not NaN)
            total_duration = filtered_data[filtered_data['duration'] > 0]['duration'].sum()
            return total_duration

        return 0.0

    def calculate_active_users(self, event: str, min_duration_seconds: float = 0,
                              start_date: str = None, end_date: str = None) -> int:
        """
        Calculate number of active users based on minimum duration threshold

        Args:
            event: Event name to analyze
            min_duration_seconds: Minimum exposure time in seconds to count as active
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            Count of active users
        """
        if self.data is None:
            self.load_data()

        filtered_data = self.data[self.data['span_nm'] == event].copy()

        if start_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] >= pd.to_datetime(start_date)]

        if end_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] <= pd.to_datetime(end_date)]

        # Calculate exposure time per session
        if 'strt_time_dt' in filtered_data.columns and 'end_time_dt' in filtered_data.columns:
            filtered_data['duration'] = (filtered_data['end_time_dt'] - filtered_data['strt_time_dt']).dt.total_seconds()

            # Group by user and check total duration
            user_durations = filtered_data.groupby('reduser_id')['duration'].sum()
            active_users = user_durations[user_durations >= min_duration_seconds].count()
            return active_users

        return 0

    def calculate_retention_rate(self, event: str, day_n: int = 7,
                                 start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        Calculate n-day retention rate

        Args:
            event: Event name to track
            day_n: Number of days for retention calculation (7, 14, 30)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            Dictionary with retention metrics
        """
        if self.data is None:
            self.load_data()

        filtered_data = self.data[self.data['span_nm'] == event].copy()

        if start_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] >= pd.to_datetime(start_date)]

        if end_date and 'strt_time_dt' in filtered_data.columns:
            filtered_data = filtered_data[filtered_data['strt_time_dt'] <= pd.to_datetime(end_date)]

        if 'strt_time_dt' not in filtered_data.columns:
            return {'day_n': day_n, 'retention_rate': 0, 'users_day_0': 0, 'users_day_n': 0}

        # Get users active on each day
        filtered_data['date'] = filtered_data['strt_time_dt'].dt.date
        daily_users = filtered_data.groupby('date')['reduser_id'].apply(set).to_dict()

        retention_pairs = []
        for date, users in daily_users.items():
            target_date = date + timedelta(days=day_n)
            if target_date in daily_users:
                users_target = daily_users[target_date]
                retained = len(users & users_target)
                retention_pairs.append((len(users), retained))

        if not retention_pairs:
            return {'day_n': day_n, 'retention_rate': 0, 'users_day_0': 0, 'users_day_n': 0}

        total_day_0 = sum(p[0] for p in retention_pairs)
        total_retained = sum(p[1] for p in retention_pairs)

        retention_rate = (total_retained / total_day_0 * 100) if total_day_0 > 0 else 0

        return {
            'day_n': day_n,
            'retention_rate': round(retention_rate, 2),
            'users_day_0': total_day_0,
            'users_day_n': total_retained
        }

    def calculate_kpi(self, kpi_name: str, **kwargs) -> Any:
        """
        Calculate a specific KPI based on configuration

        Args:
            kpi_name: Name of the KPI to calculate
            **kwargs: Additional parameters for KPI calculation

        Returns:
            Calculated KPI value
        """
        if self.config is None:
            self.load_config()

        # Find KPI config
        kpi_config = None
        for category in self.config.values():
            if isinstance(category, dict) and kpi_name in category:
                kpi_config = category[kpi_name]
                break

        if not kpi_config:
            raise ValueError(f"KPI '{kpi_name}' not found in configuration")

        kpi_type = kpi_config.get('type')

        if kpi_type == 'count_unique_users':
            event = kpi_config.get('event')
            return self.count_unique_users(event, **kwargs)

        elif kpi_type == 'count_events':
            events = kpi_config.get('events', [kpi_config.get('event')])
            unique_per_day = kpi_config.get('unique_per_user_per_day', False)
            return self.count_events(events, unique_per_user_per_day=unique_per_day, **kwargs)

        elif kpi_type == 'exposure_time':
            event = kpi_config.get('event')
            return self.calculate_exposure_time(event, **kwargs)

        elif kpi_type == 'active_rate':
            event = kpi_config.get('event')
            min_duration = kpi_config.get('min_duration_seconds', 0)
            active_users = self.calculate_active_users(event, min_duration_seconds=min_duration, **kwargs)
            total_users = self.data['reduser_id'].dropna().nunique()
            return round((active_users / total_users * 100) if total_users > 0 else 0, 2)

        elif kpi_type == 'avg_duration':
            event = kpi_config.get('event')
            total_duration = self.calculate_exposure_time(event, **kwargs)
            event_count = self.count_events([event], **kwargs)
            return round(total_duration / event_count, 2) if event_count > 0 else 0

        elif kpi_type == 'avg_opens_per_active_user':
            event = kpi_config.get('event')
            min_duration = kpi_config.get('min_duration_seconds', 0)
            total_opens = self.count_events([event], **kwargs)
            active_users = self.calculate_active_users(event, min_duration_seconds=min_duration, **kwargs)
            return round(total_opens / active_users, 2) if active_users > 0 else 0

        elif kpi_type == 'avg_events_per_user':
            event = kpi_config.get('event')
            event_count = self.count_events([event], **kwargs)
            user_count = self.count_unique_users(event, **kwargs)
            return round(event_count / user_count, 2) if user_count > 0 else 0

        elif kpi_type == 'usage_rate':
            numerator_event = kpi_config.get('numerator_event')
            denominator_events = kpi_config.get('denominator_events')
            numerator_count = self.count_events([numerator_event], **kwargs)
            denominator_count = self.count_events(denominator_events, **kwargs)
            return round((numerator_count / denominator_count * 100) if denominator_count > 0 else 0, 2)

        elif kpi_type == 'user_ratio':
            numerator_event = kpi_config.get('numerator_event')
            numerator_users = self.count_unique_users(numerator_event, **kwargs)
            total_users = self.data['reduser_id'].dropna().nunique()
            return round((numerator_users / total_users * 100) if total_users > 0 else 0, 2)

        elif kpi_type == 'ratio':
            numerator_kpi = kpi_config.get('numerator')
            denominator_kpi = kpi_config.get('denominator')
            numerator_value = self.calculate_kpi(numerator_kpi, **kwargs)
            denominator_value = self.calculate_kpi(denominator_kpi, **kwargs)
            return round(numerator_value / denominator_value, 2) if denominator_value > 0 else 0

        elif kpi_type == 'retention_rate':
            event = kpi_config.get('event')
            retention_days = kpi_config.get('retention_days', [7])
            min_duration = kpi_config.get('min_duration_seconds', 0)
            # Return retention for first specified day
            retention_result = self.calculate_retention_rate(event, day_n=retention_days[0], **kwargs)
            return retention_result['retention_rate']

        else:
            raise ValueError(f"Unknown KPI type: {kpi_type}")

    def calculate_all_kpis(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        Calculate all configured KPIs

        Args:
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)

        Returns:
            Dictionary with all KPI results
        """
        if self.config is None:
            self.load_config()

        results = {}

        for category_name, category_kpis in self.config.items():
            if category_name == 'data_source':
                continue

            if not isinstance(category_kpis, dict):
                continue

            results[category_name] = {}

            for kpi_name, kpi_config in category_kpis.items():
                try:
                    value = self.calculate_kpi(kpi_name, start_date=start_date, end_date=end_date)
                    results[category_name][kpi_name] = {
                        'name': kpi_config.get('name'),
                        'value': value,
                        'description': kpi_config.get('description', '')
                    }
                except Exception as e:
                    results[category_name][kpi_name] = {
                        'name': kpi_config.get('name'),
                        'value': f"Error: {str(e)}",
                        'description': kpi_config.get('description', '')
                    }

        return results

    def analyze_poi_data(self) -> Dict[str, Any]:
        """Analyze POI (Point of Interest) related data"""
        if self.data is None:
            self.load_data()

        poi_data = self.data[self.data['rednote_poi_title'].notna()].copy()

        results = {
            'total_poi_interactions': len(poi_data),
            'unique_poi_count': 0,
            'top_poi': {},
            'poi_type_distribution': {},
            'users_interacting_with_poi': 0
        }

        if not poi_data.empty:
            results['unique_poi_count'] = poi_data['rednote_poi_title'].nunique()
            results['users_interacting_with_poi'] = poi_data['reduser_id'].dropna().nunique()

            # Top POIs
            if 'rednote_poi_title' in poi_data.columns:
                top_pois = poi_data['rednote_poi_title'].value_counts().head(10)
                results['top_poi'] = top_pois.to_dict()

            # POI type distribution
            if 'rednote_poi_typ_nm' in poi_data.columns:
                poi_types = poi_data['rednote_poi_typ_nm'].value_counts()
                results['poi_type_distribution'] = poi_types.to_dict()

        return results

    def analyze_search_behavior(self) -> Dict[str, Any]:
        """Analyze user search behavior"""
        if self.data is None:
            self.load_data()

        search_events = self.data[
            self.data['span_nm'].str.contains('search', case=False, na=False)
        ].copy()

        results = {
            'total_search_events': len(search_events),
            'unique_search_users': 0,
            'search_event_types': {}
        }

        if not search_events.empty:
            results['unique_search_users'] = search_events['reduser_id'].dropna().nunique()

            # Search event distribution
            search_types = search_events['span_nm'].value_counts()
            results['search_event_types'] = search_types.to_dict()

        return results

    def analyze_content_interaction(self) -> Dict[str, Any]:
        """Analyze content (post) interaction behavior"""
        if self.data is None:
            self.load_data()

        results = {
            'total_likes': 0,
            'total_saves': 0,
            'total_follows': 0,
            'unique_posts_viewed': 0,
            'content_type_distribution': {}
        }

        # Count likes
        like_events = self.data[self.data['rednote_post_is_like'].notna()]
        results['total_likes'] = len(like_events)

        # Count saves
        save_events = self.data[self.data['rednote_post_is_save'].notna()]
        results['total_saves'] = len(save_events)

        # Count follows
        follow_events = self.data[self.data['rednote_post_follow'].notna()]
        results['total_follows'] = len(follow_events)

        # Content type distribution
        if 'rednote_post_typ' in self.data.columns:
            content_types = self.data['rednote_post_typ'].value_counts()
            results['content_type_distribution'] = content_types.to_dict()

        return results

    def analyze_video_behavior(self) -> Dict[str, Any]:
        """Analyze video content interaction behavior"""
        if self.data is None:
            self.load_data()

        results = {
            'video_plays': 0,
            'autoplay_enabled_count': 0,
            'play_speed_distribution': {}
        }

        # Video plays
        play_events = self.data[self.data['rednote_video_post_is_play'] == 0]
        results['video_plays'] = len(play_events)

        # Autoplay enabled
        autoplay_events = self.data[self.data['rednote_video_post_autoplay_is_open'] == 1]
        results['autoplay_enabled_count'] = len(autoplay_events)

        # Play speed distribution
        if 'rednote_video_post_play_speed' in self.data.columns:
            speed_dist = self.data['rednote_video_post_play_speed'].value_counts()
            results['play_speed_distribution'] = speed_dist.to_dict()

        return results

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate comprehensive summary report"""
        if self.data is None:
            self.load_data()

        report = {
            'data_overview': self.get_data_overview(),
            'poi_analysis': self.analyze_poi_data(),
            'search_behavior': self.analyze_search_behavior(),
            'content_interaction': self.analyze_content_interaction(),
            'video_behavior': self.analyze_video_behavior(),
            'kpi_metrics': self.calculate_all_kpis()
        }

        return report
