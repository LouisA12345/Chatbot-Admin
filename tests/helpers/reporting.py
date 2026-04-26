"""Shared rich-based reporting helpers for pytest and performance scripts."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def render_metrics_summary(title: str, rows: list[tuple[str, str]]) -> None:
    table = Table(title=title, show_header=True, header_style="bold white")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold green")

    for metric, value in rows:
        table.add_row(metric, value)

    console.print(Panel.fit(table, border_style="bright_blue"))


def render_combined_metrics_summary(unit_stats: dict, integration_stats: dict, coverage: str | None = None) -> None:
    table = Table(title="TEST SUMMARY", show_header=True, header_style="bold white")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Metric", style="white")
    table.add_column("Value", style="bold green")

    table.add_row("Unit Tests", "Pass Rate", unit_stats["pass_rate"])
    if coverage is not None:
        table.add_row("Unit Tests", "Coverage", coverage)
    table.add_row("Integration Tests", "API Success Rate", integration_stats["success_rate"])
    table.add_row("Integration Tests", "Error Rate", integration_stats["error_rate"])
    table.add_row("Totals", "Passed / Total", f"{unit_stats['passed'] + integration_stats['passed']} / {unit_stats['total'] + integration_stats['total']}")
    table.add_row("Totals", "Failures", str(unit_stats["failed"] + integration_stats["failed"]))
    console.print(Panel.fit(table, border_style="bright_blue"))


def render_performance_summary(title: str, metrics: dict) -> None:
    table = Table(title=title, show_header=True, header_style="bold white")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold green")
    for key, value in metrics.items():
        table.add_row(key, value)
    console.print(Panel.fit(table, border_style="magenta"))
