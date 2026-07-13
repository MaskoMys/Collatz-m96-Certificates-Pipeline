#!/usr/bin/env python3
"""Independently verify the exact A28 frontier certificate."""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

from exact_math import canonical_json_bytes, fraction_json, logarithm_intervals, sha256_file


P = 83_130_157_078_217
Q = 52_449_289_519_716
X = 1 << 71
EXPECTED_SCAN_MAX = 560_277
MARGIN = Fraction(27, 50)
Q26 = 6_162_414_764_360
Q27 = 11_571_718_688_839
BANDS = (
    (65_470_613_321, 137_528_045_312),
    (137_528_045_312, 753_110_839_881),
    (753_110_839_881, 5_409_303_924_479),
    (5_409_303_924_479, Q26),
    (Q26, Q27),
    (Q27, Q),
)


def greater(n1: int, d1: int, n2: int, d2: int) -> bool:
    return n1 * d2 > n2 * d1


def strict_integer_ceiling_minus_one(value: Fraction) -> int:
    """Largest integer that can satisfy d < value."""
    return (value.numerator + value.denominator - 1) // value.denominator - 1


def classify_and_check_margins() -> tuple[list[int], int]:
    intervals = logarithm_intervals()
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower, ln2_upper = intervals["ln2"]
    epsilon_lower = Q * delta_lower - P
    epsilon_upper = Q * delta_upper - P
    if epsilon_lower <= 0 or Q * epsilon_upper >= 1:
        raise AssertionError("continued-fraction epsilon bounds failed")
    completeness_upper = Q * epsilon_upper + Fraction(Q * Q, 3 * X) / ln2_lower
    scan_max = strict_integer_ceiling_minus_one(completeness_upper)
    if scan_max != EXPECTED_SCAN_MAX:
        raise AssertionError(f"derived frontier cutoff changed to {scan_max}")

    inverse = pow(P, -1, Q)
    accepted = []
    for distance in range(1, scan_max + 1):
        t = (-distance * inverse) % Q
        a_lower_num = distance * epsilon_upper.denominator - t * epsilon_upper.numerator
        a_upper_num = distance * epsilon_lower.denominator - t * epsilon_lower.numerator
        rhs_lower_num = Q * t * ln2_upper.denominator
        rhs_lower_den = 3 * X * ln2_upper.numerator
        rhs_upper_num = Q * t * ln2_lower.denominator
        rhs_upper_den = 3 * X * ln2_lower.numerator

        positive = a_lower_num > 0
        below = greater(rhs_lower_num, rhs_lower_den, a_upper_num, epsilon_lower.denominator)
        nonpositive = a_upper_num <= 0
        above = not greater(rhs_upper_num, rhs_upper_den, a_lower_num, epsilon_upper.denominator)
        if positive and below:
            accepted.append(t)
        elif not (nonpositive or above):
            raise AssertionError(f"undecided frontier residue d={distance}")

        if not (
            greater(a_lower_num, epsilon_upper.denominator, 27, 50)
            or greater(-a_upper_num, epsilon_lower.denominator, 27, 50)
        ):
            raise AssertionError(f"lower decision margin failed at d={distance}")
        b_lower_num = rhs_lower_num * epsilon_lower.denominator - a_upper_num * rhs_lower_den
        b_lower_den = rhs_lower_den * epsilon_lower.denominator
        b_upper_num = rhs_upper_num * epsilon_upper.denominator - a_lower_num * rhs_upper_den
        b_upper_den = rhs_upper_den * epsilon_upper.denominator
        if not (
            greater(b_lower_num, b_lower_den, 27, 50)
            or greater(-b_upper_num, b_upper_den, 27, 50)
        ):
            raise AssertionError(f"upper decision margin failed at d={distance}")
    accepted.sort()
    return accepted, scan_max


