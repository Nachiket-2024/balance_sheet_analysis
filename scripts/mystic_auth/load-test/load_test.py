#!/usr/bin/env python3
# scripts/mystic_auth/load-test/load_test.py
#
# Throughput/capacity load test: how many req/s a running stack sustains
# before latency or the error rate degrades. Not a pytest file - run by
# hand against a local-prod/staging stack before a release, not on every
# push. tests/backend/mystic_auth/integration/ covers concurrency
# *correctness* (does the app stay right, not just fast) as real CI pytest.
#
# Usage:
#   python scripts/mystic_auth/load-test/load_test.py --base-url http://localhost:8101
#   python scripts/mystic_auth/load-test/load_test.py --base-url http://localhost:8101 \
#       --scenario login --concurrency 50 --requests 1000
#
# Needs an account for the "login"/"me" scenarios: pass --email/--password
# for one that already exists (verified) on the target, or use --scenario
# health with no account.
#
# /auth/* routes have their own per-IP throttle (MAX_REQUESTS_PER_WINDOW /
# REQUEST_WINDOW_SECONDS, default 100/60s), separate from login lockout. A
# single test client is one IP, so --requests past that budget on login/me
# measures the rate limiter, not server capacity - keep it under the
# window, or raise MAX_REQUESTS_PER_WINDOW on the target for the test.
# /health/ready is unthrottled, safe to push arbitrarily hard.
#
# Splits work across multiple OS processes (--workers, default one per CPU
# core, capped at 8), each with its own event loop and httpx pool. A single
# Python process, even async, serializes response parsing on one core:
# this script once under-reported throughput because *it*, not the server,
# saturated one core past ~200 concurrent requests (`top` showed the
# client at 100% CPU while the target sat well below its own limit). See
# docs/mystic_auth/deployment/environment.md#7-scaling-and-load-capacity.
from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import os
import statistics
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class Result:
    status: int | None
    seconds: float
    error: str | None = None


@dataclass
class ScenarioReport:
    name: str
    results: list[Result] = field(default_factory=list)

    def summarize(self, wall_seconds: float) -> str:
        durations = sorted(r.seconds for r in self.results)
        n = len(durations)
        ok = sum(1 for r in self.results if r.error is None and r.status is not None and r.status < 500)
        errors = n - ok

        def pct(p: float) -> float:
            if not durations:
                return 0.0
            idx = min(n - 1, int(n * p))
            return durations[idx]

        lines = [
            f"== {self.name} ==",
            f"  requests:     {n}",
            f"  ok (< 500):   {ok}",
            f"  errors (>=500 or exception): {errors}",
            f"  throughput:   {n / wall_seconds:.1f} req/s (wall {wall_seconds:.2f}s)",
        ]
        if durations:
            lines += [
                f"  latency p50:  {statistics.median(durations) * 1000:.1f} ms",
                f"  latency p95:  {pct(0.95) * 1000:.1f} ms",
                f"  latency p99:  {pct(0.99) * 1000:.1f} ms",
                f"  latency max:  {durations[-1] * 1000:.1f} ms",
            ]
        return "\n".join(lines)


async def _timed(coro) -> Result:
    start = time.perf_counter()
    try:
        resp = await coro
        return Result(status=resp.status_code, seconds=time.perf_counter() - start)
    except Exception as exc:  # noqa: BLE001 - network errors count as failures, not crashes
        return Result(status=None, seconds=time.perf_counter() - start, error=str(exc))


async def _run_requests_in_one_process(
    base_url: str,
    method: str,
    path: str,
    json_body: dict | None,
    total_requests: int,
    concurrency: int,
    login_first: bool,
    email: str | None,
    password: str | None,
) -> list[tuple[int | None, float, str | None]]:
    # httpx defaults to max_connections=100 - well below --concurrency for a
    # real stress run, which would silently cap throughput on the client
    # side and misreport it as a server limit.
    limits = httpx.Limits(max_connections=max(concurrency * 2, 100), max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0, verify=False, limits=limits) as client:
        cookies = None
        if login_first:
            login_resp = await client.post("/auth/login", json={"email": email, "password": password})
            login_resp.raise_for_status()
            cookies = login_resp.cookies

        def make_request():
            if method == "GET":
                return client.get(path, cookies=cookies)
            return client.post(path, json=json_body)

        semaphore = asyncio.Semaphore(concurrency)
        results: list[Result] = []

        async def bounded():
            async with semaphore:
                results.append(await _timed(make_request()))

        await asyncio.gather(*(bounded() for _ in range(total_requests)))
        return [(r.status, r.seconds, r.error) for r in results]


