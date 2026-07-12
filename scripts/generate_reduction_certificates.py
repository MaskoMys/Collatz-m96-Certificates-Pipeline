#!/usr/bin/env python3
"""Generate deterministic exact reduction certificates for m=92..96."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from exact_math import (
    canonical_json_bytes,
    ceil_div,
    fraction_json,
    geometric_sum,
    log2_upper_witness,
    logarithm_intervals,
    sha256_file,
    strict_floor,
)


X = 1 << 71
HERCHER_K = 77_600_000_000_000_000_000
K0 = 205_632_218_873_398_596_256
Q = 7_941_964_418_702_608_664_581
DELTA_COARSE = Fraction(317, 200)
LOG_TERMS = 192
LOG_BITS = 256
EXPONENT_DENOMINATOR = 1000
ERROR_EXPONENT_CAP = 200

FIRST_FAREY = (
    Fraction(202_780_263_237_295_321_099, 127_940_101_513_462_006_853),
    Fraction(123_139_092_617_126_647_266, 77_692_117_359_936_589_403),
)
FINAL_FAREY = (
    Fraction(12_261_796_429_850_908_150_604, 7_736_332_199_829_210_068_325),
    Fraction(325_919_355_854_421_968_365, 205_632_218_873_398_596_256),
)


@dataclass(frozen=True)
class Case:
    m: int
    window_num: int
    window_den: int
    depth: int
    extra: tuple[int, ...]
    kcaps: tuple[int, ...]
    final_s: int


TERM = ceil_div(93 * (1 << 189), 50)
B2_92 = ceil_div(17_086 * (1 << 74), 10_000) + 1
CASES = (
    Case(92, 73, 10, 2, (0, X, B2_92, 1 << 118), (73, 118), 91),
    Case(93, 15, 1, 3, (0, X, X, 1 << 75, 7 << 117), (74, 118, 188), 90),
    Case(94, 24, 1, 5, (0, X, X, X, 1 << 75, 1 << 119, 1 << 189), (75, 119, 189, 299, 474), 89),
    Case(95, 24, 1, 6, (0, X, X, X, X, 3 << 74, 7 << 117, TERM), (75, 119, 189, 299, 474, 751), 90),
    Case(96, 29, 1, 7, (0, X, X, X, X, X, 3 << 74, 7 << 117, TERM), (75, 120, 191, 303, 481, 763, 1210), 90),
)


def next_upper(current: int, kmax: int) -> int:
    return ceil_div((current + 1) * pow(3, kmax), 1 << kmax) - 1


def derived_caps(case: Case) -> tuple[int, ...]:
    current = case.window_num * X // case.window_den
    result = []
    for _ in range(case.depth):
        cap = (current + 1).bit_length() - 1
        result.append(cap)
        current = next_upper(current, cap)
    return tuple(result)


def suffix_exponent_lower(
    m: int, prefix_caps: tuple[int, ...], delta_upper: Fraction
) -> Fraction:
    remaining = K0 - sum(prefix_caps)
    suffix_length = m - len(prefix_caps)
    return Fraction(remaining, 1) / geometric_sum(delta_upper, suffix_length)


def stage_records(case: Case, delta_upper: Fraction) -> list[dict[str, object]]:
    records = []
    for n_index in range(2, case.depth + 2):
        target = case.extra[n_index]
        if target == X:
            records.append(
                {"n_index": n_index, "reason": "global_minimum", "target": str(target)}
            )
            continue
        exponent = suffix_exponent_lower(
            case.m, case.kcaps[: n_index - 1], delta_upper
        )
        witness = log2_upper_witness(target + 1, EXPONENT_DENOMINATOR)
        if exponent <= witness:
            raise AssertionError(f"m={case.m} n{n_index} stage bound failed")
        records.append(
            {
                "n_index": n_index,
                "reason": "suffix_growth",
                "target": str(target),
                "log2_target_upper": fraction_json(witness),
            }
        )
    return records


def generic_error_bound(
    m: int,
    k_min: int,
    minimum: Fraction,
    block_length: int,
    ln2_lower: Fraction,
) -> tuple[Fraction, int]:
    contribution = Fraction(3 * (m - block_length), 1) / minimum
    floors = []
    for length in range(1, block_length + 1):
        exponent = (
            Fraction(length * k_min, m)
            * (DELTA_COARSE - 1)
            / (DELTA_COARSE**length - 1)
        )
        floor = strict_floor(exponent)
        floors.append(floor)
        contribution += Fraction(3, (1 << min(floor, ERROR_EXPONENT_CAP)) - 1)
    return contribution / (3 * k_min * ln2_lower), min(floors)


def m92_error_bound(ln2_lower: Fraction) -> Fraction:
    contribution = (
        Fraction(30, 73 * X)
        + Fraction(3 * 10_000, 17_086 * (1 << 74))
        + Fraction(270, (1 << 117) - 1)
    )
    return contribution / (3 * K0 * ln2_lower)


def certify_m92_split_block(delta_upper: Fraction) -> int:
    first_exponent = Fraction(91 * K0, 92) / geometric_sum(delta_upper, 91)
    first_witness = log2_upper_witness(B2_92 + 1, 10_000)
    if first_exponent <= first_witness:
        raise AssertionError("m=92 distinguished block term bound failed")
    floors = [
        strict_floor(Fraction(length * K0, 92) / geometric_sum(delta_upper, length))
        for length in range(1, 91)
    ]
    if min(floors) < 117:
        raise AssertionError("m=92 remaining block term bound failed")
    return min(floors)


def farey_record(
    pair: tuple[Fraction, Fraction], error: Fraction, expected: int
) -> dict[str, object]:
    left, right = pair
    determinant = left.numerator * right.denominator - right.numerator * left.denominator
    denominator_sum = left.denominator + right.denominator
    if determinant != -1 or denominator_sum != expected:
        raise AssertionError("invalid Farey pair")
    return {
        "left": fraction_json(left),
        "right": fraction_json(right),
        "determinant": str(determinant),
        "denominator_sum": str(denominator_sum),
        "error_upper": fraction_json(error),
    }


def prefix_gate_record(
    delta_lower: Fraction,
    delta_upper: Fraction,
    ln2_lower: Fraction,
    checked_through: int,
) -> dict[str, object]:
    worst_u = None
    minimum_margin = None
    for u in range(1, checked_through + 1):
        lower_floor = (u * delta_lower).numerator // (u * delta_lower).denominator
        upper_floor = (u * delta_upper).numerator // (u * delta_upper).denominator
        if lower_floor != upper_floor:
            raise AssertionError(f"delta interval does not decide floor at u={u}")
        positive_surplus_lower = lower_floor + 1 - u * delta_upper
        threshold_upper = Fraction(u, 3 * X) / ln2_lower
        margin = positive_surplus_lower - threshold_upper
        if margin <= 0:
            raise AssertionError(f"prefix gate fails at u={u}")
        if minimum_margin is None or margin < minimum_margin:
            worst_u = u
            minimum_margin = margin
    assert worst_u is not None and minimum_margin is not None
    return {
        "checked_u_min": 1,
        "checked_u_max": checked_through,
        "worst_u": worst_u,
        "minimum_margin": fraction_json(minimum_margin),
    }


def generate_case(
    case: Case,
    intervals: dict[str, tuple[Fraction, Fraction]],
    common: dict[str, object],
) -> dict[str, object]:
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower = intervals["ln2"][0]
    required_caps = derived_caps(case)
    if any(actual < required for actual, required in zip(case.kcaps, required_caps)):
        raise AssertionError(f"m={case.m} encoded cap is too small")

    if case.m == 92:
        final_error = m92_error_bound(ln2_lower)
        final_kind = "m92_split_block"
        block_min_floor = certify_m92_split_block(delta_upper)
    else:
        final_error, block_min_floor = generic_error_bound(
            case.m,
            K0,
            Fraction(case.window_num * X, case.window_den),
            case.final_s,
            ln2_lower,
        )
        final_kind = "generic_suffix_block"

    if not (FINAL_FAREY[0] < delta_lower):
        raise AssertionError("final lower Farey containment failed")
    if not (delta_upper + final_error < FINAL_FAREY[1]):
        raise AssertionError(f"m={case.m} final upper Farey containment failed")

    simons_upper = Fraction(924 * case.m, 625) * DELTA_COARSE**case.m
    if simons_upper >= Q:
        raise AssertionError(f"m={case.m} Simons-de Weger contradiction failed")

    return {
        "schema": "collatz-reduction-certificate-v1",
        "case": case.m,
        "common": common,
        "finite_window": {
            "minimum": str(X),
            "maximum_numerator": case.window_num,
            "maximum_denominator": case.window_den,
            "k1_max": case.kcaps[0],
            "depth": case.depth,
        },
        "caps": {
            "encoded": list(case.kcaps),
            "derived_required": list(required_caps),
        },
        "stage_bounds": stage_records(case, delta_upper),
        "final_lift": {
            "kind": final_kind,
            "block_length": case.final_s,
            "block_minimum_exponent_floor": block_min_floor,
            "minimum_numerator": case.window_num,
            "minimum_denominator": case.window_den,
            "farey": farey_record(FINAL_FAREY, final_error, Q),
        },
        "simons_de_weger": {
            "coefficient": fraction_json(Fraction(924, 625)),
            "delta_upper": fraction_json(DELTA_COARSE),
            "upper_bound": fraction_json(simons_upper),
            "contradiction_threshold": str(Q),
        },
        "result": "CERTIFIED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="certificates/reductions")
    parser.add_argument("--source", default="src/m96/affine_ladder_prefix.cpp")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_file():
        raise SystemExit(f"source file does not exist: {source}")

    intervals = logarithm_intervals(LOG_TERMS, LOG_BITS)
    delta_lower, delta_upper = intervals["delta"]
    ln2_lower = intervals["ln2"][0]
    initial_error, initial_floor = generic_error_bound(
        96, HERCHER_K, Fraction(X), 88, ln2_lower
    )
    if not (FIRST_FAREY[0] < delta_lower):
        raise AssertionError("initial lower Farey containment failed")
    if not (delta_upper + initial_error < FIRST_FAREY[1]):
        raise AssertionError("initial upper Farey containment failed")

    maximum_prefix = max(sum(case.kcaps) for case in CASES)
    common = {
        "X": str(X),
        "hercher_K_strict_lower": str(HERCHER_K),
        "K0": str(K0),
        "Q": str(Q),
        "engine_source": args.source,
        "engine_source_sha256": sha256_file(source),
        "logarithms": {
            "terms": LOG_TERMS,
            "dyadic_bits": LOG_BITS,
            **{
                name: {"lower": fraction_json(bounds[0]), "upper": fraction_json(bounds[1])}
                for name, bounds in intervals.items()
            },
        },
        "initial_lift": {
            "m_worst": 96,
            "block_length": 88,
            "minimum_exponent_floor": initial_floor,
            "farey": farey_record(FIRST_FAREY, initial_error, K0),
        },
        "prefix_gate": prefix_gate_record(
            delta_lower, delta_upper, ln2_lower, maximum_prefix
        ),
    }

    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        path = output / f"m{case.m}_reduction.json"
        path.write_bytes(canonical_json_bytes(generate_case(case, intervals, common)))
        print(path)


if __name__ == "__main__":
    main()
