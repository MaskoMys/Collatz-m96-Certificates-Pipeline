#!/usr/bin/env python3
"""Generate the exact finite certificate for the positive first-spike gate."""

from __future__ import annotations

import argparse
from pathlib import Path

from exact_math import canonical_json_bytes


def row(m: int) -> dict[str, int]:
    power2 = 1 << m
    power3 = pow(3, m)
    upper_h = max(
        h for h in range(1, 2 * m + 1) if (1 << h) * (power2 - 1) <= power3 - 1
    )
    positive_h = min(h for h in range(1, 2 * m + 1) if (1 << (m + h)) > power3)
    if positive_h <= upper_h:
        raise AssertionError(f"positive first-spike survivor at m={m}")
    return {
        "m": m,
        "largest_h_satisfying_upper": upper_h,
        "smallest_h_satisfying_positive_branch": positive_h,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="certificates/first_spike.json")
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = [row(m) for m in range(2, 103)]
    certificate = {
        "schema": "collatz-first-spike-v1",
        "range": {"m_min": 2, "m_max": 102},
        "rows": rows,
        "survivors": 0,
        "analytic_threshold_checks": {
            "two_pow_897_gt_two_times_103_pow_133": (1 << 897) > 2 * pow(103, 133),
            "two_times_two_pow_103_minus_one_pow_10_gt_two_pow_1030": 2 * pow((1 << 103) - 1, 10) > (1 << 1030),
        },
        "result": "CERTIFIED",
    }
    output.write_bytes(canonical_json_bytes(certificate))
    print(output)


if __name__ == "__main__":
    main()
