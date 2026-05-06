import json, sys
sys.path.insert(0, ".")
from mcp_server.server import create_project

data_files = [
    r"d:\projects\claude\configurable-data-analyzer\projects\rednote\data\rednote20260319-20260412.xlsx",
    r"d:\projects\claude\configurable-data-analyzer\projects\rednote\data\Rednote tracking data stracture_20260331.xlsx",
    r"d:\projects\claude\configurable-data-analyzer\projects\rednote\data\rednote KPI definition_20260323.xlsx",
    r"d:\projects\claude\configurable-data-analyzer\projects\rednote\data\Rednote dashboard V1.0 5-30 requirements.xlsx",
]

result = create_project(
    name="小红书车载应用分析-MCP测试",
    data_files=data_files,
    action="start",
)
pid = result.get("project_id")
print("=== START ===")
print("project_id:", pid)
print("state:", result.get("state"))

result2 = create_project(
    action="confirm",
    project_id=pid,
    confirmed_raw_files=["rednote20260319-20260412.xlsx"],
    confirmed_ref_files=[
        "Rednote tracking data stracture_20260331.xlsx",
        "rednote KPI definition_20260323.xlsx",
        "Rednote dashboard V1.0 5-30 requirements.xlsx",
    ],
    analysis_goals=[
        "小红书车载应用用户行为分析",
        "核心KPI指标监控（DAU、活跃率、留存率、转化率）",
        "Porsche+版块和发现页使用分析",
        "AI路书功能使用和转化分析",
    ],
)
print("=== CONFIRM ===")
print("state:", result2.get("state"))
print("project_id:", pid)
