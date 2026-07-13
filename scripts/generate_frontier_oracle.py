#!/usr/bin/env python3
"""Generate exact structural frontier counts with rational floor sums."""

from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path

from exact_math import canonical_json_bytes, logarithm_intervals


X = 1 << 71
HEIGHTS = (
    (28, 52_449_289_519_716),
    (29, 431_166_034_846_567),
    (30, 483_615_324_366_283),
    (32, 6_234_549_927_241_963),
    (34, 267_118_416_222_671_843),
    (36, 4_242_721_909_926_539_673),
    (40, 50_247_984_153_525_417_450),
)
TAU = (
    (71, 72_057_431_991),
    (80, 2_396_860_564_955),
    (88, 64_021_008_208_555),
)


def floor_sum(n: int, modulus: int, multiplier: int, offset: int = 0) -> int:
    result = 0
    while True:
        if multiplier >= modulus:
            result += (n - 1) * n * (multiplier // modulus) // 2
            multiplier %= modulus
        if offset >= modulus:
            result += n * (offset // modulus)
            offset %= modulus
        top = multiplier * n + offset
        if top < modulus:
            return result
        n = top // modulus
        offset = top % modulus
        modulus, multiplier = multiplier, modulus


def rational_floor_sum(value: Fraction, n: int) -> int:
    return floor_sum(n, value.denominator, value.numerator)


def certified_count(n: int, floor_power: int = 71) -> int:
    intervals = logarithm_intervals()
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower, ln2_upper = intervals["ln2"]
    scale = 3 * (1 << floor_power)
    beta_lower = delta_lower + Fraction(1, scale) / ln2_upper
    beta_upper = delta_upper + Fraction(1, scale) / ln2_lower
    alpha_sums = (rational_floor_sum(delta_lower, n), rational_floor_sum(delta_upper, n))
    beta_sums = (rational_floor_sum(beta_lower, n), rational_floor_sum(beta_upper, n))
    if alpha_sums[0] != alpha_sums[1] or beta_sums[0] != beta_sums[1]:
        raise AssertionError(f"floor-sum interval does not decide N={n}")
    return beta_sums[0] - alpha_sums[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="certificates/frontier/oracle_summary.json")
    args = parser.parse_args()
    counts = [
        {"J": index, "Q": str(height), "count": certified_count(height)}
        for index, height in HEIGHTS
    ]
    tau_records = []
    for exponent, value in TAU:
        before = certified_count(value, exponent)
        through = certified_count(value + 1, exponent)
        if before != 0 or through != 1:
            raise AssertionError(f"tau certificate failed for E={exponent}")
        tau_records.append(
            {"verification_exponent": exponent, "tau": str(value), "count_below": before, "count_through": through}
        )
    certificate = {
        "schema": "collatz-frontier-oracle-v1",
        "counts": counts,
        "tau": tau_records,
        "result": "CERTIFIED",
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(certificate))
    print(output)


if __name__ == "__main__":
    main()
