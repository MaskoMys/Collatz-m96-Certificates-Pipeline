#!/usr/bin/env python3
"""Independently verify descent cells and their prefix-free residue tilings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from exact_math import canonical_json_bytes, sha256_file


CONFIGURATIONS = (
    ("primitive_03", 3, 4, 24, 20, 1, 1_048_575),
    ("primitive_07", 7, 4, 24, 12_889, 66_815, 981_761),
    ("primitive_11", 11, 4, 24, 12_889, 66_815, 981_761),
    ("primitive_15", 15, 4, 24, 39_397, 234_067, 814_509),
    ("endpoint_m2", 27, 5, 28, 173_892, 716_705, 7_671_903),
)


def valuation2(value: int) -> int:
    return (value & -value).bit_length() - 1


def canonical_integer(value: str, label: str) -> int:
    if not value.isascii() or not value.isdigit() or str(int(value)) != value:
        raise AssertionError(f"noncanonical integer in {label}: {value!r}")
    return int(value)


def read_descent(path: Path):
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or lines[0] != "r,n,s,S,c":
        raise AssertionError(f"{path}: descent header mismatch")
    rows = []
    for lineno, line in enumerate(lines[1:], 2):
        fields = line.split(",")
        if len(fields) != 5:
            raise AssertionError(f"{path}:{lineno}: malformed row")
        rows.append(tuple(canonical_integer(field, f"{path}:{lineno}") for field in fields))
    if rows != sorted(set(rows)):
        raise AssertionError(f"{path}: rows are not sorted and unique")
    return rows


def read_residual(path: Path):
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or lines[0] != "r":
        raise AssertionError(f"{path}: residual header mismatch")
    rows = [canonical_integer(line, f"{path}:{lineno}") for lineno, line in enumerate(lines[1:], 2)]
    if rows != sorted(set(rows)):
        raise AssertionError(f"{path}: residual rows are not sorted and unique")
    return rows


def verify_cell(cell, base: int, base_bits: int, depth: int) -> None:
    r, bits, steps, expected_sum, expected_current = cell
    if not (base_bits <= bits <= depth) or r <= 0 or r >= 1 << bits or r % (1 << base_bits) != base:
        raise AssertionError(f"invalid descent cylinder r={r}, n={bits}")
    current = r
    valuation_sum = 0
    for _ in range(steps):
        numerator = 3 * current + 1
        valuation = valuation2(numerator)
        if valuation >= bits - valuation_sum:
            raise AssertionError(f"unforced valuation in descent cell r={r}, n={bits}")
        valuation_sum += valuation
        current = numerator >> valuation
    if valuation_sum != expected_sum or current != expected_current:
        raise AssertionError(f"affine descent data mismatch for r={r}, n={bits}")
    if current >= r or pow(3, steps) > 1 << valuation_sum:
        raise AssertionError(f"descent inequalities fail for r={r}, n={bits}")


def verify_tiling(covered, residual, base: int, base_bits: int, depth: int) -> int:
    unit_count = 1 << (depth - base_bits)
    seen = bytearray(unit_count)
    covered_units = 0
    leaves = [(r, bits, True) for r, bits, *_ in covered]
    leaves.extend((r, depth, False) for r in residual)
    for r, bits, is_covered in leaves:
        if r % (1 << base_bits) != base or r >= 1 << bits:
            raise AssertionError(f"leaf outside base cylinder r={r}, n={bits}")
        low_index = (r - base) >> base_bits
        stride = 1 << (bits - base_bits)
        descendants = 1 << (depth - bits)
        for lift in range(descendants):
            index = low_index + lift * stride
            if seen[index]:
                raise AssertionError(f"overlapping descent leaves at index {index}")
            seen[index] = 1
        if is_covered:
            covered_units += descendants
    if any(value != 1 for value in seen):
        raise AssertionError(f"residue cover for base {base} is incomplete")
    return covered_units


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificates", default="certificates/descent")
    args = parser.parse_args()
    directory = Path(args.certificates)
    expected_files = {"descent_summary.json"}
    for name, *_ in CONFIGURATIONS:
        expected_files.update({f"{name}_descent.csv", f"{name}_residual.csv"})
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise AssertionError("descent certificate file set mismatch")

    primitive = []
    primitive_covered = 0
    primitive_residual = 0
    endpoint = None
    for name, base, base_bits, depth, expected_cells, expected_residual, expected_units in CONFIGURATIONS:
        descent_path = directory / f"{name}_descent.csv"
        residual_path = directory / f"{name}_residual.csv"
        covered = read_descent(descent_path)
        residual = read_residual(residual_path)
        if len(covered) != expected_cells or len(residual) != expected_residual:
            raise AssertionError(f"{name}: certificate counts mismatch")
        for cell in covered:
            verify_cell(cell, base, base_bits, depth)
        covered_units = verify_tiling(covered, residual, base, base_bits, depth)
        if covered_units != expected_units:
            raise AssertionError(f"{name}: covered residue measure mismatch")
        details = {
            "descent_cells": len(covered),
            "residual_classes": len(residual),
            "descent_sha256": sha256_file(descent_path),
            "residual_sha256": sha256_file(residual_path),
            "base": base,
            "base_bits": base_bits,
            "depth": depth,
            "covered_units": covered_units,
            "total_units": 1 << (depth - base_bits),
            "max_steps": max(cell[2] for cell in covered),
            "max_valuation_sum": max(cell[3] for cell in covered),
        }
        if name.startswith("primitive"):
            primitive.append(details)
            primitive_covered += covered_units
            primitive_residual += len(residual)
        else:
            endpoint = details

    expected_summary = {
        "schema": "collatz-descent-covers-v1",
        "primitive": primitive,
        "primitive_combined": {
            "covered_numerator": primitive_covered // 2,
            "covered_denominator": 1 << 21,
            "residual_mod_2_pow_24": primitive_residual,
        },
        "endpoint_m2": endpoint,
        "result": "CERTIFIED",
    }
    summary_path = directory / "descent_summary.json"
    raw = summary_path.read_bytes()
    summary = json.loads(raw)
    if raw != canonical_json_bytes(summary) or summary != expected_summary:
        raise AssertionError("descent summary mismatch or noncanonical JSON")
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "primitive_descent_cells": sum(item[4] for item in CONFIGURATIONS[:4]),
                "primitive_residual_classes": primitive_residual,
                "endpoint_m2_descent_cells": CONFIGURATIONS[4][4],
                "endpoint_m2_residual_classes": CONFIGURATIONS[4][5],
                "summary_sha256": sha256_file(summary_path),
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
