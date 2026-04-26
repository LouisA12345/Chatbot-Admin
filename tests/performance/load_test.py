"""Standalone concurrent load test for the chatbot Flask API."""

from __future__ import annotations

import argparse
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from rich.console import Console

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.helpers.reporting import render_performance_summary

console = Console()


class RateLimiter:
    """Simple shared pacing limiter for live APIs with strict token budgets."""

    def __init__(self, requests_per_minute: float):
        self.min_interval = 60.0 / max(requests_per_minute, 1.0)
        self.lock = threading.Lock()
        self.last_request_at = 0.0

    def wait(self):
        with self.lock:
            now = time.perf_counter()
            elapsed = now - self.last_request_at
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_at = time.perf_counter()


def compute_safe_rpm(token_budget_per_minute: int, estimated_tokens_per_request: int) -> float:
    """Estimate a safe request budget from the available token budget."""
    estimated = max(estimated_tokens_per_request, 1)
    return max(token_budget_per_minute / estimated, 1.0)


def _hit_endpoint(session: requests.Session, url: str, payload: dict, limiter: RateLimiter):
    limiter.wait()
    started = time.perf_counter()
    try:
        response = session.post(url, json=payload, timeout=15)
        response.raise_for_status()
        latency_ms = (time.perf_counter() - started) * 1000
        return True, latency_ms, False
    except requests.exceptions.Timeout:
        latency_ms = (time.perf_counter() - started) * 1000
        return False, latency_ms, True
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000
        return False, latency_ms, False


def run_load_test(
    url: str,
    users: int,
    requests_per_user: int,
    payload: dict,
    token_budget_per_minute: int,
    estimated_tokens_per_request: int,
    safety_factor: float,
    timeout_seconds: int,
) -> dict:
    latencies = []
    failures = 0
    timeout_failures = 0
    started = time.perf_counter()
    safe_rpm = compute_safe_rpm(token_budget_per_minute, estimated_tokens_per_request) * max(min(safety_factor, 1.0), 0.05)
    limiter = RateLimiter(safe_rpm)

    console.print(
        f"[bold yellow]Safe mode enabled[/bold yellow]: shared pacing at about {safe_rpm:.2f} req/min "
        f"across {users} simulated users for a {token_budget_per_minute} TPM budget."
    )

    with ThreadPoolExecutor(max_workers=users) as executor:
        futures = []
        for _ in range(users):
            session = requests.Session()
            for _ in range(requests_per_user):
                futures.append(executor.submit(_hit_endpoint_with_timeout, session, url, payload, limiter, timeout_seconds))

        for future in as_completed(futures):
            ok, latency_ms, timed_out = future.result()
            latencies.append(latency_ms)
            if not ok:
                failures += 1
            if timed_out:
                timeout_failures += 1

    duration = max(time.perf_counter() - started, 0.001)
    total_requests = len(latencies)
    throughput = total_requests / duration
    failure_rate = (failures / total_requests * 100) if total_requests else 0.0

    return {
        "Concurrent Users": str(users),
        "Total Requests": str(total_requests),
        "Requests / Sec": f"{throughput:.2f}",
        "Avg Latency": f"{statistics.mean(latencies):.2f} ms",
        "Min Latency": f"{min(latencies):.2f} ms",
        "Max Latency": f"{max(latencies):.2f} ms",
        "Failure Rate": f"{failure_rate:.2f}%",
        "Timeouts": str(timeout_failures),
        "Safe Request Rate": f"{safe_rpm:.2f} req/min",
    }


def _hit_endpoint_with_timeout(session: requests.Session, url: str, payload: dict, limiter: RateLimiter, timeout_seconds: int):
    limiter.wait()
    started = time.perf_counter()
    try:
        response = session.post(url, json=payload, timeout=timeout_seconds)
        response.raise_for_status()
        latency_ms = (time.perf_counter() - started) * 1000
        return True, latency_ms, False
    except requests.exceptions.Timeout:
        latency_ms = (time.perf_counter() - started) * 1000
        return False, latency_ms, True
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000
        return False, latency_ms, False


def main():
    parser = argparse.ArgumentParser(description="Run a simple concurrent chatbot load test.")
    parser.add_argument("--url", default="http://127.0.0.1:5000/chat")
    parser.add_argument("--users", type=int, default=3)
    parser.add_argument("--requests-per-user", type=int, default=2)
    parser.add_argument("--site-id", default="site123")
    parser.add_argument("--message", default="Hi")
    parser.add_argument("--token-budget-per-minute", type=int, default=6000)
    parser.add_argument("--estimated-tokens-per-request", type=int, default=250)
    parser.add_argument("--safety-factor", type=float, default=0.6)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    payload = {"site_id": args.site_id, "message": args.message}
    metrics = run_load_test(
        args.url,
        args.users,
        args.requests_per_user,
        payload,
        args.token_budget_per_minute,
        args.estimated_tokens_per_request,
        args.safety_factor,
        args.timeout_seconds,
    )
    render_performance_summary("Performance Summary: Load Test", metrics)


if __name__ == "__main__":
    main()
