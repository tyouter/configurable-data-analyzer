"""
Generate KPI Analysis Report
Creates comprehensive KPI analysis with all predefined metrics
"""

import json
import os
from datetime import datetime

# Import analyzer
from analyzer import RednoteAnalyzer

# Direct paths
DATA_PATH = r"C:\projects\rednote data analyzer\data\rednote\rednote data_20260319-20260330.xlsx"
CONFIG_PATH = r"C:\projects\rednote data analyzer\rednote_analyzer\config\kpi_metrics.yaml"
OUTPUT_PATH = r"C:\projects\rednote data analyzer\rednote_analyzer\output\kpi_report.json"


def generate_kpi_report():
    """Generate comprehensive KPI report"""

    print("=" * 80)
    print("GENERATING KPI ANALYSIS REPORT")
    print("=" * 80)
    print()

    # Initialize analyzer
    analyzer = RednoteAnalyzer(DATA_PATH, CONFIG_PATH)

    # Load data
    print("Loading data...")
    analyzer.load_data()
    print(f"Loaded {len(analyzer.data)} records")

    # Get data overview
    print("\nAnalyzing data overview...")
    overview = analyzer.get_data_overview()

    # Calculate all KPIs
    print("\nCalculating all KPIs...")
    kpi_results = analyzer.calculate_all_kpis()

    # Analyze additional data
    print("\nAnalyzing POI data...")
    poi_analysis = analyzer.analyze_poi_data()

    print("\nAnalyzing search behavior...")
    search_analysis = analyzer.analyze_search_behavior()

    print("\nAnalyzing content interactions...")
    content_analysis = analyzer.analyze_content_interaction()

    print("\nAnalyzing video behavior...")
    video_analysis = analyzer.analyze_video_behavior()

    # Build complete report
    report = {
        "report_metadata": {
            "title": "Rednote KPI Analysis Report",
            "generated_at": datetime.now().isoformat(),
            "data_period": overview.get('date_range', {}),
            "total_records": overview['total_records'],
            "unique_users": overview['unique_users'],
            "unique_devices": overview['unique_devices']
        },
        "data_overview": overview,
        "kpi_metrics": kpi_results,
        "poi_analysis": poi_analysis,
        "search_behavior": search_analysis,
        "content_interaction": content_analysis,
        "video_behavior": video_analysis
    }

    # Save report to JSON
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nReport saved to: {OUTPUT_PATH}")

    # Print summary
    print("\n" + "=" * 80)
    print("KPI SUMMARY")
    print("=" * 80)

    # APP Metrics
    if 'app_metrics' in kpi_results:
        print("\n[APP Metrics]")
        for kpi_id, kpi_data in kpi_results['app_metrics'].items():
            print(f"  {kpi_id}: {kpi_data.get('value', 'N/A')}")

    # Porsche+ Metrics
    if 'porsche_plus_metrics' in kpi_results:
        print("\n[Porsche+ Metrics]")
        for kpi_id, kpi_data in kpi_results['porsche_plus_metrics'].items():
            print(f"  {kpi_id}: {kpi_data.get('value', 'N/A')}")

    # Discovery Page Metrics
    if 'discovery_page_metrics' in kpi_results:
        print("\n[Discovery Page Metrics]")
        for kpi_id, kpi_data in kpi_results['discovery_page_metrics'].items():
            print(f"  {kpi_id}: {kpi_data.get('value', 'N/A')}")

    # AI Guide Metrics
    if 'ai_guide_metrics' in kpi_results:
        print("\n[AI Guide Metrics]")
        for kpi_id, kpi_data in kpi_results['ai_guide_metrics'].items():
            print(f"  {kpi_id}: {kpi_data.get('value', 'N/A')}")

    # Share Metrics
    if 'share_metrics' in kpi_results:
        print("\n[Share Metrics]")
        for kpi_id, kpi_data in kpi_results['share_metrics'].items():
            print(f"  {kpi_id}: {kpi_data.get('value', 'N/A')}")

    print("\n" + "=" * 80)
    print("[Additional Insights]")
    print(f"  Total POI interactions: {poi_analysis.get('total_poi_interactions', 0)}")
    print(f"  Unique POIs: {poi_analysis.get('unique_poi_count', 0)}")
    print(f"  Total search events: {search_analysis.get('total_search_events', 0)}")
    print(f"  Total likes: {content_analysis.get('total_likes', 0)}")
    print(f"  Total saves: {content_analysis.get('total_saves', 0)}")
    print(f"  Total follows: {content_analysis.get('total_follows', 0)}")
    print(f"  Video plays: {video_analysis.get('video_plays', 0)}")
    print("=" * 80)

    return report


if __name__ == '__main__':
    generate_kpi_report()
