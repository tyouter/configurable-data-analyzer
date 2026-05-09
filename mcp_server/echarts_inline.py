# -*- coding: utf-8 -*-
"""
ECharts Inline Provider — download and cache echarts.min.js for offline use.

Eliminates CDN dependency for Playwright screenshots and dashboard HTML export.
"""
import os
import logging

logger = logging.getLogger(__name__)

_ECHARTS_CDN_URL = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"

# Cache location: next to this module
_CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_FILE = os.path.join(_CACHE_DIR, ".echarts_cache.js")

_echarts_js: str | None = None


def _download_echarts() -> str:
    """Download echarts.min.js from CDN and cache to disk."""
    import urllib.request
    logger.info(f"Downloading ECharts from {_ECHARTS_CDN_URL}...")
    try:
        req = urllib.request.Request(_ECHARTS_CDN_URL, headers={"User-Agent": "ChatBI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            js = resp.read().decode("utf-8")
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(js)
        logger.info(f"ECharts cached to {_CACHE_FILE} ({len(js):,} bytes)")
        return js
    except Exception as e:
        logger.warning(f"Failed to download ECharts: {e}")
        raise


def get_echarts_js() -> str:
    """
    Return echarts.min.js as a string.
    Uses disk cache if available; downloads from CDN on first call.
    """
    global _echarts_js
    if _echarts_js is not None:
        return _echarts_js

    # Try cache first
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            _echarts_js = f.read()
        if len(_echarts_js) > 10000:
            logger.debug(f"ECharts loaded from cache ({len(_echarts_js):,} bytes)")
            return _echarts_js

    # Download + cache
    _echarts_js = _download_echarts()
    return _echarts_js


def clear_cache():
    """Remove the cached echarts.js file."""
    if os.path.exists(_CACHE_FILE):
        os.remove(_CACHE_FILE)
    global _echarts_js
    _echarts_js = None
