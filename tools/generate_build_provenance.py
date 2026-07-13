#!/usr/bin/env python3
"""Record deterministic source and binary identities for authoritative engines."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import atomic_write, sha256_file
from tools.source_tree_hash import hash_paths
from verifiers.verify_work_unit_result import ENGINE_SOURCES


def output(command: list[str]) -> str:
    return subprocess.run(
        command, cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()


def linked_libraries(binary: Path) -> list[str]:
    lines = output(["ldd", str(binary)]).splitlines()
    normalized = []
    for line in lines:
        value = line.strip()
        if " (0x" in value:
            value = value.rsplit(" (0x", 1)[0]
        if value:
            normalized.append(value)
    return sorted(normalized)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prover", default="release/bin/collatz_prover")
    parser.add_argument("--verifier", default="release/bin/collatz_verify_unit")
    parser.add_argument(
        "--reproducible-build", choices=("MATCH", "NOT_RUN"), default="NOT_RUN"
    )
    parser.add_argument(
        "--out", default="release/build_provenance/authoritative_binaries.json"
    )
    args = parser.parse_args()
    binaries = {
        "cpp-gmp-prover": ROOT / args.prover,
        "independent-rust-verifier": ROOT / args.verifier,
    }
    records = []
    for engine, binary in binaries.items():
        if binary.is_symlink() or not binary.is_file():
            raise ValueError(f"missing authoritative binary: {binary}")
        records.append(
            {
                "engine": engine,
                "binary_path": binary.relative_to(ROOT).as_posix(),
                "binary_sha256": sha256_file(binary),
                "source_paths": ENGINE_SOURCES[engine],
                "source_sha256": hash_paths(ENGINE_SOURCES[engine], base=ROOT),
                "linked_libraries": linked_libraries(binary),
            }
        )
    value = {
        "schema": "collatz.authoritative-builds.v1",
        "architecture": platform.machine(),
        "reproducible_build": args.reproducible_build,
        "build_environment_lock_sha256": sha256_file(
            ROOT / "environment/Dockerfile.lock"
        ),
        "compiler": {
            "cxx": output(["g++", "--version"]).splitlines()[0],
            "rustc": output(["rustc", "--version", "--verbose"]),
            "cargo": output(["cargo", "--version"]),
        },
        "flags": {
            "cpp-gmp-prover": "-O3 -std=c++17 -Wall -Wextra -Werror",
            "independent-rust-verifier": "Cargo release: LTO=fat, codegen-units=1, panic=abort",
        },
        "engines": records,
    }
    path = ROOT / args.out
    atomic_write(path, value)
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
