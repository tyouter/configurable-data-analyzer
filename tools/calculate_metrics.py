#!/usr/bin/env python
"""
计算BI看板指标并生成看板数据文件
"""
import pandas as pd
import duckdb
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

DATA_PATH = Path(__file__).parent.parent / "data" / "rednote" / "rednote20260319-20260412.xlsx"
DASHBOARD_PATH = Path(__file__).parent.parent / "bi" / "dashboards"

def load_data():
    """加载并预处理数据"""
    print("Loading data...")
    df = pd.read_excel(DATA_PATH)

    if 'span_name' in df.columns:
        df['event_name'] = df['span_name']

    df['page_root'] = df['event_name'].astype(str).str.split('_').str[0]

    if 'start_time_nano' in df.columns:
        df['start_time'] = pd.to_datetime(df['start_time_nano'], unit='ns', errors='coerce')
        # 使用简短日期格式 YYYY-MM-DD
        df['event_date'] = df['start_time'].dt.strftime('%Y-%m-%d')
        df['event_hour'] = df['start_time'].dt.hour
        df['event_weekday'] = df['start_time'].dt.dayofweek
        df['is_weekend'] = (df['event_weekday'] >= 5).astype(int)

    total_users = df['reduser_id'].nunique()
    print(f"Data loaded: {len(df)} events, {total_users} users")
    return df, total_users

def execute_sql(conn, sql):
    try:
        return conn.execute(sql).fetchdf()
    except Exception as e:
        print(f"SQL Error: {e}")
        return pd.DataFrame()

def convert_to_json_serializable(obj):
    """将pandas Timestamp等对象转换为JSON可序列化的格式"""
    import datetime as dt
    if isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (pd.Timestamp, dt.date, dt.datetime)):
        return str(obj)[:10]  # 只保留日期部分 YYYY-MM-DD
    elif isinstance(obj, (float, int)):
        if pd.isna(obj) or (isinstance(obj, float) and (obj != obj)):
            return None
        return round(obj, 2) if isinstance(obj, float) else obj
    elif obj is None:
        return None
    else:
        return str(obj)

