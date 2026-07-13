#!/usr/bin/env python3
"""Verify complete accepted-attempt provenance for both exhaustive engines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import (
    load,
    object_id,
    parse_nat,
    require_exact_keys,
    require_relative_path,
    require_sha256,
    sha256_file,
)
from verifiers.verify_build_provenance import verify_provenance


ATTEMPT_KEYS = {
    "schema",
    "engine",
    "unit_id",
    "m",
    "accepted",
    "timed_out",
    "exit_code",
    "started_epoch",
    "elapsed_milliseconds",
    "hostname",
    "machine",
    "platform",
    "command",
    "binary_sha256",
    "result_id",
}


def expected_units(plan: Path) -> list[tuple[int, int, str]]:
    records = []
    for m in range(92, 97):
        case = plan / f"m{m}"
        for branch in sorted(case.glob("k1_*")):
            k1 = int(branch.name.split("_")[1])
            partition = load(branch / "partition.json")
            records.extend((m, k1, leaf["unit_id"]) for leaf in partition["leaves"])
    return records


def verify_computation_provenance(
    provenance_dir: Path,
    plan: Path,
    prover_results: Path,
    verifier_results: Path,
    build_provenance: Path,
) -> int:
    summary = load(provenance_dir / "execution_summary.json")
    require_exact_keys(
        summary,
        {"schema", "provenance_id", "total_units", "units"},
        "computation provenance summary",
    )
    if summary["schema"] != "collatz.computation-provenance.v1":
        raise ValueError("computation provenance schema mismatch")
    identity = dict(summary)
    claimed = identity.pop("provenance_id")
    if claimed != object_id("collatz.computation-provenance.v1", identity):
        raise ValueError("computation provenance ID mismatch")
    expected = expected_units(plan)
    entries = summary["units"]
    if not isinstance(entries, list) or len(entries) != len(expected):
        raise ValueError("computation provenance unit count mismatch")
    allowlist = verify_provenance(build_provenance)
    expected_files = {(provenance_dir / "execution_summary.json").resolve()}
    for (m, k1, identifier), entry in zip(expected, entries):
        require_exact_keys(entry, {"m", "k1", "unit_id", "prover", "verifier"}, "unit provenance")
        if (entry["m"], entry["k1"], entry["unit_id"]) != (
            str(m),
            str(k1),
            identifier,
        ):
            raise ValueError("computation provenance unit ordering mismatch")
        for engine, label, results in (
            ("cpp-gmp-prover", "prover", prover_results),
            ("independent-rust-verifier", "verifier", verifier_results),
        ):
            reference = require_exact_keys(entry[label], {"path", "sha256"}, "attempt reference")
            relative = require_relative_path(reference["path"], "attempt path")
            path = ROOT / relative
            expected_path = provenance_dir / label / f"{identifier}.json"
            if path.resolve() != expected_path.resolve():
                raise ValueError("computation attempt path mismatch")
            require_sha256(reference["sha256"], "attempt hash")
            if reference["sha256"] != sha256_file(path):
                raise ValueError("computation attempt hash mismatch")
            expected_files.add(path.resolve())
            attempt = load(path)
            require_exact_keys(attempt, ATTEMPT_KEYS, "computation attempt")
            result = load(results / f"{identifier}.json")
            if (
                attempt["schema"] != "collatz.computation-attempt.v1"
                or attempt["engine"] != engine
                or attempt["unit_id"] != identifier
                or attempt["m"] != str(m)
                or attempt["accepted"] is not True
                or attempt["timed_out"] is not False
                or attempt["exit_code"] != 0
                or attempt["result_id"] != result["result_id"]
                or attempt["binary_sha256"] != result["binary_sha256"]
                or attempt["binary_sha256"] != allowlist[engine]["binary_sha256"]
            ):
                raise ValueError(f"invalid accepted computation attempt for {identifier}")
            parse_nat(attempt["started_epoch"], "attempt start")
            parse_nat(attempt["elapsed_milliseconds"], "attempt elapsed")
            if (
                not isinstance(attempt["hostname"], str)
                or not isinstance(attempt["machine"], str)
                or not isinstance(attempt["platform"], str)
                or not isinstance(attempt["command"], list)
                or not all(isinstance(part, str) for part in attempt["command"])
            ):
                raise ValueError("computation host/command record mismatch")
    if parse_nat(summary["total_units"], "provenance total") != len(expected):
        raise ValueError("computation provenance total mismatch")
    actual_files = {
        path.resolve() for path in provenance_dir.rglob("*.json") if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("computation provenance JSON inventory mismatch")
    return len(expected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provenance", default="release/computation_provenance")
    parser.add_argument("--plan", default="certificates/search-v2/plan")
    parser.add_argument("--prover-results", default="certificates/search-v2/results/prover")
    parser.add_argument("--verifier-results", default="certificates/search-v2/results/verifier")
    parser.add_argument(
        "--build-provenance",
        default="release/build_provenance/authoritative_binaries.json",
    )
    args = parser.parse_args()
    count = verify_computation_provenance(
        ROOT / args.provenance,
        ROOT / args.plan,
        ROOT / args.prover_results,
        ROOT / args.verifier_results,
        ROOT / args.build_provenance,
    )
    print(json.dumps({"result": "ACCEPT", "verified_units": count}, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"REJECT: {error}", file=sys.stderr)
        raise SystemExit(1)