def verify_rho(accepted: list[int]) -> None:
    intervals = logarithm_intervals()
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower, ln2_upper = intervals["ln2"]
    epsilon_lower = Q * delta_lower - P
    epsilon_upper = Q * delta_upper - P
    claims = {j * Q27 for j in range(1, 5)}
    candidate_t = Q27
    candidate_d = (-candidate_t * P) % Q
    candidate_a_upper = candidate_d * epsilon_lower.denominator - candidate_t * epsilon_lower.numerator
    candidate_lower_num = candidate_t * Q * ln2_upper.denominator * epsilon_lower.denominator
    candidate_lower_den = 3 * X * ln2_upper.numerator * candidate_a_upper
    for t in accepted:
        distance = (-t * P) % Q
        a_lower = distance * epsilon_upper.denominator - t * epsilon_upper.numerator
        upper_num = t * Q * ln2_lower.denominator * epsilon_upper.denominator
        upper_den = 3 * X * ln2_lower.numerator * a_lower
        if upper_num >= 126_669 * upper_den:
            raise AssertionError(f"rho upper bound failed at t={t}")
        if t not in claims and upper_num * candidate_lower_den >= candidate_lower_num * upper_den:
            raise AssertionError(f"rho maximum is not isolated at t={t}")


def continued_fraction(count: int) -> list[int]:
    lower, upper = logarithm_intervals()["delta"]
    result = []
    for _ in range(count):
        coefficient = lower.numerator // lower.denominator
        if coefficient != upper.numerator // upper.denominator:
            raise AssertionError("continued fraction coefficient is undecided")
        result.append(coefficient)
        lower, upper = 1 / (upper - coefficient), 1 / (lower - coefficient)
    return result


def convergent(coefficients: list[int]) -> tuple[int, int]:
    p_minus_two, p_minus_one = 0, 1
    q_minus_two, q_minus_one = 1, 0
    for coefficient in coefficients:
        p = coefficient * p_minus_one + p_minus_two
        q = coefficient * q_minus_one + q_minus_two
        p_minus_two, p_minus_one = p_minus_one, p
        q_minus_two, q_minus_one = q_minus_one, q
    return p_minus_one, q_minus_one


def read_csv(path: Path) -> list[int]:
    if path.is_symlink():
        raise AssertionError("frontier CSV may not be a symlink")
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or lines[0] != "t":
        raise AssertionError("frontier CSV header mismatch")
    values = []
    for lineno, line in enumerate(lines[1:], 2):
        if not line.isascii() or not line.isdigit() or str(int(line)) != line:
            raise AssertionError(f"noncanonical frontier row {lineno}")
        values.append(int(line))
    if values != sorted(set(values)):
        raise AssertionError("frontier rows are not strictly sorted and unique")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificates", default="certificates/frontier")
    args = parser.parse_args()
    directory = Path(args.certificates)
    expected_files = {
        "A28_certificate.csv",
        "a29_scan_summary.json",
        "frontier_summary.json",
        "oracle_summary.json",
    }
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise AssertionError("frontier certificate file set mismatch")

    csv_path = directory / "A28_certificate.csv"
    coefficients = continued_fraction(29)
    if convergent(coefficients) != (P, Q):
        raise AssertionError("A28 convergent is not reconstructed from log intervals")
    recorded = read_csv(csv_path)
    regenerated, scan_max = classify_and_check_margins()
    if recorded != regenerated:
        raise AssertionError("frontier CSV does not match the complete exact scan")
    verify_rho(recorded)

    gaps = [right - left for left, right in zip(recorded, recorded[1:])]
    below_q26 = [value for value in recorded if value < Q26]
    expected_summary = {
        "schema": "collatz-a28-frontier-v1",
        "alpha_convergent": {"P": str(P), "Q": str(Q)},
        "continued_fraction_coefficients": coefficients,
        "scan_distance_max": scan_max,
        "decision_margin_strictly_greater_than": fraction_json(MARGIN),
        "undecided": 0,
        "count": len(recorded),
        "minimum": str(recorded[0]),
        "maximum": str(recorded[-1]),
        "minimum_gap": min(gaps),
        "band_counts": [sum(lower <= value < upper for value in recorded) for lower, upper in BANDS],
        "q26_subcertificate": {"count": len(below_q26), "maximum": str(below_q26[-1])},
        "rho": {"strict_upper": 126_669, "maximizers": [str(j * Q27) for j in range(1, 5)]},
        "csv_sha256": sha256_file(csv_path),
        "result": "CERTIFIED",
    }
    summary_path = directory / "frontier_summary.json"
    raw = summary_path.read_bytes()
    summary = json.loads(raw)
    if raw != canonical_json_bytes(summary) or summary != expected_summary:
        raise AssertionError("frontier summary mismatch or noncanonical JSON")

    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "count": len(recorded),
                "minimum": recorded[0],
                "maximum": recorded[-1],
                "minimum_gap": min(gaps),
                "csv_sha256": sha256_file(csv_path),
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
