"""
Dashboard Quality Validator — Playwright-based automated validation.

Inspired by Karpathy's autoresearch: fixed metric, automated evaluation, iterate until score improves.

Evaluation Dimensions (each 0-10, total 0-100):
  D1: Chart Count Coverage    — Does dashboard have all expected charts from semantic layer?
  D2: Chart Type Correctness  — Are chart types matching chart_hint in semantic config?
  D3: Data Completeness       — Do charts have actual data (not empty/zero)?
  D4: Title Correctness       — Do chart titles match metric business_name?
  D5: Legend Presence         — Do multi-series charts have visible legends?
  D6: Render Visual Quality   — Are ECharts instances rendered with non-zero dimensions?
  D7: Domain Grouping         — Are charts properly grouped by business_domain?
  D8: KPI Card Values         — Do KPI cards show reasonable numeric values?
  D9: Funnel Conversion       — Do funnel charts show conversion rates?
  D10: Encoding Integrity     — Are Chinese titles readable (not garbled)?

Usage:
  python tests/dashboard_validator.py --html <path-to-html> --config <path-to-semantic-config.json>
"""

import argparse
import json
import os
import sys
import time

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def load_semantic_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_expectations(config: dict) -> list[dict]:
    metrics = config.get("metrics", {})
    expectations = []
    for m_name, m_def in metrics.items():
        expectations.append({
            "metric_key": m_name,
            "business_name": m_def.get("business_name", ""),
            "chart_hint": m_def.get("chart_hint", "line"),
            "business_domain": m_def.get("business_domain", ""),
            "business_domain_label": m_def.get("business_domain_label", ""),
        })
    return expectations


