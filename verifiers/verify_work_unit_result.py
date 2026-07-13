#!/usr/bin/env python3
"""Strictly verify one canonical engine result against its exact unit."""

from __future__ import annotations

import argparse
import json
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
    result_id,
    sha256_file,
    unit_id,
)
from tools.source_tree_hash import hash_paths


RESULT_KEYS = {
    "schema",
    "result_id",
    "unit_id",
    "config_id",
    "engine",
    "source_sha256",
    "binary_sha256",
    "math_certificate_sha256",
    "semantic_parameters",
    "outcome",
    "hits",
    "counters",
    "max_integer_bits",
}
BASE_COUNTERS = {
    "bound_prunes",
    "deterministic_nodes",
    "deterministic_values",
    "final_intervals",
    "prefix_prunes",
    "recursive_nodes",
    "represented_input_count",
}
ENGINE_SOURCES = {
    "cpp-gmp-prover": [
        "src/prover/search_core.hpp",
        "src/prover/search_core.cpp",
        "src/prover/main.cpp",
    ],
    "independent-rust-verifier": [
        "src/verifier-rust/Cargo.toml",
        "src/verifier-rust/Cargo.lock",
        "src/verifier-rust/src/bigint.rs",
        "src/verifier-rust/src/canonical.rs",
        "src/verifier-rust/src/config.rs",
        "src/verifier-rust/src/main.rs",
        "src/verifier-rust/src/progression.rs",
        "src/verifier-rust/src/search.rs",
    ],
}


def verify_result(
    config_path: Path,
    unit_path: Path,
    result_path: Path,
    *,
    expected_engine: str,
    binary_path: Path | None = None,
) -> dict[str, Any]:
    if expected_engine not in ENGINE_SOURCES:
        raise ValueError(f"unsupported engine: {expected_engine}")
    config = load(config_path)
    unit = load(unit_path)
    result = load(result_path)
    require_exact_keys(result, RESULT_KEYS, "engine result")
    if result["schema"] != "collatz.engine-result.v1":
        raise ValueError("result schema mismatch")
    if result["result_id"] != result_id(result):
        raise ValueError("result ID mismatch")
    if unit.get("unit_id") != unit_id(unit):
        raise ValueError("unit ID mismatch")
    if result["unit_id"] != unit["unit_id"]:
        raise ValueError("result/unit identity mismatch")
    expected_config_id = config_id(config)
    if unit.get("config_id") != expected_config_id or result["config_id"] != expected_config_id:
        raise ValueError("result/config identity mismatch")
    if result["engine"] != expected_engine:
        raise ValueError("unexpected result engine")
    require_sha256(result["source_sha256"], "source hash")
    require_sha256(result["binary_sha256"], "binary hash")
    require_sha256(result["math_certificate_sha256"], "math certificate hash")
    if result["math_certificate_sha256"] != config["math_certificate_sha256"]:
        raise ValueError("result math-certificate hash mismatch")
    expected_source = hash_paths(ENGINE_SOURCES[expected_engine], base=ROOT)
    if result["source_sha256"] != expected_source:
        raise ValueError("result source hash mismatch")
    if binary_path is not None:
        if binary_path.is_symlink() or not binary_path.is_file():
            raise ValueError("authoritative binary is not a regular file")
        if result["binary_sha256"] != sha256_file(binary_path):
            raise ValueError("result binary hash mismatch")
    parameters = require_exact_keys(
        result["semantic_parameters"], {"enum_threshold"}, "semantic parameters"
    )
    parse_nat(parameters["enum_threshold"], "enum threshold", positive=True)
    hits = parse_nat(result["hits"], "hits")
    parse_nat(result["max_integer_bits"], "maximum integer bits")
    if result["outcome"] not in {"NO_SURVIVOR", "SURVIVOR", "ERROR"}:
        raise ValueError("invalid result outcome")
    if (result["outcome"] == "NO_SURVIVOR") != (hits == 0):
        raise ValueError("outcome/hit-count mismatch")
    depth = parse_nat(config["depth"], "config depth", positive=True)
    expected_counters = BASE_COUNTERS | {f"level_{index}" for index in range(1, depth + 1)}
    counters = require_exact_keys(result["counters"], expected_counters, "counters")
    for key, value in counters.items():
        parse_nat(value, f"counter {key}")
    start = parse_nat(unit["index_range"]["start"], "unit start")
    end = parse_nat(unit["index_range"]["end"], "unit end")
    if int(counters["represented_input_count"]) != end - start + 1:
        raise ValueError("represented input count mismatch")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--engine", required=True, choices=sorted(ENGINE_SOURCES))
    parser.add_argument("--binary")
    args = parser.parse_args()
    result = verify_result(
        ROOT / args.config,
        ROOT / args.unit,
        ROOT / args.result,
        expected_engine=args.engine,
        binary_path=ROOT / args.binary if args.binary else None,
    )
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "engine": result["engine"],
                "result_id": result["result_id"],
                "unit_id": result["unit_id"],
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
