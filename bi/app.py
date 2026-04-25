# -*- coding: utf-8 -*-
"""
Rednote BI - FastAPI Web Server
Run: python bi/app.py
Open: http://localhost:8501
"""

import os
import sys
import io

# Fix Windows console encoding for Unicode
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on sys.path so `bi.xxx` imports work
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from bi.data_layer import get_data_manager
from bi.agent import Agent
from bi import dashboard_store

app = FastAPI(title="Rednote BI")

# Globals — initialized on startup
_agent: Agent | None = None


@app.on_event("startup")
async def startup():
    global _agent
    print("[BI] Starting up...")
    dm = get_data_manager()
    print(f"[BI] Data loaded: {dm.meta}")
    _agent = Agent(dm)
    print("[BI] Agent ready.")


# --- API Routes ---

class QueryRequest(BaseModel):
    question: str


@app.post("/api/query")
async def api_query(req: QueryRequest):
    if not _agent:
        raise HTTPException(500, "Agent not initialized")
    result = _agent.query(req.question)
    return JSONResponse(result)


@app.get("/api/schema")
async def api_schema():
    dm = get_data_manager()
    return JSONResponse({
        "table": "events",
        "columns": dm.get_schema_info(),
        "meta": dm.meta,
    })


@app.get("/api/metrics")
async def api_metrics():
    import yaml
    semantic_path = os.path.join(os.path.dirname(__file__), "semantic.yaml")
    with open(semantic_path, encoding="utf-8") as f:
        semantic = yaml.safe_load(f)
    metrics = []
    for name, info in semantic.get("metrics", {}).items():
        metrics.append({
            "id": name,
            "business_name": info.get("business_name", name),
            "keywords": info.get("keywords", []),
        })
    return JSONResponse(metrics)


@app.get("/api/dashboards")
async def api_list_dashboards():
    dashboards = dashboard_store.list_dashboards()
    # For each dashboard, get full data with charts
    result = []
    for d in dashboards:
        full = dashboard_store.get_dashboard(d["id"])
        if full:
            result.append(full)
    return JSONResponse(result)


class SaveChartRequest(BaseModel):
    dashboard_name: str
    chart: dict


@app.post("/api/dashboards")
async def api_save_chart(req: SaveChartRequest):
    result = dashboard_store.save_chart(req.dashboard_name, req.chart)
    return JSONResponse(result)


@app.delete("/api/dashboards/{dashboard_id}/charts/{chart_id}")
async def api_delete_chart(dashboard_id: str, chart_id: str):
    ok = dashboard_store.delete_chart(dashboard_id, chart_id)
    if not ok:
        raise HTTPException(404, "Dashboard or chart not found")
    return JSONResponse({"ok": True})


# --- Static Files ---

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))


# --- Run ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BI_PORT", 8501))
    print(f"\n{'='*50}")
    print(f"  Rednote BI  →  http://localhost:{port}")
    print(f"{'='*50}\n")
    uvicorn.run(
        "bi.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
