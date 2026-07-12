#!/usr/bin/env python3
"""Generate the prefix-free height-independent descent-cover certificates."""

from __future__ import annotations

import argparse
from pathlib import Path

from exact_math import canonical_json_bytes, sha256_file


PRIMITIVE_BASES = (3, 7, 11, 15)


def valuation2(value: int) -> int:
    return (value & -value).bit_length() - 1


def first_descent_cell(r: int, bits: int, max_steps: int):
    current = r
    valuation_sum = 0
    remaining_bits = bits
    for steps in range(1, max_steps + 1):
        numerator = 3 * current + 1
        valuation = valuation2(numerator)
        if valuation >= remaining_bits:
            return None
        valuation_sum += valuation
        current = numerator >> valuation
        remaining_bits = bits - valuation_sum
        if current < r and pow(3, steps) <= 1 << valuation_sum:
            return (r, bits, steps, valuation_sum, current)
    return None


def build_cover(base: int, base_bits: int, depth: int, max_steps: int):
    covered = []
    residual = []
    stack = [(base, base_bits)]
    while stack:
        r, bits = stack.pop()
        cell = first_descent_cell(r, bits, max_steps)
        if cell is not None:
            covered.append(cell)
        elif bits == depth:
            residual.append(r)
        else:
            stack.append((r + (1 << bits), bits + 1))
            stack.append((r, bits + 1))
    covered.sort()
    residual.sort()
    return covered, residual


def write_cover(output: Path, name: str, covered, residual) -> dict[str, object]:
    covered_path = output / f"{name}_descent.csv"
    residual_path = output / f"{name}_residual.csv"
    covered_path.write_text(
        "r,n,s,S,c\n" + "".join(
            f"{r},{bits},{steps},{total},{current}\n"
            for r, bits, steps, total, current in covered
        ),
        encoding="ascii",
    )
    residual_path.write_text(
        "r\n" + "".join(f"{r}\n" for r in residual), encoding="ascii"
    )
    return {
        "descent_cells": len(covered),
        "residual_classes": len(residual),
        "descent_sha256": sha256_file(covered_path),
        "residual_sha256": sha256_file(residual_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="certificates/descent")
    args = parser.parse_args()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)

    primitive = []
    combined_covered = 0
    combined_residual = 0
    for base in PRIMITIVE_BASES:
        covered, residual = build_cover(base, 4, 24, 14)
        covered_units = sum(1 << (24 - cell[1]) for cell in covered)
        details = write_cover(output, f"primitive_{base:02d}", covered, residual)
        details.update(
            {
                "base": base,
                "base_bits": 4,
                "depth": 24,
                "covered_units": covered_units,
                "total_units": 1 << 20,
                "max_steps": max(cell[2] for cell in covered),
                "max_valuation_sum": max(cell[3] for cell in covered),
            }
        )
        primitive.append(details)
        combined_covered += covered_units
        combined_residual += len(residual)

    endpoint_covered, endpoint_residual = build_cover(27, 5, 28, 28)
    endpoint_units = sum(1 << (28 - cell[1]) for cell in endpoint_covered)
    endpoint = write_cover(output, "endpoint_m2", endpoint_covered, endpoint_residual)
    endpoint.update(
        {
            "base": 27,
            "base_bits": 5,
            "depth": 28,
            "covered_units": endpoint_units,
            "total_units": 1 << 23,
            "max_steps": max(cell[2] for cell in endpoint_covered),
            "max_valuation_sum": max(cell[3] for cell in endpoint_covered),
        }
    )

    summary = {
        "schema": "collatz-descent-covers-v1",
        "primitive": primitive,
        "primitive_combined": {
            "covered_numerator": combined_covered // 2,
            "covered_denominator": 1 << 21,
            "residual_mod_2_pow_24": combined_residual,
        },
        "endpoint_m2": endpoint,
        "result": "CERTIFIED",
    }
    summary_path = output / "descent_summary.json"
    summary_path.write_bytes(canonical_json_bytes(summary))
    print(summary_path)


if __name__ == "__main__":
    main()
