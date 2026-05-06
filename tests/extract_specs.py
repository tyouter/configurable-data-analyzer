import json

with open("tests/excel_requirements.json", "r", encoding="utf-8") as f:
    excel = json.load(f)

req_data = excel.get("req_Dashboard for 5-30", {}).get("data", [])

charts = []
for row in req_data:
    if not row or len(row) < 6:
        continue
    num = row[0].strip()
    if not num or not num.isdigit():
        continue
    charts.append({
        "num": int(num),
        "category": row[1].strip(),
        "chart_name": row[2].strip(),
        "chart_info": row[3].strip(),
        "filters": row[4].strip(),
        "theme": row[5].strip(),
    })

with open("tests/excel_dashboard_specs.json", "w", encoding="utf-8") as f:
    json.dump(charts, f, ensure_ascii=False, indent=2)
print(f"Extracted {len(charts)} chart specs")
