#!/usr/bin/env python
"""
通过调用现有BI API生成所有图表，自动获得完整审计信息
优化版本：先清理旧dashboard，支持批量处理
"""
import requests
import json
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8501"
DASHBOARD_NAME = "Business_Strategy_Analysis"

# 定义所有需要查询的问题
QUERIES = [
    # Discovery Page - 7个
    "发现页每天的帖子点击率(CTR)趋势，点击率=点击数/展示数*100",
    "发现页帖子点击在第几个顺位的分布情况，显示前20位",
    "发现页被点击的帖子中图文和视频类型的占比饼图",
    "发现页用户进入带POI帖子的比例趋势（通过POI按钮显示事件识别）",
    "发现页带POI帖子的用户中有多少发起导航的比例",
    "发现页带POI帖子的用户中有多少生成AI路书的比例",
    "漏斗分析：帖子详情页用户数到POI详情页用户数到发起导航用户数",

    # Porsche Page - 10个
    "Porsche+页每天的活跃率趋势",
    "Porsche+页每天人均打开次数",
    "Porsche+页每天的帖子点击率(CTR)趋势",
    "Porsche+页帖子点击顺位分布，显示前20位",
    "Porsche+页被点击的帖子图文和视频占比饼图",
    "Porsche+页用户进入带POI帖子的比例趋势",
    "Porsche+页带POI帖子的用户导航比例",
    "Porsche+页带POI帖子的用户AI路书比例",
    "Porsche+页每天地图操作用户数量趋势",
    "Porsche+页每天地图全屏用户数量趋势",

    # O2O/Search/Navigation - 13个
    "每天搜索用户数量趋势（搜索结果页展示）",
    "每天搜索用户活跃率趋势",
    "每天人均搜索次数",
    "导航用户导航的POI类型分布",
    "导航用户活跃时间分布按小时",
    "导航用户周末和工作日活跃人数对比",
    "POI详情页用户的POI类型分布",
    "使用AI路书和不使用AI路书用户的导航比例对比",
    "运营位帖子图文和视频占比饼图",
    "运营位视频帖子占比趋势",
]


def stream_query(question: str) -> dict:
    """调用streaming API并收集完整结果"""
    print(f"  Query: {question[:40]}...")

    response = requests.post(
        f"{BASE_URL}/api/query/stream",
        json={"question": question, "clear_history": True, "skip_clarification": True},
        stream=True,
        timeout=120
    )

    result = None
    chart_type = None

    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode('utf-8')
        if line.startswith('data: '):
            try:
                chunk = json.loads(line[6:])
                if chunk.get('type') == 'result':
                    result = chunk
                elif chunk.get('type') == 'chart':
                    result = chunk
                    chart_type = chunk.get('chart_type')
            except json.JSONDecodeError:
                continue

    return result


def get_dashboard_id_by_name(name: str) -> str:
    """通过名称获取dashboard ID"""
    resp = requests.get(f"{BASE_URL}/api/dashboards")
    dashboards = resp.json()
    for d in dashboards:
        if d.get('name') == name:
            return d['id']
    return None


def delete_dashboard(dashboard_id: str):
    """删除dashboard"""
    requests.delete(f"{BASE_URL}/api/dashboards/{dashboard_id}")


def create_dashboard(name: str) -> str:
    """创建新dashboard"""
    resp = requests.post(
        f"{BASE_URL}/api/dashboards/create",
        json={"name": name}
    )
    if resp.status_code == 200:
        return resp.json().get('id')
    return None


def save_chart_to_dashboard(dashboard_name: str, chart: dict) -> dict:
    """保存图表到dashboard"""
    resp = requests.post(
        f"{BASE_URL}/api/dashboards",
        json={"dashboard_name": dashboard_name, "chart": chart}
    )
    return resp.json()


def main():
    print("=" * 60)
    print("BI Dashboard Generator via API")
    print("=" * 60)

    # 检查服务器状态
    try:
        resp = requests.get(f"{BASE_URL}/api/dashboards", timeout=5)
        print(f"Server connected: {BASE_URL}")
    except requests.RequestException as e:
        print(f"Error: Cannot connect to server at {BASE_URL}")
        print(f"Please start server first: python bi/app.py")
        return

    # 清理旧的dashboard
    old_id = get_dashboard_id_by_name(DASHBOARD_NAME)
    if old_id:
        print(f"Deleting old dashboard: {old_id}")
        delete_dashboard(old_id)
        time.sleep(1)

    # 创建新dashboard
    dashboard_id = create_dashboard(DASHBOARD_NAME)
    print(f"Created dashboard: {DASHBOARD_NAME} (ID: {dashboard_id})")

    # 执行所有查询
    success_count = 0
    fail_count = 0

    print(f"\nGenerating {len(QUERIES)} charts...")
    print("-" * 40)

    for i, question in enumerate(QUERIES):
        print(f"\n[{i+1}/{len(QUERIES)}]")

        result = stream_query(question)

        if result and result.get('chart'):
            chart = result['chart']
            # 确保有完整审计信息
            if not chart.get('audit'):
                chart['audit'] = result.get('audit', {})

            # 保存到dashboard
            save_result = save_chart_to_dashboard(DASHBOARD_NAME, chart)
            title = chart.get('title', 'N/A')
            if isinstance(title, str) and len(title) > 30:
                title = title[:30] + '...'
            print(f"    ✓ Saved: {title}")
            success_count += 1
        else:
            print(f"    ✗ Failed: No chart generated")
            fail_count += 1

        # 短暂休息避免过载
        time.sleep(0.5)

    # 显示结果
    print("\n" + "=" * 60)
    print(f"DONE! Success: {success_count}, Failed: {fail_count}")
    print(f"View at: {BASE_URL}")
    print("=" * 60)


if __name__ == "__main__":
    main()