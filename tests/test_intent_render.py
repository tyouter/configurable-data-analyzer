import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from mcp_server.service.dashboard import render_chart

data = [
    {"date": "2024-01", "users": 100, "rate": 0.3},
    {"date": "2024-02", "users": 120, "rate": 0.35},
    {"date": "2024-03", "users": 150, "rate": 0.4},
]

# Test 1: intent-driven (no LLM, rule fallback)
result = render_chart(data=data, title="用户趋势", intent="展示活跃用户随时间的变化趋势", use_llm=False)
print(f"Test 1 (intent): type={result['chart_type']}, spec={result.get('render_spec', {}).get('reasoning', '')[:60]}")

# Test 2: user explicit type
result2 = render_chart(data=data, title="用户趋势", chart_type="area", use_llm=False)
print(f"Test 2 (explicit): type={result2['chart_type']}")

# Test 3: confirm mode
result3 = render_chart(data=data, title="用户趋势", intent="看看分布", confirm=True, use_llm=False)
print(f"Test 3 (confirm): status={result3['status']}, message={result3['message'][:80]}")

# Test 4: KPI card (单行数据 + metric_type)
kpi_data = [{"total": 297}]
result4 = render_chart(data=kpi_data, title="装机量", metric_type="count", use_llm=False)
print(f"Test 4 (kpi): type={result4['chart_type']}, has_value={'value' in result4.get('chart_option', {})}")

# Test 5: backward compat chart_hint
result5 = render_chart(data=data, title="趋势", chart_hint="展示指标随时间的变化趋势和绝对值", use_llm=False)
print(f"Test 5 (chart_hint as intent): type={result5['chart_type']}")

print("\nAll tests passed!")
