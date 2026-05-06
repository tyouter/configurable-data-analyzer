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


def _fix_double_encoding(s):
    if not isinstance(s, str):
        return s
    try:
        raw_bytes = bytearray()
        for c in s:
            cp = ord(c)
            if cp < 0x80:
                raw_bytes.append(cp)
            elif 0x80 <= cp <= 0xFF:
                raw_bytes.append(cp)
            else:
                raw_bytes.extend(c.encode("utf-8"))
        fixed = raw_bytes.decode("utf-8")
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in fixed)
        if has_cjk:
            return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return s


def _fix_chart_encoding(obj, depth=0):
    if depth > 15:
        return obj
    if isinstance(obj, dict):
        return {_fix_chart_encoding(k, depth + 1) if isinstance(k, str) else k: _fix_chart_encoding(v, depth + 1) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_fix_chart_encoding(item, depth + 1) for item in obj]
    elif isinstance(obj, str):
        return _fix_double_encoding(obj)
    return obj


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


def load_dashboard_by_name(projects_dir: str, project_id: str, name: str) -> Optional[dict]:
    d = _dashboards_dir(projects_dir, project_id)
    if not os.path.exists(d):
        return None
    for f in sorted(Path(d).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("name") == name:
                return data
        except (json.JSONDecodeError, KeyError):
            continue
    return None


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


def _check_chart_data_quality(chart: dict) -> list[str]:
    warnings = []
    data_sample = chart.get("data_sample", [])
    chart_type = chart.get("chart_type", "")
    title = chart.get("title", "untitled")

    if not data_sample:
        warnings.append(f"[{title}] data_sample is empty — query returned no rows")
    else:
        all_null = all(
            v is None for row in data_sample for v in (row.values() if isinstance(row, dict) else [row])
        )
        if all_null:
            warnings.append(
                f"[{title}] all values are NULL — SQL filter/LIKE pattern may not match any data"
            )

        has_null_metric = False
        for row in data_sample:
            if not isinstance(row, dict):
                continue
            for k, v in row.items():
                if v is None and k not in ("id",):
                    has_null_metric = True
                    break
        if has_null_metric and not all_null:
            warnings.append(
                f"[{title}] some metric values are NULL — check for division by zero or missing data"
            )

    if chart_type == "table" and data_sample and len(data_sample) == 1:
        row = data_sample[0]
        if isinstance(row, dict):
            for k, v in row.items():
                if v == 0:
                    warnings.append(
                        f"[{title}] metric '{k}' is 0 — verify this is expected"
                    )

    return warnings


def save_chart(projects_dir: str, project_id: str, dashboard_name: str, chart: dict) -> dict:
    _ensure_dir(projects_dir, project_id)
    d = _dashboards_dir(projects_dir, project_id)

    chart = _fix_chart_encoding(chart)
    quality_warnings = _check_chart_data_quality(chart)

    for f in Path(d).glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("name") == dashboard_name:
            chart_id = str(uuid.uuid4())[:8]
            chart["id"] = chart_id
            chart["saved_at"] = datetime.now().isoformat()
            if quality_warnings:
                chart["data_quality_warnings"] = quality_warnings
            data["charts"].append(chart)
            data["updated_at"] = datetime.now().isoformat()
            f.write_text(_json_dumps(data), encoding="utf-8")
            result = {"dashboard_id": data["id"], "chart_id": chart_id, "dashboard_name": dashboard_name}
            if quality_warnings:
                result["warnings"] = quality_warnings
            return result

    dashboard_id = str(uuid.uuid4())[:8]
    chart_id = str(uuid.uuid4())[:8]
    chart["id"] = chart_id
    chart["saved_at"] = datetime.now().isoformat()
    if quality_warnings:
        chart["data_quality_warnings"] = quality_warnings
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
    result = {"dashboard_id": dashboard_id, "chart_id": chart_id, "dashboard_name": dashboard_name}
    if quality_warnings:
        result["warnings"] = quality_warnings
    return result


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
