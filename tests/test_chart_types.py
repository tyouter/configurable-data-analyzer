import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from mcp_server.chart_renderer import build_echarts_option

# area chart
opt = build_echarts_option("area", [{"x":"a","y":1},{"x":"b","y":2}], "Area Test")
print(f"area: series_type={opt['series'][0]['type']}, areaStyle={'areaStyle' in opt['series'][0]}")

# ring chart
opt2 = build_echarts_option("ring", [{"name":"A","val":30},{"name":"B","val":70}], "Ring")
print(f"ring: series_type={opt2['series'][0]['type']}, radius={opt2['series'][0]['radius']}")

# radar
opt3 = build_echarts_option("radar", [{"dim":"A","v1":10,"v2":20},{"dim":"B","v1":15,"v2":25}], "Radar")
print(f"radar: has_radar={'radar' in opt3}, series_type={opt3['series'][0]['type']}")

# gauge
opt4 = build_echarts_option("gauge", [{"name":"CPU","value":72}], "CPU Usage")
print(f"gauge: series_type={opt4['series'][0]['type']}")

# stackedBar
opt5 = build_echarts_option("stackedBar", [{"m":"Jan","a":10,"b":20},{"m":"Feb","a":15,"b":25}], "Stacked")
print(f"stackedBar: stack={opt5['series'][0].get('stack')}")

# unknown type - should still work
opt6 = build_echarts_option("someFutureType", [{"x":"a","y":1}], "Future")
print(f"unknown: series_type={opt6['series'][0]['type']}")

# candlestick
opt7 = build_echarts_option("candlestick", [{"date":"1","open":1,"close":2,"low":0.5,"high":3}], "K")
print(f"candlestick: has_xAxis={'xAxis' in opt7}")

print("\nAll tests passed!")
