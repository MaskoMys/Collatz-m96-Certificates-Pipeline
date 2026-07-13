#!/usr/bin/env python3
"""Independently verify structural frontier floor-sum certificates."""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

from exact_math import canonical_json_bytes, logarithm_intervals, sha256_file


EXPECTED_COUNTS = (
    (28, 52_449_289_519_716, 280_139),
    (29, 431_166_034_846_567, 18_931_398),
    (30, 483_615_324_366_283, 23_817_367),
    (32, 6_234_549_927_241_963, 3_958_255_375),
    (34, 267_118_416_222_671_843, 7_266_098_126_207),
    (36, 4_242_721_909_926_539_673, 1_833_085_533_337_202),
    (40, 50_247_984_153_525_417_450, 257_117_053_950_509_254),
)
EXPECTED_TAU = (
    (71, 72_057_431_991),
    (80, 2_396_860_564_955),
    (88, 64_021_008_208_555),
)


def floor_sum(n: int, modulus: int, multiplier: int) -> int:
    answer = 0
    offset = 0
    while True:
        quotient, multiplier = divmod(multiplier, modulus)
        answer += quotient * n * (n - 1) // 2
        quotient, offset = divmod(offset, modulus)
        answer += quotient * n
        maximum = multiplier * n + offset
        if maximum < modulus:
            return answer
        n, offset = divmod(maximum, modulus)
        modulus, multiplier = multiplier, modulus


def sum_at(value: Fraction, n: int) -> int:
    return floor_sum(n, value.denominator, value.numerator)


def count(n: int, exponent: int) -> int:
    intervals = logarithm_intervals()
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower, ln2_upper = intervals["ln2"]
    denominator = 3 * (1 << exponent)
    shifted_lower = delta_lower + Fraction(1, denominator) / ln2_upper
    shifted_upper = delta_upper + Fraction(1, denominator) / ln2_lower
    alpha_lower = sum_at(delta_lower, n)
    alpha_upper = sum_at(delta_upper, n)
    shifted_lower_sum = sum_at(shifted_lower, n)
    shifted_upper_sum = sum_at(shifted_upper, n)
    if alpha_lower != alpha_upper or shifted_lower_sum != shifted_upper_sum:
        raise AssertionError(f"oracle interval undecided at N={n}")
    return shifted_lower_sum - alpha_lower


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificate", default="certificates/frontier/oracle_summary.json")
    args = parser.parse_args()
    path = Path(args.certificate)
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical_json_bytes(value):
        raise AssertionError("oracle certificate is not canonical JSON")
    expected_counts = []
    for index, height, expected in EXPECTED_COUNTS:
        actual = count(height, 71)
        if actual != expected:
            raise AssertionError(f"frontier count mismatch at Q{index}")
        expected_counts.append({"J": index, "Q": str(height), "count": expected})
    expected_tau = []
    for exponent, tau in EXPECTED_TAU:
        before = count(tau, exponent)
        through = count(tau + 1, exponent)
        if (before, through) != (0, 1):
            raise AssertionError(f"tau mismatch at E={exponent}")
        expected_tau.append(
            {"verification_exponent": exponent, "tau": str(tau), "count_below": 0, "count_through": 1}
        )
    expected = {
        "schema": "collatz-frontier-oracle-v1",
        "counts": expected_counts,
        "tau": expected_tau,
        "result": "CERTIFIED",
    }
    if value != expected:
        raise AssertionError("oracle certificate payload mismatch")
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "verified_counts": len(expected_counts),
                "verified_tau": len(expected_tau),
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
