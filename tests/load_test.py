#!/usr/bin/env python3
"""
Load test for the Image to SVG backend API.

Usage:
    python load_test.py [--host HOST] [--port PORT] [--concurrency N] [--requests N]

Requires: httpx (pip install httpx)
"""

import argparse
import asyncio
import base64
import statistics
import time
import uuid

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    raise SystemExit(1)


# 1x1 red PNG (smallest valid PNG)
TINY_PNG = base64.b64encode(
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
    b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
    b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
).decode()


async def send_request(client: httpx.AsyncClient, base_url: str, preset: str = "fast") -> float:
    """Send a single upload request and return response time in ms."""
    request_id = str(uuid.uuid4())
    url = f"{base_url}/backend/upload/{request_id}"
    payload = {
        "name": "test.png",
        "data": f"data:image/png;base64,{TINY_PNG}",
        "preset": preset,
    }

    start = time.perf_counter()
    response = await client.post(url, json=payload, timeout=30.0)
    elapsed = (time.perf_counter() - start) * 1000  # ms

    if response.status_code != 200:
        print(f"  Error: {response.status_code} - {response.text[:100]}")

    return elapsed


async def run_load_test(base_url: str, concurrency: int, total_requests: int) -> None:
    """Run load test with given concurrency level."""
    print(f"\nLoad Test Configuration:")
    print(f"  Target:      {base_url}")
    print(f"  Concurrency: {concurrency}")
    print(f"  Requests:    {total_requests}")
    print(f"  Preset:      fast")
    print()

    semaphore = asyncio.Semaphore(concurrency)
    results: list[float] = []
    errors = 0

    async def bounded_request(client: httpx.AsyncClient) -> None:
        nonlocal errors
        async with semaphore:
            try:
                elapsed = await send_request(client, base_url)
                results.append(elapsed)
            except Exception as e:
                errors += 1
                print(f"  Request failed: {e}")

    start_time = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [bounded_request(client) for _ in range(total_requests)]
        await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_time

    # Report
    if results:
        results.sort()
        p95_idx = int(len(results) * 0.95)
        p99_idx = int(len(results) * 0.99)

        print(f"Results:")
        print(f"  Total time:    {total_time:.2f}s")
        print(f"  Successful:    {len(results)}/{total_requests}")
        print(f"  Errors:        {errors}")
        print(f"  Throughput:    {len(results) / total_time:.1f} req/s")
        print(f"  Avg latency:   {statistics.mean(results):.1f}ms")
        print(f"  Min latency:   {min(results):.1f}ms")
        print(f"  Max latency:   {max(results):.1f}ms")
        print(f"  P95 latency:   {results[p95_idx]:.1f}ms")
        print(f"  P99 latency:   {results[p99_idx]:.1f}ms")
        if len(results) > 1:
            print(f"  Std dev:       {statistics.stdev(results):.1f}ms")
    else:
        print("No successful requests.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test for Image to SVG API")
    parser.add_argument("--host", default="localhost", help="Backend host (default: localhost)")
    parser.add_argument("--port", type=int, default=55031, help="Backend port (default: 55031)")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent requests (default: 5)")
    parser.add_argument("--requests", type=int, default=50, help="Total requests (default: 50)")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    asyncio.run(run_load_test(base_url, args.concurrency, args.requests))


if __name__ == "__main__":
    main()
