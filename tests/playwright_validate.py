import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def validate_dashboard():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    html_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "projects", "1bd90a0c", "dashboards", "小红书KPI看板.html")
    )
    if not os.path.exists(html_path):
        print(f"Dashboard HTML not found: {html_path}")
        return

    file_url = f"file:///{html_path.replace(os.sep, '/')}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        await page.goto(file_url, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        results = {
            "chart_count": 0,
            "kpi_cards": [],
            "echarts_charts": [],
            "domain_groups": [],
            "errors": console_errors,
        }

        domain_sections = await page.query_selector_all(".domain-section")
        for section in domain_sections:
            title_el = await section.query_selector(".domain-title")
            title = await title_el.inner_text() if title_el else "Unknown"
            results["domain_groups"].append(title)

        kpi_cards = await page.query_selector_all(".kpi-card")
        results["chart_count"] += len(kpi_cards)
        for card in kpi_cards:
            label_el = await card.query_selector(".kpi-title")
            value_el = await card.query_selector(".kpi-value")
            label = await label_el.inner_text() if label_el else ""
            value = await value_el.inner_text() if value_el else ""
            results["kpi_cards"].append({"label": label, "value": value})

        chart_containers = await page.query_selector_all(".chart-container")
        results["chart_count"] += len(kpi_cards)
        for container in chart_containers:
            data_title = await container.get_attribute("data-title") or ""
            option_str = await container.get_attribute("data-option") or "{}"
            try:
                option = json.loads(option_str)
            except json.JSONDecodeError:
                option = {}

            series = option.get("series", [])
            chart_info = {
                "title": data_title,
                "series_count": len(series),
                "series_types": [s.get("type", "?") for s in series],
                "has_data": any(len(s.get("data", [])) > 0 for s in series),
            }

            if option.get("xAxis"):
                chart_info["xAxis_type"] = option["xAxis"].get("type", "?")
            if option.get("yAxis"):
                ya = option["yAxis"]
                if isinstance(ya, list):
                    chart_info["yAxis_count"] = len(ya)
                else:
                    chart_info["yAxis_count"] = 1

            has_legend = bool(option.get("legend"))
            chart_info["has_legend"] = has_legend

            results["echarts_charts"].append(chart_info)

        total_charts = len(kpi_cards) + len(chart_containers)
        results["chart_count"] = total_charts

        await browser.close()

    print("=" * 60)
    print("DASHBOARD VALIDATION REPORT")
    print("=" * 60)
    print(f"\nTotal charts: {results['chart_count']}")
    print(f"  KPI cards: {len(results['kpi_cards'])}")
    print(f"  ECharts charts: {len(results['echarts_charts'])}")
    print(f"  Domain groups: {len(results['domain_groups'])}")

    print(f"\nDomain groups: {results['domain_groups']}")

    print("\n--- KPI Cards ---")
    for card in results["kpi_cards"]:
        print(f"  {card['label']}: {card['value']}")

    print("\n--- ECharts Charts ---")
    for chart in results["echarts_charts"]:
        status = "OK" if chart["has_data"] else "NO DATA"
        print(f"  [{status}] {chart['title']} | series={chart['series_count']} types={chart['series_types']} legend={chart['has_legend']}")

    no_data_count = sum(1 for c in results["echarts_charts"] if not c["has_data"])
    print(f"\nCharts with no data: {no_data_count}")

    if results["errors"]:
        print(f"\n--- Console Errors ({len(results['errors'])}) ---")
        for err in results["errors"]:
            print(f"  {err}")
    else:
        print("\nNo console errors!")

    spec_charts = 33
    coverage = (total_charts / spec_charts * 100) if spec_charts else 0
    print(f"\nSpec coverage: {total_charts}/{spec_charts} = {coverage:.1f}%")

    if total_charts >= spec_charts and no_data_count == 0 and not results["errors"]:
        print("\n✅ DASHBOARD VALIDATION PASSED")
    else:
        issues = []
        if total_charts < spec_charts:
            issues.append(f"Missing {spec_charts - total_charts} charts")
        if no_data_count > 0:
            issues.append(f"{no_data_count} charts have no data")
        if results["errors"]:
            issues.append(f"{len(results['errors'])} console errors")
        print(f"\n❌ DASHBOARD VALIDATION FAILED: {'; '.join(issues)}")


if __name__ == "__main__":
    asyncio.run(validate_dashboard())
