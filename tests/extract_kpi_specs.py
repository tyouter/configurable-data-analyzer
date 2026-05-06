import json

with open("tests/excel_requirements.json", "r", encoding="utf-8") as f:
    excel = json.load(f)

kpi_data = excel.get("kpi_KPI list (2)", {}).get("data", [])

kpis = []
for row in kpi_data:
    if not row or len(row) < 7:
        continue
    kpi_id = row[1].strip()
    if not kpi_id.startswith("KPI"):
        continue
    kpis.append({
        "kpi_id": kpi_id,
        "kpi_name_en": row[2].strip(),
        "kpi_name_cn": row[3].strip(),
        "time_period": row[4].strip(),
        "formula": row[5].strip(),
        "remark": row[6].strip(),
        "description": row[7].strip(),
        "data_source": row[8].strip() if len(row) > 8 else "",
        "period_date": row[10].strip() if len(row) > 10 else "",
        "period_week": row[11].strip() if len(row) > 11 else "",
        "period_month": row[12].strip() if len(row) > 12 else "",
    })

with open("tests/excel_kpi_specs.json", "w", encoding="utf-8") as f:
    json.dump(kpis, f, ensure_ascii=False, indent=2)
print(f"Extracted {len(kpis)} KPI specs")
