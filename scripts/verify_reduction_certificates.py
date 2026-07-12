#!/usr/bin/env python3
"""Independently verify the exact m=92..96 reduction certificates."""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

from exact_math import (
    canonical_json_bytes,
    ceil_div,
    dyadic_lower,
    dyadic_upper,
    fraction_json,
    geometric_sum,
    ln_interval,
    log2_upper_witness,
    parse_fraction,
    sha256_file,
    strict_floor,
)


X = 1 << 71
HERCHER_K = 77_600_000_000_000_000_000
K0 = 205_632_218_873_398_596_256
Q = 7_941_964_418_702_608_664_581
DELTA_COARSE = Fraction(317, 200)
COEFFICIENT = Fraction(924, 625)
LOG_TERMS = 192
LOG_BITS = 256
ERROR_EXPONENT_CAP = 200
EXPONENT_DENOMINATOR = 1000

FIRST_FAREY = (
    Fraction(202_780_263_237_295_321_099, 127_940_101_513_462_006_853),
    Fraction(123_139_092_617_126_647_266, 77_692_117_359_936_589_403),
)
FINAL_FAREY = (
    Fraction(12_261_796_429_850_908_150_604, 7_736_332_199_829_210_068_325),
    Fraction(325_919_355_854_421_968_365, 205_632_218_873_398_596_256),
)

TERM = ceil_div(93 * (1 << 189), 50)
B2_92 = ceil_div(17_086 * (1 << 74), 10_000) + 1
CASES = {
    92: {"window": (73, 10), "depth": 2, "extra": (0, X, B2_92, 1 << 118), "caps": (73, 118), "s": 91},
    93: {"window": (15, 1), "depth": 3, "extra": (0, X, X, 1 << 75, 7 << 117), "caps": (74, 118, 188), "s": 90},
    94: {"window": (24, 1), "depth": 5, "extra": (0, X, X, X, 1 << 75, 1 << 119, 1 << 189), "caps": (75, 119, 189, 299, 474), "s": 89},
    95: {"window": (24, 1), "depth": 6, "extra": (0, X, X, X, X, 3 << 74, 7 << 117, TERM), "caps": (75, 119, 189, 299, 474, 751), "s": 90},
    96: {"window": (29, 1), "depth": 7, "extra": (0, X, X, X, X, X, 3 << 74, 7 << 117, TERM), "caps": (75, 120, 191, 303, 481, 763, 1210), "s": 90},
}


