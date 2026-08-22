#!/usr/bin/env python3
"""
Latency test for the heatmap points endpoint.
One request per city, 11 requests total.

Requires: pip install requests
"""

import statistics
import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8000/heatmap/get-heatmap-points-by-city-date-metric"

CITIES = [
    "atlanta",
    "boston",
    "dallas",
    "houston",
    "kansas_city",
    "los_angeles",
    "miami",
    "new_york_nj",
    "philadelphia",
    "san_francisco",
    "seattle",
]

DATE = "2020-01-01"
METRIC = "average_temperature_c"
ADDITIONAL_METRICS = "maximum_temperature_c"
TIMEOUT = 30.0


def percentile(sorted_values, pct):
    """Linear-interpolation percentile (same method as numpy's default)."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def main():
    session = requests.Session()
    latencies = []
    failures = []

    print(f"Endpoint : {BASE_URL}")
    print(f"Params   : date={DATE}, metric={METRIC}, "
          f"additional_metrics={ADDITIONAL_METRICS}")
    print(f"Plan     : 1 request per city, {len(CITIES)} requests total\n")

    print(f"{'City':<16}{'Latency (ms)':>14}{'Status':>10}")
    print("-" * 40)

    for city in CITIES:
        params = {
            "city": city,
            "date": DATE,
            "metric": METRIC,
            "additional_metrics": ADDITIONAL_METRICS,
        }
        start = time.perf_counter()
        try:
            resp = session.get(BASE_URL, params=params, timeout=TIMEOUT)
            resp.content  # read the full body before stopping the clock
            elapsed_ms = (time.perf_counter() - start) * 1000
            if resp.status_code == 200:
                latencies.append(elapsed_ms)
                print(f"{city:<16}{elapsed_ms:>14.2f}{resp.status_code:>10}")
            else:
                failures.append((city, f"HTTP {resp.status_code}"))
                print(f"{city:<16}{elapsed_ms:>14.2f}{resp.status_code:>10}")
        except requests.RequestException as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            failures.append((city, str(exc)))
            print(f"{city:<16}{elapsed_ms:>14.2f}{'ERROR':>10}")

    if not latencies:
        print("\nNo successful requests. Is the API running on 127.0.0.1:8000?",
              file=sys.stderr)
        for city, err in failures:
            print(f"  {city}: {err}", file=sys.stderr)
        sys.exit(1)

    s = sorted(latencies)
    print("\n" + "=" * 40)
    print(f"LATENCY REPORT (ms, n={len(s)})")
    print("=" * 40)
    print(f"{'Average':<12}{statistics.fmean(s):>12.2f}")
    print(f"{'Min':<12}{s[0]:>12.2f}")
    print(f"{'P25':<12}{percentile(s, 25):>12.2f}")
    print(f"{'Median':<12}{percentile(s, 50):>12.2f}")
    print(f"{'P75':<12}{percentile(s, 75):>12.2f}")
    print(f"{'P95':<12}{percentile(s, 95):>12.2f}")
    print(f"{'Max':<12}{s[-1]:>12.2f}")
    print("=" * 40)

    if failures:
        print("\nFailures:")
        for city, err in failures:
            print(f"  {city}: {err}")


if __name__ == "__main__":
    main()