def _worker_entrypoint(args_tuple) -> list[tuple[int | None, float, str | None]]:
    # Runs in its own OS process (ProcessPoolExecutor), so it gets its own
    # Python interpreter, own GIL, own event loop - a real extra core, not
    # just an extra coroutine sharing the one this function was called from.
    return asyncio.run(_run_requests_in_one_process(*args_tuple))


def _split_evenly(total: int, parts: int) -> list[int]:
    base, remainder = divmod(total, parts)
    return [base + (1 if i < remainder else 0) for i in range(parts)]


async def run_scenario(
    name: str,
    base_url: str,
    method: str,
    path: str,
    json_body: dict | None,
    total_requests: int,
    concurrency: int,
    num_workers: int,
    login_first: bool = False,
    email: str | None = None,
    password: str | None = None,
) -> ScenarioReport:
    report = ScenarioReport(name=name)
    workers = max(1, min(num_workers, total_requests, concurrency))
    per_worker_requests = _split_evenly(total_requests, workers)
    # Concurrency splits the same way, floored at 1, so --concurrency 50
    # across 8 workers runs ~6-7 in-flight requests per worker, 50 total in
    # flight overall, matching what a single-process run with --concurrency
    # 50 would have had in flight, not 50 per worker.
    per_worker_concurrency = max(1, concurrency // workers)

    worker_args = [
        (
            base_url,
            method,
            path,
            json_body,
            requests_for_this_worker,
            per_worker_concurrency,
            login_first,
            email,
            password,
        )
        for requests_for_this_worker in per_worker_requests
        if requests_for_this_worker > 0
    ]

    start = time.perf_counter()
    loop = asyncio.get_running_loop()
    with multiprocessing.get_context("spawn").Pool(processes=len(worker_args)) as pool:
        worker_results = await loop.run_in_executor(None, pool.map, _worker_entrypoint, worker_args)
    report_wall = time.perf_counter() - start

    for results in worker_results:
        for status, seconds, error in results:
            report.results.append(Result(status=status, seconds=seconds, error=error))

    print(report.summarize(report_wall))
    print(f"  ({workers} worker process(es), ~{per_worker_concurrency} concurrent request(s) each)")
    print()
    return report


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="e.g. http://localhost:8101")
    parser.add_argument("--scenario", choices=["health", "login", "me", "all"], default="all")
    parser.add_argument("--requests", type=int, default=500, help="total requests per scenario")
    parser.add_argument("--concurrency", type=int, default=50, help="in-flight requests at once, across all workers")
    parser.add_argument(
        "--workers",
        type=int,
        default=min(os.cpu_count() or 1, 8),
        help="OS processes to split the load across (default: one per CPU core, capped at 8)",
    )
    parser.add_argument("--email", default=None, help="existing verified account, for login/me scenarios")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    if args.scenario in ("health", "all"):
        await run_scenario(
            "GET /health/ready (unauthenticated, no DB write)",
            args.base_url,
            "GET",
            "/health/ready",
            None,
            args.requests,
            args.concurrency,
            args.workers,
        )

    if args.scenario in ("login", "all"):
        if not (args.email and args.password):
            print("Skipping login/me scenarios: pass --email/--password for an existing verified account.")
            return

        await run_scenario(
            "POST /auth/login (real Argon2 hash + Valkey lockout counters, repeated)",
            args.base_url,
            "POST",
            "/auth/login",
            {"email": args.email, "password": args.password},
            args.requests,
            args.concurrency,
            args.workers,
        )

    if args.scenario in ("me", "all"):
        await run_scenario(
            "GET /auth/me (authenticated read, real DB round trip)",
            args.base_url,
            "GET",
            "/auth/me",
            None,
            args.requests,
            args.concurrency,
            args.workers,
            login_first=True,
            email=args.email,
            password=args.password,
        )


if __name__ == "__main__":
    asyncio.run(main())
