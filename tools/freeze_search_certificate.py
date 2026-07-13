#!/usr/bin/env python3
"""Freeze a complete mutable v2 computation into the release certificate tree."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_json_tree(source: Path, destination: Path) -> None:
    for path in source.rglob("*.json"):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"unsafe source path: {path}")
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def copy_root_results(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.glob("*.json"):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"unsafe result path: {path}")
        shutil.copyfile(path, destination / path.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="dist/search-v2/plan")
    parser.add_argument("--prover-results", default="dist/search-v2/results/prover")
    parser.add_argument("--verifier-results", default="dist/search-v2/results/verifier")
    parser.add_argument("--out", default="certificates/search-v2")
    parser.add_argument("--prover-binary", default="release/bin/collatz_prover")
    parser.add_argument(
        "--verifier-binary", default="release/bin/collatz_verify_unit"
    )
    parser.add_argument(
        "--build-provenance",
        default="release/build_provenance/authoritative_binaries.json",
    )
    parser.add_argument(
        "--computation-provenance", default="release/computation_provenance"
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    source_plan = ROOT / args.plan
    source_prover = ROOT / args.prover_results
    source_verifier = ROOT / args.verifier_results
    destination = ROOT / args.out
    if destination.exists():
        if not args.replace:
            raise ValueError(f"destination exists (use --replace): {destination}")
        shutil.rmtree(destination)
    try:
        copy_json_tree(source_plan, destination / "plan")
        copy_root_results(source_prover, destination / "results/prover")
        copy_root_results(source_verifier, destination / "results/verifier")
        relative_plan = (destination / "plan").relative_to(ROOT).as_posix()
        relative_prover = (destination / "results/prover").relative_to(ROOT).as_posix()
        relative_verifier = (destination / "results/verifier").relative_to(ROOT).as_posix()
        relative_certificates = (destination / "certificates").relative_to(ROOT).as_posix()
        subprocess.run(
            [
                sys.executable,
                "verifiers/verify_partition_manifest.py",
                "--all",
                "--partitions",
                relative_plan,
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "tools/aggregate_search_certificate.py",
                "--plan",
                relative_plan,
                "--prover-results",
                relative_prover,
                "--verifier-results",
                relative_verifier,
                "--out",
                relative_certificates,
                "--prover-binary",
                args.prover_binary,
                "--verifier-binary",
                args.verifier_binary,
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "verifiers/verify_global_search_certificate.py",
                "--plan",
                relative_plan,
                "--prover-results",
                relative_prover,
                "--verifier-results",
                relative_verifier,
                "--certificates",
                relative_certificates,
                "--prover-binary",
                args.prover_binary,
                "--verifier-binary",
                args.verifier_binary,
                "--build-provenance",
                args.build_provenance,
                "--computation-provenance",
                args.computation_provenance,
            ],
            cwd=ROOT,
            check=True,
        )
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    print(destination.relative_to(ROOT))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