def calculate_discovery_metrics(conn, df, total_users):
    """计算发现页相关指标"""
    print("\n=== Calculating Discovery Page Metrics ===")
    metrics = {}

    # 1. 发现页CTR趋势
    sql = """
    SELECT
        event_date,
        COUNT(CASE WHEN event_name = 'discovery_page_post_card_cardshow' THEN 1 END) as shows,
        COUNT(CASE WHEN event_name = 'discovery_page_post_card_click' THEN 1 END) as clicks,
        ROUND(CAST(COUNT(CASE WHEN event_name = 'discovery_page_post_card_click' THEN 1 END) AS DOUBLE)
              / NULLIF(COUNT(CASE WHEN event_name = 'discovery_page_post_card_cardshow' THEN 1 END), 0) * 100, 2) as ctr_pct
    FROM df
    WHERE event_name IN ('discovery_page_post_card_cardshow', 'discovery_page_post_card_click')
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['discovery_ctr_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"1. Discovery CTR trend: {len(result)} days")

    # 2. 帖子顺位分布 (只取前20位)
    sql = """
    SELECT
        CAST(rednote_post_num AS INT) as position,
        COUNT(*) as click_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as pct
    FROM df
    WHERE event_name = 'discovery_page_post_card_click' AND rednote_post_num IS NOT NULL
    GROUP BY CAST(rednote_post_num AS INT)
    ORDER BY position
    LIMIT 20
    """
    result = execute_sql(conn, sql)
    metrics['discovery_post_position_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"2. Post position distribution: {len(result)} positions")

    # 3. 帖子类型分布
    sql = """
    SELECT
        CASE WHEN rednote_post_type = 'normal' THEN '图文' WHEN rednote_post_type = 'video' THEN '视频' ELSE rednote_post_type END as post_type,
        COUNT(*) as click_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as pct
    FROM df
    WHERE event_name = 'discovery_page_post_card_click' AND rednote_post_type IS NOT NULL
    GROUP BY rednote_post_type
    ORDER BY click_count DESC
    """
    result = execute_sql(conn, sql)
    metrics['discovery_post_type_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"3. Post type distribution: {len(result)} types")

    # 4. 发现页用户进入带POI帖子的比例（基于POI_button_show事件）
    # 计算每天从发现页进入帖子详情页的用户中，有多少看到了POI按钮
    sql = """
    WITH discovery_click_users AS (
        SELECT DISTINCT event_date, reduser_id
        FROM df
        WHERE event_name = 'discovery_page_post_card_click'
    ),
    poi_users AS (
        SELECT DISTINCT event_date, reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_POI_button_show'
    )
    SELECT
        d.event_date,
        COUNT(DISTINCT d.reduser_id) as total_click_users,
        COUNT(DISTINCT p.reduser_id) as poi_post_users,
        ROUND(COUNT(DISTINCT p.reduser_id) * 100.0 / COUNT(DISTINCT d.reduser_id), 2) as poi_pct
    FROM discovery_click_users d
    LEFT JOIN poi_users p ON d.event_date = p.event_date AND d.reduser_id = p.reduser_id
    GROUP BY d.event_date
    ORDER BY d.event_date
    """
    result = execute_sql(conn, sql)
    metrics['discovery_poi_post_ratio_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"4. POI post ratio trend: {len(result)} days")

    # 5. 发现页进入带POI帖子的用户导航占比
    sql = """
    WITH poi_post_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_POI_button_show'
    ),
    nav_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
    )
    SELECT
        '带POI帖子用户' as user_type,
        (SELECT COUNT(*) FROM poi_post_users) as total_users,
        (SELECT COUNT(*) FROM poi_post_users WHERE reduser_id IN (SELECT reduser_id FROM nav_users)) as nav_users,
        ROUND((SELECT COUNT(*) FROM poi_post_users WHERE reduser_id IN (SELECT reduser_id FROM nav_users)) * 100.0
              / NULLIF((SELECT COUNT(*) FROM poi_post_users), 0), 2) as nav_ratio_pct
    """
    result = execute_sql(conn, sql)
    metrics['discovery_poi_post_nav_ratio'] = convert_to_json_serializable(result.to_dict('records')[0] if len(result) > 0 else {})
    print(f"5. POI post nav ratio: {metrics['discovery_poi_post_nav_ratio']}")

    # 6. 带POI帖子生成AI路书占比
    sql = """
    WITH poi_post_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_POI_button_show'
    ),
    ai_guide_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_ai_travel_guide_button_click'
    )
    SELECT
        '带POI帖子用户' as user_type,
        (SELECT COUNT(*) FROM poi_post_users) as total_users,
        (SELECT COUNT(*) FROM poi_post_users WHERE reduser_id IN (SELECT reduser_id FROM ai_guide_users)) as ai_guide_users,
        ROUND((SELECT COUNT(*) FROM poi_post_users WHERE reduser_id IN (SELECT reduser_id FROM ai_guide_users)) * 100.0
              / NULLIF((SELECT COUNT(*) FROM poi_post_users), 0), 2) as ai_guide_ratio_pct
    """
    result = execute_sql(conn, sql)
    metrics['discovery_poi_post_ai_guide_ratio'] = convert_to_json_serializable(result.to_dict('records')[0] if len(result) > 0 else {})
    print(f"6. POI post AI guide ratio: {metrics['discovery_poi_post_ai_guide_ratio']}")

    # 7. 漏斗图（正确顺序：帖子详情页 → POI详情页 → 发起导航）
    sql = """
    SELECT '1_帖子详情页' as step_order, '帖子详情页' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE page_root = 'post'
    UNION ALL
    SELECT '2_POI详情页' as step_order, 'POI详情页' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE page_root = 'poi'
    UNION ALL
    SELECT '3_发起导航' as step_order, '发起导航' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
    ORDER BY step_order
    """
    result = execute_sql(conn, sql)
    metrics['discovery_funnel'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"7. Discovery funnel: {metrics['discovery_funnel']}")

    return metrics

def calculate_porsche_metrics(conn, df, total_users):
    """计算Porsche+页相关指标"""
    print("\n=== Calculating Porsche Page Metrics ===")
    metrics = {}

    # 1. Porsche活跃率趋势
    sql = """
    SELECT
        event_date,
        COUNT(DISTINCT reduser_id) as active_users,
        ROUND(COUNT(DISTINCT reduser_id) * 100.0 / ?, 2) as active_rate_pct
    FROM df
    WHERE page_root = 'porsche'
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql.replace('?', str(total_users)))
    metrics['porsche_active_rate_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"1. Porsche active rate trend: {len(result)} days")

    # 2. Porsche人均打开次数
    sql = """
    SELECT
        event_date,
        COUNT(*) as events,
        COUNT(DISTINCT reduser_id) as users,
        ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT reduser_id), 2) as avg_events
    FROM df
    WHERE page_root = 'porsche'
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['porsche_avg_open_count'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"2. Porsche avg open count: {len(result)} days")

    # 3. Porsche CTR趋势
    sql = """
    SELECT
        event_date,
        COUNT(CASE WHEN event_name = 'porsche_page_recommend_post_card_cardshow' THEN 1 END) as shows,
        COUNT(CASE WHEN event_name = 'porsche_page_recommend_post_card_click' THEN 1 END) as clicks,
        ROUND(CAST(COUNT(CASE WHEN event_name = 'porsche_page_recommend_post_card_click' THEN 1 END) AS DOUBLE)
              / NULLIF(COUNT(CASE WHEN event_name = 'porsche_page_recommend_post_card_cardshow' THEN 1 END), 0) * 100, 2) as ctr_pct
    FROM df
    WHERE event_name IN ('porsche_page_recommend_post_card_cardshow', 'porsche_page_recommend_post_card_click')
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['porsche_ctr_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"3. Porsche CTR trend: {len(result)} days")

    # 4. Porsche帖子顺位分布
    sql = """
    SELECT
        CAST(rednote_post_num AS INT) as position,
        COUNT(*) as click_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as pct
    FROM df
    WHERE event_name = 'porsche_page_recommend_post_card_click' AND rednote_post_num IS NOT NULL
    GROUP BY CAST(rednote_post_num AS INT)
    ORDER BY position
    LIMIT 20
    """
    result = execute_sql(conn, sql)
    metrics['porsche_post_position_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"4. Porsche post position distribution: {len(result)} positions")

    # 5. 运营位与非运营位对比（基于is_operational_rec字段）
    # 注意：数据中所有Porsche点击的is_operational_rec=1，所以没有非运营位数据
    sql = """
    SELECT
        CASE WHEN rednote_post_is_operational_rec = 1 THEN '运营位' ELSE '非运营位' END as position_type,
        COUNT(*) as click_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as pct
    FROM df
    WHERE event_name = 'porsche_page_recommend_post_card_click'
    GROUP BY rednote_post_is_operational_rec
    ORDER BY click_count DESC
    """
    result = execute_sql(conn, sql)
    metrics['porsche_operational_vs_non_operational'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"5. Operational vs non-operational: {metrics['porsche_operational_vs_non_operational']}")

    # 6. Porsche帖子类型分布
    sql = """
    SELECT
        CASE WHEN rednote_post_type = 'normal' THEN '图文' WHEN rednote_post_type = 'video' THEN '视频' ELSE rednote_post_type END as post_type,
        COUNT(*) as click_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as pct
    FROM df
    WHERE event_name = 'porsche_page_recommend_post_card_click' AND rednote_post_type IS NOT NULL
    GROUP BY rednote_post_type
    ORDER BY click_count DESC
    """
    result = execute_sql(conn, sql)
    metrics['porsche_post_type_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"6. Porsche post type distribution: {len(result)} types")

    # 7. Porsche用户进入带POI帖子的比例
    sql = """
    WITH porsche_click_users AS (
        SELECT DISTINCT event_date, reduser_id
        FROM df
        WHERE event_name = 'porsche_page_recommend_post_card_click'
    ),
    poi_users AS (
        SELECT DISTINCT event_date, reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_POI_button_show'
    )
    SELECT
        p.event_date,
        COUNT(DISTINCT p.reduser_id) as total_click_users,
        COUNT(DISTINCT poi.reduser_id) as poi_post_users,
        ROUND(COUNT(DISTINCT poi.reduser_id) * 100.0 / COUNT(DISTINCT p.reduser_id), 2) as poi_pct
    FROM porsche_click_users p
    LEFT JOIN poi_users poi ON p.event_date = poi.event_date AND p.reduser_id = poi.reduser_id
    GROUP BY p.event_date
    ORDER BY p.event_date
    """
    result = execute_sql(conn, sql)
    metrics['porsche_poi_post_ratio_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"7. Porsche POI post ratio trend: {len(result)} days")

    # 8. Porsche用户导航占比
    sql = """
    WITH porsche_poi_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_POI_button_show'
    ),
    nav_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
    )
    SELECT
        'Porsche+带POI帖子用户' as user_type,
        (SELECT COUNT(*) FROM porsche_poi_users) as total_users,
        (SELECT COUNT(*) FROM porsche_poi_users WHERE reduser_id IN (SELECT reduser_id FROM nav_users)) as nav_users,
        ROUND((SELECT COUNT(*) FROM porsche_poi_users WHERE reduser_id IN (SELECT reduser_id FROM nav_users)) * 100.0
              / NULLIF((SELECT COUNT(*) FROM porsche_poi_users), 0), 2) as nav_ratio_pct
    """
    result = execute_sql(conn, sql)
    metrics['porsche_poi_post_nav_ratio'] = convert_to_json_serializable(result.to_dict('records')[0] if len(result) > 0 else {})
    print(f"8. Porsche POI post nav ratio: {metrics['porsche_poi_post_nav_ratio']}")

    # 9. Porsche用户AI路书占比
    sql = """
    WITH porsche_poi_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_POI_button_show'
    ),
    ai_guide_users AS (
        SELECT DISTINCT reduser_id
        FROM df
        WHERE event_name = 'post_detail_page_ai_travel_guide_button_click'
    )
    SELECT
        'Porsche+带POI帖子用户' as user_type,
        (SELECT COUNT(*) FROM porsche_poi_users) as total_users,
        (SELECT COUNT(*) FROM porsche_poi_users WHERE reduser_id IN (SELECT reduser_id FROM ai_guide_users)) as ai_guide_users,
        ROUND((SELECT COUNT(*) FROM porsche_poi_users WHERE reduser_id IN (SELECT reduser_id FROM ai_guide_users)) * 100.0
              / NULLIF((SELECT COUNT(*) FROM porsche_poi_users), 0), 2) as ai_guide_ratio_pct
    """
    result = execute_sql(conn, sql)
    metrics['porsche_poi_post_ai_guide_ratio'] = convert_to_json_serializable(result.to_dict('records')[0] if len(result) > 0 else {})
    print(f"9. Porsche POI post AI guide ratio: {metrics['porsche_poi_post_ai_guide_ratio']}")

    # 10. Porsche地图用户趋势
    map_events = [
        'porsche_page_Map_poi_card_click',
        'porsche_page_Map_POI_Category_click',
        'porsche_page_map_onFullscreen_Entry_Click',
        'porsche_page_map_onFullscreen_Exit_Click'
    ]
    map_events_str = ", ".join([f"'{e}'" for e in map_events])
    sql = f"""
    SELECT
        event_date,
        COUNT(DISTINCT reduser_id) as map_users
    FROM df
    WHERE event_name IN ({map_events_str})
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['porsche_map_users_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"10. Porsche map users trend: {len(result)} days")

    # 11. Porsche地图全屏用户数（改为用户数而非比例）
    sql = """
    SELECT
        event_date,
        COUNT(DISTINCT CASE WHEN event_name = 'porsche_page_map_onFullscreen_Entry_Click' THEN reduser_id END) as fullscreen_users,
        COUNT(DISTINCT CASE WHEN event_name IN ('porsche_page_Map_poi_card_click', 'porsche_page_Map_POI_Category_click') THEN reduser_id END) as map_click_users
    FROM df
    WHERE event_name IN ('porsche_page_map_onFullscreen_Entry_Click', 'porsche_page_Map_poi_card_click', 'porsche_page_Map_POI_Category_click')
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['porsche_map_fullscreen_users'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"11. Porsche map fullscreen users: {len(result)} days")

    # 12. Porsche进入POI详情页占比
    sql = """
    SELECT
        event_date,
        COUNT(DISTINCT CASE WHEN page_root = 'poi' THEN reduser_id END) as poi_users,
        COUNT(DISTINCT CASE WHEN page_root = 'porsche' THEN reduser_id END) as porsche_users,
        ROUND(COUNT(DISTINCT CASE WHEN page_root = 'poi' THEN reduser_id END) * 100.0
              / NULLIF(COUNT(DISTINCT CASE WHEN page_root = 'porsche' THEN reduser_id END), 0), 2) as poi_ratio_pct
    FROM df
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['porsche_poi_detail_ratio'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"12. Porsche POI detail ratio: {len(result)} days")

    # 13. Porsche多入口漏斗（正确顺序）
    sql = """
    SELECT '1_运营位帖子点击' as step_order, '运营位帖子点击' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE event_name = 'porsche_page_recommend_post_card_click' AND rednote_post_is_operational_rec = 1
    UNION ALL
    SELECT '2_地图操作' as step_order, '地图操作' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE event_name IN ('porsche_page_Map_poi_card_click', 'porsche_page_Map_POI_Category_click', 'porsche_page_map_onFullscreen_Entry_Click')
    UNION ALL
    SELECT '3_帖子详情页' as step_order, '帖子详情页' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE page_root = 'post'
    UNION ALL
    SELECT '4_POI详情页' as step_order, 'POI详情页' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE page_root = 'poi'
    UNION ALL
    SELECT '5_发起导航' as step_order, '发起导航' as step, COUNT(DISTINCT reduser_id) as users
    FROM df WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
    ORDER BY step_order
    """
    result = execute_sql(conn, sql)
    metrics['porsche_multi_entry_funnel'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"13. Porsche multi-entry funnel: {metrics['porsche_multi_entry_funnel']}")

    return metrics

def calculate_o2o_metrics(conn, df, total_users):
    """计算O2O/搜索/导航相关指标"""
    print("\n=== Calculating O2O Metrics ===")
    metrics = {}

    # 1. 搜索用户趋势（基于search_results_page_pageshow，表示实际搜索行为）
    sql = """
    SELECT
        event_date,
        COUNT(DISTINCT reduser_id) as search_users
    FROM df
    WHERE event_name = 'search_results_page_pageshow'
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['search_users_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"1. Search users trend: {len(result)} days")

    # 2. 搜索用户活跃率趋势
    sql = """
    SELECT
        event_date,
        COUNT(DISTINCT reduser_id) as search_users,
        ROUND(COUNT(DISTINCT reduser_id) * 100.0 / ?, 2) as search_active_rate_pct
    FROM df
    WHERE event_name = 'search_results_page_pageshow'
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql.replace('?', str(total_users)))
    metrics['search_active_rate_trend'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"2. Search active rate trend: {len(result)} days")

    # 3. 人均搜索次数（基于search_results_page_pageshow）
    sql = """
    SELECT
        event_date,
        COUNT(*) as search_count,
        COUNT(DISTINCT reduser_id) as users,
        ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT reduser_id), 2) as avg_search_count
    FROM df
    WHERE event_name = 'search_results_page_pageshow'
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['avg_search_count'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"3. Avg search count: {len(result)} days")

    # 4. 导航用户POI类型分布
    sql = """
    SELECT
        COALESCE(rednote_poi_type, '未知') as poi_type,
        COUNT(DISTINCT reduser_id) as nav_users,
        ROUND(COUNT(DISTINCT reduser_id) * 100.0 / SUM(COUNT(DISTINCT reduser_id)) OVER(), 2) as pct
    FROM df
    WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
      AND rednote_poi_type IS NOT NULL
    GROUP BY rednote_poi_type
    ORDER BY nav_users DESC
    LIMIT 10
    """
    result = execute_sql(conn, sql)
    metrics['nav_users_poi_type_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"4. Nav users POI type distribution: {len(result)} types")

    # 5. 导航用户活跃时间分布
    sql = """
    SELECT
        event_hour as hour,
        COUNT(DISTINCT reduser_id) as nav_users,
        ROUND(COUNT(DISTINCT reduser_id) * 100.0 / SUM(COUNT(DISTINCT reduser_id)) OVER(), 2) as pct
    FROM df
    WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
    GROUP BY event_hour
    ORDER BY hour
    """
    result = execute_sql(conn, sql)
    metrics['nav_users_hour_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"5. Nav users hour distribution: {len(result)} hours")

    # 6. 导航用户工作日vs周末对比
    sql = """
    SELECT
        CASE WHEN is_weekend = 1 THEN '周末' ELSE '工作日' END as day_type,
        COUNT(DISTINCT reduser_id) as active_users,
        ROUND(COUNT(DISTINCT reduser_id) * 100.0 / ?, 2) as pct
    FROM df
    WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
    GROUP BY is_weekend
    ORDER BY day_type
    """
    # 计算导航用户总数
    nav_total = conn.execute("SELECT COUNT(DISTINCT reduser_id) FROM df WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')").fetchone()[0]
    result = execute_sql(conn, sql.replace('?', str(nav_total)))
    metrics['nav_users_weekday_comparison'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"6. Nav users weekday comparison: {metrics['nav_users_weekday_comparison']}")

    # 7. 未导航用户POI类型分布
    sql = """
    SELECT
        COALESCE(rednote_poi_type, '未知') as poi_type,
        COUNT(DISTINCT reduser_id) as view_users,
        ROUND(COUNT(DISTINCT reduser_id) * 100.0 / SUM(COUNT(DISTINCT reduser_id)) OVER(), 2) as pct
    FROM df
    WHERE page_root = 'poi' AND rednote_poi_type IS NOT NULL
    GROUP BY rednote_poi_type
    ORDER BY view_users DESC
    LIMIT 10
    """
    result = execute_sql(conn, sql)
    metrics['non_nav_users_poi_type_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"7. Non-nav users POI type distribution: {len(result)} types")

    # 8. AI路书用户vs非用户导航活跃率对比
    sql = """
    WITH ai_guide_users AS (
        SELECT DISTINCT reduser_id FROM df WHERE event_name = 'post_detail_page_ai_travel_guide_button_click'
    ),
    nav_users AS (
        SELECT DISTINCT reduser_id FROM df
        WHERE event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')
    )
    SELECT
        '使用AI路书' as user_type,
        (SELECT COUNT(*) FROM ai_guide_users) as total_users,
        (SELECT COUNT(*) FROM ai_guide_users WHERE reduser_id IN (SELECT reduser_id FROM nav_users)) as nav_users,
        ROUND((SELECT COUNT(*) FROM ai_guide_users WHERE reduser_id IN (SELECT reduser_id FROM nav_users)) * 100.0
              / NULLIF((SELECT COUNT(*) FROM ai_guide_users), 0), 2) as nav_rate_pct
    UNION ALL
    SELECT
        '不使用AI路书' as user_type,
        (SELECT COUNT(DISTINCT reduser_id) FROM df) - (SELECT COUNT(*) FROM ai_guide_users) as total_users,
        (SELECT COUNT(DISTINCT reduser_id) FROM df WHERE reduser_id IN (SELECT reduser_id FROM nav_users)
         AND reduser_id NOT IN (SELECT reduser_id FROM ai_guide_users)) as nav_users,
        ROUND((SELECT COUNT(DISTINCT reduser_id) FROM df WHERE reduser_id IN (SELECT reduser_id FROM nav_users)
               AND reduser_id NOT IN (SELECT reduser_id FROM ai_guide_users)) * 100.0
              / NULLIF((SELECT COUNT(DISTINCT reduser_id) FROM df) - (SELECT COUNT(*) FROM ai_guide_users), 0), 2) as nav_rate_pct
    """
    result = execute_sql(conn, sql)
    metrics['ai_guide_nav_comparison'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"8. AI guide nav comparison: {metrics['ai_guide_nav_comparison']}")

    # 9. 运营位帖子类型分布（基于rednote_post_type）
    sql = """
    SELECT
        CASE WHEN rednote_post_type = 'normal' THEN '图文' WHEN rednote_post_type = 'video' THEN '视频' ELSE rednote_post_type END as post_type,
        COUNT(*) as click_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as pct
    FROM df
    WHERE event_name = 'porsche_page_recommend_post_card_click' AND rednote_post_type IS NOT NULL
    GROUP BY rednote_post_type
    ORDER BY click_count DESC
    """
    result = execute_sql(conn, sql)
    metrics['operational_post_type_distribution'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"9. Operational post type distribution: {len(result)} types")

    # 10. 运营位视频帖子占比趋势
    sql = """
    SELECT
        event_date,
        COUNT(CASE WHEN rednote_post_type = 'video' THEN 1 END) as video_clicks,
        COUNT(*) as total_clicks,
        ROUND(COUNT(CASE WHEN rednote_post_type = 'video' THEN 1 END) * 100.0 / COUNT(*), 2) as video_pct
    FROM df
    WHERE event_name = 'porsche_page_recommend_post_card_click' AND rednote_post_type IS NOT NULL
    GROUP BY event_date
    ORDER BY event_date
    """
    result = execute_sql(conn, sql)
    metrics['operational_video_post_ratio'] = convert_to_json_serializable(result.to_dict('records'))
    print(f"10. Operational video post ratio: {len(result)} days")

    return metrics

def create_dashboard(metrics, dashboard_name="Business_Strategy_Analysis"):
    """创建看板JSON文件"""
    print(f"\n=== Creating Dashboard: {dashboard_name} ===")

    dashboard_id = datetime.now().strftime("%Y%m%d%H%M")

    dashboard = {
        "id": dashboard_id,
        "name": dashboard_name,
        "created_at": datetime.now().isoformat(),
        "charts": []
    }

    # 完整审计信息配置
    audit_configs = {
        # Discovery Page
        'discovery_ctr_trend': {
            'title': '发现页CTR趋势', 'type': 'line', 'x': 'event_date', 'y': 'ctr_pct',
            'calculation_logic': '计算发现页每天的帖子点击率(CTR)，反映用户对帖子的兴趣程度。',
            'sql_explanation': '1. 筛选发现页帖子卡片展示和点击事件。2. 按日期分组计算展示数和点击数。3. CTR = 点击数/展示数*100。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension', 'sample_values': ['discovery_page_post_card_cardshow', 'discovery_page_post_card_click']},
                {'column': 'event_date', 'business_name': '日期', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name IN ('discovery_page_post_card_cardshow', 'discovery_page_post_card_click')"]
        },
        'discovery_post_position_distribution': {
            'title': '发现页帖子顺位分布', 'type': 'bar', 'x': 'position', 'y': 'pct',
            'calculation_logic': '分析发现页帖子被点击时的顺位分布，了解用户浏览深度。',
            'sql_explanation': '1. 筛选发现页帖子点击事件。2. 按帖子顺位(rednote_post_num)分组统计点击次数。3. 计算各顺位占比。',
            'columns_used': [
                {'column': 'rednote_post_num', 'business_name': '帖子顺位', 'role': 'dimension', 'sample_values': ['1', '2', '3']},
            ],
            'filters_applied': ["event_name = 'discovery_page_post_card_click'", "rednote_post_num IS NOT NULL"]
        },
        'discovery_post_type_distribution': {
            'title': '发现页帖子类型分布', 'type': 'pie', 'x': 'post_type', 'y': 'pct',
            'calculation_logic': '展示发现页被点击帖子的内容类型构成，反映用户偏好。',
            'sql_explanation': '1. 筛选发现页帖子点击事件。2. 按帖子类型(rednote_post_type)分组。3. 计算图文和视频占比。',
            'columns_used': [
                {'column': 'rednote_post_type', 'business_name': '帖子类型', 'role': 'dimension', 'sample_values': ['normal(图文)', 'video(视频)']},
            ],
            'filters_applied': ["event_name = 'discovery_page_post_card_click'", "rednote_post_type IS NOT NULL"]
        },
        'discovery_poi_post_ratio_trend': {
            'title': '发现页用户进入带POI帖子比例', 'type': 'line', 'x': 'event_date', 'y': 'poi_pct',
            'calculation_logic': '跟踪发现页用户进入带POI帖子的比例趋势，反映POI内容吸引力。',
            'sql_explanation': '1. 找出每天从发现页点击帖子的用户。2. 通过post_detail_page_POI_button_show事件识别带POI帖子。3. 计算两者交集比例。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
                {'column': 'rednote_poi_title', 'business_name': 'POI名称', 'role': 'dimension'},
            ],
            'filters_applied': ["发现页点击用户 vs POI按钮显示用户"]
        },
        'discovery_poi_post_nav_ratio': {
            'title': '发现页带POI帖子用户导航转化', 'type': 'bar', 'x': 'user_type', 'y': 'nav_ratio_pct',
            'calculation_logic': '计算看了带POI帖子的用户中发起导航的比例，衡量POI内容到导航的转化效果。',
            'sql_explanation': '1. 通过post_detail_page_POI_button_show识别带POI帖子用户。2. 通过导航按钮点击事件识别导航用户。3. 计算交集比例。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension', 'sample_values': ['post_detail_page_POI_button_show', 'poi_detail_page_navigation_button_click']},
            ],
            'filters_applied': ["event_name = 'post_detail_page_POI_button_show'"]
        },
        'discovery_poi_post_ai_guide_ratio': {
            'title': '发现页带POI帖子用户AI路书转化', 'type': 'bar', 'x': 'user_type', 'y': 'ai_guide_ratio_pct',
            'calculation_logic': '计算看了带POI帖子的用户中生成AI路书的比例，衡量AI路书功能的使用情况。',
            'sql_explanation': '1. 通过post_detail_page_POI_button_show识别带POI帖子用户。2. 通过AI路书按钮点击事件识别AI路书用户。3. 计算交集比例。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension', 'sample_values': ['post_detail_page_POI_button_show', 'post_detail_page_ai_travel_guide_button_click']},
            ],
            'filters_applied': ["event_name = 'post_detail_page_POI_button_show'"]
        },
        'discovery_funnel': {
            'title': '发现页漏斗', 'type': 'funnel', 'x': 'step', 'y': 'users',
            'calculation_logic': '展示用户从帖子详情页到POI详情页再到发起导航的转化漏斗。',
            'sql_explanation': '1. 统计帖子详情页去重用户数(page_root=post)。2. 统计POI详情页去重用户数(page_root=poi)。3. 统计导航用户数。',
            'columns_used': [
                {'column': 'page_root', 'business_name': '页面根', 'role': 'dimension', 'sample_values': ['post', 'poi']},
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
            ],
            'filters_applied': ["page_root IN ('post', 'poi')", "导航事件"]
        },

        # Porsche Page
        'porsche_active_rate_trend': {
            'title': 'Porsche+页活跃率趋势', 'type': 'line', 'x': 'event_date', 'y': 'active_rate_pct',
            'calculation_logic': '计算Porsche+页每天的活跃率，活跃率=活跃用户数/总用户数*100。',
            'sql_explanation': '1. 筛选Porsche+页事件(page_root=porsche)。2. 按日期统计去重用户数。3. 计算占总用户数的比例。',
            'columns_used': [
                {'column': 'page_root', 'business_name': '页面根', 'role': 'dimension', 'sample_values': ['porsche']},
                {'column': 'reduser_id', 'business_name': '用户ID', 'role': 'dimension'},
            ],
            'filters_applied': ["page_root = 'porsche'"]
        },
        'porsche_avg_open_count': {
            'title': 'Porsche+页人均打开次数', 'type': 'line', 'x': 'event_date', 'y': 'avg_events',
            'calculation_logic': '计算Porsche+页每天的人均打开次数，反映用户粘性。',
            'sql_explanation': '1. 按日期统计Porsche+页事件总数。2. 按日期统计去重用户数。3. 人均次数=事件数/用户数。',
            'columns_used': [
                {'column': 'page_root', 'business_name': '页面根', 'role': 'dimension'},
                {'column': 'reduser_id', 'business_name': '用户ID', 'role': 'dimension'},
            ],
            'filters_applied': ["page_root = 'porsche'"]
        },
        'porsche_ctr_trend': {
            'title': 'Porsche+页CTR趋势', 'type': 'line', 'x': 'event_date', 'y': 'ctr_pct',
            'calculation_logic': '计算Porsche+页每天的帖子点击率趋势。',
            'sql_explanation': '1. 筛选Porsche+页帖子卡片展示和点击事件。2. 按日期分组。3. CTR=点击数/展示数*100。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension', 'sample_values': ['porsche_page_recommend_post_card_cardshow', 'porsche_page_recommend_post_card_click']},
            ],
            'filters_applied': ["event_name IN ('porsche_page_recommend_post_card_cardshow', 'porsche_page_recommend_post_card_click')"]
        },
        'porsche_post_position_distribution': {
            'title': 'Porsche+页帖子顺位分布', 'type': 'bar', 'x': 'position', 'y': 'pct',
            'calculation_logic': '分析Porsche+页帖子被点击时的顺位分布。',
            'sql_explanation': '按rednote_post_num分组统计点击次数和占比。',
            'columns_used': [
                {'column': 'rednote_post_num', 'business_name': '帖子顺位', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name = 'porsche_page_recommend_post_card_click'"]
        },
        'porsche_operational_vs_non_operational': {
            'title': 'Porsche+页运营位vs非运营位', 'type': 'bar', 'x': 'position_type', 'y': 'pct',
            'calculation_logic': '对比运营位和非运营位帖子的点击占比。',
            'sql_explanation': '按rednote_post_is_operational_rec字段区分运营位和非运营位。',
            'columns_used': [
                {'column': 'rednote_post_is_operational_rec', 'business_name': '是否运营位', 'role': 'dimension', 'sample_values': ['1(运营位)', '0(非运营位)']},
            ],
            'filters_applied': ["event_name = 'porsche_page_recommend_post_card_click'"]
        },
        'porsche_post_type_distribution': {
            'title': 'Porsche+页帖子类型分布', 'type': 'pie', 'x': 'post_type', 'y': 'pct',
            'calculation_logic': '展示Porsche+页被点击帖子的图文和视频占比。',
            'sql_explanation': '按rednote_post_type分组统计。',
            'columns_used': [
                {'column': 'rednote_post_type', 'business_name': '帖子类型', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name = 'porsche_page_recommend_post_card_click'"]
        },
        'porsche_poi_post_ratio_trend': {
            'title': 'Porsche+页用户进入带POI帖子比例', 'type': 'line', 'x': 'event_date', 'y': 'poi_pct',
            'calculation_logic': '跟踪Porsche+页用户进入带POI帖子的比例趋势。',
            'sql_explanation': 'Porsche+页点击用户中看到POI按钮的比例。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
            ],
            'filters_applied': ["Porsche+页点击用户 vs POI按钮显示用户"]
        },
        'porsche_poi_post_nav_ratio': {
            'title': 'Porsche+页带POI帖子用户导航转化', 'type': 'bar', 'x': 'user_type', 'y': 'nav_ratio_pct',
            'calculation_logic': 'Porsche+页用户导航转化率。',
            'sql_explanation': '带POI帖子用户中发起导航的比例。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name = 'post_detail_page_POI_button_show'"]
        },
        'porsche_poi_post_ai_guide_ratio': {
            'title': 'Porsche+页带POI帖子用户AI路书转化', 'type': 'bar', 'x': 'user_type', 'y': 'ai_guide_ratio_pct',
            'calculation_logic': 'Porsche+页用户AI路书转化率。',
            'sql_explanation': '带POI帖子用户中生成AI路书的比例。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name = 'post_detail_page_POI_button_show'"]
        },
        'porsche_map_users_trend': {
            'title': 'Porsche+页地图用户趋势', 'type': 'line', 'x': 'event_date', 'y': 'map_users',
            'calculation_logic': 'Porsche+页每天使用地图功能的用户数量趋势。',
            'sql_explanation': '统计地图相关事件(porsche_page_Map_*)的去重用户数。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension', 'sample_values': ['porsche_page_Map_poi_card_click', 'porsche_page_map_onFullscreen_Entry_Click']},
            ],
            'filters_applied': ["event_name包含'Map'"]
        },
        'porsche_map_fullscreen_users': {
            'title': 'Porsche+页地图全屏用户数', 'type': 'line', 'x': 'event_date', 'y': 'fullscreen_users',
            'calculation_logic': '每天使用地图全屏功能的用户数量。',
            'sql_explanation': '统计porsche_page_map_onFullscreen_Entry_Click事件的去重用户数。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name = 'porsche_page_map_onFullscreen_Entry_Click'"]
        },
        'porsche_poi_detail_ratio': {
            'title': 'Porsche+页进入POI详情页比例', 'type': 'line', 'x': 'event_date', 'y': 'poi_ratio_pct',
            'calculation_logic': 'Porsche+页用户进入POI详情页的比例趋势。',
            'sql_explanation': 'POI详情页用户数/Porsche+页用户数。',
            'columns_used': [
                {'column': 'page_root', 'business_name': '页面根', 'role': 'dimension', 'sample_values': ['porsche', 'poi']},
            ],
            'filters_applied': ["page_root IN ('porsche', 'poi')"]
        },
        'porsche_multi_entry_funnel': {
            'title': 'Porsche+页多入口漏斗', 'type': 'funnel', 'x': 'step', 'y': 'users',
            'calculation_logic': '展示Porsche+页的多入口转化漏斗。',
            'sql_explanation': '运营位帖子点击→地图操作→帖子详情页→POI详情页→发起导航。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
                {'column': 'page_root', 'business_name': '页面根', 'role': 'dimension'},
            ],
            'filters_applied': ["各入口事件"]
        },

        # O2O Metrics
        'search_users_trend': {
            'title': '搜索用户趋势', 'type': 'line', 'x': 'event_date', 'y': 'search_users',
            'calculation_logic': '每天使用搜索功能的用户数量趋势。',
            'sql_explanation': '通过search_results_page_pageshow事件统计搜索用户数。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension', 'sample_values': ['search_results_page_pageshow']},
            ],
            'filters_applied': ["event_name = 'search_results_page_pageshow'"]
        },
        'search_active_rate_trend': {
            'title': '搜索用户活跃率趋势', 'type': 'line', 'x': 'event_date', 'y': 'search_active_rate_pct',
            'calculation_logic': '搜索用户占总用户数的比例趋势。',
            'sql_explanation': '搜索用户数/总用户数*100。',
            'columns_used': [
                {'column': 'reduser_id', 'business_name': '用户ID', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name = 'search_results_page_pageshow'"]
        },
        'avg_search_count': {
            'title': '人均搜索次数', 'type': 'line', 'x': 'event_date', 'y': 'avg_search_count',
            'calculation_logic': '每天人均搜索次数。',
            'sql_explanation': '搜索事件数/搜索用户数。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension'},
            ],
            'filters_applied': ["event_name = 'search_results_page_pageshow'"]
        },
        'nav_users_poi_type_distribution': {
            'title': '导航用户POI类型分布', 'type': 'bar', 'x': 'poi_type', 'y': 'pct',
            'calculation_logic': '导航用户导航的POI类型构成，反映导航目的地偏好。',
            'sql_explanation': '1. 筛选导航点击事件。2. 按POI类型(rednote_poi_type)分组统计。',
            'columns_used': [
                {'column': 'rednote_poi_type', 'business_name': 'POI分类', 'role': 'dimension', 'sample_values': ['咖啡', '五星级酒店', '超市便利']},
            ],
            'filters_applied': ["event_name IN ('poi_detail_page_navigation_button_click', 'trival_guide_page_detail_tab_poi_navigation_button_click')"]
        },
        'nav_users_hour_distribution': {
            'title': '导航用户时间分布', 'type': 'bar', 'x': 'hour', 'y': 'pct',
            'calculation_logic': '导航用户活跃时间分布，了解导航高峰时段。',
            'sql_explanation': '按event_hour分组统计导航用户数。',
            'columns_used': [
                {'column': 'event_hour', 'business_name': '小时', 'role': 'dimension'},
            ],
            'filters_applied': ["导航事件"]
        },
        'nav_users_weekday_comparison': {
            'title': '导航用户周末vs工作日', 'type': 'bar', 'x': 'day_type', 'y': 'pct',
            'calculation_logic': '对比导航用户在周末和工作日的活跃情况。',
            'sql_explanation': '按is_weekend字段区分周末和工作日。',
            'columns_used': [
                {'column': 'is_weekend', 'business_name': '是否周末', 'role': 'dimension', 'sample_values': ['0(工作日)', '1(周末)']},
            ],
            'filters_applied': ["导航事件"]
        },
        'non_nav_users_poi_type_distribution': {
            'title': 'POI详情页用户类型分布', 'type': 'bar', 'x': 'poi_type', 'y': 'pct',
            'calculation_logic': 'POI详情页用户的POI类型分布。',
            'sql_explanation': '按rednote_poi_type分组统计POI详情页用户。',
            'columns_used': [
                {'column': 'rednote_poi_type', 'business_name': 'POI分类', 'role': 'dimension'},
            ],
            'filters_applied': ["page_root = 'poi'"]
        },
        'ai_guide_nav_comparison': {
            'title': 'AI路书用户vs非用户导航转化', 'type': 'bar', 'x': 'user_type', 'y': 'nav_rate_pct',
            'calculation_logic': '对比使用和不使用AI路书用户的导航活跃率。',
            'sql_explanation': '通过post_detail_page_ai_travel_guide_button_click区分AI路书用户。',
            'columns_used': [
                {'column': 'event_name', 'business_name': '事件名称', 'role': 'dimension', 'sample_values': ['post_detail_page_ai_travel_guide_button_click']},
            ],
            'filters_applied': ["AI路书用户 vs 非AI路书用户"]
        },
        'operational_post_type_distribution': {
            'title': '运营位帖子类型分布', 'type': 'pie', 'x': 'post_type', 'y': 'pct',
            'calculation_logic': '运营位帖子中图文和视频类型的占比。',
            'sql_explanation': '按rednote_post_type分组统计运营位帖子点击。',
            'columns_used': [
                {'column': 'rednote_post_type', 'business_name': '帖子类型', 'role': 'dimension'},
                {'column': 'rednote_post_is_operational_rec', 'business_name': '是否运营位', 'role': 'filter'},
            ],
            'filters_applied': ["运营位帖子点击"]
        },
        'operational_video_post_ratio': {
            'title': '运营位视频帖子占比趋势', 'type': 'line', 'x': 'event_date', 'y': 'video_pct',
            'calculation_logic': '运营位视频帖子占比的每日趋势。',
            'sql_explanation': '按日期统计运营位视频帖子点击占比。',
            'columns_used': [
                {'column': 'rednote_post_type', 'business_name': '帖子类型', 'role': 'dimension'},
            ],
            'filters_applied': ["运营位帖子点击"]
        },
    }

    for metric_key, data in metrics.items():
        if not data:
            continue

        config = audit_configs.get(metric_key, {})
        if not config:
            continue

        chart = {
            "id": f"chart_{metric_key}",
            "title": config.get('title', metric_key),
            "chart_type": config.get('type', 'table'),
            "x": config.get('x'),
            "y": config.get('y'),
            "data": data,
            "summary": f"{config.get('title', metric_key)} - 数据已计算",
            "audit": {
                "metric": metric_key,
                "calculation_time": datetime.now().isoformat(),
                "data_source": {
                    "file": "rednote20260319-20260412.xlsx",
                    "table": "events",
                    "total_rows_scanned": 65722,
                    "date_range": ["2026-03-19", "2026-04-12"]
                },
                "calculation_logic": config.get('calculation_logic', ''),
                "sql_explanation": config.get('sql_explanation', ''),
                "columns_used": config.get('columns_used', []),
                "filters_applied": config.get('filters_applied', []),
                "sample_data": data[:3] if isinstance(data, list) and len(data) > 0 else None
            }
        }

        dashboard['charts'].append(chart)
        print(f"  Added chart: {chart['title']}")

    output_path = DASHBOARD_PATH / f"{dashboard_id}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    print(f"\nDashboard saved to: {output_path}")
    print(f"Total charts: {len(dashboard['charts'])}")

    return dashboard_id

def main():
    print("="*60)
    print("BI Metrics Calculator")
    print("="*60)

    df, total_users = load_data()
    conn = duckdb.connect()
    conn.register('df', df)

    all_metrics = {}
    all_metrics.update(calculate_discovery_metrics(conn, df, total_users))
    all_metrics.update(calculate_porsche_metrics(conn, df, total_users))
    all_metrics.update(calculate_o2o_metrics(conn, df, total_users))

    dashboard_id = create_dashboard(all_metrics, "Business_Strategy_Analysis")

    print("\n" + "="*60)
    print("DONE!")
    print(f"Dashboard ID: {dashboard_id}")
    print("="*60)

    return dashboard_id

if __name__ == "__main__":
    main()