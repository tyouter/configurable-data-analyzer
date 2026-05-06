import json
import os
from typing import Optional

_THEMES_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE: dict[str, dict] = {}


def list_themes() -> list[str]:
    names = []
    for f in sorted(os.listdir(_THEMES_DIR)):
        if f.endswith(".json"):
            names.append(f[:-5])
    return names


def load_theme(name: str) -> Optional[dict]:
    if name in _CACHE:
        return _CACHE[name]
    path = os.path.join(_THEMES_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        theme = json.load(f)
    _CACHE[name] = theme
    return theme


def deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
