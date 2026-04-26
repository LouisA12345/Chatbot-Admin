"""Pytest fixtures and clean terminal reporting for the chatbot test suite."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

import pytest

from tests.helpers.db_utils import create_customer_db, create_owner_db
from tests.helpers.reporting import render_combined_metrics_summary, render_metrics_summary
from tests.helpers.runtime import bootstrap_app

_METRICS = defaultdict(lambda: {"passed": 0, "failed": 0, "skipped": 0, "total": 0})


def pytest_configure(config):
    _METRICS.clear()
    config.addinivalue_line("markers", "unit: unit-level tests")
    config.addinivalue_line("markers", "integration: integration tests using Flask test client")


def _group_from_nodeid(nodeid: str) -> str:
    if "/integration/" in nodeid.replace("\\", "/"):
        return "integration"
    return "unit"


def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    stats = _METRICS[_group_from_nodeid(report.nodeid)]
    stats["total"] += 1
    if report.passed:
        stats["passed"] += 1
    elif report.failed:
        stats["failed"] += 1
    elif report.skipped:
        stats["skipped"] += 1


def pytest_terminal_summary(terminalreporter):
    unit = _METRICS["unit"]
    integration = _METRICS["integration"]
    invoked_args = [str(arg).replace("\\", "/").lower() for arg in terminalreporter.config.invocation_params.args]
    requested_unit_only = any("tests/unit" in arg for arg in invoked_args) and not any("tests/integration" in arg for arg in invoked_args)
    requested_integration_only = any("tests/integration" in arg for arg in invoked_args) and not any("tests/unit" in arg for arg in invoked_args)

    def rate(passed, total, empty_message):
        return f"{(passed / total * 100):.0f}%" if total else empty_message

    cov_plugin = terminalreporter.config.pluginmanager.getplugin("_cov")
    coverage = None
    if cov_plugin:
        total = getattr(cov_plugin, "cov_total", None)
        if total is not None:
            coverage = f"{total:.0f}%"

    unit_stats = {
        "passed": unit["passed"],
        "failed": unit["failed"],
        "total": unit["total"],
        "pass_rate": rate(unit["passed"], unit["total"], "No unit tests run"),
    }
    integration_stats = {
        "passed": integration["passed"],
        "failed": integration["failed"],
        "total": integration["total"],
        "success_rate": rate(integration["passed"], integration["total"], "No integration tests run"),
        "error_rate": f"{(integration['failed'] / integration['total'] * 100):.0f}%" if integration["total"] else "0%",
    }

    if requested_unit_only or (unit["total"] and not integration["total"]):
        rows = [
            ("Pass Rate", unit_stats["pass_rate"]),
            ("Passed / Total", f"{unit_stats['passed']} / {unit_stats['total']}"),
            ("Failures", str(unit_stats["failed"])),
        ]
        if coverage is not None:
            rows.insert(1, ("Coverage", coverage))
        render_metrics_summary("UNIT TEST SUMMARY", rows)
        return

    if requested_integration_only or (integration["total"] and not unit["total"]):
        rows = [
            ("API Success Rate", integration_stats["success_rate"]),
            ("Error Rate", integration_stats["error_rate"]),
            ("Passed / Total", f"{integration_stats['passed']} / {integration_stats['total']}"),
            ("Failures", str(integration_stats["failed"])),
        ]
        if coverage is not None:
            rows.insert(1, ("Coverage", coverage))
        render_metrics_summary("INTEGRATION TEST SUMMARY", rows)
        return

    render_combined_metrics_summary(unit_stats, integration_stats, coverage)


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    """Provide a fresh Flask app and module graph per integration test."""
    runtime = bootstrap_app(monkeypatch, tmp_path)
    runtime.app.config.update(TESTING=True)
    return runtime


@pytest.fixture
def client(isolated_app):
    """Provide a Flask test client bound to the isolated app instance."""
    return isolated_app.app.test_client()


@pytest.fixture
def auth_databases(isolated_app):
    """Ensure auth/customer databases exist for endpoint integration tests."""
    create_customer_db(isolated_app.customer_db)
    create_owner_db(isolated_app.owner_db)
    isolated_app.auth.ensure_tables()
    return isolated_app.customer_db, isolated_app.owner_db


@pytest.fixture
def sqlite_row_count():
    """Return a helper for counting rows in a temporary SQLite table."""

    def _count(path, table_name: str) -> int:
        connection = sqlite3.connect(path)
        count = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        connection.close()
        return count

    return _count
