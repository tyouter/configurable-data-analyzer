# -*- coding: utf-8 -*-
"""
Dashboard Persistence: JSON file CRUD
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path


DASHBOARDS_DIR = os.path.join(os.path.dirname(__file__), "dashboards")


def _ensure_dir():
    os.makedirs(DASHBOARDS_DIR, exist_ok=True)


def _filepath(dashboard_id: str) -> str:
    return os.path.join(DASHBOARDS_DIR, f"{dashboard_id}.json")


def list_dashboards() -> list[dict]:
    """List all saved dashboards."""
    _ensure_dir()
    dashboards = []
    for f in sorted(Path(DASHBOARDS_DIR).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            dashboards.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", f.stem),
                "charts_count": len(data.get("charts", [])),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return dashboards


def get_dashboard(dashboard_id: str) -> dict | None:
    """Get a single dashboard by ID."""
    fp = _filepath(dashboard_id)
    if not os.path.exists(fp):
        return None
    return json.loads(open(fp, encoding="utf-8").read())


def save_chart(dashboard_name: str, chart: dict) -> dict:
    """Save a chart to a dashboard. Creates dashboard if not exists."""
    _ensure_dir()

    # Find existing dashboard by name
    for f in Path(DASHBOARDS_DIR).glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("name") == dashboard_name:
            chart_id = str(uuid.uuid4())[:8]
            chart["id"] = chart_id
            chart["saved_at"] = datetime.now().isoformat()
            data["charts"].append(chart)
            data["updated_at"] = datetime.now().isoformat()
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"dashboard_id": data["id"], "chart_id": chart_id, "dashboard_name": dashboard_name}

    # Create new dashboard
    dashboard_id = str(uuid.uuid4())[:8]
    chart_id = str(uuid.uuid4())[:8]
    chart["id"] = chart_id
    chart["saved_at"] = datetime.now().isoformat()
    dashboard = {
        "id": dashboard_id,
        "name": dashboard_name,
        "charts": [chart],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    fp = _filepath(dashboard_id)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    return {"dashboard_id": dashboard_id, "chart_id": chart_id, "dashboard_name": dashboard_name}


def delete_chart(dashboard_id: str, chart_id: str) -> bool:
    """Delete a chart from a dashboard."""
    fp = _filepath(dashboard_id)
    if not os.path.exists(fp):
        return False
    data = json.loads(open(fp, encoding="utf-8").read())
    data["charts"] = [c for c in data.get("charts", []) if c.get("id") != chart_id]
    data["updated_at"] = datetime.now().isoformat()
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True
