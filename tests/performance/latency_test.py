"""Standalone latency benchmark for the chatbot Flask API."""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import requests
from rich.console import Console

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.helpers.reporting import render_performance_summary

console = Console()


def compute_safe_rpm(token_budget_per_minute: int, estimated_tokens_per_request: int) -> float:
    """Estimate a safe request budget from the available token budget."""
    estimated = max(estimated_tokens_per_request, 1)
    return max(token_budget_per_minute / estimated, 1.0)


def maybe_wait(last_request_at: float, min_interval_seconds: float) -> float:
    """Sleep just enough to respect the configured pacing interval."""
    now = time.perf_counter()
    elapsed = now - last_request_at
    if elapsed < min_interval_seconds:
        time.sleep(min_interval_seconds - elapsed)
    return time.perf_counter()


def run_latency_test(
    url: str,
    total_requests: int,
    payload: dict,
    token_budget_per_minute: int,
    estimated_tokens_per_request: int,
    safety_factor: float,
    timeout_seconds: int,
) -> dict:
    session = requests.Session()
    latencies = []
    safe_rpm = compute_safe_rpm(token_budget_per_minute, estimated_tokens_per_request) * max(min(safety_factor, 1.0), 0.05)
    min_interval_seconds = 60.0 / safe_rpm
    request_failures = 0
    timeout_failures = 0
    last_request_at = 0.0

    console.print(
        f"[bold yellow]Safe mode enabled[/bold yellow]: pacing requests at about {safe_rpm:.2f} req/min "
        f"for a {token_budget_per_minute} TPM budget and ~{estimated_tokens_per_request} tokens/request."
    )

    last_request_at = maybe_wait(last_request_at, min_interval_seconds)
    start = time.perf_counter()
    try:
        response = session.post(url, json=payload, timeout=timeout_seconds)
        if response.status_code >= 400:
            request_failures += 1
    except requests.exceptions.Timeout:
        request_failures += 1
        timeout_failures += 1
    first_request_ms = (time.perf_counter() - start) * 1000
    last_request_at = time.perf_counter()

    for _ in range(total_requests):
        last_request_at = maybe_wait(last_request_at, min_interval_seconds)
        request_start = time.perf_counter()
        try:
            response = session.post(url, json=payload, timeout=timeout_seconds)
            if response.status_code >= 400:
                request_failures += 1
        except requests.exceptions.Timeout:
            request_failures += 1
            timeout_failures += 1
        latencies.append((time.perf_counter() - request_start) * 1000)
        last_request_at = time.perf_counter()

    return {
        "First Request": f"{first_request_ms:.2f} ms",
        "Repeated Avg Latency": f"{statistics.mean(latencies):.2f} ms",
        "Min Latency": f"{min(latencies):.2f} ms",
        "Max Latency": f"{max(latencies):.2f} ms",
        "Requests Executed": str(total_requests),
        "HTTP Failures": str(request_failures),
        "Timeouts": str(timeout_failures),
        "Safe Request Rate": f"{safe_rpm:.2f} req/min",
    }


def main():
    parser = argparse.ArgumentParser(description="Measure chatbot endpoint latency.")
    parser.add_argument("--url", default="http://127.0.0.1:5000/chat")
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--site-id", default="site123")
    parser.add_argument("--message", default="Hi")
    parser.add_argument("--token-budget-per-minute", type=int, default=6000)
    parser.add_argument("--estimated-tokens-per-request", type=int, default=250)
    parser.add_argument("--safety-factor", type=float, default=0.6)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    payload = {"site_id": args.site_id, "message": args.message}
    metrics = run_latency_test(
        args.url,
        args.requests,
        payload,
        args.token_budget_per_minute,
        args.estimated_tokens_per_request,
        args.safety_factor,
        args.timeout_seconds,
    )
    render_performance_summary("Performance Summary: Latency Test", metrics)


if __name__ == "__main__":
    main()
