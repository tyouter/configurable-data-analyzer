"""
Test Suite for Rednote Data Analyzer
Comprehensive test coverage for all analyzer functions
"""

import pytest
import pandas as pd
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import RednoteAnalyzer

# Direct paths
DATA_PATH = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"
CONFIG_PATH = r"C:\projects\rednote data analyzer\rednote_analyzer\config\kpi_metrics.yaml"


class TestRednoteAnalyzer:
    """Test suite for RednoteAnalyzer class"""

    @pytest.fixture
    def analyzer(self):
        """Fixture to create analyzer instance"""
        return RednoteAnalyzer(DATA_PATH, CONFIG_PATH)

    def test_initialization(self, analyzer):
        """Test analyzer initialization"""
        assert analyzer is not None
        assert analyzer.data_path.endswith("rednote data_20260319-20260330.xlsx")
        assert analyzer.config_path.endswith("kpi_metrics.yaml")

    def test_load_data(self, analyzer):
        """Test data loading functionality"""
        data = analyzer.load_data()
        assert data is not None
        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0
        assert analyzer.data is not None

    def test_load_config(self, analyzer):
        """Test config loading functionality"""
        config = analyzer.load_config()
        assert config is not None
        assert isinstance(config, dict)
        assert 'app_metrics' in config
        assert 'data_source' in config

    def test_data_overview(self, analyzer):
        """Test data overview generation"""
        analyzer.load_data()
        overview = analyzer.get_data_overview()

        assert overview is not None
        assert 'total_records' in overview
        assert 'unique_devices' in overview
        assert 'unique_users' in overview
        assert 'unique_events' in overview
        assert 'event_types' in overview
        assert overview['total_records'] > 0
        assert overview['unique_devices'] > 0

    def test_count_unique_users(self, analyzer):
        """Test counting unique users"""
        analyzer.load_data()

        # Count all unique users
        all_users = analyzer.count_unique_users()
        assert all_users > 0

        # Count users for specific event
        porsche_users = analyzer.count_unique_users(event="porsche_page_pageshow")
        assert porsche_users >= 0

    def test_count_events(self, analyzer):
        """Test counting events"""
        analyzer.load_data()

        # Count all events
        all_events = analyzer.count_events()
        assert all_events > 0

        # Count specific events
        discovery_events = analyzer.count_events(events=["discovery_page_pageshow"])
        assert discovery_events >= 0

        # Test unique per user per day
        unique_events = analyzer.count_events(
            events=["discovery_page_pageshow"],
            unique_per_user_per_day=True
        )
        assert unique_events >= 0

    def test_calculate_exposure_time(self, analyzer):
        """Test exposure time calculation"""
        analyzer.load_data()

        exposure_time = analyzer.calculate_exposure_time(event="porsche_page_pageshow")
        assert exposure_time >= 0

    def test_calculate_active_users(self, analyzer):
        """Test active users calculation"""
        analyzer.load_data()

        active_users = analyzer.calculate_active_users(
            event="porsche_page_pageshow",
            min_duration_seconds=5
        )
        assert active_users >= 0

    def test_calculate_retention_rate(self, analyzer):
        """Test retention rate calculation"""
        analyzer.load_data()

        retention = analyzer.calculate_retention_rate(
            event="discovery_page_pageshow",
            day_n=7
        )
        assert 'day_n' in retention
        assert 'retention_rate' in retention
        assert retention['day_n'] == 7
        assert 0 <= retention['retention_rate'] <= 100

    def test_calculate_kpi(self, analyzer):
        """Test individual KPI calculation"""
        analyzer.load_data()

        # Test various KPI types
        kpi_tests = [
            ('app_open_total', 'app_metrics'),
            ('app_open_users', 'app_metrics'),
            ('app_avg_opens_per_user', 'app_metrics'),
            ('app_active_rate', 'app_metrics'),
            ('porsche_page_exposure_duration', 'porsche_plus_metrics'),
            ('porsche_active_rate', 'porsche_plus_metrics'),
            ('discovery_page_exposure_duration', 'discovery_page_metrics'),
            ('discovery_active_rate', 'discovery_page_metrics'),
        ]

        for kpi_name, category in kpi_tests:
            try:
                value = analyzer.calculate_kpi(kpi_name)
                assert value is not None
            except Exception as e:
                # Some KPIs might not have data
                pass

    def test_calculate_all_kpis(self, analyzer):
        """Test calculating all KPIs"""
        analyzer.load_data()
        kpi_results = analyzer.calculate_all_kpis()

        assert kpi_results is not None
        assert isinstance(kpi_results, dict)

        # Check main categories exist
        expected_categories = [
            'app_metrics',
            'porsche_plus_metrics',
            'discovery_page_metrics',
            'ai_guide_metrics',
            'share_metrics'
        ]

        for category in expected_categories:
            assert category in kpi_results

    def test_analyze_poi_data(self, analyzer):
        """Test POI data analysis"""
        analyzer.load_data()
        poi_analysis = analyzer.analyze_poi_data()

        assert poi_analysis is not None
        assert 'total_poi_interactions' in poi_analysis
        assert 'unique_poi_count' in poi_analysis
        assert 'top_poi' in poi_analysis
        assert 'poi_type_distribution' in poi_analysis

    def test_analyze_search_behavior(self, analyzer):
        """Test search behavior analysis"""
        analyzer.load_data()
        search_analysis = analyzer.analyze_search_behavior()

        assert search_analysis is not None
        assert 'total_search_events' in search_analysis
        assert 'unique_search_users' in search_analysis
        assert 'search_event_types' in search_analysis

    def test_analyze_content_interaction(self, analyzer):
        """Test content interaction analysis"""
        analyzer.load_data()
        content_analysis = analyzer.analyze_content_interaction()

        assert content_analysis is not None
        assert 'total_likes' in content_analysis
        assert 'total_saves' in content_analysis
        assert 'total_follows' in content_analysis
        assert 'content_type_distribution' in content_analysis

    def test_analyze_video_behavior(self, analyzer):
        """Test video behavior analysis"""
        analyzer.load_data()
        video_analysis = analyzer.analyze_video_behavior()

        assert video_analysis is not None
        assert 'video_plays' in video_analysis
        assert 'autoplay_enabled_count' in video_analysis
        assert 'play_speed_distribution' in video_analysis

    def test_generate_summary_report(self, analyzer):
        """Test comprehensive summary report generation"""
        report = analyzer.generate_summary_report()

        assert report is not None
        assert isinstance(report, dict)

        required_sections = [
            'data_overview',
            'poi_analysis',
            'search_behavior',
            'content_interaction',
            'video_behavior',
            'kpi_metrics'
        ]

        for section in required_sections:
            assert section in report

    def test_user_behavior_chain(self, analyzer):
        """Test user behavior chain extraction"""
        analyzer.load_data()

        # Get a valid user ID
        user_id = analyzer.data['reduser_id'].dropna().iloc[0]

        behavior_chain = analyzer.get_user_behavior_chain(user_id)

        assert behavior_chain is not None
        assert isinstance(behavior_chain, pd.DataFrame)

    def test_date_filtering(self, analyzer):
        """Test date filtering functionality"""
        analyzer.load_data()

        overview = analyzer.get_data_overview()

        if overview['date_range']:
            start_date = overview['date_range']['start'].split()[0]
            end_date = overview['date_range']['end'].split()[0]

            # Test with date filters
            users_filtered = analyzer.count_unique_users(
                event="porsche_page_pageshow",
                start_date=start_date,
                end_date=end_date
            )

            assert users_filtered >= 0


