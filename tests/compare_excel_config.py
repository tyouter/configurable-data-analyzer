import json

with open("tests/excel_requirements.json", "r", encoding="utf-8") as f:
    excel = json.load(f)

with open("projects/1bd90a0c/semantic_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

metrics = config["metrics"]

print("=" * 120)
print("EXCEL DASHBOARD REQUIREMENTS (33 charts) vs SEMANTIC CONFIG (34 metrics)")
print("=" * 120)

req_data = excel.get("req_Dashboard for 5-30", {}).get("data", [])
kpi_data = excel.get("kpi_KPI list (2)", {}).get("data", [])

print("\n\n### PART 1: Dashboard Requirements (33 charts)")
print("-" * 120)
print(f"{'Num':<5} {'Category':<18} {'Chart Name':<50} {'Chart Info':<30} {'In Config?':<12}")
print("-" * 120)

for row in req_data:
    if not row or len(row) < 6:
        continue
    num = row[0].strip()
    cat = row[1].strip()
    name = row[2].strip()
    info = row[3].strip()[:50]
    theme = row[5].strip()

    if not num or not num.isdigit():
        continue

    in_config = "NO"
    for m_name, m_def in metrics.items():
        bname = m_def.get("business_name", "")
        if bname and (bname in name or name in bname):
            in_config = f"YES ({m_name})"
            break

    print(f"{num:<5} {cat:<18} {name:<50} {info:<30} {in_config:<12}")

print("\n\n### PART 2: KPI Definitions (25 KPIs)")
print("-" * 120)
print(f"{'KPI ID':<10} {'KPI Name CN':<40} {'In Config?':<40}")
print("-" * 120)

for row in kpi_data:
    if not row or len(row) < 4:
        continue
    kpi_id = row[1].strip()
    kpi_name = row[3].strip()

    if not kpi_id.startswith("KPI"):
        continue

    in_config = "NO"
    for m_name, m_def in metrics.items():
        bname = m_def.get("business_name", "")
        if bname and (bname in kpi_name or kpi_name in bname):
            in_config = f"YES ({m_name})"
            break

    print(f"{kpi_id:<10} {kpi_name:<40} {in_config:<40}")
