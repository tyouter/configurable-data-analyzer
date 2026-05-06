import duckdb, os

db_path = r"d:\projects\claude\configurable-data-analyzer\projects\a6a4c0cb\a6a4c0cb.duckdb"
con = duckdb.connect(database=db_path, read_only=True)

print("=== Tables ===")
print(con.execute("SHOW TABLES").fetchall())

print("\n=== Columns ===")
cols = con.execute("DESCRIBE events").fetchall()
for c in cols:
    print(f"  {c[0]}: {c[1]}")

print("\n=== event_date exists? ===")
event_date_cols = [c for c in cols if c[0] == 'event_date']
print(f"  Found: {event_date_cols}")

print("\n=== start_time_nano sample ===")
r = con.execute("SELECT start_time_nano FROM events LIMIT 2").fetchall()
print(r)

print("\n=== Try creating event_date manually ===")
con.close()

con2 = duckdb.connect(database=db_path)
try:
    con2.execute("ALTER TABLE events ADD COLUMN event_date DATE")
    con2.execute("UPDATE events SET event_date = CAST(TRY_CAST(start_time_nano AS TIMESTAMP) AS DATE)")
    r = con2.execute("SELECT event_date, COUNT(*) as cnt FROM events GROUP BY event_date ORDER BY event_date LIMIT 5").fetchall()
    print(r)
    print("SUCCESS!")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    con2.close()
