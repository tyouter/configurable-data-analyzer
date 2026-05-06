import json

with open("tests/excel_requirements.json", "r", encoding="utf-8") as f:
    excel = json.load(f)

with open("projects/1bd90a0c/semantic_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

metrics = config["metrics"]

def fuzzy_match(excel_name, config_metrics):
    excel_clean = excel_name.replace("【", "").replace("】", "").replace("（", "(").replace("）", ")").replace(" ", "").strip()
    candidates = []
    for m_name, m_def in config_metrics.items():
        bname = m_def.get("business_name", "").replace(" ", "").strip()
        desc = m_def.get("description", "").replace(" ", "").strip()[:60]
        score = 0
        if bname and bname in excel_clean:
            score = 100
        elif excel_clean and excel_clean in bname:
            score = 90
        else:
            keywords_bname = set(bname) if bname else set()
            keywords_excel = set(excel_clean)
            overlap = keywords_bname & keywords_excel
            if keywords_bname and keywords_excel:
                score = int(len(overlap) / max(len(keywords_bname), len(keywords_excel), 1) * 60)
        if score > 20:
            candidates.append((score, m_name, m_def.get("business_name", "")))
    candidates.sort(key=lambda x: -x[0])
    if candidates:
        return candidates[0]
    return None

print("=" * 140)
print("EXCEL DASHBOARD REQUIREMENTS (33 charts) vs SEMANTIC CONFIG (34 metrics) — FUZZY MATCH")
print("=" * 140)

req_data = excel.get("req_Dashboard for 5-30", {}).get("data", [])
kpi_data = excel.get("kpi_KPI list (2)", {}).get("data", [])

print("\n### DASHBOARD CHART REQUIREMENTS")
print("-" * 140)
print(f"{'#':<4} {'Category':<16} {'Excel Chart Name':<55} {'Chart Type':<20} {'Match?':<6} {'Config Metric':<30} {'Config business_name':<25}")
print("-" * 140)

matched_count = 0
unmatched = []

for row in req_data:
    if not row or len(row) < 6:
        continue
    num = row[0].strip()
    cat = row[1].strip()
    name = row[2].strip()
    info = row[3].strip()[:30]
    theme = row[5].strip()

    if not num or not num.isdigit():
        continue

    match = fuzzy_match(name, metrics)
    if match:
        score, m_name, bname = match
        matched_count += 1
        print(f"{num:<4} {cat:<16} {name:<55} {info:<20} {'YES':<6} {m_name:<30} {bname:<25}")
    else:
        unmatched.append((num, cat, name, info))
        print(f"{num:<4} {cat:<16} {name:<55} {info:<20} {'NO':<6} {'---':<30} {'---':<25}")

print(f"\nMatched: {matched_count}, Unmatched: {len(unmatched)}")

print("\n\n### UNMATCHED CHARTS (need to add to semantic_config or dashboard)")
print("-" * 140)
for num, cat, name, info in unmatched:
    print(f"  #{num} [{cat}] {name} — 图表类型: {info}")

print("\n\n### KPI DEFINITIONS")
print("-" * 140)
print(f"{'KPI ID':<10} {'Excel KPI Name':<45} {'Match?':<6} {'Config Metric':<30} {'Config business_name':<25}")
print("-" * 140)

kpi_matched = 0
kpi_unmatched = []

for row in kpi_data:
    if not row or len(row) < 4:
        continue
    kpi_id = row[1].strip()
    kpi_name = row[3].strip()

    if not kpi_id.startswith("KPI"):
        continue

    match = fuzzy_match(kpi_name, metrics)
    if match:
        score, m_name, bname = match
        kpi_matched += 1
        print(f"{kpi_id:<10} {kpi_name:<45} {'YES':<6} {m_name:<30} {bname:<25}")
    else:
        kpi_unmatched.append((kpi_id, kpi_name))
        print(f"{kpi_id:<10} {kpi_name:<45} {'NO':<6} {'---':<30} {'---':<25}")

print(f"\nKPI Matched: {kpi_matched}, Unmatched: {len(kpi_unmatched)}")

print("\n\n### UNMATCHED KPIs (need to add to semantic_config)")
print("-" * 140)
for kpi_id, kpi_name in kpi_unmatched:
    print(f"  {kpi_id}: {kpi_name}")
