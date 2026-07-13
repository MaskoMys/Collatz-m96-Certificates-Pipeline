#!/usr/bin/env python3
"""Aggregate independently verified unit pairs into branch and case records."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import (
    atomic_write,
    config_id,
    load,
    object_id,
    sha256_file,
)
from verifiers.verify_work_unit_result import verify_result


CASES = range(92, 97)


def branch_certificate(
    m: int,
    branch_dir: Path,
    config_path: Path,
    prover_dir: Path,
    verifier_dir: Path,
    prover_binary: Path,
    verifier_binary: Path,
) -> dict[str, Any]:
    config = load(config_path)
    partition_path = branch_dir / "partition.json"
    partition = load(partition_path)
    pairs = []
    total_inputs = 0
    prover_hits = 0
    verifier_hits = 0
    for leaf in partition["leaves"]:
        identifier = leaf["unit_id"]
        unit_path = branch_dir / "units" / f"{identifier}.json"
        prover = verify_result(
            config_path,
            unit_path,
            prover_dir / f"{identifier}.json",
            expected_engine="cpp-gmp-prover",
            binary_path=prover_binary,
        )
        verifier = verify_result(
            config_path,
            unit_path,
            verifier_dir / f"{identifier}.json",
            expected_engine="independent-rust-verifier",
            binary_path=verifier_binary,
        )
        if (
            prover["outcome"] != "NO_SURVIVOR"
            or verifier["outcome"] != "NO_SURVIVOR"
            or prover["hits"] != "0"
            or verifier["hits"] != "0"
        ):
            raise ValueError(f"nonzero or unresolved result for unit {identifier}")
        if prover["semantic_parameters"] != verifier["semantic_parameters"]:
            raise ValueError(f"semantic parameter disagreement for unit {identifier}")
        if prover["counters"] != verifier["counters"]:
            raise ValueError(f"cross-engine counter disagreement for unit {identifier}")
        total_inputs += int(prover["counters"]["represented_input_count"])
        prover_hits += int(prover["hits"])
        verifier_hits += int(verifier["hits"])
        pairs.append(
            {
                "unit_id": identifier,
                "prover_result_id": prover["result_id"],
                "verifier_result_id": verifier["result_id"],
            }
        )
    if total_inputs != int(partition["root"]["count"]):
        raise ValueError(f"branch m={m},k1={partition['k1']} input-count mismatch")
    certificate = {
        "schema": "collatz.branch-certificate.v1",
        "m": str(m),
        "k1": partition["k1"],
        "config_id": config_id(config),
        "root": partition["root"],
        "partition_id": partition["partition_id"],
        "partition_sha256": sha256_file(partition_path),
        "units": pairs,
        "total_input_count": str(total_inputs),
        "prover_hits": str(prover_hits),
        "verifier_hits": str(verifier_hits),
        "unresolved": "0",
        "result": "NO_SURVIVOR",
    }
    certificate["branch_id"] = object_id("collatz.branch-certificate.v1", certificate)
    return certificate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="dist/search-v2/plan")
    parser.add_argument("--prover-results", default="dist/search-v2/results/prover")
    parser.add_argument("--verifier-results", default="dist/search-v2/results/verifier")
    parser.add_argument("--out", default="dist/search-v2/certificates")
    parser.add_argument("--prover-binary", default="build/collatz_prover")
    parser.add_argument("--verifier-binary", default="build/collatz_verify_unit")
    parser.add_argument("--case", action="append", type=int, choices=CASES)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    cases = sorted(set(args.case)) if args.case else list(CASES)
    plan = ROOT / args.plan
    prover_results = ROOT / args.prover_results
    verifier_results = ROOT / args.verifier_results
    output = ROOT / args.out
    if output.exists():
        if not args.replace:
            raise ValueError(f"output exists (use --replace): {output}")
        shutil.rmtree(output)
    total_units = 0
    total_branches = 0
    case_records = []
    for m in cases:
        config_path = ROOT / f"certificates/config/case_m{m}.json"
        config = load(config_path)
        branches = []
        for k1 in range(int(config["k1_range"]["min"]), int(config["k1_range"]["max"]) + 1):
            branch_dir = plan / f"m{m}" / f"k1_{k1:02d}"
            certificate = branch_certificate(
                m,
                branch_dir,
                config_path,
                prover_results,
                verifier_results,
                ROOT / args.prover_binary,
                ROOT / args.verifier_binary,
            )
            path = output / f"m{m}" / f"k1_{k1:02d}.json"
            atomic_write(path, certificate)
            total_units += len(certificate["units"])
            total_branches += 1
            branches.append(
                {
                    "k1": str(k1),
                    "branch_id": certificate["branch_id"],
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(path),
                }
            )
        case_certificate = {
            "schema": "collatz.case-search-certificate.v1",
            "m": str(m),
            "config_id": config_id(config),
            "branches": branches,
            "total_hits": "0",
            "unresolved": "0",
            "result": "NO_SURVIVOR",
        }
        case_certificate["case_id"] = object_id(
            "collatz.case-search-certificate.v1", case_certificate
        )
        case_path = output / f"m{m}" / "case_certificate.json"
        atomic_write(case_path, case_certificate)
        case_records.append(
            {
                "m": str(m),
                "case_id": case_certificate["case_id"],
                "path": case_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(case_path),
            }
        )
    global_certificate = {
        "schema": "collatz.global-search-certificate.v1",
        "analytic_sha256": sha256_file(
            ROOT / "certificates/analytic/m92_96_reductions.json"
        ),
        "frontier_sha256": sha256_file(
            ROOT / "certificates/frontier/frontier_summary.json"
        ),
        "cases": case_records,
        "total_branches": str(total_branches),
        "total_units": str(total_units),
        "total_hits": "0",
        "unresolved": "0",
        "result": "NO_M_CYCLE_92_TO_96" if cases == list(CASES) else "INCOMPLETE_CASE_SET",
    }
    global_certificate["global_id"] = object_id(
        "collatz.global-search-certificate.v1", global_certificate
    )
    atomic_write(output / "global_search_certificate.json", global_certificate)
    print(
        f"aggregated {len(case_records)} cases, {global_certificate['total_branches']} "
        f"branches and {total_units} units"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
