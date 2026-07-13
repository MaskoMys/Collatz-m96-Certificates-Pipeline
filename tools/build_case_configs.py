#!/usr/bin/env python3
"""Build canonical search configurations from verified exact reductions."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import atomic_write, config_id, sha256_file, strict_loads


CASES = range(92, 97)


def load_legacy_json(path: Path) -> dict[str, Any]:
    value = strict_loads(path.read_bytes(), require_canonical=False)
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def semantic_config(
    certificate: dict[str, Any], first_positive_surplus: str
) -> dict[str, Any]:
    m = int(certificate["case"])
    common = certificate["common"]
    window = certificate["finite_window"]
    delta = common["logarithms"]["delta"]
    stages = certificate["stage_bounds"]
    depth = int(window["depth"])
    if [record["n_index"] for record in stages] != list(range(2, depth + 2)):
        raise ValueError(f"m={m} stage records are not consecutive")
    stage_minima = [common["X"], *[record["target"] for record in stages]]
    value = {
        "schema": "collatz.case-config.v1",
        "m": str(m),
        "X": common["X"],
        "window": {
            "numerator": str(window["maximum_numerator"]),
            "denominator": str(window["maximum_denominator"]),
        },
        "depth": str(depth),
        "k1_range": {"min": "1", "max": str(window["k1_max"])},
        "k_caps": [str(item) for item in certificate["caps"]["encoded"]],
        "stage_minima": stage_minima,
        "alpha_bracket": {
            "lower_num": delta["lower"]["numerator"],
            "lower_den": delta["lower"]["denominator"],
            "upper_num": delta["upper"]["numerator"],
            "upper_den": delta["upper"]["denominator"],
        },
        "first_positive_surplus": first_positive_surplus,
    }
    if len(value["k_caps"]) != depth or len(stage_minima) != depth + 1:
        raise ValueError(f"m={m} configuration dimensions are inconsistent")
    return value


def build_analytic_index(
    reductions: Path, first_positive_surplus: str
) -> dict[str, Any]:
    records = []
    for m in CASES:
        path = reductions / f"m{m}_reduction.json"
        certificate = load_legacy_json(path)
        if certificate.get("case") != m or certificate.get("result") != "CERTIFIED":
            raise ValueError(f"unaccepted reduction certificate for m={m}")
        records.append(
            {
                "case": str(m),
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
                "search_config": semantic_config(
                    certificate, first_positive_surplus
                ),
            }
        )
    return {
        "schema": "collatz.mathematical-reductions.v1",
        "case_certificates": records,
    }


def case_config(
    certificate: dict[str, Any], math_hash: str, first_positive_surplus: str
) -> dict[str, Any]:
    config = semantic_config(certificate, first_positive_surplus)
    config["math_certificate_sha256"] = math_hash
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reductions", default="certificates/reductions")
    parser.add_argument(
        "--analytic", default="certificates/analytic/m92_96_reductions.json"
    )
    parser.add_argument("--configs", default="certificates/config")
    args = parser.parse_args()

    subprocess.run(
        [sys.executable, "scripts/verify_reduction_certificates.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    reductions = (ROOT / args.reductions).resolve()
    analytic_path = (ROOT / args.analytic).resolve()
    config_dir = (ROOT / args.configs).resolve()
    frontier = load_legacy_json(ROOT / "certificates/frontier/frontier_summary.json")
    first_positive_surplus = frontier["minimum"]
    analytic = build_analytic_index(reductions, first_positive_surplus)
    atomic_write(analytic_path, analytic)
    math_hash = sha256_file(analytic_path)

    identifiers = {}
    for m in CASES:
        reduction = load_legacy_json(reductions / f"m{m}_reduction.json")
        config = case_config(reduction, math_hash, first_positive_surplus)
        atomic_write(config_dir / f"case_m{m}.json", config)
        identifiers[str(m)] = config_id(config)

    print(f"wrote analytic index {analytic_path.relative_to(ROOT)} ({math_hash})")
    for m, identifier in identifiers.items():
        print(f"m={m} config_id={identifier}")


if __name__ == "__main__":
    main()
