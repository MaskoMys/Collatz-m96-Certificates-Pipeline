#!/usr/bin/env python3
"""Verify exact reductions and derive every v1 search configuration field."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import (
    config_id,
    load,
    parse_nat,
    require_exact_keys,
    require_sha256,
    sha256_file,
    strict_loads,
)


CASES = range(92, 97)
CONFIG_KEYS = {
    "schema",
    "m",
    "X",
    "window",
    "depth",
    "k1_range",
    "k_caps",
    "stage_minima",
    "alpha_bracket",
    "first_positive_surplus",
    "math_certificate_sha256",
}


def legacy_load(path: Path) -> dict[str, Any]:
    value = strict_loads(path.read_bytes(), require_canonical=False)
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def expected_config(cert: dict[str, Any], math_hash: str, surplus: str) -> dict[str, Any]:
    common = cert["common"]
    window = cert["finite_window"]
    delta = common["logarithms"]["delta"]
    depth = window["depth"]
    return {
        "schema": "collatz.case-config.v1",
        "m": str(cert["case"]),
        "X": common["X"],
        "window": {
            "numerator": str(window["maximum_numerator"]),
            "denominator": str(window["maximum_denominator"]),
        },
        "depth": str(depth),
        "k1_range": {"min": "1", "max": str(window["k1_max"])},
        "k_caps": [str(value) for value in cert["caps"]["encoded"]],
        "stage_minima": [
            common["X"], *[record["target"] for record in cert["stage_bounds"]]
        ],
        "alpha_bracket": {
            "lower_num": delta["lower"]["numerator"],
            "lower_den": delta["lower"]["denominator"],
            "upper_num": delta["upper"]["numerator"],
            "upper_den": delta["upper"]["denominator"],
        },
        "first_positive_surplus": surplus,
        "math_certificate_sha256": math_hash,
    }


def expected_semantic_config(cert: dict[str, Any], surplus: str) -> dict[str, Any]:
    value = expected_config(cert, "", surplus)
    del value["math_certificate_sha256"]
    return value


def validate_shape(config: dict[str, Any], m: int) -> None:
    require_exact_keys(config, CONFIG_KEYS, f"m={m} config")
    if config["schema"] != "collatz.case-config.v1" or config["m"] != str(m):
        raise ValueError(f"m={m} config schema/case mismatch")
    depth = parse_nat(config["depth"], f"m={m}.depth", positive=True)
    parse_nat(config["X"], f"m={m}.X", positive=True)
    parse_nat(config["first_positive_surplus"], f"m={m}.surplus", positive=True)
    require_sha256(config["math_certificate_sha256"], f"m={m}.math hash")
    if len(config["k_caps"]) != depth or len(config["stage_minima"]) != depth + 1:
        raise ValueError(f"m={m} config dimensions mismatch")
    for index, value in enumerate(config["k_caps"]):
        parse_nat(value, f"m={m}.k_caps[{index}]", positive=True)
    for index, value in enumerate(config["stage_minima"]):
        parse_nat(value, f"m={m}.stage_minima[{index}]", positive=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analytic", default="certificates/analytic/m92_96_reductions.json")
    parser.add_argument("--configs", default="certificates/config")
    parser.add_argument("--reductions", default="certificates/reductions")
    args = parser.parse_args()

    subprocess.run(
        [sys.executable, "scripts/verify_reduction_certificates.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    analytic_path = ROOT / args.analytic
    analytic = load(analytic_path)
    require_exact_keys(analytic, {"schema", "case_certificates"}, "analytic index")
    if analytic["schema"] != "collatz.mathematical-reductions.v1":
        raise ValueError("analytic index schema mismatch")
    records = analytic["case_certificates"]
    if not isinstance(records, list) or len(records) != 5:
        raise ValueError("analytic index must contain five cases")

    reductions = ROOT / args.reductions
    frontier = legacy_load(ROOT / "certificates/frontier/frontier_summary.json")
    surplus = frontier["minimum"]
    expected_records = []
    certificates = {}
    for m in CASES:
        path = reductions / f"m{m}_reduction.json"
        certificates[m] = legacy_load(path)
        expected_records.append(
            {
                "case": str(m),
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
                "search_config": expected_semantic_config(
                    certificates[m], surplus
                ),
            }
        )
    if records != expected_records:
        raise ValueError("analytic index does not match verified reduction files")

    math_hash = sha256_file(analytic_path)
    identifiers = {}
    for m in CASES:
        config = load(ROOT / args.configs / f"case_m{m}.json")
        validate_shape(config, m)
        expected = expected_config(certificates[m], math_hash, surplus)
        if config != expected:
            raise ValueError(f"m={m} config is not derived from the exact reduction")
        identifiers[str(m)] = config_id(config)

    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "analytic_sha256": math_hash,
                "config_ids": identifiers,
                "verified_cases": [str(m) for m in CASES],
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