def run_playwright_validation(html_path: str, config_path: str) -> dict:
    from playwright.sync_api import sync_playwright

    config = load_semantic_config(config_path)
    expectations = build_expectations(config)
    expected_domains = sorted(set(e["business_domain"] for e in expectations if e["business_domain"]))
    expected_kpi_metrics = [e for e in expectations if e["chart_hint"] == "kpi_card"]
    expected_funnel_metrics = [e for e in expectations if e["chart_hint"] == "funnel"]

    results = {
        "html_path": html_path,
        "config_path": config_path,
        "expected_metrics_count": len(expectations),
        "expected_domains": expected_domains,
        "dimensions": {},
        "issues": [],
        "score": 0,
    }

    abs_html_path = os.path.abspath(html_path)
    file_url = f"file:///{abs_html_path.replace(os.sep, '/')}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(file_url, wait_until="networkidle", timeout=30000)
        try:
            page.wait_for_function("typeof echarts !== 'undefined'", timeout=15000)
        except Exception:
            pass
        time.sleep(5)

        # --- D1: Chart Count Coverage ---
        chart_containers = page.query_selector_all(".chart-container, .echarts-chart, [data-chart-id]")
        try:
            page.wait_for_function("document.querySelectorAll('[_echarts_instance_]').length > 0", timeout=10000)
        except Exception:
            pass
        time.sleep(2)
        rendered_charts = page.evaluate("""() => {
            const instances = [];
            // Check for ECharts instances
            const doms = document.querySelectorAll('[_echarts_instance_]');
            doms.forEach((dom, i) => {
                const inst = echarts.getInstanceByDom(dom);
                if (inst) {
                    const opt = inst.getOption();
                    const title = opt.title ? (opt.title[0] || {}).text || '' : '';
                    const seriesTypes = (opt.series || []).map(s => s.type || 'unknown');
                    const hasData = (opt.series || []).some(s =>
                        (s.data && s.data.length > 0) ||
                        (s.dataset && s.dataset.source && s.dataset.source.length > 0)
                    );
                    const hasLegend = !!(opt.legend && opt.legend[0] && opt.legend[0].data && opt.legend[0].data.length > 0);
                    const rect = dom.getBoundingClientRect();
                    instances.push({
                        index: i,
                        title: title,
                        seriesTypes: seriesTypes,
                        hasData: hasData,
                        hasLegend: hasLegend,
                        width: rect.width,
                        height: rect.height,
                        visible: rect.width > 0 && rect.height > 0,
                    });
                }
            });
            return instances;
        }""")

        kpi_cards = page.evaluate("""() => {
            const cards = document.querySelectorAll('.kpi-card, .metric-card, [data-role="kpi"]');
            const results = [];
            cards.forEach((card, i) => {
                const titleEl = card.querySelector('.kpi-title, .metric-title, h3, h4');
                const valueEl = card.querySelector('.kpi-value, .metric-value, .value');
                results.push({
                    index: i,
                    title: titleEl ? titleEl.textContent.trim() : '',
                    value: valueEl ? valueEl.textContent.trim() : '',
                });
            });
            return results;
        }""")

        domain_sections = page.evaluate("""() => {
            const sections = document.querySelectorAll('.domain-section, [data-domain]');
            const results = [];
            sections.forEach((sec, i) => {
                const label = sec.getAttribute('data-domain-label') || sec.getAttribute('data-domain') || '';
                const chartCount = sec.querySelectorAll('[_echarts_instance_]').length;
                results.push({
                    domain: sec.getAttribute('data-domain') || '',
                    label: label,
                    chartCount: chartCount,
                });
            });
            return results;
        }""")

        page_title = page.title()
        body_text = page.inner_text("body")

        garbled_count = 0
        for m in page.evaluate("""() => {
            const titles = document.querySelectorAll('[_echarts_instance_]');
            const results = [];
            titles.forEach(dom => {
                const inst = echarts.getInstanceByDom(dom);
                if (inst) {
                    const opt = inst.getOption();
                    const t = opt.title ? (opt.title[0] || {}).text || '' : '';
                    results.push(t);
                }
            });
            return results;
        }"""):
            for ch in m:
                if 0xFFFD == ord(ch) or (0x80 <= ord(ch) <= 0x9F):
                    garbled_count += 1

        browser.close()

    # --- Scoring ---

    # D1: Chart Count Coverage (0-10)
    total_rendered = len(rendered_charts) + len(kpi_cards)
    coverage_ratio = min(total_rendered / max(len(expectations), 1), 1.0)
    d1_score = round(coverage_ratio * 10, 1)
    results["dimensions"]["D1_chart_count_coverage"] = {
        "score": d1_score,
        "detail": f"{total_rendered} rendered vs {len(expectations)} expected (ratio={coverage_ratio:.2f})",
    }
    if coverage_ratio < 0.8:
        results["issues"].append(f"D1: Only {total_rendered} charts rendered, expected {len(expectations)}")

    # D2: Chart Type Correctness (0-10)
    type_matches = 0
    type_checks = 0
    chart_hint_type_map = {
        "kpi_card": ["kpi_card"],
        "line": ["line"],
        "bar": ["bar"],
        "bar_line": ["bar", "line"],
        "pie": ["pie"],
        "funnel": ["funnel"],
        "scatter": ["scatter"],
        "ranking_bar": ["bar"],
    }
    for rc in rendered_charts:
        for exp in expectations:
            if exp["business_name"] and exp["business_name"] in rc.get("title", ""):
                expected_types = chart_hint_type_map.get(exp["chart_hint"], ["line"])
                actual_types = rc.get("seriesTypes", [])
                if any(at in expected_types for at in actual_types):
                    type_matches += 1
                type_checks += 1
                break
    d2_score = round((type_matches / max(type_checks, 1)) * 10, 1) if type_checks > 0 else 5.0
    results["dimensions"]["D2_chart_type_correctness"] = {
        "score": d2_score,
        "detail": f"{type_matches}/{type_checks} type matches",
    }

    # D3: Data Completeness (0-10)
    charts_with_data = sum(1 for rc in rendered_charts if rc.get("hasData"))
    kpi_with_value = sum(1 for kc in kpi_cards if kc.get("value") and kc["value"] not in ("", "0", "N/A"))
    data_complete = charts_with_data + kpi_with_value
    d3_score = round((data_complete / max(total_rendered, 1)) * 10, 1)
    results["dimensions"]["D3_data_completeness"] = {
        "score": d3_score,
        "detail": f"{data_complete}/{total_rendered} have data (charts={charts_with_data}, kpi={kpi_with_value})",
    }
    if data_complete < total_rendered:
        empty_count = total_rendered - data_complete
        results["issues"].append(f"D3: {empty_count} charts/cards have no data")

    # D4: Title Correctness (0-10)
    titled_charts = sum(1 for rc in rendered_charts if rc.get("title") and rc["title"].strip())
    titled_kpis = sum(1 for kc in kpi_cards if kc.get("title") and kc["title"].strip())
    titled_total = titled_charts + titled_kpis
    d4_score = round((titled_total / max(total_rendered, 1)) * 10, 1)
    results["dimensions"]["D4_title_correctness"] = {
        "score": d4_score,
        "detail": f"{titled_total}/{total_rendered} have titles",
    }

    # D5: Legend Presence (0-10)
    multi_series = [rc for rc in rendered_charts if len(rc.get("seriesTypes", [])) > 1]
    legends_present = sum(1 for rc in multi_series if rc.get("hasLegend"))
    d5_score = round((legends_present / max(len(multi_series), 1)) * 10, 1) if multi_series else 10.0
    results["dimensions"]["D5_legend_presence"] = {
        "score": d5_score,
        "detail": f"{legends_present}/{len(multi_series)} multi-series charts have legends",
    }
    if multi_series and legends_present < len(multi_series):
        results["issues"].append(f"D5: {len(multi_series) - legends_present} multi-series charts missing legends")

    # D6: Render Visual Quality (0-10)
    visible_charts = sum(1 for rc in rendered_charts if rc.get("visible") and rc.get("width", 0) > 100 and rc.get("height", 0) > 100)
    d6_score = round((visible_charts / max(len(rendered_charts), 1)) * 10, 1) if rendered_charts else 0
    results["dimensions"]["D6_render_visual_quality"] = {
        "score": d6_score,
        "detail": f"{visible_charts}/{len(rendered_charts)} charts have adequate dimensions (>100x100)",
    }

    # D7: Domain Grouping (0-10)
    domains_found = set(ds.get("domain", "") for ds in domain_sections if ds.get("domain"))
    domains_expected = set(expected_domains)
    domain_overlap = len(domains_found & domains_expected)
    d7_score = round((domain_overlap / max(len(domains_expected), 1)) * 10, 1)
    results["dimensions"]["D7_domain_grouping"] = {
        "score": d7_score,
        "detail": f"{domain_overlap}/{len(domains_expected)} domains matched (found={domains_found})",
    }
    missing_domains = domains_expected - domains_found
    if missing_domains:
        results["issues"].append(f"D7: Missing domains: {missing_domains}")

    # D8: KPI Card Values (0-10)
    valid_kpis = 0
    for kc in kpi_cards:
        val = kc.get("value", "")
        if val and val not in ("", "N/A", "NaN", "undefined", "null"):
            try:
                float(val.replace(",", "").replace("%", ""))
                valid_kpis += 1
            except ValueError:
                pass
    d8_score = round((valid_kpis / max(len(kpi_cards), 1)) * 10, 1) if kpi_cards else 0
    results["dimensions"]["D8_kpi_card_values"] = {
        "score": d8_score,
        "detail": f"{valid_kpis}/{len(kpi_cards)} KPI cards have valid numeric values",
    }
    if valid_kpis < len(kpi_cards):
        invalid = len(kpi_cards) - valid_kpis
        results["issues"].append(f"D8: {invalid} KPI cards have invalid/missing values")

    # D9: Funnel Conversion (0-10)
    funnel_charts = [rc for rc in rendered_charts if "funnel" in rc.get("seriesTypes", [])]
    if expected_funnel_metrics:
        d9_score = round(min(len(funnel_charts) / max(len(expected_funnel_metrics), 1), 1.0) * 10, 1)
    else:
        d9_score = 10.0
    results["dimensions"]["D9_funnel_conversion"] = {
        "score": d9_score,
        "detail": f"{len(funnel_charts)} funnel charts rendered (expected {len(expected_funnel_metrics)})",
    }

    # D10: Encoding Integrity (0-10)
    d10_score = 10.0 if garbled_count == 0 else max(0, 10 - garbled_count)
    results["dimensions"]["D10_encoding_integrity"] = {
        "score": d10_score,
        "detail": f"{garbled_count} garbled characters detected",
    }
    if garbled_count > 0:
        results["issues"].append(f"D10: {garbled_count} garbled characters in chart titles")

    # --- Total Score ---
    total = sum(d["score"] for d in results["dimensions"].values())
    results["score"] = round(total, 1)
    results["max_score"] = 100

    return results


