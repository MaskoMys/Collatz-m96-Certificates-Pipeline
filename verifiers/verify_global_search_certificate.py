#!/usr/bin/env python3
"""Verify aggregate certificates from roots through both engine results."""

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
    object_id,
    parse_nat,
    require_relative_path,
    sha256_file,
)
from verifiers.verify_partition_manifest import verify_branch as verify_partition
from verifiers.verify_build_provenance import verify_provenance
from verifiers.verify_computation_provenance import verify_computation_provenance
from verifiers.verify_work_unit_result import verify_result


ALL_CASES = list(range(92, 97))


def identified(domain: str, value: dict[str, Any], key: str) -> bool:
    payload = dict(value)
    claimed = payload.pop(key, None)
    return claimed == object_id(domain, payload)


def verify_branch_certificate(
    m: int,
    k1: int,
    branch_path: Path,
    plan_branch: Path,
    config_path: Path,
    prover_results: Path,
    verifier_results: Path,
    prover_binary: Path,
    verifier_binary: Path,
) -> tuple[int, int]:
    certificate = load(branch_path)
    if not identified("collatz.branch-certificate.v1", certificate, "branch_id"):
        raise ValueError(f"m={m},k1={k1} branch ID mismatch")
    if (
        certificate.get("schema") != "collatz.branch-certificate.v1"
        or certificate.get("m") != str(m)
        or certificate.get("k1") != str(k1)
        or certificate.get("result") != "NO_SURVIVOR"
    ):
        raise ValueError(f"m={m},k1={k1} branch header mismatch")
    config = load(config_path)
    if certificate.get("config_id") != config_id(config):
        raise ValueError(f"m={m},k1={k1} config ID mismatch")
    verify_partition(config, plan_branch, k1)
    partition_path = plan_branch / "partition.json"
    partition = load(partition_path)
    if (
        certificate.get("root") != partition["root"]
        or certificate.get("partition_id") != partition["partition_id"]
        or certificate.get("partition_sha256") != sha256_file(partition_path)
    ):
        raise ValueError(f"m={m},k1={k1} partition reference mismatch")
    recorded_pairs = certificate.get("units")
    if not isinstance(recorded_pairs, list) or len(recorded_pairs) != len(partition["leaves"]):
        raise ValueError(f"m={m},k1={k1} unit-pair count mismatch")
    total_inputs = 0
    for leaf, pair in zip(partition["leaves"], recorded_pairs):
        identifier = leaf["unit_id"]
        if pair.get("unit_id") != identifier:
            raise ValueError(f"m={m},k1={k1} unit ordering mismatch")
        unit_path = plan_branch / "units" / f"{identifier}.json"
        prover = verify_result(
            config_path,
            unit_path,
            prover_results / f"{identifier}.json",
            expected_engine="cpp-gmp-prover",
            binary_path=prover_binary,
        )
        verifier = verify_result(
            config_path,
            unit_path,
            verifier_results / f"{identifier}.json",
            expected_engine="independent-rust-verifier",
            binary_path=verifier_binary,
        )
        if (
            pair.get("prover_result_id") != prover["result_id"]
            or pair.get("verifier_result_id") != verifier["result_id"]
        ):
            raise ValueError(f"m={m},k1={k1} result ID mismatch")
        if (
            prover["outcome"] != "NO_SURVIVOR"
            or verifier["outcome"] != "NO_SURVIVOR"
            or prover["hits"] != "0"
            or verifier["hits"] != "0"
            or prover["semantic_parameters"] != verifier["semantic_parameters"]
            or prover["counters"] != verifier["counters"]
        ):
            raise ValueError(f"m={m},k1={k1} cross-engine disagreement")
        total_inputs += int(prover["counters"]["represented_input_count"])
    if (
        certificate.get("total_input_count") != str(total_inputs)
        or total_inputs != int(partition["root"]["count"])
        or certificate.get("prover_hits") != "0"
        or certificate.get("verifier_hits") != "0"
        or certificate.get("unresolved") != "0"
    ):
        raise ValueError(f"m={m},k1={k1} branch totals mismatch")
    return len(recorded_pairs), total_inputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="dist/search-v2/plan")
    parser.add_argument("--prover-results", default="dist/search-v2/results/prover")
    parser.add_argument("--verifier-results", default="dist/search-v2/results/verifier")
    parser.add_argument("--certificates", default="dist/search-v2/certificates")
    parser.add_argument("--prover-binary", default="build/collatz_prover")
    parser.add_argument("--verifier-binary", default="build/collatz_verify_unit")
    parser.add_argument(
        "--build-provenance",
        default="release/build_provenance/authoritative_binaries.json",
    )
    parser.add_argument(
        "--computation-provenance", default="release/computation_provenance"
    )
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    subprocess.run(
        [sys.executable, "verifiers/verify_mathematical_reductions.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [sys.executable, "scripts/verify_frontier_certificate.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    certificate_dir = ROOT / args.certificates
    global_path = certificate_dir / "global_search_certificate.json"
    global_certificate = load(global_path)
    if not identified(
        "collatz.global-search-certificate.v1", global_certificate, "global_id"
    ):
        raise ValueError("global certificate ID mismatch")
    records = global_certificate.get("cases")
    if not isinstance(records, list):
        raise ValueError("global case records missing")
    selected = [parse_nat(record.get("m"), "global case", positive=True) for record in records]
    if selected != sorted(set(selected)) or any(m not in ALL_CASES for m in selected):
        raise ValueError("global case set is invalid")
    if not args.allow_incomplete and selected != ALL_CASES:
        raise ValueError("theorem certificate does not contain all five cases")
    expected_global_result = (
        "NO_M_CYCLE_92_TO_96" if selected == ALL_CASES else "INCOMPLETE_CASE_SET"
    )
    if global_certificate.get("result") != expected_global_result:
        raise ValueError("global result marker mismatch")
    if global_certificate.get("analytic_sha256") != sha256_file(
        ROOT / "certificates/analytic/m92_96_reductions.json"
    ):
        raise ValueError("global analytic hash mismatch")
    if global_certificate.get("frontier_sha256") != sha256_file(
        ROOT / "certificates/frontier/frontier_summary.json"
    ):
        raise ValueError("global frontier hash mismatch")

    provenance = None
    computation_units = None
    if selected == ALL_CASES:
        provenance = verify_provenance(ROOT / args.build_provenance)
        expected_binaries = {
            "cpp-gmp-prover": ROOT / args.prover_binary,
            "independent-rust-verifier": ROOT / args.verifier_binary,
        }
        for engine, binary in expected_binaries.items():
            if provenance[engine]["binary_sha256"] != sha256_file(binary):
                raise ValueError(f"{engine} is not the authoritative allowlisted binary")
        computation_units = verify_computation_provenance(
            ROOT / args.computation_provenance,
            ROOT / args.plan,
            ROOT / args.prover_results,
            ROOT / args.verifier_results,
            ROOT / args.build_provenance,
        )

    total_branches = 0
    total_units = 0
    expected_plan_json: set[Path] = set()
    expected_result_names: set[str] = set()
    expected_certificate_json: set[Path] = {global_path.resolve()}
    for m, record in zip(selected, records):
        relative = require_relative_path(record.get("path"), "case path")
        case_path = ROOT / relative
        expected_case_path = certificate_dir / f"m{m}" / "case_certificate.json"
        expected_certificate_json.add(expected_case_path.resolve())
        if case_path.resolve() != expected_case_path.resolve() or record.get("sha256") != sha256_file(case_path):
            raise ValueError(f"m={m} case path/hash mismatch")
        case_certificate = load(case_path)
        if (
            not identified(
                "collatz.case-search-certificate.v1", case_certificate, "case_id"
            )
            or record.get("case_id") != case_certificate["case_id"]
            or case_certificate.get("schema") != "collatz.case-search-certificate.v1"
            or case_certificate.get("m") != str(m)
            or case_certificate.get("result") != "NO_SURVIVOR"
            or case_certificate.get("total_hits") != "0"
            or case_certificate.get("unresolved") != "0"
        ):
            raise ValueError(f"m={m} case certificate mismatch")
        config_path = ROOT / f"certificates/config/case_m{m}.json"
        config = load(config_path)
        if case_certificate.get("config_id") != config_id(config):
            raise ValueError(f"m={m} case config mismatch")
        low = int(config["k1_range"]["min"])
        high = int(config["k1_range"]["max"])
        branches = case_certificate.get("branches")
        if not isinstance(branches, list) or [record.get("k1") for record in branches] != [
            str(k1) for k1 in range(low, high + 1)
        ]:
            raise ValueError(f"m={m} branch cover mismatch")
        for k1, branch_record in zip(range(low, high + 1), branches):
            relative = require_relative_path(branch_record.get("path"), "branch path")
            branch_path = ROOT / relative
            expected = certificate_dir / f"m{m}" / f"k1_{k1:02d}.json"
            expected_certificate_json.add(expected.resolve())
            if branch_path.resolve() != expected.resolve() or branch_record.get("sha256") != sha256_file(branch_path):
                raise ValueError(f"m={m},k1={k1} branch path/hash mismatch")
            branch = load(branch_path)
            if branch_record.get("branch_id") != branch.get("branch_id"):
                raise ValueError(f"m={m},k1={k1} branch reference mismatch")
            units, _ = verify_branch_certificate(
                m,
                k1,
                branch_path,
                ROOT / args.plan / f"m{m}" / f"k1_{k1:02d}",
                config_path,
                ROOT / args.prover_results,
                ROOT / args.verifier_results,
                ROOT / args.prover_binary,
                ROOT / args.verifier_binary,
            )
            plan_branch = ROOT / args.plan / f"m{m}" / f"k1_{k1:02d}"
            partition = load(plan_branch / "partition.json")
            expected_plan_json.add((plan_branch / "partition.json").resolve())
            for leaf in partition["leaves"]:
                expected_plan_json.add(
                    (plan_branch / "units" / f"{leaf['unit_id']}.json").resolve()
                )
                expected_result_names.add(f"{leaf['unit_id']}.json")
            total_branches += 1
            total_units += units
    if (
        global_certificate.get("total_branches") != str(total_branches)
        or global_certificate.get("total_units") != str(total_units)
        or global_certificate.get("total_hits") != "0"
        or global_certificate.get("unresolved") != "0"
    ):
        raise ValueError("global totals mismatch")
    actual_plan_json = {
        path.resolve() for path in (ROOT / args.plan).rglob("*.json") if path.is_file()
    }
    if actual_plan_json != expected_plan_json:
        raise ValueError("plan JSON inventory mismatch")
    for label, directory in (
        ("prover", ROOT / args.prover_results),
        ("verifier", ROOT / args.verifier_results),
    ):
        actual = {path.name for path in directory.glob("*.json") if path.is_file()}
        if actual != expected_result_names:
            raise ValueError(f"{label} result JSON inventory mismatch")
    actual_certificate_json = {
        path.resolve() for path in certificate_dir.rglob("*.json") if path.is_file()
    }
    if actual_certificate_json != expected_certificate_json:
        raise ValueError("aggregate certificate JSON inventory mismatch")
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "profile": "theorem-artifacts" if selected == ALL_CASES else "incomplete-artifacts",
                "verified_cases": [str(m) for m in selected],
                "verified_branches": total_branches,
                "verified_units": total_units,
                "computational_marker": (
                    "ACCEPT_COMPUTATIONAL_ARTIFACT_SET_M_LE_96"
                    if selected == ALL_CASES
                    else None
                ),
                "theorem_marker": None,
                "authoritative_builds": "ACCEPT" if provenance is not None else "DEVELOPMENT",
                "computation_provenance": (
                    "ACCEPT" if computation_units is not None else "DEVELOPMENT"
                ),
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
