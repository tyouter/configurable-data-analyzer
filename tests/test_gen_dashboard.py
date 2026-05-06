import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
from mcp_server.project_model import ProjectSession, PROJECTS_DIR
from mcp_server.server import generate_dashboard_from_spec, switch_project

session = ProjectSession()
projects = session.store.list_projects()
print("Available projects:")
for p in projects:
    print(f"  {p['id']}: {p['name']}")

target = "1bd90a0c"
print(f"\nSwitching to project {target}...")
switch_project(target)

print("\nGenerating dashboard from spec...")
result = generate_dashboard_from_spec()
print(f"\nStatus: {result.get('status')}")
print(f"Dashboard: {result.get('dashboard_name')}")
print(f"Total specs: {result.get('total_specs')}")
print(f"Charts created: {result.get('charts_created')}")
print(f"Errors: {result.get('errors_count')}")

if result.get('errors'):
    print("\nErrors:")
    for e in result['errors']:
        print(f"  {e.get('chart_id', '?')} - {e.get('name', '?')}: {e.get('error', '?')}")

if result.get('charts'):
    print("\nCreated charts:")
    for c in result['charts']:
        print(f"  {c['chart_id']} ({c['chart_type']}) - {c['name']} [{c['category']}] rows={c['rows']}")

if result.get('html_path'):
    print(f"\nHTML exported to: {result['html_path']}")