def print_report(results: dict):
    print("\n" + "=" * 70)
    print("  DASHBOARD QUALITY VALIDATION REPORT")
    print("=" * 70)
    print(f"  HTML: {results['html_path']}")
    print(f"  Config: {results['config_path']}")
    print(f"  Expected Metrics: {results['expected_metrics_count']}")
    print(f"  Expected Domains: {results['expected_domains']}")
    print("-" * 70)
    print(f"  {'Dimension':<35} {'Score':>6}  Detail")
    print("-" * 70)
    for dim_name, dim_data in results["dimensions"].items():
        label = dim_name.replace("_", " ").title()
        print(f"  {label:<35} {dim_data['score']:>5.1f}  {dim_data['detail']}")
    print("-" * 70)
    print(f"  {'TOTAL SCORE':<35} {results['score']:>5.1f} / {results['max_score']}")
    print("=" * 70)

    if results["issues"]:
        print(f"\n  ISSUES ({len(results['issues'])}):")
        for i, issue in enumerate(results["issues"], 1):
            print(f"    {i}. {issue}")
    else:
        print("\n  No issues found!")

    print()
    return results["score"]


def main():
    parser = argparse.ArgumentParser(description="Dashboard Quality Validator")
    parser.add_argument("--html", required=True, help="Path to dashboard HTML file")
    parser.add_argument("--config", required=True, help="Path to semantic_config.json")
    args = parser.parse_args()

    results = run_playwright_validation(args.html, args.config)
    score = print_report(results)

    report_path = args.html.replace(".html", "_validation.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  Report saved to: {report_path}")

    return score


if __name__ == "__main__":
    score = main()
    sys.exit(0 if score >= 80 else 1)
