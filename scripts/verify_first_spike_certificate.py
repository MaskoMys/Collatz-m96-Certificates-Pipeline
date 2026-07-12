#!/usr/bin/env python3
"""Independently verify the positive first-spike finite certificate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from exact_math import canonical_json_bytes, sha256_file


def exact_row(m: int) -> dict[str, int]:
    upper_h = None
    positive_h = None
    for h in range(1, 2 * m + 1):
        if (1 << h) * ((1 << m) - 1) <= pow(3, m) - 1:
            upper_h = h
        if positive_h is None and (1 << (m + h)) > pow(3, m):
            positive_h = h
    if upper_h is None or positive_h is None or positive_h <= upper_h:
        raise AssertionError(f"first-spike finite check failed at m={m}")
    return {
        "m": m,
        "largest_h_satisfying_upper": upper_h,
        "smallest_h_satisfying_positive_branch": positive_h,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificate", default="certificates/first_spike.json")
    args = parser.parse_args()
    path = Path(args.certificate)
    if path.is_symlink():
        raise AssertionError("first-spike certificate may not be a symlink")
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical_json_bytes(value):
        raise AssertionError("first-spike certificate is not canonical JSON")
    expected = {
        "schema": "collatz-first-spike-v1",
        "range": {"m_min": 2, "m_max": 102},
        "rows": [exact_row(m) for m in range(2, 103)],
        "survivors": 0,
        "analytic_threshold_checks": {
            "two_pow_897_gt_two_times_103_pow_133": (1 << 897) > 2 * pow(103, 133),
            "two_times_two_pow_103_minus_one_pow_10_gt_two_pow_1030": 2 * pow((1 << 103) - 1, 10) > (1 << 1030),
        },
        "result": "CERTIFIED",
    }
    if value != expected or not all(expected["analytic_threshold_checks"].values()):
        raise AssertionError("first-spike certificate mismatch")
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "verified_m": 101,
                "survivors": 0,
                "certificate_sha256": sha256_file(path),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"REJECT: {error}", file=sys.stderr)
        raise SystemExit(1)
