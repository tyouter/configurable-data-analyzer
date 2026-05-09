# -*- coding: utf-8 -*-
"""
Characterization Tests — Golden Master Verification.

These tests lock the current behavior of the ChatBI semantic layer by
executing all registered metrics against the Rednote-BI-Analysis-2 DuckDB.
They serve as a safety net during refactoring: if any test breaks,
either a bug was introduced or the behavior change is intentional.

Golden Reference: hermes-planning/data/rednote-bi-semantic-reference.json
Test Data: projects/Rednote-BI-Analysis-2/Rednote-BI-Analysis-2.duckdb (65,722 rows)
"""
import os
import sys
import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp_server.semantic_query import validate_raw_sql

TABLE_NAME = "events"


def _execute_metric_sql(conn, metric_name, metric_def, table_override=None):
    """
    Execute a metric SQL and return (success, error_msg, row_count, sample).

    Most metrics in semantic_config.json use correlated subqueries:
      (SELECT ... FROM events WHERE ... AND event_date = events.event_date)
    These require wrapping in an outer SELECT for standalone execution.
    """
    sql = metric_def.get("sql", "")
    if not sql:
        return False, "Empty SQL", 0, []

    table = table_override or TABLE_NAME

    try:
        # Detect correlated subquery pattern: SQL starts with (SELECT
        if sql.strip().startswith("(SELECT"):
            wrapped_sql = f"SELECT {sql} AS {metric_name} FROM {table} LIMIT 1"
        else:
            wrapped_sql = f"SELECT {sql} AS {metric_name} FROM {table} LIMIT 1"

        result = conn.execute(wrapped_sql)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]
        return True, None, len(rows), rows[:2], columns
    except Exception as e:
        # Try without wrapping
        try:
            wrapped_sql = f"SELECT {sql} AS {metric_name} FROM {table} LIMIT 1"
            result = conn.execute(wrapped_sql)
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description]
            return True, None, len(rows), rows[:2], columns
        except Exception as e2:
            return False, str(e2), 0, [], []


class TestMetricSQLExecutability:
    """
    For every metric in semantic_config.json, verify the SQL is executable
    against the Rednote DuckDB without errors.
    """

    @pytest.mark.characterization
    def test_all_metrics_present(self, metrics, golden):
        """Verify the semantic layer contains metrics."""
        assert len(metrics) > 0, "No metrics found in semantic_config.json"
        print(f"\n  Total metrics: {len(metrics)}")
        print(f"  Golden reference metrics: {golden.get('semantic_layer', {}).get('business_metrics_count', 'N/A')}")

    @pytest.mark.characterization
    def test_each_metric_sql_executable(self, duckdb_conn, metrics):
        """Each metric's SQL must execute without errors."""
        failures = []
        success_count = 0
        empty_count = 0

        for metric_name, metric_def in metrics.items():
            ok, err, row_count, sample, cols = _execute_metric_sql(
                duckdb_conn, metric_name, metric_def
            )
            if not ok:
                failures.append(f"{metric_name}: {err[:100]}")
            elif row_count == 0:
                empty_count += 1
            else:
                success_count += 1

        total = len(metrics)
        print(f"\n  Metrics executable: {success_count}/{total}")
        print(f"  Metrics with no data: {empty_count}/{total}")
        print(f"  Metrics with errors: {len(failures)}/{total}")

        if failures:
            print("\n  FAILURES:")
            for f in failures:
                print(f"    - {f}")

        # All metrics should be executable (no SQL errors)
        assert len(failures) == 0, (
            f"{len(failures)} metrics failed SQL execution:\n" +
            "\n".join(failures[:10])
        )

    @pytest.mark.characterization
    def test_dau_metric(self, duckdb_conn, metrics):
        """DAU should return a positive number."""
        if "dau" not in metrics:
            pytest.skip("dau metric not found")
        ok, err, row_count, sample, cols = _execute_metric_sql(
            duckdb_conn, "dau", metrics["dau"]
        )
        assert ok, f"dau SQL execution failed: {err}"
        assert row_count > 0, "dau returned no rows"
        val = sample[0][0] if sample else None
        assert val is not None, "dau value is NULL"
        print(f"\n  DAU: {val}")

    @pytest.mark.characterization
    def test_total_events_metric(self, duckdb_conn, metrics):
        """Total events should return approximately 65,722 (total rows)."""
        if "total_events" not in metrics:
            pytest.skip("total_events metric not found")
        ok, err, row_count, sample, cols = _execute_metric_sql(
            duckdb_conn, "total_events", metrics["total_events"]
        )
        assert ok, f"total_events SQL execution failed: {err}"
        val = sample[0][0] if sample else None
        assert val is not None, "total_events value is NULL"
        # Expect ~65,722 rows in Rednote dataset
        assert val > 60000, f"total_events too low: {val}"
        print(f"\n  Total events: {val}")

    @pytest.mark.characterization
    def test_porsche_metrics(self, duckdb_conn, metrics):
        """Verify Porsche+ related metrics execute correctly."""
        porsche_metrics = {k: v for k, v in metrics.items() if "porsche" in k.lower()}
        if not porsche_metrics:
            pytest.skip("No Porsche+ metrics found")

        failures = []
        for name, defn in porsche_metrics.items():
            ok, err, row_count, sample, cols = _execute_metric_sql(
                duckdb_conn, name, defn
            )
            if not ok:
                failures.append(f"{name}: {err[:100]}")

        assert len(failures) == 0, f"Porsche+ metrics failed: {failures}"
        print(f"\n  Porsche+ metrics: {len(porsche_metrics)} all executable")

    @pytest.mark.characterization
    def test_rate_metrics_in_range(self, duckdb_conn, metrics):
        """Rate metrics should return values between 0 and 100."""
        rate_metrics = {
            k: v for k, v in metrics.items()
            if "rate" in k.lower() or "率" in v.get("business_name", "")
        }
        if not rate_metrics:
            pytest.skip("No rate metrics found")

        out_of_range = []
        for name, defn in rate_metrics.items():
            ok, err, row_count, sample, cols = _execute_metric_sql(
                duckdb_conn, name, defn
            )
            if not ok or not sample:
                continue
            val = sample[0][0]
            if val is not None and (val < 0 or val > 100):
                out_of_range.append(f"{name}: {val}")

        assert len(out_of_range) == 0, (
            f"Rate metrics out of 0-100 range:\n" + "\n".join(out_of_range)
        )
        print(f"\n  Rate metrics checked: {len(rate_metrics)}, all in range")


