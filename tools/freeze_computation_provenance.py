#!/usr/bin/env python3
"""Freeze accepted runner attempts as non-proof computation provenance."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import atomic_write, load, object_id, sha256_file
from tools.run_engine_units import enumerate_units


ENGINES = (
    ("cpp-gmp-prover", "prover"),
    ("independent-rust-verifier", "verifier"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="dist/search-v2/plan")
    parser.add_argument("--prover-run", default="dist/search-v2/results/prover")
    parser.add_argument("--verifier-run", default="dist/search-v2/results/verifier")
    parser.add_argument("--out", default="release/computation_provenance")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    plan = ROOT / args.plan
    run_dirs = {
        "prover": ROOT / args.prover_run,
        "verifier": ROOT / args.verifier_run,
    }
    output = ROOT / args.out
    if output.exists():
        if not args.replace:
            raise ValueError(f"output exists (use --replace): {output}")
        shutil.rmtree(output)
    units = enumerate_units(plan, None)
    records = []
    try:
        for m, unit_path in units:
            unit = load(unit_path)
            identifier = unit["unit_id"]
            entry = {"m": str(m), "k1": unit["k1"], "unit_id": identifier}
            for engine, label in ENGINES:
                run_dir = run_dirs[label]
                result = load(run_dir / f"{identifier}.json")
                attempt_path = run_dir / ".provenance" / f"{identifier}.json"
                attempt = load(attempt_path)
                if (
                    attempt.get("accepted") is not True
                    or attempt.get("timed_out") is not False
                    or attempt.get("engine") != engine
                    or attempt.get("unit_id") != identifier
                    or attempt.get("result_id") != result.get("result_id")
                    or attempt.get("binary_sha256") != result.get("binary_sha256")
                ):
                    raise ValueError(f"invalid accepted attempt for {engine} {identifier}")
                destination = output / label / f"{identifier}.json"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(attempt_path, destination)
                entry[label] = {
                    "path": destination.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(destination),
                }
            records.append(entry)
        summary = {
            "schema": "collatz.computation-provenance.v1",
            "total_units": str(len(records)),
            "units": records,
        }
        summary["provenance_id"] = object_id(
            "collatz.computation-provenance.v1", summary
        )
        atomic_write(output / "execution_summary.json", summary)
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
