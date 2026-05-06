import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SPEC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "projects", "1bd90a0c", "dashboard_spec.json"))


def load_spec():
    with open(SPEC_PATH, encoding="utf-8") as f:
        return json.load(f)


async def validate_dashboard():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    html_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "projects", "1bd90a0c", "dashboards", "小红书KPI看板.html")
    )
    if not os.path.exists(html_path):
        print(f"Dashboard HTML not found: {html_path}")
        return False

    spec = load_spec()
    spec_charts = {c["chart_id"]: c for c in spec.get("charts", [])}
    spec_categories = {c["id"]: c for c in spec.get("categories", [])}

    file_url = f"file:///{html_path.replace(os.sep, '/')}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        await page.goto(file_url, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        total_score = 0
        total_checks = 0
        issues = []

        print("=" * 70)
        print("DASHBOARD SPEC-ALIGNED VALIDATION REPORT")
        print("=" * 70)

        # 1. Chart count check
        kpi_cards = await page.query_selector_all(".kpi-card")
        chart_containers = await page.query_selector_all(".chart-container")
        total_charts = len(kpi_cards) + len(chart_containers)
        expected_count = len(spec_charts)
        total_checks += 1
        if total_charts >= expected_count:
            total_score += 1
            print(f"\n✅ Chart count: {total_charts}/{expected_count}")
        else:
            issues.append(f"Chart count mismatch: {total_charts}/{expected_count}")
            print(f"\n❌ Chart count: {total_charts}/{expected_count}")

        # 2. Domain group check
        domain_sections = await page.query_selector_all(".domain-section")
        rendered_domains = set()
        for section in domain_sections:
            title_el = await section.query_selector(".domain-title")
            if title_el:
                rendered_domains.add(await title_el.inner_text())

        spec_domain_labels = {c["label"] for c in spec.get("categories", [])}
        total_checks += 1
        domain_match = len(rendered_domains & spec_domain_labels)
        if domain_match >= len(spec_domain_labels) * 0.7:
            total_score += 1
            print(f"✅ Domain groups: {domain_match}/{len(spec_domain_labels)} matched")
        else:
            issues.append(f"Domain groups: only {domain_match}/{len(spec_domain_labels)} matched")
            print(f"❌ Domain groups: {domain_match}/{len(spec_domain_labels)} matched")

        # 3. KPI card validation
        kpi_data = {}
        for card in kpi_cards:
            title_el = await card.query_selector(".kpi-title")
            value_el = await card.query_selector(".kpi-value")
            title = await title_el.inner_text() if title_el else ""
            value = await value_el.inner_text() if value_el else ""
            kpi_data[title.strip()] = value.strip()

        spec_kpi_charts = {cid: c for cid, c in spec_charts.items() if c.get("chart_type") == "kpi_card"}
        kpi_matched = 0
        kpi_no_data = 0
        print(f"\n--- KPI Cards ({len(spec_kpi_charts)} expected) ---")
        for cid, c in spec_kpi_charts.items():
            name = c["name"]
            total_checks += 1
            if name in kpi_data:
                val = kpi_data[name]
                if val and val != "-":
                    kpi_matched += 1
                    total_score += 1
                    print(f"  ✅ {name}: {val}")
                else:
                    kpi_no_data += 1
                    total_score += 0.5
                    print(f"  ⚠️  {name}: {val} (no data)")
            else:
                found = False
                for k, v in kpi_data.items():
                    if name in k or k in name:
                        found = True
                        if v and v != "-":
                            kpi_matched += 1
                            total_score += 1
                            print(f"  ✅ {name} → {k}: {v}")
                        else:
                            kpi_no_data += 1
                            total_score += 0.5
                            print(f"  ⚠️  {name} → {k}: {v} (no data)")
                        break
                if not found:
                    issues.append(f"KPI card missing: {name}")
                    print(f"  ❌ {name}: NOT FOUND")

        # 4. ECharts chart validation
        echarts_data = []
        for container in chart_containers:
            data_title = await container.get_attribute("data-title") or ""
            option_str = await container.get_attribute("data-option") or "{}"
            try:
                option = json.loads(option_str)
            except json.JSONDecodeError:
                option = {}
            echarts_data.append({"title": data_title, "option": option})

        spec_echarts = {cid: c for cid, c in spec_charts.items() if c.get("chart_type") != "kpi_card"}
        print(f"\n--- ECharts Charts ({len(spec_echarts)} expected) ---")

        for cid, c in spec_echarts.items():
            name = c["name"]
            expected_type = c.get("chart_type", "")
            total_checks += 1

            matched_chart = None
            for ec in echarts_data:
                if name in ec["title"] or ec["title"] in name:
                    matched_chart = ec
                    break

            if not matched_chart:
                for ec in echarts_data:
                    if any(w in ec["title"] for w in name.split() if len(w) > 1):
                        matched_chart = ec
                        break

            if matched_chart:
                option = matched_chart["option"]
                series = option.get("series", [])
                has_data = any(len(s.get("data", [])) > 0 for s in series)
                has_legend = bool(option.get("legend"))
                series_types = [s.get("type", "?") for s in series]

                type_ok = True
                type_map = {
                    "bar_line": ["bar", "line"],
                    "line": ["line"],
                    "bar": ["bar"],
                    "pie": ["pie"],
                    "boxplot": ["boxplot"],
                    "ranking_bar": ["bar"],
                    "funnel": ["funnel"],
                    "scatter": ["scatter"],
                }
                expected_types = type_map.get(expected_type, [])
                if expected_types:
                    for et in expected_types:
                        if et not in series_types:
                            type_ok = False

                score = 0
                status_parts = []
                if has_data:
                    score += 0.4
                    status_parts.append("data✓")
                else:
                    status_parts.append("data✗")

                if has_legend:
                    score += 0.3
                    status_parts.append("legend✓")
                else:
                    status_parts.append("legend✗")

                if type_ok:
                    score += 0.3
                    status_parts.append(f"type✓({expected_type})")
                else:
                    status_parts.append(f"type✗(exp:{expected_type} got:{series_types})")

                total_score += score
                sym = "✅" if score >= 0.9 else "⚠️" if score >= 0.5 else "❌"
                print(f"  {sym} {name} [{', '.join(status_parts)}]")
            else:
                issues.append(f"ECharts chart missing: {name}")
                print(f"  ❌ {name}: NOT FOUND")

        # 5. Console errors
        total_checks += 1
        if not console_errors:
            total_score += 1
            print(f"\n✅ No console errors")
        else:
            issues.append(f"{len(console_errors)} console errors")
            print(f"\n❌ {len(console_errors)} console errors:")
            for err in console_errors[:5]:
                print(f"    {err[:100]}")

        # 6. Global filters check
        total_checks += 1
        filter_els = await page.query_selector_all(".filter-select, .filter-input, .date-range-input")
        spec_filters = spec.get("global_filters", [])
        if len(filter_els) > 0 or len(spec_filters) == 0:
            total_score += 1
            print(f"✅ Filter controls present: {len(filter_els)}")
        else:
            total_score += 0.5
            print(f"⚠️  No filter controls found (spec defines {len(spec_filters)})")

        await browser.close()

    # Summary
    pct = (total_score / total_checks * 100) if total_checks else 0
    print(f"\n{'=' * 70}")
    print(f"OVERALL SCORE: {total_score:.1f}/{total_checks} = {pct:.1f}%")
    print(f"{'=' * 70}")

    if issues:
        print(f"\nIssues ({len(issues)}):")
        for i in issues:
            print(f"  - {i}")

    if pct >= 90:
        print("\n✅ DASHBOARD VALIDATION PASSED (≥90%)")
        return True
    elif pct >= 70:
        print("\n⚠️  DASHBOARD VALIDATION PARTIAL (70-90%)")
        return True
    else:
        print("\n❌ DASHBOARD VALIDATION FAILED (<70%)")
        return False


if __name__ == "__main__":
    result = asyncio.run(validate_dashboard())
    sys.exit(0 if result else 1)
