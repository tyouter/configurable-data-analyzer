import json, sys
sys.path.insert(0, ".")
from mcp_server.server import create_project

pid = "ca6e5291"

result = create_project(
    action="build",
    project_id=pid,
)
print("=== BUILD RESULT ===")
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
