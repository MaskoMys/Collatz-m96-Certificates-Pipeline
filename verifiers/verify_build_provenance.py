#!/usr/bin/env python3
"""Verify source, binary, and pinned-environment build provenance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canonical_json import (
    load,
    require_exact_keys,
    require_relative_path,
    require_sha256,
    sha256_file,
)
from tools.source_tree_hash import hash_paths
from verifiers.verify_work_unit_result import ENGINE_SOURCES


TOP_KEYS = {
    "schema",
    "architecture",
    "build_environment_lock_sha256",
    "compiler",
    "flags",
    "engines",
    "reproducible_build",
}
ENGINE_KEYS = {
    "engine",
    "binary_path",
    "binary_sha256",
    "source_paths",
    "source_sha256",
    "linked_libraries",
}


def verify_provenance(path: Path) -> dict[str, dict[str, object]]:
    record = load(path)
    require_exact_keys(record, TOP_KEYS, "build provenance")
    if record.get("schema") != "collatz.authoritative-builds.v1":
        raise ValueError("build provenance schema mismatch")
    if record.get("architecture") != "x86_64":
        raise ValueError("authoritative build architecture mismatch")
    if record.get("reproducible_build") != "MATCH":
        raise ValueError("authoritative binaries lack a reproducible-build match")
    require_sha256(
        record.get("build_environment_lock_sha256"), "build environment lock hash"
    )
    if record.get("build_environment_lock_sha256") != sha256_file(
        ROOT / "environment/Dockerfile.lock"
    ):
        raise ValueError("build environment lock mismatch")
    engines = record.get("engines")
    if not isinstance(engines, list) or [entry.get("engine") for entry in engines] != [
        "cpp-gmp-prover",
        "independent-rust-verifier",
    ]:
        raise ValueError("authoritative engine set mismatch")
    accepted = {}
    for entry in engines:
        require_exact_keys(entry, ENGINE_KEYS, "authoritative engine")
        engine = entry["engine"]
        require_sha256(entry.get("source_sha256"), f"{engine} source hash")
        require_sha256(entry.get("binary_sha256"), f"{engine} binary hash")
        if entry.get("source_paths") != ENGINE_SOURCES[engine]:
            raise ValueError(f"{engine} source path set mismatch")
        if entry.get("source_sha256") != hash_paths(ENGINE_SOURCES[engine], base=ROOT):
            raise ValueError(f"{engine} source hash mismatch")
        relative = require_relative_path(entry.get("binary_path"), "binary path")
        binary = ROOT / relative
        if binary.is_symlink() or not binary.is_file():
            raise ValueError(f"{engine} binary missing")
        if entry.get("binary_sha256") != sha256_file(binary):
            raise ValueError(f"{engine} binary hash mismatch")
        if not isinstance(entry.get("linked_libraries"), list):
            raise ValueError(f"{engine} linked-library record missing")
        accepted[engine] = entry
    return accepted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provenance",
        default="release/build_provenance/authoritative_binaries.json",
    )
    args = parser.parse_args()
    engines = verify_provenance(ROOT / args.provenance)
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "verified_engines": list(engines),
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
