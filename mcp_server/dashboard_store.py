# -*- coding: utf-8 -*-
"""
Project-level Dashboard Persistence: JSON file CRUD

Each project has its own dashboards/ directory:
  projects/{project_id}/dashboards/{dashboard_id}.json
"""

import json
import os
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from decimal import Decimal


class _ChartJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        if hasattr(o, "item"):
            return o.item()
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return super().default(o)


def _json_dumps(obj, **kwargs):
    return json.dumps(obj, cls=_ChartJSONEncoder, ensure_ascii=False, indent=2, **kwargs)


def _json_dump(obj, fp, **kwargs):
    return json.dump(obj, fp, cls=_ChartJSONEncoder, ensure_ascii=False, indent=2, **kwargs)


def _dashboards_dir(projects_dir: str, project_id: str) -> str:
    return os.path.join(projects_dir, project_id, "dashboards")


def _ensure_dir(projects_dir: str, project_id: str) -> str:
    d = _dashboards_dir(projects_dir, project_id)
    os.makedirs(d, exist_ok=True)
    return d


def _filepath(projects_dir: str, project_id: str, dashboard_id: str) -> str:
    return os.path.join(_dashboards_dir(projects_dir, project_id), f"{dashboard_id}.json")


def list_dashboards(projects_dir: str, project_id: str) -> list[dict]:
    dashboards = []
    d = _ensure_dir(projects_dir, project_id)
    for f in sorted(Path(d).glob("*.json")):
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


def get_dashboard(projects_dir: str, project_id: str, dashboard_id: str) -> Optional[dict]:
    fp = _filepath(projects_dir, project_id, dashboard_id)
    if not os.path.exists(fp):
        return None
    return json.loads(open(fp, encoding="utf-8").read())


def create_dashboard(projects_dir: str, project_id: str, name: str) -> dict:
    _ensure_dir(projects_dir, project_id)
    d = _dashboards_dir(projects_dir, project_id)
    for f in Path(d).glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("name") == name:
            return {"id": data["id"], "name": name, "exists": True}

    dashboard_id = str(uuid.uuid4())[:8]
    dashboard = {
        "id": dashboard_id,
        "name": name,
        "charts": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    fp = _filepath(projects_dir, project_id, dashboard_id)
    with open(fp, "w", encoding="utf-8") as f:
        _json_dump(dashboard, f)
    return {"id": dashboard_id, "name": name, "exists": False}


def save_chart(projects_dir: str, project_id: str, dashboard_name: str, chart: dict) -> dict:
    _ensure_dir(projects_dir, project_id)
    d = _dashboards_dir(projects_dir, project_id)

    for f in Path(d).glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("name") == dashboard_name:
            chart_id = str(uuid.uuid4())[:8]
            chart["id"] = chart_id
            chart["saved_at"] = datetime.now().isoformat()
            data["charts"].append(chart)
            data["updated_at"] = datetime.now().isoformat()
            f.write_text(_json_dumps(data), encoding="utf-8")
            return {"dashboard_id": data["id"], "chart_id": chart_id, "dashboard_name": dashboard_name}

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
    fp = _filepath(projects_dir, project_id, dashboard_id)
    with open(fp, "w", encoding="utf-8") as f:
        _json_dump(dashboard, f)
    return {"dashboard_id": dashboard_id, "chart_id": chart_id, "dashboard_name": dashboard_name}


def delete_chart(projects_dir: str, project_id: str, dashboard_id: str, chart_id: str) -> bool:
    fp = _filepath(projects_dir, project_id, dashboard_id)
    if not os.path.exists(fp):
        return False
    data = json.loads(open(fp, encoding="utf-8").read())
    data["charts"] = [c for c in data.get("charts", []) if c.get("id") != chart_id]
    data["updated_at"] = datetime.now().isoformat()
    with open(fp, "w", encoding="utf-8") as f:
        _json_dump(data, f)
    return True


def delete_dashboard(projects_dir: str, project_id: str, dashboard_id: str) -> bool:
    fp = _filepath(projects_dir, project_id, dashboard_id)
    if not os.path.exists(fp):
        return False
    os.remove(fp)
    return True
