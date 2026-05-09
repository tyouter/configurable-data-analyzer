# -*- coding: utf-8 -*-
"""
ChatBI — Test fixtures and configuration.

Provides:
- rednote_project: fixture that loads Rednote-BI-Analysis-2 DuckDB
- semantic_config: fixture that loads semantic_config.json
- golden: fixture that loads rednote-bi-semantic-reference.json
"""
import os
import json
import sys
import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import duckdb
from mcp_server.project_model import ProjectStore, ProjectSession

# Paths
PROJECTS_DIR = os.path.join(_PROJECT_ROOT, "projects")
REDNOTE_PROJECT_ID = "Rednote-BI-Analysis-2"
REDNOTE_DUCKDB = os.path.join(PROJECTS_DIR, REDNOTE_PROJECT_ID, f"{REDNOTE_PROJECT_ID}.duckdb")
REDNOTE_SEMANTIC_CONFIG = os.path.join(PROJECTS_DIR, REDNOTE_PROJECT_ID, "semantic_config.json")
GOLDEN_REFERENCE = os.path.join(_PROJECT_ROOT, "hermes-planning", "data", "rednote-bi-semantic-reference.json")


@pytest.fixture(scope="session")
def duckdb_conn():
    """Session-scoped DuckDB connection to Rednote-BI-Analysis-2."""
    if not os.path.exists(REDNOTE_DUCKDB):
        pytest.skip(f"DuckDB not found: {REDNOTE_DUCKDB}")
    conn = duckdb.connect(REDNOTE_DUCKDB, read_only=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def semantic_config():
    """Load semantic_config.json from Rednote-BI-Analysis-2."""
    if not os.path.exists(REDNOTE_SEMANTIC_CONFIG):
        pytest.skip(f"semantic_config.json not found: {REDNOTE_SEMANTIC_CONFIG}")
    with open(REDNOTE_SEMANTIC_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def golden():
    """Load rednote-bi-semantic-reference.json — the golden master."""
    if not os.path.exists(GOLDEN_REFERENCE):
        pytest.skip(f"Golden reference not found: {GOLDEN_REFERENCE}")
    with open(GOLDEN_REFERENCE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def table_name(semantic_config):
    """Get the table name from semantic config."""
    return semantic_config.get("project_type", "events") if isinstance(semantic_config, dict) else "events"


@pytest.fixture(scope="session")
def metrics(semantic_config):
    """Extract metrics dict from semantic config."""
    if not isinstance(semantic_config, dict):
        return {}
    return semantic_config.get("metrics", {})


@pytest.fixture(scope="session")
def events(semantic_config):
    """Extract events dict from semantic config."""
    if not isinstance(semantic_config, dict):
        return {}
    return semantic_config.get("events", {}) or semantic_config.get("event_definitions", {})


@pytest.fixture(scope="session")
def columns(semantic_config):
    """Extract columns dict from semantic config."""
    if not isinstance(semantic_config, dict):
        return {}
    return semantic_config.get("columns", {})


def pytest_configure(config):
    config.addinivalue_line("markers", "characterization: golden master characterization tests")
