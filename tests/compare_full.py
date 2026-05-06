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
        if bname and bname in excel_clean:
            candidates.append((100, m_name, m_def.get("business_name", "")))
        elif excel_clean and excel_clean in bname:
            candidates.append((90, m_name, m_def.get("business_name", "")))
        else:
            keywords_bname = set(bname) if bname else set()
            keywords_excel = set(excel_clean)
            overlap = keywords_bname & keywords_excel
            if keywords_bname and keywords_excel:
                score = int(len(overlap) / max(len(keywords_bname), len(keywords_excel), 1) * 60)
                if score > 25:
                    candidates.append((score, m_name, m_def.get("business_name", "")))
    candidates.sort(key=lambda x: -x[0])
    return candidates[0] if candidates else None

req_data = excel.get("req_Dashboard for 5-30", {}).get("data", [])

print("### FULL DASHBOARD CHART REQUIREMENTS COMPARISON")
print("-" * 140)

matched = []
unmatched = []

for row in req_data:
    if not row or len(row) < 6:
        continue
    num = row[0].strip()
    cat = row[1].strip()
    name = row[2].strip()
    info = row[3].strip()
    theme = row[5].strip()

    if not num or not num.isdigit():
        continue

    match = fuzzy_match(name, metrics)
    if match and match[0] >= 40:
        matched.append((num, cat, name, info, match))
    else:
        unmatched.append((num, cat, name, info, theme))

print(f"\n=== MATCHED ({len(matched)}) ===")
for num, cat, name, info, (score, m_name, bname) in matched:
    print(f"  #{num} [{cat}] {name}")
    print(f"       -> config: {m_name} ({bname}) [score={score}]")
    print(f"       Excel chart type: {info[:80]}")

print(f"\n=== UNMATCHED ({len(unmatched)}) ===")
for num, cat, name, info, theme in unmatched:
    print(f"  #{num} [{cat}] {name}")
    print(f"       Excel chart type: {info[:80]}")
    print(f"       Theme: {theme[:80]}")

print(f"\n\nTotal Excel charts: {len(matched) + len(unmatched)}")
print(f"Matched: {len(matched)}")
print(f"Unmatched (MISSING from config/dashboard): {len(unmatched)}")