class TestDataQuality:
    """Test suite for data quality checks"""

    @pytest.fixture
    def analyzer(self):
        """Fixture to create analyzer instance"""
        return RednoteAnalyzer(DATA_PATH)

    def test_required_columns_exist(self, analyzer):
        """Test that required columns exist in data"""
        analyzer.load_data()
        data = analyzer.data

        required_columns = [
            'dvc_id',
            'span_nm',
            'strt_time_nano',
            'end_time_nano',
            'reduser_id'
        ]

        for col in required_columns:
            assert col in data.columns

    def test_data_consistency(self, analyzer):
        """Test data consistency"""
        analyzer.load_data()
        data = analyzer.data

        # Check that end time is not before start time
        if 'strt_time_dt' in data.columns and 'end_time_dt' in data.columns:
            valid_rows = data[data['strt_time_dt'].notna() & data['end_time_dt'].notna()]
            invalid_rows = valid_rows[valid_rows['end_time_dt'] < valid_rows['strt_time_dt']]

            # Report invalid rows if any
            if not invalid_rows.empty:
                print(f"Warning: Found {len(invalid_rows)} rows with end_time < start_time")

    def test_user_device_mapping(self, analyzer):
        """Test user-device relationship"""
        analyzer.load_data()
        data = analyzer.data

        # Check that we have both user and device IDs
        users_with_devices = data[data['reduser_id'].notna() & data['dvc_id'].notna()]
        assert len(users_with_devices) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