def require_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise AssertionError(
            f"{label} keys mismatch missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )
    return value


def require_decimal(value: Any, expected: int, label: str) -> None:
    if not isinstance(value, str) or value != str(expected):
        raise AssertionError(f"{label} mismatch")


def require_fraction(value: Any, expected: Fraction, label: str) -> None:
    actual = parse_fraction(value)
    if actual != expected:
        raise AssertionError(f"{label} mismatch")


def logarithm_bounds(logs: dict[str, Any]) -> dict[str, tuple[Fraction, Fraction]]:
    require_keys(logs, {"terms", "dyadic_bits", "ln2", "ln3", "delta"}, "logarithms")
    if logs["terms"] != LOG_TERMS or logs["dyadic_bits"] != LOG_BITS:
        raise AssertionError("logarithm precision mismatch")

    raw2 = ln_interval(2, LOG_TERMS)
    raw3 = ln_interval(3, LOG_TERMS)
    expected2 = (dyadic_lower(raw2[0], LOG_BITS), dyadic_upper(raw2[1], LOG_BITS))
    expected3 = (dyadic_lower(raw3[0], LOG_BITS), dyadic_upper(raw3[1], LOG_BITS))
    ratio = (expected3[0] / expected2[1], expected3[1] / expected2[0])
    expected_delta = (
        dyadic_lower(ratio[0], LOG_BITS),
        dyadic_upper(ratio[1], LOG_BITS),
    )
    result = {"ln2": expected2, "ln3": expected3, "delta": expected_delta}
    for name, expected in result.items():
        block = require_keys(logs[name], {"lower", "upper"}, f"logarithms.{name}")
        require_fraction(block["lower"], expected[0], f"{name}.lower")
        require_fraction(block["upper"], expected[1], f"{name}.upper")
    if not expected_delta[1] < DELTA_COARSE:
        raise AssertionError("317/200 does not enclose delta from above")
    return result


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
        if floor <= 0:
            raise AssertionError("nonpositive suffix exponent")
        floors.append(floor)
        contribution += Fraction(3, (1 << min(floor, ERROR_EXPONENT_CAP)) - 1)
    return contribution / (3 * k_min * ln2_lower), min(floors)


def verify_farey(
    block: dict[str, Any],
    expected_pair: tuple[Fraction, Fraction],
    error: Fraction,
    threshold: int,
    delta: tuple[Fraction, Fraction],
    label: str,
) -> None:
    require_keys(
        block,
        {"left", "right", "determinant", "denominator_sum", "error_upper"},
        label,
    )
    left, right = expected_pair
    require_fraction(block["left"], left, f"{label}.left")
    require_fraction(block["right"], right, f"{label}.right")
    require_fraction(block["error_upper"], error, f"{label}.error_upper")
    require_decimal(block["determinant"], -1, f"{label}.determinant")
    require_decimal(block["denominator_sum"], threshold, f"{label}.denominator_sum")
    determinant = left.numerator * right.denominator - right.numerator * left.denominator
    if determinant != -1 or left.denominator + right.denominator != threshold:
        raise AssertionError(f"{label} is not the claimed adjacent Farey pair")
    if not left < delta[0] or not delta[1] + error < right:
        raise AssertionError(f"{label} does not contain the full rational interval")


def verify_prefix_gate(
    block: dict[str, Any],
    delta: tuple[Fraction, Fraction],
    ln2_lower: Fraction,
) -> None:
    require_keys(
        block,
        {"checked_u_min", "checked_u_max", "worst_u", "minimum_margin"},
        "prefix_gate",
    )
    if block["checked_u_min"] != 1 or block["checked_u_max"] != 3143:
        raise AssertionError("prefix gate range mismatch")
    minimum = None
    worst = None
    for u in range(1, 3144):
        lo_value = u * delta[0]
        hi_value = u * delta[1]
        lo_floor = lo_value.numerator // lo_value.denominator
        hi_floor = hi_value.numerator // hi_value.denominator
        if lo_floor != hi_floor:
            raise AssertionError(f"floor(log2(3)*{u}) is not decided")
        surplus_lower = lo_floor + 1 - hi_value
        admissible_upper = Fraction(u, 3 * X) / ln2_lower
        margin = surplus_lower - admissible_upper
        if margin <= 0:
            raise AssertionError(f"positive-surplus gate fails at u={u}")
        if minimum is None or margin < minimum:
            minimum = margin
            worst = u
    if block["worst_u"] != worst:
        raise AssertionError("prefix gate worst_u mismatch")
    require_fraction(block["minimum_margin"], minimum, "prefix_gate.minimum_margin")


def verify_common(
    common: dict[str, Any], source: Path
) -> dict[str, tuple[Fraction, Fraction]]:
    require_keys(
        common,
        {
            "X",
            "hercher_K_strict_lower",
            "K0",
            "Q",
            "engine_source",
            "engine_source_sha256",
            "logarithms",
            "initial_lift",
            "prefix_gate",
        },
        "common",
    )
    require_decimal(common["X"], X, "common.X")
    require_decimal(common["hercher_K_strict_lower"], HERCHER_K, "common.Hercher K")
    require_decimal(common["K0"], K0, "common.K0")
    require_decimal(common["Q"], Q, "common.Q")
    if common["engine_source"] != "src/m96/affine_ladder_prefix.cpp":
        raise AssertionError("engine source path mismatch")
    if common["engine_source_sha256"] != sha256_file(source):
        raise AssertionError("engine source hash mismatch")

    intervals = logarithm_bounds(common["logarithms"])
    initial = require_keys(
        common["initial_lift"],
        {"m_worst", "block_length", "minimum_exponent_floor", "farey"},
        "initial_lift",
    )
    if initial["m_worst"] != 96 or initial["block_length"] != 88:
        raise AssertionError("initial lift configuration mismatch")
    initial_error, minimum_floor = generic_error_bound(
        96, HERCHER_K, Fraction(X), 88, intervals["ln2"][0]
    )
    if initial["minimum_exponent_floor"] != minimum_floor:
        raise AssertionError("initial lift exponent floor mismatch")
    verify_farey(
        initial["farey"], FIRST_FAREY, initial_error, K0, intervals["delta"], "initial_lift.farey"
    )
    verify_prefix_gate(common["prefix_gate"], intervals["delta"], intervals["ln2"][0])
    return intervals


def next_upper(current: int, kmax: int) -> int:
    return ceil_div((current + 1) * pow(3, kmax), 1 << kmax) - 1


def required_caps(case: dict[str, Any]) -> tuple[int, ...]:
    numerator, denominator = case["window"]
    current = numerator * X // denominator
    caps = []
    for _ in range(case["depth"]):
        cap = (current + 1).bit_length() - 1
        caps.append(cap)
        current = next_upper(current, cap)
    return tuple(caps)


def suffix_exponent(
    m: int, prefix_caps: tuple[int, ...], delta_upper: Fraction
) -> Fraction:
    return Fraction(K0 - sum(prefix_caps), 1) / geometric_sum(
        delta_upper, m - len(prefix_caps)
    )


def verify_stages(
    records: Any, m: int, case: dict[str, Any], delta_upper: Fraction
) -> None:
    if not isinstance(records, list) or len(records) != case["depth"]:
        raise AssertionError(f"m={m} stage record count mismatch")
    for n_index, record in enumerate(records, 2):
        target = case["extra"][n_index]
        if target == X:
            require_keys(record, {"n_index", "reason", "target"}, f"m={m}.stage{n_index}")
            if record != {"n_index": n_index, "reason": "global_minimum", "target": str(X)}:
                raise AssertionError(f"m={m} global minimum stage mismatch")
            continue
        require_keys(
            record,
            {"n_index", "reason", "target", "log2_target_upper"},
            f"m={m}.stage{n_index}",
        )
        if record["n_index"] != n_index or record["reason"] != "suffix_growth":
            raise AssertionError(f"m={m} stage identity mismatch")
        require_decimal(record["target"], target, f"m={m}.stage{n_index}.target")
        witness = log2_upper_witness(target + 1, EXPONENT_DENOMINATOR)
        require_fraction(
            record["log2_target_upper"], witness, f"m={m}.stage{n_index}.witness"
        )
        exponent = suffix_exponent(m, case["caps"][: n_index - 1], delta_upper)
        if exponent <= witness:
            raise AssertionError(f"m={m} stage n{n_index} implication failed")
        if (1 << witness.numerator) <= pow(target + 1, witness.denominator):
            raise AssertionError(f"m={m} stage n{n_index} witness is not an upper log bound")


def m92_error(ln2_lower: Fraction) -> Fraction:
    contribution = (
        Fraction(30, 73 * X)
        + Fraction(30_000, 17_086 * (1 << 74))
        + Fraction(270, (1 << 117) - 1)
    )
    return contribution / (3 * K0 * ln2_lower)


def verify_m92_split_block(delta_upper: Fraction) -> None:
    first_exponent = Fraction(91 * K0, 92) / geometric_sum(delta_upper, 91)
    first_witness = log2_upper_witness(B2_92 + 1, 10_000)
    if first_exponent <= first_witness:
        raise AssertionError("m=92 distinguished block term bound failed")
    minimum_floor = min(
        strict_floor(Fraction(length * K0, 92) / geometric_sum(delta_upper, length))
        for length in range(1, 91)
    )
    if minimum_floor < 117:
        raise AssertionError("m=92 remaining block exponent bound failed")


def verify_case(path: Path, source: Path) -> tuple[int, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical_json_bytes(value):
        raise AssertionError(f"{path}: certificate JSON is not canonical")
    cert = require_keys(
        value,
        {
            "schema",
            "case",
            "common",
            "finite_window",
            "caps",
            "stage_bounds",
            "final_lift",
            "simons_de_weger",
            "result",
        },
        str(path),
    )
    if cert["schema"] != "collatz-reduction-certificate-v1" or cert["result"] != "CERTIFIED":
        raise AssertionError(f"{path}: schema or result mismatch")
    m = cert["case"]
    if type(m) is not int or m not in CASES:
        raise AssertionError(f"{path}: unsupported case")
    case = CASES[m]
    intervals = verify_common(cert["common"], source)

    window = require_keys(
        cert["finite_window"],
        {"minimum", "maximum_numerator", "maximum_denominator", "k1_max", "depth"},
        f"m={m}.finite_window",
    )
    numerator, denominator = case["window"]
    expected_window = {
        "minimum": str(X),
        "maximum_numerator": numerator,
        "maximum_denominator": denominator,
        "k1_max": case["caps"][0],
        "depth": case["depth"],
    }
    if window != expected_window:
        raise AssertionError(f"m={m} finite window mismatch")
    upper = numerator * X // denominator
    if upper + 1 >= 1 << (case["caps"][0] + 1):
        raise AssertionError(f"m={m} k1 cover is incomplete")

    caps = require_keys(cert["caps"], {"encoded", "derived_required"}, f"m={m}.caps")
    derived = required_caps(case)
    if caps["encoded"] != list(case["caps"]) or caps["derived_required"] != list(derived):
        raise AssertionError(f"m={m} cap table mismatch")
    if any(encoded < needed for encoded, needed in zip(case["caps"], derived)):
        raise AssertionError(f"m={m} encoded cap is not conservative")
    verify_stages(cert["stage_bounds"], m, case, intervals["delta"][1])

    final = require_keys(
        cert["final_lift"],
        {
            "kind",
            "block_length",
            "block_minimum_exponent_floor",
            "minimum_numerator",
            "minimum_denominator",
            "farey",
        },
        f"m={m}.final_lift",
    )
    if final["block_length"] != case["s"]:
        raise AssertionError(f"m={m} final block length mismatch")
    if final["minimum_numerator"] != numerator or final["minimum_denominator"] != denominator:
        raise AssertionError(f"m={m} final minimum mismatch")
    if m == 92:
        if final["kind"] != "m92_split_block" or final["block_minimum_exponent_floor"] != 117:
            raise AssertionError("m=92 split block metadata mismatch")
        verify_m92_split_block(intervals["delta"][1])
        error = m92_error(intervals["ln2"][0])
    else:
        if final["kind"] != "generic_suffix_block":
            raise AssertionError(f"m={m} final lift kind mismatch")
        error, minimum_floor = generic_error_bound(
            m,
            K0,
            Fraction(numerator * X, denominator),
            case["s"],
            intervals["ln2"][0],
        )
        if final["block_minimum_exponent_floor"] != minimum_floor:
            raise AssertionError(f"m={m} final exponent floor mismatch")
    verify_farey(final["farey"], FINAL_FAREY, error, Q, intervals["delta"], f"m={m}.final_farey")

    simons = require_keys(
        cert["simons_de_weger"],
        {"coefficient", "delta_upper", "upper_bound", "contradiction_threshold"},
        f"m={m}.simons_de_weger",
    )
    upper_bound = COEFFICIENT * m * DELTA_COARSE**m
    require_fraction(simons["coefficient"], COEFFICIENT, f"m={m}.coefficient")
    require_fraction(simons["delta_upper"], DELTA_COARSE, f"m={m}.delta_upper")
    require_fraction(simons["upper_bound"], upper_bound, f"m={m}.upper_bound")
    require_decimal(simons["contradiction_threshold"], Q, f"m={m}.threshold")
    if upper_bound >= Q:
        raise AssertionError(f"m={m} final contradiction failed")
    return m, sha256_file(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificates", default="certificates/reductions")
    parser.add_argument("--source", default="src/m96/affine_ladder_prefix.cpp")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.is_file():
        raise AssertionError(f"source file missing: {source}")
    directory = Path(args.certificates)
    expected = {f"m{m}_reduction.json" for m in CASES}
    actual = {path.name for path in directory.iterdir() if path.is_file() and not path.name.startswith(".")}
    if actual != expected:
        raise AssertionError(
            f"reduction certificate set mismatch missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )
    accepted = [verify_case(directory / name, source) for name in sorted(expected)]
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "verified_cases": [m for m, _ in accepted],
                "certificate_sha256": {str(m): digest for m, digest in accepted},
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
