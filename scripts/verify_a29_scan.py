#!/usr/bin/env python3
"""Verify an independent exact A29 direct-scan result."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from exact_math import canonical_json_bytes, logarithm_intervals, sha256_file


P = 683_381_996_816_440
Q = 431_166_034_846_567
X = 1 << 71
SCALE_BITS = 100
SCAN_MAX = 37_862_796


def scaled_lower(value: Fraction) -> int:
    return value.numerator * (1 << SCALE_BITS) // value.denominator


def scaled_upper(value: Fraction) -> int:
    return -(-value.numerator * (1 << SCALE_BITS) // value.denominator)


def expected() -> dict[str, object]:
    intervals = logarithm_intervals()
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower, ln2_upper = intervals["ln2"]
    epsilon_lower = P - Q * delta_upper
    epsilon_upper = P - Q * delta_lower
    inv_m_lower = Fraction(1, 3 * X) / ln2_upper
    inv_m_upper = Fraction(1, 3 * X) / ln2_lower
    completeness = Q * epsilon_upper + Q * Q * inv_m_upper
    if int(completeness) != SCAN_MAX:
        raise AssertionError("A29 completeness bound mismatch")
    return {
        "P": str(P),
        "Q": str(Q),
        "accepted": 18_931_398,
        "epsilon_hi_scaled": str(scaled_upper(epsilon_upper)),
        "epsilon_lo_scaled": str(scaled_lower(epsilon_lower)),
        "inv_m_hi_scaled": str(scaled_upper(inv_m_upper)),
        "inv_m_lo_scaled": str(scaled_lower(inv_m_lower)),
        "rejected": SCAN_MAX - 18_931_398,
        "result": "CERTIFIED",
        "scale_bits": SCALE_BITS,
        "scan_max": SCAN_MAX,
        "undecided": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default="certificates/frontier/a29_scan_summary.json")
    parser.add_argument("--exe", help="run this scanner and compare its JSON output")
    args = parser.parse_args()
    if args.exe:
        process = subprocess.run([args.exe], text=True, capture_output=True)
        if process.returncode != 0:
            raise AssertionError(process.stderr or "A29 scanner failed")
        value = json.loads(process.stdout)
    else:
        path = Path(args.result)
        raw = path.read_bytes()
        value = json.loads(raw)
        if raw != canonical_json_bytes(value):
            raise AssertionError("A29 scan summary is not canonical JSON")
    if value != expected():
        raise AssertionError("A29 direct-scan result mismatch")
    payload = {
        "result": "ACCEPT",
        "accepted": value["accepted"],
        "scan_max": value["scan_max"],
        "undecided": value["undecided"],
    }
    if not args.exe:
        payload["summary_sha256"] = sha256_file(Path(args.result))
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"REJECT: {error}", file=sys.stderr)
        raise SystemExit(1)
