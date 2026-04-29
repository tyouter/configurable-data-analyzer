# -*- coding: utf-8 -*-
"""
SQL Validation for L3 raw SQL queries.
L1/L2 query building is now handled dynamically by server.py
using each project's semantic layer.
"""

import re


def validate_raw_sql(sql: str) -> str:
    """
    Validate L3 raw SQL for safety.
    - Only SELECT allowed
    - No DDL/DML
    - Must have LIMIT
    - Max row limit 2000
    """
    sql_stripped = sql.strip().upper()

    forbidden_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
        "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
        "ATTACH", "DETACH", "COPY", "EXPORT",
    ]
    for kw in forbidden_keywords:
        if re.search(rf'\b{kw}\b', sql_stripped):
            raise ValueError(f"Forbidden SQL keyword: {kw}. Only SELECT queries are allowed.")

    if not sql_stripped.startswith("SELECT") and not sql_stripped.startswith("WITH"):
        raise ValueError("Only SELECT or WITH...SELECT queries are allowed.")

    if "LIMIT" not in sql_stripped:
        sql = sql.rstrip(";") + "\nLIMIT 2000"
    else:
        limit_match = re.search(r'LIMIT\s+(\d+)', sql_stripped)
        if limit_match:
            limit_val = int(limit_match.group(1))
            if limit_val > 2000:
                sql = re.sub(r'LIMIT\s+\d+', 'LIMIT 2000', sql, flags=re.IGNORECASE)

    return sql
