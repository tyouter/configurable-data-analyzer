import duckdb
con = duckdb.connect()

test_data = [["2026-03-19T19:10:16.123456789Z"], ["2026-03-20T08:30:00.987654321Z"]]
con.execute("CREATE TABLE test_ts (start_time_nano VARCHAR)")
con.execute("INSERT INTO test_ts VALUES (?)", test_data[0])
con.execute("INSERT INTO test_ts VALUES (?)", test_data[1])

print("=== TRY_CAST to TIMESTAMP ===")
r = con.execute("SELECT start_time_nano, TRY_CAST(start_time_nano AS TIMESTAMP) FROM test_ts").fetchall()
print(r)

print("\n=== CAST to DATE ===")
r = con.execute("SELECT CAST(TRY_CAST(start_time_nano AS TIMESTAMP) AS DATE) FROM test_ts").fetchall()
print(r)

con.close()