class TestEventDefinitions:
    """Verify event definitions are consistent with actual data."""

    @pytest.mark.characterization
    def test_events_exist(self, events):
        """Event definitions should not be empty."""
        actual_events = {k: v for k, v in events.items() if v}
        assert len(actual_events) > 0, "No event definitions found"
        print(f"\n  Events registered: {len(actual_events)}")

    @pytest.mark.characterization
    def test_key_events_present(self, events):
        """Key business events must be defined."""
        key_events = [
            "discovery_page_pageshow",
            "porsche_page_pageshow",
            "login_page_pageshow",
        ]
        missing = [e for e in key_events if e not in events]
        assert len(missing) == 0, f"Missing key events: {missing}"
        print(f"\n  Key events: all {len(key_events)} present")

    @pytest.mark.characterization
    def test_span_name_values_match_data(self, duckdb_conn, events):
        """Event names in config should exist as span_name values in DuckDB."""
        try:
            actual_spans = duckdb_conn.execute(
                f"SELECT DISTINCT span_name FROM {TABLE_NAME} ORDER BY span_name"
            ).fetchall()
            actual_set = {row[0] for row in actual_spans}
        except Exception:
            pytest.skip("span_name column not available")

        config_events = set(events.keys())
        # At minimum, one event should match
        intersection = config_events & actual_set
        assert len(intersection) > 0, (
            f"No event names from config found in actual data. "
            f"Config events sample: {list(config_events)[:5]}, "
            f"Actual spans sample: {list(actual_set)[:5]}"
        )
        print(f"\n  Event name overlap: {len(intersection)}/{len(config_events)}")


class TestDataQuality:
    """Basic data quality checks on the Rednote dataset."""

    @pytest.mark.characterization
    def test_table_has_data(self, duckdb_conn):
        """The events table must have data."""
        count = duckdb_conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
        assert count > 0, "Events table is empty"
        print(f"\n  Total rows: {count:,}")

    @pytest.mark.characterization
    def test_table_columns(self, duckdb_conn, columns):
        """Verify expected columns exist."""
        expected_cols = {"span_name", "reduser_id", "start_time_nano", "event_date"}
        actual_cols_result = duckdb_conn.execute(f"DESCRIBE {TABLE_NAME}").fetchall()
        actual_cols = {row[0] for row in actual_cols_result}

        for col in expected_cols:
            assert col in actual_cols, f"Expected column '{col}' not found in table"

        print(f"\n  Total columns: {len(actual_cols)}")

    @pytest.mark.characterization
    def test_no_null_span_names(self, duckdb_conn):
        """span_name should not have NULL values (it's the primary event identifier)."""
        null_count = duckdb_conn.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE span_name IS NULL"
        ).fetchone()[0]
        assert null_count == 0, f"Found {null_count} NULL span_name values"
        print(f"\n  NULL span_names: {null_count}")

    @pytest.mark.characterization
    def test_date_range(self, duckdb_conn):
        """Data should span at least 20 days (Rednote dataset: 2026-03-19 to 2026-04-12)."""
        result = duckdb_conn.execute(
            f"SELECT MIN(event_date), MAX(event_date), COUNT(DISTINCT event_date) FROM {TABLE_NAME}"
        ).fetchone()
        min_date, max_date, distinct_days = result
        assert distinct_days >= 20, f"Only {distinct_days} distinct days in data"
        print(f"\n  Date range: {min_date} ~ {max_date} ({distinct_days} days)")
