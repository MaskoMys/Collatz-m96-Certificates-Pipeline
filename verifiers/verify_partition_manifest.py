#!/usr/bin/env python3
"""Independently verify root arithmetic and complete work-unit partitions."""

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
    partition_id,
    require_exact_keys,
    unit_id,
)


CASES = range(92, 97)


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def independently_derive_root(config: dict[str, Any], k1: int) -> dict[str, str]:
    x = parse_nat(config["X"], "X", positive=True)
    a = parse_nat(config["window"]["numerator"], "window numerator", positive=True)
    b = parse_nat(config["window"]["denominator"], "window denominator", positive=True)
    n1_max = a * x // b
    lower = ceil_div(x + 1, 2**k1)
    upper = (n1_max + 1) // (2**k1)
    first = lower + ((lower + 1) % 2)
    last = upper - ((upper + 1) % 2)
    count = max(0, (last - first) // 2 + 1)
    return {
        "first": str(first),
        "last": str(last if count else first - 2),
        "count": str(count),
        "residue": "1",
        "bits": "1",
    }


def verify_tree(node: Any, expected_start: int, expected_end: int) -> list[tuple[int, int, str]]:
    if not isinstance(node, dict) or node.get("kind") not in {"leaf", "split"}:
        raise ValueError("invalid partition tree node")
    start = parse_nat(node.get("start"), "tree start")
    end = parse_nat(node.get("end"), "tree end")
    if (start, end) != (expected_start, expected_end):
        raise ValueError("partition tree node interval mismatch")
    if node["kind"] == "leaf":
        require_exact_keys(node, {"kind", "start", "end", "unit_id"}, "tree leaf")
        return [(start, end, node["unit_id"])]
    require_exact_keys(
        node, {"kind", "start", "end", "split_after", "left", "right"}, "tree split"
    )
    split_after = parse_nat(node["split_after"], "split_after")
    if not start <= split_after < end:
        raise ValueError("invalid partition split point")
    left = verify_tree(node["left"], start, split_after)
    right = verify_tree(node["right"], split_after + 1, end)
    return left + right


def verify_branch(config: dict[str, Any], branch_dir: Path, k1: int) -> int:
    partition = load(branch_dir / "partition.json")
    require_exact_keys(
        partition,
        {"schema", "partition_id", "config_id", "m", "k1", "root", "tree", "leaves"},
        "partition",
    )
    if partition["schema"] != "collatz.root-partition.v1":
        raise ValueError("partition schema mismatch")
    if partition["partition_id"] != partition_id(partition):
        raise ValueError("partition ID mismatch")
    if partition["config_id"] != config_id(config):
        raise ValueError("partition config ID mismatch")
    if partition["m"] != config["m"] or partition["k1"] != str(k1):
        raise ValueError("partition case/branch mismatch")
    root = independently_derive_root(config, k1)
    if partition["root"] != root:
        raise ValueError("partition root is not mathematically derived")
    count = int(root["count"])
    if count == 0:
        expected_tree_range = (0, 0)
    else:
        expected_tree_range = (0, count - 1)
    tree_leaves = verify_tree(partition["tree"], *expected_tree_range)
    leaves = partition["leaves"]
    if not isinstance(leaves, list) or len(leaves) != len(tree_leaves):
        raise ValueError("partition leaf list mismatch")
    listed = []
    seen = set()
    units_dir = branch_dir / "units"
    expected_files = set()
    for position, (leaf, tree_leaf) in enumerate(zip(leaves, tree_leaves)):
        require_exact_keys(leaf, {"unit_id", "start", "end"}, f"leaf {position}")
        triple = (parse_nat(leaf["start"], "leaf start"), parse_nat(leaf["end"], "leaf end"), leaf["unit_id"])
        if triple != tree_leaf:
            raise ValueError("ordered leaves do not match partition tree")
        if leaf["unit_id"] in seen:
            raise ValueError("duplicate unit ID")
        seen.add(leaf["unit_id"])
        unit_path = units_dir / f"{leaf['unit_id']}.json"
        expected_files.add(unit_path.name)
        unit = load(unit_path)
        if unit.get("unit_id") != unit_id(unit):
            raise ValueError("work-unit ID mismatch")
        if unit.get("config_id") != config_id(config) or unit.get("root") != root:
            raise ValueError("work unit config/root mismatch")
        if unit.get("m") != config["m"] or unit.get("k1") != str(k1):
            raise ValueError("work unit case/branch mismatch")
        if unit.get("index_range") != {"start": leaf["start"], "end": leaf["end"]}:
            raise ValueError("work unit interval mismatch")
        listed.append(triple)
    actual_files = {path.name for path in units_dir.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise ValueError("unexpected or missing work-unit file")
    return len(listed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--case", type=int, choices=CASES, action="append")
    parser.add_argument("--configs", default="certificates/config")
    parser.add_argument("--partitions", default="dist/search-v2/plan")
    args = parser.parse_args()
    if not args.all and args.case is None:
        parser.error("select --all or --case")
    cases = CASES if args.all else sorted(set(args.case))
    total_branches = 0
    total_units = 0
    base = ROOT / args.partitions
    expected_case_dirs = {f"m{m}" for m in cases}
    actual_case_dirs = {path.name for path in base.iterdir() if path.is_dir()}
    if args.all and actual_case_dirs != expected_case_dirs:
        raise ValueError("partition case-directory set mismatch")
    for m in cases:
        config = load(ROOT / args.configs / f"case_m{m}.json")
        low = parse_nat(config["k1_range"]["min"], "k1 minimum", positive=True)
        high = parse_nat(config["k1_range"]["max"], "k1 maximum", positive=True)
        case_dir = base / f"m{m}"
        expected_branches = {f"k1_{k1:02d}" for k1 in range(low, high + 1)}
        actual_branches = {path.name for path in case_dir.iterdir() if path.is_dir()}
        if actual_branches != expected_branches:
            raise ValueError(f"m={m} branch-directory set mismatch")
        for k1 in range(low, high + 1):
            total_units += verify_branch(config, case_dir / f"k1_{k1:02d}", k1)
            total_branches += 1
    print(
        json.dumps(
            {
                "result": "ACCEPT",
                "verified_branches": total_branches,
                "verified_units": total_units,
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
