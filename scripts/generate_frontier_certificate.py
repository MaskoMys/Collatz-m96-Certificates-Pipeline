#!/usr/bin/env python3
"""Generate the exact A28 surplus-frontier certificate."""

from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path

from exact_math import canonical_json_bytes, fraction_json, logarithm_intervals, sha256_file


P = 83_130_157_078_217
Q = 52_449_289_519_716
X = 1 << 71
SCAN_MAX = 560_277
MARGIN = Fraction(27, 50)
Q16 = 53_715_833
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


def scan() -> tuple[list[int], int]:
    intervals = logarithm_intervals()
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower, ln2_upper = intervals["ln2"]
    epsilon_lower = Q * delta_lower - P
    epsilon_upper = Q * delta_upper - P
    inverse = pow(P, -1, Q)
    accepted = []
    undecided = 0

    for distance in range(1, SCAN_MAX + 1):
        t = (-distance * inverse) % Q
        a_lower_num = distance * epsilon_upper.denominator - t * epsilon_upper.numerator
        a_upper_num = distance * epsilon_lower.denominator - t * epsilon_lower.numerator

        rhs_lower_num = Q * t * ln2_upper.denominator
        rhs_lower_den = 3 * X * ln2_upper.numerator
        rhs_upper_num = Q * t * ln2_lower.denominator
        rhs_upper_den = 3 * X * ln2_lower.numerator

        positive = a_lower_num > 0
        below = greater(
            rhs_lower_num,
            rhs_lower_den,
            a_upper_num,
            epsilon_lower.denominator,
        )
        nonpositive = a_upper_num <= 0
        above = not greater(
            rhs_upper_num,
            rhs_upper_den,
            a_lower_num,
            epsilon_upper.denominator,
        )
        if positive and below:
            accepted.append(t)
        elif not (nonpositive or above):
            undecided += 1

        a_far_positive = greater(
            a_lower_num, epsilon_upper.denominator, MARGIN.numerator, MARGIN.denominator
        )
        a_far_negative = greater(
            -a_upper_num, epsilon_lower.denominator, MARGIN.numerator, MARGIN.denominator
        )
        if not (a_far_positive or a_far_negative):
            raise AssertionError(f"lower frontier decision margin failed at d={distance}")

        b_lower_num = (
            rhs_lower_num * epsilon_lower.denominator
            - a_upper_num * rhs_lower_den
        )
        b_lower_den = rhs_lower_den * epsilon_lower.denominator
        b_upper_num = (
            rhs_upper_num * epsilon_upper.denominator
            - a_lower_num * rhs_upper_den
        )
        b_upper_den = rhs_upper_den * epsilon_upper.denominator
        b_far_positive = greater(
            b_lower_num, b_lower_den, MARGIN.numerator, MARGIN.denominator
        )
        b_far_negative = greater(
            -b_upper_num, b_upper_den, MARGIN.numerator, MARGIN.denominator
        )
        if not (b_far_positive or b_far_negative):
            raise AssertionError(f"upper frontier decision margin failed at d={distance}")

    accepted.sort()
    return accepted, undecided


def verify_rho(accepted: list[int]) -> None:
    intervals = logarithm_intervals()
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower, ln2_upper = intervals["ln2"]
    epsilon_lower = Q * delta_lower - P
    epsilon_upper = Q * delta_upper - P
    inverse = pow(P, -1, Q)
    claims = {multiple * Q27 for multiple in range(1, 5)}
    if not claims.issubset(accepted):
        raise AssertionError("rho maximizers are absent from A28")

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
            raise AssertionError(f"rho bound failed at t={t}")
        if t not in claims and upper_num * candidate_lower_den >= candidate_lower_num * upper_den:
            raise AssertionError(f"rho maximizer separation failed at t={t}")


def continued_fraction_coefficients(count: int) -> list[int]:
    lower, upper = logarithm_intervals()["delta"]
    result = []
    for _ in range(count):
        coefficient = lower.numerator // lower.denominator
        if coefficient != upper.numerator // upper.denominator:
            raise AssertionError("logarithm interval does not decide continued fraction")
        result.append(coefficient)
        lower, upper = 1 / (upper - coefficient), 1 / (lower - coefficient)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="certificates/frontier")
    args = parser.parse_args()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)

    accepted, undecided = scan()
    if undecided:
        raise AssertionError(f"frontier scan has {undecided} undecided residues")
    verify_rho(accepted)

    csv_path = output / "A28_certificate.csv"
    csv_path.write_text("t\n" + "".join(f"{value}\n" for value in accepted), encoding="ascii")
    gaps = [right - left for left, right in zip(accepted, accepted[1:])]
    below_q26 = [value for value in accepted if value < Q26]
    summary = {
        "schema": "collatz-a28-frontier-v1",
        "alpha_convergent": {"P": str(P), "Q": str(Q)},
        "continued_fraction_coefficients": continued_fraction_coefficients(29),
        "scan_distance_max": SCAN_MAX,
        "decision_margin_strictly_greater_than": fraction_json(MARGIN),
        "undecided": undecided,
        "count": len(accepted),
        "minimum": str(accepted[0]),
        "maximum": str(accepted[-1]),
        "minimum_gap": min(gaps),
        "band_counts": [sum(lower <= value < upper for value in accepted) for lower, upper in BANDS],
        "q26_subcertificate": {"count": len(below_q26), "maximum": str(below_q26[-1])},
        "rho": {"strict_upper": 126_669, "maximizers": [str(j * Q27) for j in range(1, 5)]},
        "csv_sha256": sha256_file(csv_path),
        "result": "CERTIFIED",
    }
    summary_path = output / "frontier_summary.json"
    summary_path.write_bytes(canonical_json_bytes(summary))
    print(csv_path)
    print(summary_path)


if __name__ == "__main__":
    main()
